"""Build a neo4j-graphrag (1.22.0) knowledge graph over the UDA-Bench NBA corpus.

Replicates SimpleKGPipeline's default components, minus the Neo4j writer, so it
runs without a database:

    FixedSizeSplitter(4000, 200, approximate=True)
      -> LLMEntityRelationExtractor(use_structured_output=True, default prompt)
      -> GraphPruning(schema)
      -> exact-match entity resolution, reimplemented in Python

    envs/neo4j-graphrag/bin/python baselines/neo4j_graphrag_build.py \
        --data runs/x6-pilot-data --out runs/neo4j-pilot

Decisions:
- Schema: workspace-v1/knowledge_model.json is translated slot by slot. A key
  goes into the tool's matching slot, or nowhere (see mapping.md in the run dir):
  - entity description -> NodeType.description
  - field description -> PropertyType.description (type STRING)
  - entity primary_key -> ConstraintType KEY
  - required relationship field -> ConstraintType EXISTENCE
  - endpoints -> patterns
  - all additional_* flags are False.
  Field instructions, examples, options, regexes and the domain statement have
  no slot and are dropped. The Team/City key properties team_name/city_name are
  renamed to `name` in the tool schema, because the resolver works on `name`.
  They are mapped back on export.
- Entity resolution reimplements SinglePropertyExactMatchResolver plus
  apoc.refactor.mergeNodes(properties:'discard', mergeRels:true):
  - group per label on an exact `name` match;
  - the first node (document order, then chunk order, then extraction order)
    keeps its property values, and nodes later in that order only fill
    properties it lacks;
  - relationships of the same type between the same resolved endpoints are
    merged, with the first one's properties kept.
  Nodes without a name are not resolved; the KEY constraint already prunes them.
- on_error: SimpleKGPipeline's default is IGNORE, which drops a chunk whose
  output does not parse. Here every failed chunk (bad output, or an API error
  after retries) is dropped the same way, but it is counted and logged in
  meta.json. Under IGNORE, an API error would abort the whole document.
- The chunk embedder is skipped: it only adds chunk embeddings and does not
  affect extraction.
- Document metadata matches SimpleKGPipeline.run_async(text=..., file_path=doc_id):
  DocumentInfo(path="player/1", document_type=INLINE_TEXT), nothing else.
- Concurrency: documents run concurrently. The extractor keeps its default
  max_concurrency=5 per document, and a global semaphore caps in-flight LLM
  calls at --max-inflight (default 16). Rate-limit errors are retried by
  RetryRateLimitHandler.
- Resumable: each document's pruned graph is cached in <out>/cache/. A rerun
  skips cached documents; usage.jsonl is appended to.

Outputs in --out: graph/nodes.jsonl, graph/edges.jsonl, usage.jsonl,
meta.json, mapping.md, schema.json, cache/.
"""

import argparse
import asyncio
import json
import logging
import time
from importlib import metadata as md
from pathlib import Path

from neo4j_graphrag.components.entity_relation_extractor import LLMEntityRelationExtractor, OnError
from neo4j_graphrag.components.graph_pruning import GraphPruning
from neo4j_graphrag.components.schema import GraphSchema
from neo4j_graphrag.components.text_splitters.fixed_size_splitter import FixedSizeSplitter
from neo4j_graphrag.components.types import DocumentInfo, DocumentType, LexicalGraphConfig, Neo4jGraph
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.utils.rate_limit import RetryRateLimitHandler

HERE = Path(__file__).resolve().parent.parent
KM_PATH = HERE / 'workspace-v1' / 'knowledge_model.json'
TYPES = ('player', 'team', 'city', 'owner')
LEX = LexicalGraphConfig()

MODEL = 'gpt-5.6-luna'
MODEL_PARAMS = {'reasoning_effort': 'low'}
CHUNK_SIZE, CHUNK_OVERLAP = 4000, 200
EXTRACTOR_MAX_CONCURRENCY = 5  # LLMEntityRelationExtractor default
RETRY = dict(max_attempts=6, min_wait=1.0, max_wait=60.0)

log = logging.getLogger('neo4j_graphrag_build')


# ---------------------------------------------------------------- schema

def key_field(et: dict) -> str:
    return et['primary_key']


def tool_prop_name(et: dict, field: str) -> str:
    """Key properties are renamed to `name` (the resolver's property)."""
    return 'name' if field == key_field(et) else field


def build_schema(km: dict) -> GraphSchema:
    node_types, constraints = [], []
    for label, et in km['entity_types'].items():
        node_types.append(dict(
            label=label,
            description=et.get('description', ''),
            properties=[dict(name=tool_prop_name(et, f), type='STRING', description=fd.get('description', ''))
                        for f, fd in et['fields'].items()],
            additional_properties=False,
        ))
        constraints.append(dict(type='KEY', node_type=label, property_names=['name']))
    rel_types, patterns = [], []
    for label, rt in km['relationship_types'].items():
        fields = rt.get('fields', {})
        rel_types.append(dict(
            label=label,
            description=rt.get('description', ''),
            properties=[dict(name=f, type='STRING', description=fd.get('description', ''))
                        for f, fd in fields.items()],
            additional_properties=False,
        ))
        for f, fd in fields.items():
            if fd.get('required'):
                constraints.append(dict(type='EXISTENCE', relationship_type=label, property_names=[f]))
        for src, tgts in rt['endpoints'].items():
            for tgt in tgts:
                patterns.append((src, label, tgt))
    return GraphSchema.model_validate(dict(
        node_types=node_types, relationship_types=rel_types, patterns=patterns, constraints=constraints,
        additional_node_types=False, additional_relationship_types=False, additional_patterns=False,
    ))


def slot_for(path: list[str], km: dict) -> str:
    """Where a knowledge-model key went in the tool schema (for mapping.md)."""
    p = path
    if p[0] == 'extraction_config':
        return 'no slot'
    if p[0] == 'entity_types':
        et = km['entity_types'][p[1]]
        if len(p) == 2:
            return f'NodeType.label = "{p[1]}"'
        if p[2] == 'description':
            return 'NodeType.description'
        if p[2] == 'primary_key':
            return f'ConstraintType(type=KEY, node_type="{p[1]}", property_names=["name"])'
        if p[2] == 'fields':
            if len(p) == 3:
                return 'NodeType.properties'
            f = p[3]
            if len(p) == 4:
                return f'PropertyType.name = "{tool_prop_name(et, f)}"' + (
                    f' (renamed from {f}; mapped back on export)' if tool_prop_name(et, f) != f else '')
            if p[4] == 'data_type':
                return 'PropertyType.type = "STRING"'
            if p[4] == 'description':
                return 'PropertyType.description'
            if p[4] == 'required' and f == key_field(et):
                return 'covered by the KEY constraint (the tool forbids KEY + EXISTENCE on one property)'
        return 'no slot'
    if p[0] == 'relationship_types':
        if len(p) == 2:
            return f'RelationshipType.label = "{p[1]}"'
        if p[2] == 'description':
            return 'RelationshipType.description'
        if p[2] == 'endpoints':
            if len(p) == 5:
                return f'GraphSchema.patterns: ("{p[3]}", "{p[1]}", "{p[4]}")'
            return 'no slot' if len(p) > 5 else 'GraphSchema.patterns'
        if p[2] == 'fields':
            if len(p) == 3:
                return 'RelationshipType.properties'
            if len(p) == 4:
                return f'PropertyType.name = "{p[3]}"'
            if p[4] == 'data_type':
                return 'PropertyType.type = "STRING"'
            if p[4] == 'description':
                return 'PropertyType.description'
            if p[4] == 'required':
                return f'ConstraintType(type=EXISTENCE, relationship_type="{p[1]}", property_names=["{p[3]}"])'
        if p[2] == 'primary_key':
            return 'no slot (a relationship KEY in the tool means unique across all relationships of the type)'
        return 'no slot'
    return 'no slot'


def write_mapping(km: dict, out: Path) -> None:
    rows = []

    def walk(d, path):
        for k, v in d.items():
            p = path + [k]
            if isinstance(v, dict):
                if (p[0] in ('entity_types', 'relationship_types') and len(p) == 2) or p[-1] == 'fields' \
                        or (len(p) == 4 and p[-2] == 'fields') or (p[0] == 'relationship_types' and len(p) == 5):
                    rows.append((p, None))
                walk(v, p)
            elif isinstance(v, list) and v and isinstance(v[0], dict):  # endpoint context-level lists
                rows.append((p, None))
                for i, item in enumerate(v):
                    for kk, vv in item.items():
                        rows.append((p + [str(i), kk], vv))
            else:
                rows.append((p, v))

    walk(km, [])
    lines = [
        '# Knowledge model -> neo4j-graphrag 1.22.0 schema',
        '',
        f'Source: `{KM_PATH.relative_to(HERE)}`. Tool-side settings that do not come from the knowledge model: '
        '`additional_node_types`, `additional_relationship_types`, `additional_patterns` and each type\'s '
        '`additional_properties` are False. All properties are STRING. The schema is passed to '
        'LLMEntityRelationExtractor (it goes into the default prompt as `schema.model_dump()`) and to GraphPruning. '
        'The translated schema is in `schema.json`.',
        '',
        '| knowledge-model key | value | tool schema slot |',
        '|---|---|---|',
    ]
    for p, v in rows:
        val = '' if v is None else json.dumps(v, ensure_ascii=False)
        if len(val) > 60:
            val = val[:57] + '...'
        val = val.replace('|', '\\|')
        lines.append(f'| `{".".join(p)}` | {val} | {slot_for(p, km)} |')
    (out / 'mapping.md').write_text('\n'.join(lines) + '\n')


# ---------------------------------------------------------------- LLM

class UsageOpenAILLM(OpenAILLM):
    """OpenAILLM that caps in-flight calls and logs every call's usage to usage.jsonl."""

    def __init__(self, *a, usage_log: Path, max_inflight: int, **kw):
        super().__init__(*a, **kw)
        self.n_calls = 0
        sem = asyncio.Semaphore(max_inflight)
        orig = self.async_client.chat.completions.create

        async def wrapped(*args, **kwargs):
            async with sem:
                t0 = time.time()
                resp = await orig(*args, **kwargs)
            u = resp.usage
            if u is not None:
                rec = {
                    'ts': t0, 'secs': round(time.time() - t0, 2),
                    'input': u.prompt_tokens,
                    'cached': getattr(u.prompt_tokens_details, 'cached_tokens', 0) or 0,
                    'output': u.completion_tokens,
                    'reasoning': getattr(u.completion_tokens_details, 'reasoning_tokens', 0) or 0,
                }
                with usage_log.open('a') as fh:
                    fh.write(json.dumps(rec) + '\n')
            self.n_calls += 1
            return resp

        self.async_client.chat.completions.create = wrapped


class CountingExtractor(LLMEntityRelationExtractor):
    """Drops a failed chunk (as on_error=IGNORE does) but records it."""

    def __init__(self, *a, failures: list, **kw):
        super().__init__(*a, on_error=OnError.RAISE, **kw)
        self.failures = failures

    async def extract_for_chunk(self, schema, examples, chunk):
        try:
            return await super().extract_for_chunk(schema, examples, chunk)
        except Exception as e:  # LLMGenerationError (bad output) or API error after retries
            doc = (chunk.metadata or {}).get('doc')
            self.failures.append({'doc': doc, 'chunk': chunk.index, 'error': f'{type(e).__name__}: {e}'[:500]})
            log.warning('chunk failed: %s #%s: %s', doc, chunk.index, e)
            return Neo4jGraph()


# ---------------------------------------------------------------- pipeline

def list_docs(data: Path) -> list[tuple[str, Path]]:
    docs = []
    for t in TYPES:
        for p in sorted((data / t / t).glob('*.txt'), key=lambda p: int(p.stem)):
            docs.append((f'{t}/{p.stem}', p))
    return docs


async def process_doc(doc_id: str, path: Path, schema: GraphSchema, llm, failures: list, cache: Path) -> dict:
    cfile = cache / (doc_id.replace('/', '_') + '.json')
    if cfile.exists():
        return json.loads(cfile.read_text())
    text = path.read_text()
    chunks = await FixedSizeSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, approximate=True).run(text=text)
    for c in chunks.chunks:
        c.metadata = {'doc': doc_id}
    doc_failures: list = []
    extractor = CountingExtractor(llm=llm, use_structured_output=True,
                                  max_concurrency=EXTRACTOR_MAX_CONCURRENCY, failures=doc_failures)
    graph = await extractor.run(
        chunks=chunks, schema=schema, lexical_graph_config=LEX,
        document_info=DocumentInfo(path=doc_id, document_type=DocumentType.INLINE_TEXT),
    )
    pruned = await GraphPruning().run(graph=graph, schema=schema, lexical_graph_config=LEX)
    stats = pruned.pruning_stats
    chunk_names = {c.chunk_id: f'{doc_id}#{c.index}' for c in chunks.chunks}
    result = {
        'doc': doc_id,
        'n_chunks': len(chunks.chunks),
        'failures': doc_failures,
        'pruned': {'nodes': stats.number_of_pruned_nodes, 'relationships': stats.number_of_pruned_relationships,
                   'properties': stats.number_of_pruned_properties},
        'chunk_names': chunk_names,
        'graph': pruned.graph.model_dump(),
    }
    cfile.write_text(json.dumps(result))
    failures.extend(doc_failures)
    log.info('%s: %d chunks, %d failed', doc_id, len(chunks.chunks), len(doc_failures))
    return result


def resolve(results: list[dict], km: dict):
    """Python port of SinglePropertyExactMatchResolver + apoc mergeNodes(discard, mergeRels)."""
    lexical_labels = set(LEX.lexical_graph_node_labels)
    # entity nodes in insertion order: documents in input order, then chunk order, then extraction order
    nodes, rels, node_chunks = [], [], {}
    for r in results:
        g = r['graph']
        for n in g['nodes']:
            if n['label'] not in lexical_labels:
                nodes.append(n)
        for e in g['relationships']:
            if e['type'] == LEX.node_to_chunk_relationship_type:
                node_chunks.setdefault(e['start_node_id'], []).append(r['chunk_names'][e['end_node_id']])
            elif e['type'] not in LEX.lexical_graph_relationship_types:
                chunk_uid = e['start_node_id'].rsplit(':', 1)[0]
                rels.append({**e, 'chunk': r['chunk_names'].get(chunk_uid)})
    pre = {'nodes': len(nodes), 'edges': len(rels)}

    canon = {}   # tool node id -> resolved id
    merged = {}  # resolved id -> node record
    for n in nodes:
        name = n['properties'].get('name')
        rid = f"{n['label']}:{name}" if name is not None else n['id']
        canon[n['id']] = rid
        if rid not in merged:
            merged[rid] = {'id': rid, 'type': n['label'], 'props': dict(n['properties']), 'chunks': []}
        else:
            for k, v in n['properties'].items():  # properties:'discard' -> first value wins
                merged[rid]['props'].setdefault(k, v)
        for c in node_chunks.get(n['id'], []):
            if c not in merged[rid]['chunks']:
                merged[rid]['chunks'].append(c)

    edges = {}
    for e in rels:
        key = (canon[e['start_node_id']], e['type'], canon[e['end_node_id']])
        if key not in edges:  # mergeRels -> first relationship's properties kept
            edges[key] = {'src': key[0], 'dst': key[2], 'label': key[1], 'props': dict(e['properties']), 'chunks': []}
        if e['chunk'] and e['chunk'] not in edges[key]['chunks']:
            edges[key]['chunks'].append(e['chunk'])

    out_nodes = []
    for m in merged.values():
        et = km['entity_types'][m['type']]
        attrs = {}
        for f in et['fields']:
            v = m['props'].get(tool_prop_name(et, f))
            if v is not None:
                attrs[f] = v
        out_nodes.append({'id': m['id'], 'type': m['type'], 'name': m['props'].get('name'),
                          'attrs': attrs, 'chunks': m['chunks']})
    return out_nodes, list(edges.values()), pre


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--doc-concurrency', type=int, default=8)
    ap.add_argument('--max-inflight', type=int, default=16)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)

    out = args.out
    (out / 'graph').mkdir(parents=True, exist_ok=True)
    cache = out / 'cache'
    cache.mkdir(exist_ok=True)
    km = json.loads(KM_PATH.read_text())
    schema = build_schema(km)
    (out / 'schema.json').write_text(json.dumps(schema.model_dump(), indent=2, default=str))
    write_mapping(km, out)

    llm = UsageOpenAILLM(model_name=MODEL, model_params=MODEL_PARAMS,
                         rate_limit_handler=RetryRateLimitHandler(**RETRY),
                         usage_log=out / 'usage.jsonl', max_inflight=args.max_inflight)
    docs = list_docs(args.data)
    failures: list = []
    doc_sem = asyncio.Semaphore(args.doc_concurrency)

    async def run_one(doc_id, path):
        async with doc_sem:
            return await process_doc(doc_id, path, schema, llm, failures, cache)

    t0 = time.time()
    results = await asyncio.gather(*(run_one(d, p) for d, p in docs))
    wall = time.time() - t0

    nodes, edges, pre = resolve(results, km)
    with (out / 'graph' / 'nodes.jsonl').open('w') as fh:
        for n in nodes:
            fh.write(json.dumps(n, ensure_ascii=False) + '\n')
    with (out / 'graph' / 'edges.jsonl').open('w') as fh:
        for e in edges:
            fh.write(json.dumps(e, ensure_ascii=False) + '\n')

    all_failures = [f for r in results for f in r['failures']]
    count = lambda xs, k: {t: sum(1 for x in xs if x[k] == t) for t in sorted({x[k] for x in xs})}
    meta = {
        'tool': 'neo4j-graphrag',
        'versions': {p: md.version(p) for p in ('neo4j-graphrag', 'openai', 'neo4j', 'pydantic')},
        'data': str(args.data), 'knowledge_model': str(KM_PATH),
        'settings': {
            'llm': {'class': 'OpenAILLM', 'model_name': MODEL, 'model_params': MODEL_PARAMS,
                    'rate_limit_handler': {'class': 'RetryRateLimitHandler', **RETRY}},
            'splitter': {'class': 'FixedSizeSplitter', 'chunk_size': CHUNK_SIZE, 'chunk_overlap': CHUNK_OVERLAP,
                         'approximate': True, 'unit': 'characters'},
            'extractor': {'class': 'LLMEntityRelationExtractor', 'prompt_template': 'ERExtractionTemplate (default)',
                          'use_structured_output': True, 'create_lexical_graph': True,
                          'max_concurrency_per_doc': EXTRACTOR_MAX_CONCURRENCY,
                          'on_error': 'IGNORE-equivalent: failed chunks dropped, counted in failed_chunks'},
            'pruning': 'GraphPruning (default), all additional_* = False',
            'resolver': 'Python port of SinglePropertyExactMatchResolver(resolve_property="name") + '
                        'apoc.refactor.mergeNodes(properties:"discard", mergeRels:true)',
            'chunk_embedder': 'skipped (only adds chunk embeddings; does not affect extraction)',
            'writer': 'none (no Neo4j database)',
            'doc_concurrency': args.doc_concurrency, 'max_inflight_llm_calls': args.max_inflight,
        },
        'n_docs': len(docs),
        'n_chunks': sum(r['n_chunks'] for r in results),
        'failed_chunks': all_failures,
        'n_failed_chunks': len(all_failures),
        'wall_seconds': round(wall, 1),
        'wall_note': 'this invocation only; cached documents are not re-extracted',
        'llm_calls_this_invocation': llm.n_calls,
        'pruned_by_graph_pruning': {k: sum(r['pruned'][k] for r in results) for k in ('nodes', 'relationships', 'properties')},
        'pre_resolution': pre,
        'post_resolution': {'nodes': len(nodes), 'edges': len(edges),
                            'nodes_by_type': count(nodes, 'type'), 'edges_by_label': count(edges, 'label')},
    }
    (out / 'meta.json').write_text(json.dumps(meta, indent=2))
    log.info('done: %d docs, %d chunks, %d failed, %d nodes, %d edges, %.0fs',
             len(docs), meta['n_chunks'], len(all_failures), len(nodes), len(edges), wall)


if __name__ == '__main__':
    asyncio.run(main())
