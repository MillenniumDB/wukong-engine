"""Benchmark of the supported LLMs at several reasoning effort levels, on a sample of the crime news dataset.

Each setting (model and effort level) extracts the same sample in its own workspace, and an LLM judge scores the
extractions of all settings side by side, one request per chunk and extraction kind. See README.md for the method and
the steps; no subcommand spends money unless it is given ``--submit``.

Subcommands:
    prepare: Write the sample, its data directory, the settings' configurations and their workspaces.
    cost: Report the token usage and cost of the extraction runs, from their staging databases.
    judge: Build the judge requests and estimate their cost, or with ``--submit`` send them.
    collect: Retrieve the results of a submitted judge batch.
    report: Score every setting from the judgments and write the report.
"""

import argparse
import asyncio
import hashlib
import json
import math
import shutil
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import numpy as np
from dotenv import load_dotenv
from openai import AsyncOpenAI

BENCH_DIR = Path(__file__).resolve().parent
REPO_DIR = BENCH_DIR.parents[1]
CRIME_DATA_DIR = REPO_DIR / 'data' / 'crime'
SEED = 2026

MODELS = ('gpt-5.6-luna', 'gpt-6-luna', 'claude-haiku-5-5')
DEFAULT_EFFORTS = ('none', 'low')
MAX_CONCURRENCY = 10

# USD per 1M tokens: input, cached input, cache write and output (reasoning included). Extraction runs in real time,
# and both Anthropic and OpenAI bill cache reads at 0.1x and (5-minute or 30-minute) cache writes at 1.25x the input
EXTRACTION_PRICES = {
    'gpt-5.6-luna': (0.20, 0.02, 0.25, 1.20),
    'gpt-6-luna': (0.10, 0.01, 0.125, 0.50),
    'claude-haiku-5-5': (0.10, 0.01, 0.125, 0.50),  # Prompts up to 100K tokens, far above an extraction prompt
}

JUDGE_MODEL = 'gpt-6.1-sol'
JUDGE_EFFORT = 'low'  # Its lowest level: it has no "none"
JUDGE_MAX_OUTPUT_TOKENS = 6000  # Bounds the worst-case cost estimate
JUDGE_EXPECTED_OUTPUT_TOKENS = 1500  # Verdicts plus reasoning, per request
JUDGE_PRICES = {  # Same layout as EXTRACTION_PRICES; cached input is 0.05x on this model
    'batch': (1.00, 0.05, 1.25, 5.00),
    'realtime': (2.00, 0.10, 2.50, 10.00),
}
JUDGE_CONCURRENCY = 8
BOOTSTRAP_SAMPLES = 2000

KINDS = ('entities', 'relationships')
VERDICTS = ('correct', 'field_error', 'invalid')

RUBRIC = {
    'entities': """\
You evaluate knowledge extraction systems. You are given the definitions of the entity types to extract, a passage of
a news article, and the entities that several anonymous systems (S1, S2, ...) extracted from it. Judge only against the
passage and the definitions: systems can be wrong in different ways, so never assume an item is right because several
systems agree on it.

1. Build the reference: every entity of a defined type that the passage supports and that should be extracted
   according to the definitions, once per distinct real-world entity, whether or not any system found it. Describe
   each in at most six words.
2. Give every item of every system exactly one verdict:
   - "correct": a reference entity, of the right type, with correct field values.
   - "field_error": a reference entity of the right type, but with at least one field value that is wrong, contradicts
     the passage or looks invented.
   - "invalid": not supported by the passage, of the wrong type, not an entity according to the definitions, or a
     duplicate of another item of the same system.
   List "correct" and "field_error" items as [item number, id of the reference entity it matches] pairs, and
   "invalid" items by their item number.

Field values may have been merged from other passages of the same article: a value that is merely absent from this
passage is not an error unless it looks invented, and a missing optional value is not an error. Include every system
in your answer, even one without items, and be strict but consistent across systems.""",
    'relationships': """\
You evaluate knowledge extraction systems. You are given the definitions of the relationship types to extract (with
the entity types they connect), a passage of a news article, and the relationships that several anonymous systems (S1,
S2, ...) extracted from it, each between two entities that the system extracted. Judge only against the passage and the
definitions: systems can be wrong in different ways, so never assume an item is right because several systems agree
on it.

1. Build the reference: every relationship of a defined type, between entities mentioned in the passage and in the
   direction its definition allows, that the passage supports and that should be extracted according to the
   definitions, once per distinct relationship, whether or not any system found it. Describe each in at most six
   words.
2. Give every item of every system exactly one verdict:
   - "correct": a reference relationship, of the right type and direction, between the right entities, with correct
     field values.
   - "field_error": a reference relationship, but with at least one field value that is wrong, contradicts the passage
     or looks invented.
   - "invalid": not supported by the passage, of the wrong type or direction, between the wrong entities, or a
     duplicate of another item of the same system.
   List "correct" and "field_error" items as [item number, id of the reference relationship it matches] pairs, and
   "invalid" items by their item number.

An entity is identified by the label shown, and a missing optional value is not an error. Include every system in
your answer, even one without items, and be strict but consistent across systems.""",
}

JUDGE_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['reference', 'systems'],
    'properties': {
        'reference': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['id', 'description'],
                'properties': {'id': {'type': 'integer'}, 'description': {'type': 'string'}},
            },
        },
        'systems': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['system', *VERDICTS],
                # Pairs and bare numbers instead of an object per item, as output tokens make most of the judge's cost
                'properties': {
                    'system': {'type': 'string'},
                    'correct': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'integer'}}},
                    'field_error': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'integer'}}},
                    'invalid': {'type': 'array', 'items': {'type': 'integer'}},
                },
            },
        },
    },
}


@dataclass
class Chunk:
    """A chunk of a sampled document, with what one setting extracted from it.

    Attributes:
        key: Identifier of the chunk shared by all settings: the document's file name and the chunk index.
        content: Text of the chunk.
        items: Rendered extracted items, by extraction kind.
    """

    key: str
    content: str
    items: dict[str, list[str]] = field(default_factory=lambda: {kind: [] for kind in KINDS})


@dataclass
class Counts:
    """Verdict counts of one setting, on one extraction kind and one or more chunks.

    Attributes:
        verdicts: Number of items per verdict.
        unjudged: Number of items the judge gave no verdict.
        found: Number of distinct reference items matched by a correct or field_error item.
        reference: Number of reference items.
    """

    verdicts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(VERDICTS, 0))
    unjudged: int = 0
    found: int = 0
    reference: int = 0

    def add(self, other: Counts) -> None:
        """Add the counts of another chunk to these ones.

        Args:
            other: Counts to add.
        """
        for verdict in VERDICTS:
            self.verdicts[verdict] += other.verdicts[verdict]
        self.unjudged += other.unjudged
        self.found += other.found
        self.reference += other.reference

    def scores(self) -> dict[str, float]:
        """Compute the precision, recall, F1 and field accuracy of the counts.

        Returns:
            The scores, each NaN when its denominator is zero. Unjudged items count as invalid.
        """
        valid = self.verdicts['correct'] + self.verdicts['field_error']
        items = valid + self.verdicts['invalid'] + self.unjudged
        precision = valid / items if items else math.nan
        recall = self.found / self.reference if self.reference else math.nan
        f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else math.nan
        field_accuracy = self.verdicts['correct'] / valid if valid else math.nan
        return {'precision': precision, 'recall': recall, 'f1': f1, 'field_accuracy': field_accuracy}


def _settings(efforts: tuple[str, ...]) -> list[tuple[str, str]]:
    """List the (model, effort) settings of the benchmark, one per model and effort level."""
    return [(model, effort) for model in MODELS for effort in efforts]


def _setting_name(model: str, effort: str) -> str:
    """Name a setting, as used for its workspace and configuration file."""
    return f'{model}@{effort}'


def _suite_runs(suite: str) -> list[Path]:
    """List the workspaces of the settings prepared for a suite, sorted by name.

    Raises:
        SystemExit: If the suite has not been prepared.
    """
    runs_dir = BENCH_DIR / 'runs' / suite
    runs = sorted(path for path in runs_dir.glob('*@*') if path.is_dir()) if runs_dir.is_dir() else []
    if not runs:
        raise SystemExit(f'Suite "{suite}" has no prepared settings, run "prepare" first')
    return runs


def _ordered_sample() -> list[str]:
    """Order the documents of the full dataset for sampling, so that every sample size extends the smaller ones.

    The documents of the test set come first, then the rest, each group shuffled with a fixed seed.

    Returns:
        The file names of every document of the full dataset.
    """
    full = {path.name for path in (CRIME_DATA_DIR / 'full').glob('*.txt')}
    test = {path.name for path in (CRIME_DATA_DIR / 'test').glob('*.txt')}
    return _shuffled(test, 'sample') + _shuffled(full - test, 'sample')


def _shuffled(values: Iterable[str], salt: str) -> list[str]:
    """Shuffle values reproducibly, by sorting them on a hash of the seed, a salt and each value.

    Args:
        values: Distinct values to shuffle.
        salt: Distinguishes the orders of separate shuffles of the same values.

    Returns:
        The values in an order that only depends on the seed, the salt and the values themselves.
    """
    return sorted(values, key=lambda value: hashlib.sha256(f'{SEED}:{salt}:{value}'.encode()).hexdigest())


def _config(model: str, effort: str, *, extract: bool) -> str:
    """Render the engine configuration of a setting.

    Args:
        model: Model of the setting.
        effort: Generalized reasoning effort level of the setting.
        extract: Whether to extract, or only ingest the documents (which makes no LLM calls).

    Returns:
        The TOML configuration, with the chunking of the default configuration and no export.
    """
    return f"""\
# Generated by benchmark/llm_effort/bench.py
[pipeline]
ingest_documents = true
extract_entities = {str(extract).lower()}
extract_relationships = {str(extract).lower()}
export_knowledge = false

[llm]
model = "{model}"
execution_mode = "real-time"
max_concurrency = {MAX_CONCURRENCY}
reasoning_effort = "{effort}"

[chunking]
target_tokens = 800
overlap_tokens = 120
"""


def prepare(suite: str, docs: int, efforts: tuple[str, ...]) -> None:
    """Write the sample of a suite, its data directory, the settings' configurations and their workspaces.

    Args:
        suite: Name of the suite (e.g. ``smoke`` or ``main``).
        docs: Number of documents to sample.
        efforts: Generalized reasoning effort levels to benchmark for every model.

    Raises:
        SystemExit: If the suite's data directory holds documents that aren't in its sample.
    """
    sample = _ordered_sample()[:docs]
    (BENCH_DIR / 'samples').mkdir(exist_ok=True)
    (BENCH_DIR / 'samples' / f'{suite}.txt').write_text('\n'.join(sample) + '\n')

    # The data directory holds copies of the sampled documents only
    data_dir = BENCH_DIR / 'data' / suite
    data_dir.mkdir(parents=True, exist_ok=True)
    extra = {path.name for path in data_dir.glob('*.txt')} - set(sample)
    if extra:
        raise SystemExit(f'{data_dir} holds {len(extra)} documents outside the sample, remove them first')
    for name in sample:
        if not (data_dir / name).exists():
            shutil.copy2(CRIME_DATA_DIR / 'full' / name, data_dir / name)

    # One configuration and one workspace per setting, sharing the knowledge model and the collection registry
    configs_dir = BENCH_DIR / 'configs'
    configs_dir.mkdir(exist_ok=True)
    for model, effort in _settings(efforts):
        name = _setting_name(model, effort)
        (configs_dir / f'{name}.toml').write_text(_config(model, effort, extract=True))
        (configs_dir / f'{name}.ingest.toml').write_text(_config(model, effort, extract=False))
        workspace = BENCH_DIR / 'runs' / suite / name
        workspace.mkdir(parents=True, exist_ok=True)
        for file_name in ('knowledge_model.json', 'document_collections.json'):
            shutil.copy2(BENCH_DIR / file_name, workspace / file_name)

    print(f'Prepared suite "{suite}": {len(sample)} documents, {len(_settings(efforts))} settings')
    print('Run each setting with (ingestion alone with the .ingest.toml configuration, which is free):')
    relative = BENCH_DIR.relative_to(REPO_DIR)
    print(
        f'  poetry run wukong run {relative}/runs/{suite}/<setting> {relative}/data/{suite} '
        f'--config {relative}/configs/<setting>.toml'
    )


def _connect(workspace: Path) -> sqlite3.Connection:
    """Open the staging database of a workspace read-only."""
    return sqlite3.connect(f'file:{workspace / "staging" / "extraction.db"}?mode=ro', uri=True)


def cost(suite: str) -> dict[str, dict[str, Any]]:
    """Report the token usage and cost of the extraction runs of a suite.

    Args:
        suite: Name of the suite.

    Returns:
        Per setting: its total tokens per category, its number of jobs per type and status, and its cost in USD.
    """
    results: dict[str, dict[str, Any]] = {}
    for workspace in _suite_runs(suite):
        model = workspace.name.split('@')[0]
        with _connect(workspace) as connection:
            tokens = connection.execute(
                'SELECT SUM(input_tokens), SUM(cached_tokens), SUM(cache_write_tokens), SUM(output_tokens), '
                'SUM(reasoning_tokens) FROM extraction_jobs',
            ).fetchone()
            jobs = connection.execute(
                'SELECT job_type, job_status, COUNT(*) FROM extraction_jobs GROUP BY job_type, job_status',
            ).fetchall()
        uncached, cached, cache_write, output, reasoning = (value or 0 for value in tokens)
        prices = EXTRACTION_PRICES[model]
        usd = (
            uncached * prices[0] + cached * prices[1] + cache_write * prices[2] + (output + reasoning) * prices[3]
        ) / 1_000_000
        results[workspace.name] = {
            'tokens': {
                'input': uncached,
                'cached': cached,
                'cache_write': cache_write,
                'output': output,
                'reasoning': reasoning,
            },
            'jobs': {f'{job_type.lower()}:{status.lower()}': count for job_type, status, count in jobs},
            'usd': usd,
        }
    return results


def _print_cost(suite: str) -> None:
    """Print the extraction cost of each setting of a suite and their total."""
    results = cost(suite)
    for name, result in results.items():
        tokens = result['tokens']
        print(
            f'{name:<26} ${result["usd"]:.4f}  input {tokens["input"]:>9,}  cached {tokens["cached"]:>9,}  '
            f'output {tokens["output"]:>8,}  reasoning {tokens["reasoning"]:>9,}  jobs {result["jobs"]}',
        )
    print(f'{"Total":<26} ${sum(result["usd"] for result in results.values()):.4f}')


def _label(entity_type: str, properties: dict[str, Any]) -> str:
    """Label an entity for the judge by its type and its name, or its first property if it has none."""
    value = properties.get('name') or next(iter(properties.values()), '?')
    return f'{entity_type}("{value}")'


def _load_chunks(workspace: Path) -> dict[str, Chunk]:
    """Load the chunks of a workspace, with the rendered items extracted from each one.

    Args:
        workspace: Workspace of a setting.

    Returns:
        The chunks by key, their items sorted so that the rendering doesn't depend on storage order.
    """
    chunks: dict[str, Chunk] = {}
    by_id: dict[bytes, Chunk] = {}
    with _connect(workspace) as connection:
        for content_id, source_uri, chunk_index, content in connection.execute(
            'SELECT c.content_id, d.source_uri, c.chunk_index, c.content '
            'FROM chunks c JOIN documents d ON d.content_id = c.document_content_id',
        ):
            chunk = Chunk(key=f'{Path(source_uri).name}#{chunk_index}', content=content)
            chunks[chunk.key] = by_id[content_id] = chunk
        for chunk_id, entity_type, properties in connection.execute(
            'SELECT p.context_content_id, e.entity_type_name, e.properties FROM entity_provenance p '
            "JOIN entities e ON e.content_id = p.entity_content_id WHERE p.context_level = 'CHUNK'",
        ):
            if chunk_id in by_id:
                rendered = json.dumps(json.loads(properties), ensure_ascii=False, sort_keys=True)
                by_id[chunk_id].items['entities'].append(f'{entity_type} {rendered}')
        for chunk_id, relationship_type, properties, source_type, source, target_type, target in connection.execute(
            'SELECT p.chunk_content_id, r.relationship_type_name, r.properties, s.entity_type_name, s.properties, '
            't.entity_type_name, t.properties FROM relationship_provenance p '
            'JOIN relationships r ON r.content_id = p.relationship_content_id '
            'JOIN entities s ON s.content_id = r.source_content_id '
            'JOIN entities t ON t.content_id = r.target_content_id',
        ):
            if chunk_id in by_id:
                rendered = json.dumps(json.loads(properties), ensure_ascii=False, sort_keys=True)
                endpoints = f'{_label(source_type, json.loads(source))} -> {_label(target_type, json.loads(target))}'
                by_id[chunk_id].items['relationships'].append(f'{relationship_type}: {endpoints} {rendered}')
    for chunk in chunks.values():
        for items in chunk.items.values():
            items.sort()
    return chunks


def _render_definitions(kind: str) -> str:
    """Render the definitions the judge checks one extraction kind against, from the benchmark's knowledge model."""
    knowledge_model = json.loads((BENCH_DIR / 'knowledge_model.json').read_text())
    context = knowledge_model['extraction_config']['llm']
    lines = [f'Domain: {context["domain"]} (language: {context["language"]})', '']
    entity_types = knowledge_model['entity_types']
    if kind == 'entities':
        lines.append('Entity types:')
        for name, entity_type in entity_types.items():
            lines.append(f'- {name}: {entity_type["description"]}')
            if entity_type.get('instructions'):
                lines.append(f'  Instructions: {entity_type["instructions"]}')
            for field_name, field_def in entity_type['fields'].items():
                required = ' (required)' if field_def.get('required') else ''
                lines.append(f'  - {field_name}{required}: {field_def["description"]}')
                if field_def.get('instructions'):
                    lines.append(f'    Instructions: {field_def["instructions"]}')
                if field_def.get('options'):
                    lines.append(f'    Options: {", ".join(field_def["options"])}')
    else:
        lines.append('Entity types: ' + '; '.join(f'{name}: {t["description"]}' for name, t in entity_types.items()))
        lines.extend(['', 'Relationship types:'])
        for name, relationship_type in knowledge_model['relationship_types'].items():
            endpoints = ', '.join(
                f'{source} -> {target}'
                for source, targets in relationship_type['endpoints'].items()
                for target in targets
            )
            lines.append(f'- {name} ({endpoints}): {relationship_type["description"]}')
            for field_name, field_def in relationship_type.get('fields', {}).items():
                lines.append(f'  - {field_name}: {field_def["description"]}')
                if field_def.get('options'):
                    lines.append(f'    Options: {", ".join(field_def["options"])}')
    return '\n'.join(lines)


def _build_judge_requests(suite: str) -> list[dict[str, Any]]:
    """Build one judge request per chunk and extraction kind, showing every setting's items in a shuffled order.

    Args:
        suite: Name of the suite.

    Returns:
        The requests, each with its ``custom_id``, its Responses API ``body`` and the ``systems`` mapping of each
        anonymous system label to its setting.

    Raises:
        SystemExit: If the settings didn't chunk the documents identically.
    """
    runs = {workspace.name: _load_chunks(workspace) for workspace in _suite_runs(suite)}
    keys = set(next(iter(runs.values())))
    for name, chunks in runs.items():
        if set(chunks) != keys or any(chunks[key].content != next(iter(runs.values()))[key].content for key in keys):
            raise SystemExit(f'Setting "{name}" chunked the documents differently from the others')

    requests = []
    for kind in KINDS:
        definitions = _render_definitions(kind)
        for key in sorted(keys):
            settings = _shuffled(runs, f'{kind}:{key}')  # Hides the settings and evens out position bias
            systems = {f'S{i}': setting for i, setting in enumerate(settings, start=1)}
            candidates = []
            for label, setting in systems.items():
                items = runs[setting][key].items[kind]
                rendered = '\n'.join(f'  [{i}] {item}' for i, item in enumerate(items, start=1)) or '  (no items)'
                candidates.append(f'{label}:\n{rendered}')
            content = runs[settings[0]][key].content
            passage = f'Passage:\n"""\n{content}\n"""\n\nExtracted {kind}:\n\n' + '\n\n'.join(candidates)
            body = {
                'model': JUDGE_MODEL,
                'instructions': RUBRIC[kind],
                'input': [
                    {
                        'role': 'user',
                        'content': [
                            # The definitions are identical across the requests of a kind, so they are cached
                            {
                                'type': 'input_text',
                                'text': definitions + '\n\n',
                                'prompt_cache_breakpoint': {'mode': 'explicit'},
                            },
                            {'type': 'input_text', 'text': passage},
                        ],
                    },
                ],
                'reasoning': {'effort': JUDGE_EFFORT},
                'max_output_tokens': JUDGE_MAX_OUTPUT_TOKENS,
                'text': {'format': {'type': 'json_schema', 'name': 'judgment', 'strict': True, 'schema': JUDGE_SCHEMA}},
                'prompt_cache_options': {'mode': 'explicit'},
            }
            requests.append({'custom_id': f'{kind}:{key}', 'body': body, 'systems': systems})
    return requests


async def _count_input_tokens(client: AsyncOpenAI, requests: list[dict[str, Any]]) -> list[int]:
    """Count the input tokens of each judge request through the free input token counting endpoint."""
    semaphore = asyncio.Semaphore(JUDGE_CONCURRENCY)

    async def count(body: dict[str, Any]) -> int:
        check = {key: body[key] for key in ('model', 'instructions', 'input', 'text')}
        async with semaphore:
            # The SDK has no typed method for the input token counting endpoint yet
            response = cast('dict[str, Any]', await client.post('/responses/input_tokens', cast_to=object, body=check))
        return int(response['input_tokens'])

    return await asyncio.gather(*(count(request['body']) for request in requests))


async def _send_realtime(client: AsyncOpenAI, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Send the judge requests in real time, returning a result per request in the format of batch output lines."""
    semaphore = asyncio.Semaphore(JUDGE_CONCURRENCY)

    async def send(request: dict[str, Any]) -> dict[str, Any]:
        body = dict(request['body'])
        extra_body = {'prompt_cache_options': body.pop('prompt_cache_options')}
        async with semaphore:
            response = await client.responses.create(**body, extra_body=extra_body)
        return {'custom_id': request['custom_id'], 'response': {'status_code': 200, 'body': response.model_dump()}}

    return await asyncio.gather(*(send(request) for request in requests))


def _raw_dir(suite: str) -> Path:
    """Return the directory of a suite's judge requests and judgments, which stays out of version control."""
    path = BENCH_DIR / 'runs' / suite / 'judge'
    path.mkdir(parents=True, exist_ok=True)
    return path


def judge(suite: str, *, mode: str, budget: float, submit: bool, missing: bool) -> None:
    """Build the judge requests of a suite and estimate their cost, sending them only when asked to.

    Args:
        suite: Name of the suite.
        mode: ``batch`` to submit a 24-hour batch (half price), or ``realtime`` to send the requests directly.
        budget: Maximum expected cost in USD: the requests aren't sent if their estimate exceeds it.
        submit: Whether to send the requests, which spends money, or only estimate their cost.
        missing: Whether to only send the requests without a usable judgment yet (e.g. those a cancelled batch
            didn't finish), adding their judgments to the existing ones. Only in real time.

    Raises:
        SystemExit: If only missing requests are asked for in batch mode, or the expected cost exceeds the budget
            while submitting.
    """
    if missing and mode != 'realtime':
        raise SystemExit('--missing only works with --mode realtime, to keep the existing judgments')
    load_dotenv(REPO_DIR / '.env', override=False)
    requests = _build_judge_requests(suite)
    raw_dir = _raw_dir(suite)
    (raw_dir / 'requests.jsonl').write_text('\n'.join(json.dumps(request) for request in requests) + '\n')
    existing = _read_judgments(raw_dir) if missing else {}
    if missing:
        requests = [
            request for request in requests if _judgment_counts(request, existing.get(request['custom_id'])) is None
        ]
    # A single event loop for every call: the client's pooled connections can't outlive the loop that opened them
    asyncio.run(_judge(requests, raw_dir, existing, mode=mode, budget=budget, submit=submit))


def _read_judgments(raw_dir: Path) -> dict[str, dict[str, Any]]:
    """Read the judgments of a suite by request ID, empty if there are none yet."""
    path = raw_dir / 'judgments.jsonl'
    if not path.exists():
        return {}
    results = (json.loads(line) for line in path.read_text().splitlines() if line)
    return {result['custom_id']: result for result in results}


async def _judge(
    requests: list[dict[str, Any]],
    raw_dir: Path,
    existing: dict[str, dict[str, Any]],
    *,
    mode: str,
    budget: float,
    submit: bool,
) -> None:
    """Estimate the cost of the judge requests, and send them if asked to and within the budget.

    Args:
        requests: Judge requests to send, as built by ``_build_judge_requests``.
        raw_dir: Directory where the judgments (in real time) or the batch identifier are written.
        existing: Judgments to keep, by request ID, which those of the requests sent in real time replace.
        mode: ``batch`` or ``realtime``, as in ``judge``.
        budget: Maximum expected cost in USD.
        submit: Whether to send the requests.

    Raises:
        SystemExit: If the expected cost exceeds the budget while submitting.
    """
    if not requests:
        print('Every request already has a judgment, nothing to send')
        return
    client = AsyncOpenAI()

    # Estimate the cost without caching, which only lowers it
    input_tokens = await _count_input_tokens(client, requests)
    prices = JUDGE_PRICES[mode]
    input_usd = sum(input_tokens) * prices[0] / 1_000_000
    expected = input_usd + len(requests) * JUDGE_EXPECTED_OUTPUT_TOKENS * prices[3] / 1_000_000
    worst = input_usd + len(requests) * JUDGE_MAX_OUTPUT_TOKENS * prices[3] / 1_000_000
    print(
        f'{len(requests)} judge requests ({mode}), {sum(input_tokens):,} input tokens: '
        f'expected ${expected:.2f}, at most ${worst:.2f} (budget ${budget:.2f})',
    )
    if not submit:
        print('Nothing was sent: add --submit to send the requests')
        return
    if expected > budget:
        raise SystemExit('The expected cost exceeds the budget, nothing was sent')

    if mode == 'realtime':
        results = existing | {result['custom_id']: result for result in await _send_realtime(client, requests)}
        (raw_dir / 'judgments.jsonl').write_text('\n'.join(json.dumps(result) for result in results.values()) + '\n')
        print(f'Judged {len(requests)} requests, run "report" to score them')
        return

    lines = [
        json.dumps(
            {'custom_id': request['custom_id'], 'method': 'POST', 'url': '/v1/responses', 'body': request['body']}
        )
        for request in requests
    ]
    file = await client.files.create(file=('judge.jsonl', '\n'.join(lines).encode()), purpose='batch')
    batch = await client.batches.create(input_file_id=file.id, endpoint='/v1/responses', completion_window='24h')
    (raw_dir / 'batch.json').write_text(json.dumps({'batch_id': batch.id}) + '\n')
    print(f'Submitted batch {batch.id}, run "collect" once it has completed')


def collect(suite: str) -> None:
    """Retrieve the results of the judge batch of a suite once it has ended.

    Args:
        suite: Name of the suite.

    Raises:
        SystemExit: If the batch hasn't ended yet, or ended without results.
    """
    load_dotenv(REPO_DIR / '.env', override=False)
    client = AsyncOpenAI()
    raw_dir = _raw_dir(suite)
    batch_id = json.loads((raw_dir / 'batch.json').read_text())['batch_id']

    async def retrieve() -> str:
        batch = await client.batches.retrieve(batch_id)
        if batch.status not in {'completed', 'expired', 'cancelled'}:
            raise SystemExit(f'Batch {batch_id} is "{batch.status}", try again later')
        lines = [
            (await client.files.content(file_id)).text.strip()
            for file_id in (batch.output_file_id, batch.error_file_id)
            if file_id is not None
        ]
        if not lines:
            raise SystemExit(f'Batch {batch_id} ended without results')
        return '\n'.join(lines) + '\n'

    (raw_dir / 'judgments.jsonl').write_text(asyncio.run(retrieve()))
    print(f'Collected the results of batch {batch_id}, run "report" to score them')


def _judgment_counts(request: dict[str, Any], result: dict[str, Any] | None) -> dict[str, Counts] | None:
    """Count the verdicts of every setting in one judgment.

    Args:
        request: Judge request, with the items shown to the judge and the mapping of system labels to settings.
        result: Batch output line of the request, or None if it has none.

    Returns:
        The counts per setting, or None if the judgment is missing, failed or can't be parsed.
    """
    body = (result or {}).get('response', {}).get('body') or {}
    text = next(
        (
            content['text']
            for output in body.get('output', [])
            if output.get('type') == 'message'
            for content in output.get('content', [])
            if content.get('type') == 'output_text'
        ),
        None,
    )
    if body.get('status') != 'completed' or text is None:
        return None
    try:
        judgment = json.loads(text)
    except json.JSONDecodeError:
        return None
    reference_ids = {item['id'] for item in judgment['reference']}
    systems = {system['system']: system for system in judgment['systems']}
    counts: dict[str, Counts] = {}
    kind = request['custom_id'].split(':')[0]
    passage = request['body']['input'][0]['content'][1]['text']
    for label, setting in request['systems'].items():
        item_count = _item_count(passage, label, kind)
        system = systems.get(label, {})

        # Each item keeps its first verdict, ignoring malformed pairs and numbers that aren't items of the system
        judged: dict[int, tuple[str, int | None]] = {}
        for verdict in ('correct', 'field_error'):
            for pair in system.get(verdict, []):
                match pair:
                    case [int(item), int(reference_id)] if 1 <= item <= item_count:
                        judged.setdefault(item, (verdict, reference_id))
                    case _:
                        pass
        for item in system.get('invalid', []):
            if 1 <= item <= item_count:
                judged.setdefault(item, ('invalid', None))

        chunk_counts = Counts(reference=len(reference_ids), unjudged=item_count - len(judged))
        for verdict, _ in judged.values():
            chunk_counts.verdicts[verdict] += 1
        chunk_counts.found = len(
            {ref for verdict, ref in judged.values() if verdict != 'invalid' and ref in reference_ids}
        )
        counts[setting] = chunk_counts
    return counts


def _item_count(passage: str, label: str, kind: str) -> int:
    """Count the items of a system in the rendered judge input, from its numbered lines."""
    section = passage.split(f'Extracted {kind}:\n\n', 1)[1]
    block = next(block for block in section.split('\n\n') if block.startswith(f'{label}:\n'))
    return sum(1 for line in block.splitlines()[1:] if line.startswith('  ['))


def _bootstrap_f1(per_chunk: list[Counts]) -> tuple[float, float]:
    """Estimate a 95% confidence interval of the F1 score by resampling chunks.

    Args:
        per_chunk: Counts of one setting and kind, one per chunk.

    Returns:
        The 2.5th and 97.5th percentiles of the resampled F1 scores, NaN when none of them is defined.
    """
    # Per chunk: valid items, all items (unjudged ones count as invalid), found and reference items
    columns = np.array(
        [
            (
                counts.verdicts['correct'] + counts.verdicts['field_error'],
                sum(counts.verdicts.values()) + counts.unjudged,
                counts.found,
                counts.reference,
            )
            for counts in per_chunk
        ],
        dtype=float,
    )
    resampled = np.random.default_rng(SEED).integers(0, len(per_chunk), size=(BOOTSTRAP_SAMPLES, len(per_chunk)))
    valid, items, found, reference = columns[resampled].sum(axis=1).T
    with np.errstate(divide='ignore', invalid='ignore'):
        precision = valid / items
        recall = found / reference
        f1 = 2 * precision * recall / (precision + recall)
    f1 = f1[np.isfinite(f1)]
    if not f1.size:
        return math.nan, math.nan
    low, high = np.percentile(f1, [2.5, 97.5])
    return float(low), float(high)


def report(suite: str) -> None:
    """Score every setting of a suite from its judgments, and write the scores and a Markdown report.

    Args:
        suite: Name of the suite.
    """
    raw_dir = _raw_dir(suite)
    requests = [json.loads(line) for line in (raw_dir / 'requests.jsonl').read_text().splitlines() if line]
    results = _read_judgments(raw_dir)

    per_chunk: dict[tuple[str, str], list[Counts]] = {}
    failed = dict.fromkeys(KINDS, 0)
    judge_usage = {'input': 0, 'cached': 0, 'output': 0}
    for request in requests:
        kind = request['custom_id'].split(':')[0]
        result = results.get(request['custom_id'])
        counts = _judgment_counts(request, result)
        if counts is None:
            failed[kind] += 1
            continue
        usage = (result['response']['body'].get('usage') or {}) if result else {}
        cached = (usage.get('input_tokens_details') or {}).get('cached_tokens') or 0
        judge_usage['input'] += (usage.get('input_tokens') or 0) - cached
        judge_usage['cached'] += cached
        judge_usage['output'] += usage.get('output_tokens') or 0
        for setting, setting_counts in counts.items():
            per_chunk.setdefault((setting, kind), []).append(setting_counts)

    extraction = cost(suite)
    scores: dict[str, Any] = {'settings': {}, 'failed_judgments': failed, 'judge_tokens': judge_usage}
    for setting in sorted(extraction):
        entry: dict[str, Any] = {'extraction': extraction[setting]}
        for kind in KINDS:
            chunk_counts = per_chunk.get((setting, kind), [])
            total = Counts()
            for counts in chunk_counts:
                total.add(counts)
            low, high = _bootstrap_f1(chunk_counts) if chunk_counts else (math.nan, math.nan)
            entry[kind] = {
                **total.scores(),
                'f1_ci95': [low, high],
                'verdicts': total.verdicts,
                'unjudged': total.unjudged,
                'found': total.found,
                'reference': total.reference,
                'chunks': len(chunk_counts),
            }
        scores['settings'][setting] = entry

    results_dir = BENCH_DIR / 'results' / suite
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / 'scores.json').write_text(json.dumps(scores, indent=2) + '\n')
    (results_dir / 'report.md').write_text(_render_report(suite, scores))
    print((results_dir / 'report.md').read_text())


def _render_report(suite: str, scores: dict[str, Any]) -> str:
    """Render the scores of a suite as a Markdown report."""

    def pct(value: float) -> str:
        return '—' if math.isnan(value) else f'{value:.1%}'

    sample_size = len((BENCH_DIR / 'samples' / f'{suite}.txt').read_text().split())
    lines = [
        f'# Results: suite `{suite}`',
        '',
        (
            f'{sample_size} documents, judged by `{JUDGE_MODEL}` at `{JUDGE_EFFORT}` effort. F1 is shown with its 95% '
            'bootstrap interval over chunks. Precision counts correct and field_error items as valid, and field '
            'accuracy is the share of valid items with correct field values.'
        ),
        '',
        (
            '| Setting | Entity P | Entity R | Entity F1 | Entity fields | Rel. P | Rel. R | Rel. F1 | Rel. fields '
            '| Extraction cost | Reasoning tokens | Failed jobs |'
        ),
        '|---|---|---|---|---|---|---|---|---|---|---|---|',
    ]
    for setting, entry in scores['settings'].items():
        cells = [f'`{setting}`']
        for kind in KINDS:
            kind_scores = entry[kind]
            low, high = kind_scores['f1_ci95']
            cells += [
                pct(kind_scores['precision']),
                pct(kind_scores['recall']),
                f'{pct(kind_scores["f1"])} [{pct(low)}, {pct(high)}]',
                pct(kind_scores['field_accuracy']),
            ]
        extraction = entry['extraction']
        failed_jobs = sum(count for job, count in extraction['jobs'].items() if job.endswith(':failed'))
        cells += [f'${extraction["usd"]:.3f}', f'{extraction["tokens"]["reasoning"]:,}', str(failed_jobs)]
        lines.append('| ' + ' | '.join(cells) + ' |')
    failed = scores['failed_judgments']
    lines += [
        '',
        (
            f"Judgments that failed or couldn't be parsed: {failed['entities']} for entities, "
            f"{failed['relationships']} for relationships (their chunks are left out of every setting's scores)."
        ),
        '',
    ]
    return '\n'.join(lines)


def main() -> None:
    """Parse the command line and run the requested subcommand."""
    parser = argparse.ArgumentParser(description='Benchmark of the supported LLMs at several reasoning effort levels.')
    subparsers = parser.add_subparsers(dest='command', required=True)
    prepare_parser = subparsers.add_parser('prepare', help='write the sample, configurations and workspaces')
    prepare_parser.add_argument('suite')
    prepare_parser.add_argument('--docs', type=int, required=True, help='number of documents to sample')
    prepare_parser.add_argument('--efforts', nargs='+', default=list(DEFAULT_EFFORTS), help='effort levels')
    cost_parser = subparsers.add_parser('cost', help='report the cost of the extraction runs')
    cost_parser.add_argument('suite')
    judge_parser = subparsers.add_parser('judge', help='estimate the judge cost, or send the requests with --submit')
    judge_parser.add_argument('suite')
    judge_parser.add_argument('--mode', choices=['batch', 'realtime'], default='batch')
    judge_parser.add_argument('--budget', type=float, required=True, help='maximum expected cost in USD')
    judge_parser.add_argument('--submit', action='store_true', help='send the requests, which spends money')
    judge_parser.add_argument('--missing', action='store_true', help='only send requests without a judgment yet')
    collect_parser = subparsers.add_parser('collect', help='retrieve the results of the judge batch')
    collect_parser.add_argument('suite')
    report_parser = subparsers.add_parser('report', help='score the settings and write the report')
    report_parser.add_argument('suite')

    args = parser.parse_args()
    match args.command:
        case 'prepare':
            prepare(args.suite, args.docs, tuple(args.efforts))
        case 'cost':
            _print_cost(args.suite)
        case 'judge':
            judge(args.suite, mode=args.mode, budget=args.budget, submit=args.submit, missing=args.missing)
        case 'collect':
            collect(args.suite)
        case 'report':
            report(args.suite)


if __name__ == '__main__':
    main()
