"""Run the benchmark's own prompts on a current model: the same-model prompting baseline (X1a).

Text2KGBench ships the exact prompts its Vicuna-13B and Alpaca-LoRA-13B baselines were given
(`data/<dataset>/baselines/prompts/ont_<onto>_prompts.jsonl`: the ontology's concepts and relations, the most
similar train sentence with one example triple, and the test sentence). This sends each prompt, unchanged, to the
model WUKONG uses, through the engine's own OpenAI client so that model, reasoning effort, output limit and retries
are the same, and parses the reply into triples.

The benchmark never released the parser behind its baselines' `triples` (its notebook leaves it as a TODO), and its
outputs show that it split relation labels at commas. This parser:

    - reads one triple per line written as `relation(subject,object)`, ignoring other lines (notes, blank lines),
      list markers, code fences and markdown-escaped underscores;
    - finds where the relation ends using the ontology's own labels, so a label with a comma or a parenthesis
      (`languages_spoken,_written_or_signed`) is not cut, and keeps the relation as the model wrote it (spaces become
      underscores), so a relation outside the ontology still counts against conformance;
    - splits subject from object at the comma for which both sides occur in the sentence, then at the first comma
      whose subject side does, then at the first comma.

Any parsing advantage goes to the baseline, never to WUKONG.

Writes, under --out:

    - `llm/ont_<onto>_llm_responses.jsonl`: `{"id", "response", "triples"}` per test sentence, the format of the
      published baselines (score with text2kg_eval.py --sys-pattern 'ont_$$onto$$_llm_responses.jsonl');
    - `runs/<onto>.json`: model, reasoning effort, engine commit, prompt file hash, prompts, failed calls, tokens,
      and wall clock.

An ontology whose responses file already exists is skipped, so an interrupted run resumes.

Example:
    OPENAI_API_KEY=... python paper/benchmark/text2kg_prompt_baseline.py \
        --benchmark ../benchmarks/Text2KGBench --out paper/benchmark/results-x1-prompt-r1
"""

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from text2kg_record import engine_revision  # noqa: E402
from text2kg_setup import ONTOLOGIES  # noqa: E402

from wukong_engine.app.llm.elements import LLMRequest  # noqa: E402
from wukong_engine.app.llm.elements.values import ReasoningEffort  # noqa: E402
from wukong_engine.app.llm.elements.values.prompt import LLMPrompt  # noqa: E402
from wukong_engine.app.llm.model import LLM  # noqa: E402
from wukong_engine.infrastructure.llm.openai.client import OpenAIClient  # noqa: E402
from wukong_engine.infrastructure.llm.openai.config import OpenAIConfig  # noqa: E402

ATTEMPTS = 4  # per prompt, on top of the SDK's own retries
# The retrieved example (most similar train sentence and its triple) between the ontology and the test sentence
EXAMPLE_BLOCK = re.compile(r'\n\nExample Sentence: .*?\nExample Output: .*?(?=\n\nTest Sentence: )', re.DOTALL)
# What replaces it with --no-example: the example was the only place the output format appeared
FORMAT_LINE = '\n\nOutput format: relation(subject,object), one triple per line.'
LIST_MARKER = re.compile(r'^(?:[-*•]+|\d+[.)])\s*')
OUTPUT_LABEL = re.compile(r'^(?:test\s+)?output\s*:\s*', re.IGNORECASE)


def _split_arguments(arguments: str, sentence: str) -> tuple[str, str] | None:
    """Split `subject,object` at the comma that best separates the two arguments.

    Args:
        arguments: Text between the parentheses of a triple.
        sentence: Test sentence, used to choose between several commas.

    Returns:
        The stripped subject and object, or None if there is no comma or either side is empty.
    """
    commas = [i for i, char in enumerate(arguments) if char == ',']
    if not commas:
        return None
    lowered = sentence.lower()
    candidates = [(arguments[:i].strip(' "\''), arguments[i + 1:].strip(' "\'')) for i in commas]
    for test in (
        lambda s, o: s.lower() in lowered and o.lower() in lowered,
        lambda s, o: s.lower() in lowered,
        lambda s, o: True,
    ):
        for subject, obj in candidates:
            if subject and obj and test(subject, obj):
                return subject, obj
    return None


def parse_response(text: str, relations: list[str], sentence: str) -> list[list[str]]:
    """Parse a model reply into `[subject, relation, object]` triples.

    Args:
        text: Model reply.
        relations: Ontology relation labels, with spaces replaced by underscores.
        sentence: Test sentence the reply is about.

    Returns:
        The distinct triples, in order of appearance.
    """
    # Longest labels first, so that a label is never cut by a shorter one it starts with
    label_patterns = [
        re.compile(r'\s*'.join(re.escape(part) for part in re.split(r'[_ ]+', label.strip('_'))) + r'[_ ]*\(', re.IGNORECASE)
        for label in sorted(relations, key=len, reverse=True)
    ]
    triples: list[list[str]] = []
    for raw in text.replace('\\_', '_').splitlines():
        line = OUTPUT_LABEL.sub('', LIST_MARKER.sub('', raw.strip().strip('`').strip())).strip().rstrip('.;')
        if '(' not in line or not line.endswith(')'):
            continue
        match = next((m for p in label_patterns if (m := p.match(line))), None)
        if match is not None:
            relation, arguments = line[:match.end() - 1], line[match.end():-1]
        else:
            relation, arguments = line[:line.index('(')], line[line.index('(') + 1:-1]
        relation = re.sub(r'\s+', '_', relation.strip())
        split = _split_arguments(arguments, sentence)
        if relation and split is not None:
            triple = [split[0], relation, split[1]]
            if triple not in triples:
                triples.append(triple)
    return triples


async def _ask(client: OpenAIClient, prompt: str, effort: ReasoningEffort) -> tuple[str | None, dict]:
    """Send one prompt, retrying with backoff.

    Args:
        client: Engine OpenAI client.
        prompt: Prompt text, sent unchanged as the user message.
        effort: Reasoning effort.

    Returns:
        The reply text, or None if every attempt failed, and the usage metrics of the successful call.
    """
    request = LLMRequest(prompt=LLMPrompt(content=prompt, instructions=None), reasoning_effort=effort)
    for attempt in range(ATTEMPTS):
        try:
            response = await client.generate(request)
            return response.content, response.metrics
        except Exception as error:  # noqa: BLE001
            if attempt == ATTEMPTS - 1:
                print(f'    gave up after {ATTEMPTS} attempts: {type(error).__name__}: {error}', file=sys.stderr)
                return None, {}
            await asyncio.sleep(2 ** attempt * 5)
    return None, {}


def _usage(metrics: list[dict]) -> dict[str, int]:
    """Sum the usage metrics of several responses.

    Args:
        metrics: Usage metrics as returned by the Responses API.

    Returns:
        Input, cached input, output and reasoning token totals.
    """
    total = {'input_tokens': 0, 'cached_tokens': 0, 'output_tokens': 0, 'reasoning_tokens': 0}
    for m in metrics:
        total['input_tokens'] += m.get('input_tokens') or 0
        total['cached_tokens'] += (m.get('input_tokens_details') or {}).get('cached_tokens') or 0
        total['output_tokens'] += m.get('output_tokens') or 0
        total['reasoning_tokens'] += (m.get('output_tokens_details') or {}).get('reasoning_tokens') or 0
    return total


async def run_ontology(args: argparse.Namespace, client: OpenAIClient, onto: str) -> None:
    """Run every prompt of one ontology and write its responses and run record.

    Args:
        args: Parsed command-line arguments.
        client: Engine OpenAI client.
        onto: Ontology identifier.
    """
    out_file = args.out / 'llm' / f'ont_{onto}_llm_responses.jsonl'
    if out_file.exists():
        print(f'{onto:12s} already done -> {out_file}')
        return
    dataset = args.benchmark / 'data' / args.dataset
    prompts_file = dataset / 'baselines' / 'prompts' / f'ont_{onto}_prompts.jsonl'
    prompts = [json.loads(line) for line in prompts_file.read_text(encoding='utf-8').splitlines() if line.strip()]
    if args.no_example:
        for item in prompts:
            item['prompt'], found = EXAMPLE_BLOCK.subn(FORMAT_LINE, item['prompt'])
            if found != 1:
                raise ValueError(f'{item["id"]}: expected one example block, found {found}')
    sentences = {
        row['id']: row['sent']
        for line in (dataset / 'test' / f'ont_{onto}_test.jsonl').read_text(encoding='utf-8').splitlines()
        if line.strip() and (row := json.loads(line))
    }
    ontology = json.loads((dataset / 'ontologies' / f'{onto}_ontology.json').read_text(encoding='utf-8'))
    relations = [rel['label'].replace(' ', '_') for rel in ontology['relations']]

    semaphore = asyncio.Semaphore(args.concurrency)

    async def one(item: dict) -> tuple[str | None, dict]:
        async with semaphore:
            return await _ask(client, item['prompt'], args.effort)

    started = time.monotonic()
    results = await asyncio.gather(*(one(item) for item in prompts))
    seconds = round(time.monotonic() - started)

    rows = [
        {
            'id': item['id'],
            'response': reply,
            'triples': parse_response(reply, relations, sentences.get(item['id'], '')) if reply is not None else [],
        }
        for item, (reply, _) in zip(prompts, results, strict=True)
    ]
    failed = sum(reply is None for reply, _ in results)
    record = {
        'ontology': onto,
        'system': 'prompting baseline (benchmark prompts' + (', example removed)' if args.no_example else ')'),
        'recorded_at': datetime.now(UTC).isoformat(timespec='seconds'),
        'model': args.model,
        'reasoning_effort': args.effort.value,
        'engine': engine_revision(),
        'prompts_file_sha256': hashlib.sha256(prompts_file.read_bytes()).hexdigest(),
        'prompts': len(prompts),
        'failed': failed,
        'with_triples': sum(bool(row['triples']) for row in rows),
        'triples': sum(len(row['triples']) for row in rows),
        'usage': _usage([metrics for _, metrics in results]),
        'seconds': seconds,
    }
    (args.out / 'runs').mkdir(parents=True, exist_ok=True)
    (args.out / 'runs' / f'{onto}.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    if failed:
        print(f'{onto:12s} {failed} prompts failed; responses not written, re-run to retry', file=sys.stderr)
        return
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    print(f'{onto:12s} prompts={len(prompts)} with_triples={record["with_triples"]} triples={record["triples"]} '
          f'seconds={seconds} -> {out_file}')


async def main_async(args: argparse.Namespace) -> int:
    """Run every selected ontology in turn.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The process exit code: 1 if any ontology had failed prompts, 0 otherwise.
    """
    from wukong_engine.infrastructure.config.env import load_env_config  # noqa: PLC0415

    client = OpenAIClient(OpenAIConfig(api_key=load_env_config().openai_api_key, model=LLM(name=args.model)))
    for onto in args.onto or [*ONTOLOGIES]:
        await run_ontology(args, client, onto)
    missing = [onto for onto in (args.onto or ONTOLOGIES) if not (args.out / 'llm' / f'ont_{onto}_llm_responses.jsonl').exists()]
    return 1 if missing else 0


def main() -> int:
    """Parse the arguments and run.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--benchmark', type=Path, required=True, help='Path to the Text2KGBench repository')
    parser.add_argument('--dataset', default='wikidata_tekgen')
    parser.add_argument('--out', type=Path, required=True, help='Results directory of this run')
    parser.add_argument('--onto', action='append', choices=[*ONTOLOGIES], help='Ontology to run (repeatable)')
    parser.add_argument('--model', default='gpt-5.6-luna')
    parser.add_argument('--effort', type=ReasoningEffort, default=ReasoningEffort.LOW, help='Reasoning effort')
    parser.add_argument('--concurrency', type=int, default=15)
    parser.add_argument('--no-example', action='store_true',
                        help='Remove the retrieved example from each prompt (zero-shot control), stating the output format instead')
    args = parser.parse_args()
    args.benchmark = args.benchmark.resolve()
    return asyncio.run(main_async(args))


if __name__ == '__main__':
    sys.exit(main())
