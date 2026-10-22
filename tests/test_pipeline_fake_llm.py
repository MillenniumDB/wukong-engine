"""End-to-end test of the engine with a fake LLM: no API key, no cost.

Runs the real `wukong run` pipeline on a two-document corpus and a small knowledge model (Person, Ship, Report;
Crews, Knows), with the OpenAI client replaced by a fake that returns scripted responses, then checks the staging
database and both export formats (QM file and Neo4j CSV files) against the expected results. The scripted responses
contain one case of every validation rejection, a symbol-only primary key, one response that fails to decode and is
retried, and document-level responses with several candidates. The config sets document_prefix_tokens to 6, so
document-level prompts must not contain the end of a document, and reasoning_effort to "medium", which every request
must carry. Every regular expression must appear in the prompts of its own kind of job.

Usage (Python 3.14 environment with the engine installed; see paper/REPRODUCE.md):
    python tests/test_pipeline_fake_llm.py                    # both execution modes, in temporary folders
    python tests/test_pipeline_fake_llm.py <real-time|batch> <out_dir>   # one mode, keeping its files in out_dir

Exits with status 0 when every check passes.
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[1]
MODES = ('real-time', 'batch')

# --- Expected results --------------------------------------------------------------------------------------------------
EXPECTED_JOBS = {'COMPLETED': 6, 'FAILED': 1}  # the FAILED job is the undecodable response; every job keeps it raw
EXPECTED_REJECTIONS = {  # (scope, reason, type, field): count, over completed jobs
    ('OBJECT', 'INVALID_PRIMARY_KEY', 'Person', 'name'): 2,  # control characters only; '#' (no letter or digit)
    ('OBJECT', 'MISSING_VALUE', 'Person', 'name'): 1,
    ('OBJECT', 'REGEX_MISMATCH', 'Ship', 'code'): 1,
    ('OBJECT', 'UNKNOWN_TYPE', None, None): 1,  # no type
    ('OBJECT', 'UNKNOWN_TYPE', 'Planet', None): 1,
    ('VALUE', 'INVALID_OPTION', 'Person', 'role'): 1,  # value unset, object kept
    ('VALUE', 'REGEX_MISMATCH', 'Person', 'badge'): 1,
    ('OBJECT', 'INVALID_ENDPOINT', 'Crews', None): 1,
    ('OBJECT', 'MISSING_ENDPOINT', 'Crews', None): 1,
    ('OBJECT', 'UNRESOLVED_ENDPOINT', 'Crews', None): 1,
    ('OBJECT', 'SELF_LOOP', 'Knows', None): 1,
    ('OBJECT', 'UNKNOWN_TYPE', 'Owns', None): 1,
    ('VALUE', 'REGEX_MISMATCH', 'Crews', 'since'): 1,
    ('OBJECT', 'REGEX_MISMATCH', 'Report', 'id'): 1,  # document level
    ('OBJECT', 'EXTRA_DOCUMENT_ENTITY', 'Report', None): 1,
}
EXPECTED_ENTITIES = {  # (type, key): properties; Report R1 is merged with its repetition r1
    ('Person', 'Ana'): {'name': 'Ana', 'role': 'pilot', 'badge': 'B123'},
    ('Person', 'Bo'): {'name': 'Bo'},
    ('Ship', 'ABC'): {'code': 'ABC'},
    ('Report', 'R1'): {'id': 'R1'},
    ('Report', 'R3'): {'id': 'R3'},
}
EXPECTED_RELATIONSHIPS = Counter(
    {('Crews', 'Ana', 'ABC', '2020'): 1, ('Crews', 'Bo', 'ABC', None): 1, ('Knows', 'Bo', 'Ana', None): 1},
)
EXPECTED_EXPORT = {'Person': 2, 'Ship': 1, 'Report': 2, 'Crews': 2, 'Knows': 1}  # nodes or edges per label
EXPECTED_REGEXES = {
    'document': ['^[Rr][0-9]$'],
    'entities': ['^B[0-9]{3}$', '^[A-Z]{3}$'],
    'relationships': ['^[0-9]{4}$'],
}

# --- Scripted responses ------------------------------------------------------------------------------------------------
USAGE = {'input_tokens': 100, 'output_tokens': 10}
ENTITIES_A = [
    {'_entity_type': 'Person', 'name': 'Ana', 'role': 'pilot', 'badge': 'B123'},  # valid
    {'_entity_type': 'Person', 'name': 'Bo', 'role': 'captain', 'badge': 'X'},  # kept; role and badge unset
    {'_entity_type': 'Person', 'name': None, 'role': 'pilot'},  # MISSING_VALUE name
    {'_entity_type': 'Person', 'name': '\x01\x02', 'role': 'chef', 'badge': 'B999'},  # INVALID_PRIMARY_KEY
    {'_entity_type': 'Person', 'name': '#', 'role': 'pilot'},  # INVALID_PRIMARY_KEY (no letter or digit)
    {'_entity_type': 'Ship', 'code': 'abc'},  # REGEX_MISMATCH on the required code
    {'_entity_type': 'Ship', 'code': 'ABC'},  # valid
    {'_entity_type': 'Planet', 'name': 'Mars'},  # UNKNOWN_TYPE
    {'name': 'Nobody'},  # UNKNOWN_TYPE (no type)
]
ENTITIES_B = [{'_entity_type': 'Person', 'name': 'Ana', 'role': 'engineer'}]
REPORTS_A = [
    {'_entity_type': 'Report', 'id': 'bad'},  # REGEX_MISMATCH on the required id
    {'_entity_type': 'Report', 'id': 'R1'},  # first valid: kept
    {'_entity_type': 'Report', 'id': 'r1'},  # same identity as R1: a repetition, merged
    {'_entity_type': 'Report', 'id': 'R2'},  # EXTRA_DOCUMENT_ENTITY
]
REPORTS_B = [{'_entity_type': 'Report', 'id': 'R3'}]


def knowledge_model() -> dict:
    """Knowledge model of the test corpus."""
    chunk = {'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}
    return {
        'extraction_config': {'llm': {'domain': 'Test crew reports.', 'language': 'en'}},
        'entity_types': {
            'Person': {
                'description': 'A person.',
                'primary_key': 'name',
                'deduplication': 'primary_key',
                'default_merge_strategy': 'keep',
                'fields': {
                    'name': {'data_type': 'string', 'description': 'Name.', 'required': True},
                    'role': {'data_type': 'string', 'description': 'Role.', 'options': ['pilot', 'engineer']},
                    'badge': {'data_type': 'string', 'description': 'Badge.', 'regex': '^B[0-9]{3}$'},
                },
                'document_collections': {'chunk': ['docs']},
            },
            'Report': {
                'description': 'The report a document is.',
                'primary_key': 'id',
                'deduplication': 'primary_key',
                'default_merge_strategy': 'keep',
                'fields': {
                    'id': {
                        'data_type': 'string',
                        'description': 'Report id.',
                        'regex': '^[Rr][0-9]$',
                        'required': True,
                    },
                },
                'document_collections': {'document': ['docs']},
            },
            'Ship': {
                'description': 'A ship.',
                'primary_key': 'code',
                'deduplication': 'primary_key',
                'default_merge_strategy': 'keep',
                'fields': {
                    'code': {'data_type': 'string', 'description': 'Code.', 'regex': '^[A-Z]{3}$', 'required': True},
                },
                'document_collections': {'chunk': ['docs']},
            },
        },
        'relationship_types': {
            'Crews': {
                'description': 'A person crews a ship.',
                'deduplication': 'none',
                'default_merge_strategy': 'keep',
                'endpoints': {'Person': {'Ship': chunk}},
                'fields': {'since': {'data_type': 'string', 'description': 'Year.', 'regex': '^[0-9]{4}$'}},
            },
            'Knows': {
                'description': 'A person knows another.',
                'deduplication': 'endpoints',
                'default_merge_strategy': 'keep',
                'irreflexive': True,
                'endpoints': {'Person': {'Person': chunk}},
                'fields': {},
            },
        },
    }


def setup(mode: str, out: Path) -> tuple[Path, Path, Path]:
    """Write the corpus, the workspace and the two configs (extraction, then Neo4j export only)."""
    shutil.rmtree(out, ignore_errors=True)
    ws, data = out / 'ws', out / 'data'
    (data / 'docs').mkdir(parents=True)
    (data / 'docs' / 'a.txt').write_text('DOC-A. Ana (badge B123) pilots the ship ABC. Bo knows Ana.\n')
    (data / 'docs' / 'b.txt').write_text('DOC-B. Ana is an engineer.\n')
    ws.mkdir(parents=True)
    (ws / 'document_collections.json').write_text(
        json.dumps({'collections': {'docs': {'sources': [{'root': 'docs', 'mode': 'directory'}]}}}),
    )
    (ws / 'knowledge_model.json').write_text(json.dumps(knowledge_model()))
    config = (ROOT / 'config' / 'default.toml').read_text()
    for old, new in (
        ('execution_mode = "real-time"', f'execution_mode = "{mode}"'),
        ('document_prefix_tokens = 8000', 'document_prefix_tokens = 6'),
        ('reasoning_effort = "low"', 'reasoning_effort = "medium"'),
    ):
        if old not in config:
            raise RuntimeError(f'config/default.toml no longer contains {old!r}')
        config = config.replace(old, new)
    (out / 'config.toml').write_text(config)
    export_only = config
    for step in ('ingest_documents', 'extract_entities', 'extract_relationships'):
        export_only = export_only.replace(f'{step} = true', f'{step} = false')
    export_only = re.sub(r'(?m)^format = "\w+"', 'format = "neo4j"', export_only)
    (out / 'config-neo4j.toml').write_text(export_only)
    return ws, data, out / 'config.toml'


class FakeClient:
    """Stands in for the OpenAI client: answers from the scripted responses and records what the prompts contain."""

    calls: ClassVar[Counter] = Counter()
    document_level_saw_end = False
    efforts: ClassVar[set[str]] = set()
    regexes: ClassVar[dict[str, set[str]]] = {'document': set(), 'entities': set(), 'relationships': set()}
    batches: ClassVar[dict[str, list[tuple[str, str]]]] = {}

    def __init__(self, config: object) -> None:
        """Accept the engine's LLM configuration, which the fake does not need."""

    def _content(self, request: object) -> str:
        FakeClient.efforts.add(request.reasoning_effort.value if request.reasoning_effort else 'None')
        prompt = request.prompt
        text = (prompt.shared_content or '') + prompt.content
        doc = 'A' if 'DOC-A' in text else 'B'
        is_relationships = '"relationships"' in json.dumps(prompt.schema)
        kind = 'document' if 'single primary entity' in text else 'relationships' if is_relationships else 'entities'
        FakeClient.regexes[kind].update(re.findall(r'Must match the regular expression: (\S+)', text))
        FakeClient.calls[f'{kind}-{doc}'] += 1
        if kind == 'document':
            FakeClient.document_level_saw_end |= 'knows Ana' in prompt.content or 'engineer' in prompt.content
            return json.dumps({'entities': REPORTS_A if doc == 'A' else REPORTS_B})
        if kind == 'entities':
            if doc == 'B' and FakeClient.calls['entities-B'] == 1:
                return 'not json {'  # decoding fails once; the job fails and is retried
            return json.dumps({'entities': ENTITIES_A if doc == 'A' else ENTITIES_B})
        if doc == 'B':
            return json.dumps({'relationships': []})
        ids = {pk: temp for temp, pk in re.findall(r'Entity ID: (E\d+)\n\w+: (.+)', text)}
        ana, bo, ship = ids['Ana'], ids['Bo'], ids['ABC']
        return json.dumps(
            {
                'relationships': [
                    {
                        '_relationship_type': 'Crews',
                        '_source_entity_id': ana,
                        '_target_entity_id': ship,
                        'since': '2020',
                    },
                    {
                        '_relationship_type': 'Crews',
                        '_source_entity_id': bo.lower(),
                        '_target_entity_id': ship,
                        'since': 'last year',
                    },  # since unset
                    {
                        '_relationship_type': 'Crews',
                        '_source_entity_id': 'E99',
                        '_target_entity_id': ship,
                    },  # UNRESOLVED_ENDPOINT
                    {'_relationship_type': 'Crews', '_source_entity_id': ana},  # MISSING_ENDPOINT
                    {
                        '_relationship_type': 'Crews',
                        '_source_entity_id': ship,
                        '_target_entity_id': ana,
                    },  # INVALID_ENDPOINT
                    {'_relationship_type': 'Knows', '_source_entity_id': ana, '_target_entity_id': ana},  # SELF_LOOP
                    {'_relationship_type': 'Knows', '_source_entity_id': bo, '_target_entity_id': ana},  # valid
                    {'_relationship_type': 'Owns', '_source_entity_id': ana, '_target_entity_id': ship},  # UNKNOWN_TYPE
                ],
            },
        )

    async def generate(self, request: object) -> object:
        """Answer one real-time request."""
        from wukong_engine.app.llm.elements import LLMResponse  # noqa: PLC0415

        return LLMResponse(content=self._content(request), model='fake', metrics=USAGE)

    async def create_batch(self, requests: list, job_ids: list) -> object:
        """Answer a batch at once and keep the answers until they are collected."""
        from wukong_engine.app.llm.elements.response import LLMBatchCreationResponse  # noqa: PLC0415
        from wukong_engine.app.llm.model.values import LLMProvider  # noqa: PLC0415

        batch_id = f'batch-{len(FakeClient.batches)}'
        FakeClient.batches[batch_id] = [(job_id, self._content(r)) for r, job_id in zip(requests, job_ids, strict=True)]
        return LLMBatchCreationResponse(batch_id=batch_id, provider=LLMProvider.OPENAI)

    async def get_batch_status(self, batch_id: str) -> str:  # noqa: ARG002
        """Report every batch as completed."""
        return 'completed'

    async def get_batch_results(self, batch_id: str) -> tuple:
        """Return the answers of a batch."""
        from wukong_engine.app.llm.elements import LLMResponse  # noqa: PLC0415
        from wukong_engine.app.llm.elements.response import LLMBatchResult  # noqa: PLC0415

        return tuple(
            LLMBatchResult(job_id=job_id, response=LLMResponse(content=c, model='fake', metrics=USAGE))
            for job_id, c in FakeClient.batches[batch_id]
        )


def run_cli(ws: Path, data: Path, config: Path) -> None:
    """Run `wukong run` in this process (the fake client is patched in)."""
    from wukong_engine.presentation.cli.main import main  # noqa: PLC0415

    sys.argv = ['wukong', 'run', str(ws), str(data), '--config', str(config)]
    try:
        main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            print(f'wukong run exited with {exc.code}')


def pipeline_done(db: Path) -> bool:
    """Whether the last extraction step of the pipeline has completed."""
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT checkpoint_status FROM pipeline_checkpoints WHERE checkpoint_name LIKE '%RELATIONSHIPS_EXTRACTED%'",
    ).fetchone()
    con.close()
    return bool(row) and row[0] == 'COMPLETED'


def staging_results(db: Path) -> tuple[dict, dict, dict, Counter]:
    """Jobs per status (and how many keep their raw response), rejections, entities and relationships."""
    con = sqlite3.connect(db)
    jobs = {
        s: (n, raw)
        for s, n, raw in con.execute(
            'SELECT job_status, COUNT(*), SUM(raw_response IS NOT NULL) FROM extraction_jobs GROUP BY 1',
        )
    }
    rejections = {
        (scope, reason, t, f): n
        for scope, reason, t, f, n in con.execute(
            'SELECT rejection_scope, rejection_reason, type_name, field_name, SUM(rejection_count) '
            'FROM extraction_rejections r JOIN extraction_jobs j USING (job_id) '
            "WHERE j.job_status = 'COMPLETED' GROUP BY 1, 2, 3, 4",
        )
    }
    keys = {'Person': 'name', 'Ship': 'code', 'Report': 'id'}
    entities, names = {}, {}
    for cid, t, stored in con.execute('SELECT content_id, entity_type_name, properties FROM entities'):
        props = {k: v for k, v in json.loads(stored).items() if v is not None}
        entities[t, props.get(keys.get(t))] = props
        names[cid] = props.get(keys.get(t))
    relationships = Counter(
        (t, names.get(s), names.get(o), json.loads(props).get('since'))
        for t, s, o, props in con.execute(
            'SELECT relationship_type_name, source_content_id, target_content_id, properties FROM relationships',
        )
    )
    con.close()
    return jobs, rejections, entities, relationships


def qm_counts(path: Path) -> Counter:
    """Nodes and edges per label in a QM export (`N_x :Label ...` and `N_x->N_y :Label ...` lines)."""
    counts = Counter()
    for line in path.read_text().splitlines():
        m = re.match(r'N_\w+(?:->N_\w+)? :(\w+)', line)
        if m:
            counts[m.group(1)] += 1
    return counts


def neo4j_counts(folder: Path) -> Counter:
    """Rows per label in a Neo4j export (one CSV file per node or edge label, with a header row)."""
    return Counter({p.stem: len(p.read_text().splitlines()) - 1 for p in folder.glob('*/*.csv')})


def run_mode(mode: str, out: Path) -> int:
    """Run one execution mode end to end and check its results; return the number of failed checks."""
    os.environ['OPENAI_API_KEY'] = 'dummy'
    ws, data, config = setup(mode, out)
    from wukong_engine.bootstrap.cli import application  # noqa: PLC0415

    application.OpenAIClient = FakeClient
    db = ws / 'staging' / 'extraction.db'
    for _ in range(8):  # batch mode needs several invocations: submit, then synchronize
        run_cli(ws, data, config)
        if pipeline_done(db):
            break
    calls_after_extraction = sum(FakeClient.calls.values())
    run_cli(ws, data, out / 'config-neo4j.toml')  # export only, in the other format: no LLM call

    failures = []

    def check(what: str, actual: object, expected: object) -> None:
        ok = actual == expected
        print(
            f'  [{"ok" if ok else "FAIL"}] {what}'
            + ('' if ok else f'\n         expected {expected}\n         got      {actual}'),
        )
        if not ok:
            failures.append(what)

    print(f'{mode}:')
    check('pipeline completed', pipeline_done(db), expected=True)
    jobs, rejections, entities, relationships = staging_results(db)
    check('extraction jobs per status', {s: n for s, (n, _) in jobs.items()}, EXPECTED_JOBS)
    check('every job keeps its raw response', all(n == raw for n, raw in jobs.values()), expected=True)
    check('rejections per scope, reason, type and field', rejections, EXPECTED_REJECTIONS)
    check('entities and their properties', entities, EXPECTED_ENTITIES)
    check('relationships', relationships, EXPECTED_RELATIONSHIPS)
    check(
        'document-level prompts stop before the end of the document',
        FakeClient.document_level_saw_end,
        expected=False,
    )
    check('reasoning effort of every request', sorted(FakeClient.efforts), ['medium'])
    check(
        'regexes shown in the prompts of their own kind of job',
        {k: sorted(v) for k, v in FakeClient.regexes.items()},
        EXPECTED_REGEXES,
    )
    check(
        'export to a QM file: nodes and edges per label',
        {k: v for k, v in qm_counts(ws / 'exports' / 'mdb' / 'knowledge_graph.qm').items() if k in EXPECTED_EXPORT},
        EXPECTED_EXPORT,
    )
    check(
        'export to Neo4j CSV files: rows per label',
        {k: v for k, v in neo4j_counts(ws / 'exports' / 'neo4j').items() if k in EXPECTED_EXPORT},
        EXPECTED_EXPORT,
    )
    check('the export-only run makes no LLM call', sum(FakeClient.calls.values()), calls_after_extraction)
    return len(failures)


def main() -> int:
    """Run both modes, each in its own process, or the one mode given on the command line."""
    if sys.argv[1:]:
        return 1 if run_mode(sys.argv[1], Path(sys.argv[2])) else 0
    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        for mode in MODES:  # one process per mode, so that no state carries over
            result = subprocess.run(  # noqa: S603
                [sys.executable, __file__, mode, str(Path(tmp) / mode)],
                capture_output=True,
                text=True,
                check=False,
            )
            print('\n'.join(line for line in result.stdout.splitlines() if line.startswith((' ', mode))))
            if result.returncode:
                failed.append(mode)
                print(result.stderr[-3000:])
    print('PASS' if not failed else f'FAIL ({", ".join(failed)})')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
