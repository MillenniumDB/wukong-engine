"""Build a KGGen knowledge graph over the UDA-Bench NBA corpus, following the README pipeline:
generate one graph per document, aggregate them, deduplicate the aggregate.

    envs/kggen/bin/python baselines/kggen_build.py --data runs/x6-pilot-data --out runs/kggen-pilot

Decisions:
- Version: GitHub stair-lab/kg-gen at commit 6259b4c (2026-03-24), not the latest release 0.4.0
  (2025-09-30). The release's cluster() puts every remaining item of the graph in one prompt, which
  cannot hold the entities of 216 articles. The newer deduplication (semantic hashing, then k-means
  groups of 128 and one LLM call per item within its group) is built for large graphs. The env is
  the repo's own lock (envs/kggen-src at that commit, `uv sync --frozen --no-dev`): newer semhash
  releases drop the attribute KGGen reads, and every document fails.
- Schema: KGGen takes none. Its only slot is `context` ("description of data context"), which
  gets the corpus domain statement of workspace-x6-s4. At this commit generate() passes it to no
  prompt and deduplicate() marks it TODO; it is passed anyway, per the slot rule.
- Model: gpt-5.6-luna through LiteLLM/DSPy, reasoning effort low. KGGen requires temperature 1.0
  and max_tokens >= 16000 for gpt-5 family models. DSPy's response cache is disabled, so every
  call is a real call (and the pilot does not warm the full run).
- generate(): defaults otherwise: no chunk_size (the whole article per call; KGGen chunks at
  16,384 characters only on a context-length error), deduplication SEMHASH per document.
- Aggregate + deduplicate(method=FULL), the default of deduplicate(): SemHash at 0.95, then
  LLM deduplication within k-means groups. Its retrieval model is text-embedding-3-small
  (baselines/openai_embed.py), the embedder of LightRAG and GraphRAG; KGGen's own experiments use
  all-MiniLM-L6-v2 or all-mpnet-base-v2.
- Concurrency: --doc-concurrency documents at a time; the deduplication uses KGGen's own pool.
- Resumable: each document's graph is cached in <out>/docs/.

Outputs in --out: graph/nodes.jsonl, graph/edges.jsonl (untyped: KGGen nodes are strings, edges
are (subject, predicate, object)), aggregate.json (before corpus deduplication), graph.json
(after), usage.jsonl, meta.json, mapping.md.
"""
import argparse
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import metadata as md
from pathlib import Path

import litellm
from kg_gen import KGGen
from kg_gen.models import Graph
from kg_gen.steps._3_deduplicate import DeduplicateMethod

from openai_embed import OpenAIEmbedder

HERE = Path(__file__).resolve().parent.parent
KM_PATH = HERE / 'workspace-x6-s4' / 'knowledge_model.json'
TYPES = ('player', 'team', 'city', 'owner')
MODEL = 'openai/gpt-5.6-luna'
REASONING = 'low'
COMMIT = '6259b4c71523ceae75dafb4acec2eb833bef8f8e'
log = logging.getLogger('kggen_build')


def list_docs(data: Path) -> list[tuple[str, Path]]:
    docs = []
    for t in TYPES:
        for p in sorted((data / t / t).glob('*.txt'), key=lambda p: int(p.stem)):
            docs.append((f'{t}/{p.stem}', p))
    return docs


class UsageLog:
    """LiteLLM success callback: one line per LLM call, tagged with the current stage."""

    def __init__(self, path: Path):
        self.path, self.lock, self.stage, self.n = path, threading.Lock(), 'generate', 0

    def __call__(self, kwargs, response, start, end):
        u = getattr(response, 'usage', None)
        if u is None:
            return
        det = getattr(u, 'completion_tokens_details', None)
        pdet = getattr(u, 'prompt_tokens_details', None)
        rec = {'ts': time.time(), 'secs': round((end - start).total_seconds(), 2), 'stage': self.stage,
               'input': u.prompt_tokens, 'cached': getattr(pdet, 'cached_tokens', 0) or 0,
               'output': u.completion_tokens, 'reasoning': getattr(det, 'reasoning_tokens', 0) or 0}
        with self.lock, self.path.open('a') as fh:
            fh.write(json.dumps(rec) + '\n')
            self.n += 1


def write_mapping(km: dict, out: Path) -> None:
    lines = ['# Schema mapping: workspace-x6-s4 -> KGGen', '',
             '| workspace-x6-s4 | KGGen slot |', '|---|---|',
             '| extraction_config.llm.domain | `context` of generate() and deduplicate() (unused by the code at this commit) |',
             '| everything else (types, fields, relationships, annotations) | no slot |', '',
             f'context = {json.dumps(km["extraction_config"]["llm"]["domain"])}']
    (out / 'mapping.md').write_text('\n'.join(lines) + '\n')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--doc-concurrency', type=int, default=8)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    for noisy in ('httpx', 'LiteLLM', 'litellm', 'kg_gen'):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    out = args.out
    for d in ('graph', 'docs'):
        (out / d).mkdir(parents=True, exist_ok=True)
    km = json.loads(KM_PATH.read_text())
    context = km['extraction_config']['llm']['domain']
    write_mapping(km, out)

    usage = UsageLog(out / 'usage.jsonl')
    litellm.success_callback = [usage]
    kg = KGGen(model=MODEL, reasoning_effort=REASONING, temperature=1.0, max_tokens=16000,
               disable_cache=True)
    kg.retrieval_model = OpenAIEmbedder(out / 'usage.jsonl')

    docs = list_docs(args.data)
    failures = []

    def run_doc(doc_id, path):
        cfile = out / 'docs' / (doc_id.replace('/', '_') + '.json')
        if cfile.exists():
            return Graph.from_file(str(cfile))
        text = path.read_text()
        for attempt in range(3):
            try:
                g = kg.generate(input_data=text, context=context)
                g.to_file(str(cfile))
                return g
            except Exception as e:  # noqa: BLE001 - logged and retried, then counted
                log.warning('%s attempt %d failed: %s', doc_id, attempt + 1, e)
                time.sleep(5)
        failures.append(doc_id)
        return None

    t0 = time.time()
    graphs = {}
    with ThreadPoolExecutor(args.doc_concurrency) as pool:
        futs = {pool.submit(run_doc, d, p): d for d, p in docs}
        for i, f in enumerate(as_completed(futs), 1):
            graphs[futs[f]] = f.result()
            if i % 10 == 0 or i == len(docs):
                log.info('generated %d/%d documents (%.0fs)', i, len(docs), time.time() - t0)
    t_gen = time.time() - t0

    agg = kg.aggregate([graphs[d] for d, _ in docs if graphs.get(d) is not None])
    agg.to_file(str(out / 'aggregate.json'))
    log.info('aggregate: %d entities, %d edge labels, %d relations', len(agg.entities), len(agg.edges),
             len(agg.relations))
    usage.stage = 'deduplicate'
    t1 = time.time()
    final = kg.deduplicate(agg, method=DeduplicateMethod.FULL, context=context)
    t_dedup = time.time() - t1
    final.to_file(str(out / 'graph.json'))

    # as Graph.from_file does: endpoints missing from the entity set (deduplication can rename an
    # entity in a relation without listing the alias) are added as entities
    with (out / 'graph' / 'nodes.jsonl').open('w') as fh:
        for n in sorted(set(final.entities) | {x for s, _, o in final.relations for x in (s, o)}):
            fh.write(json.dumps({'id': n, 'type': '', 'name': n, 'attrs': {}}, ensure_ascii=False) + '\n')
    with (out / 'graph' / 'edges.jsonl').open('w') as fh:
        for s, p, o in sorted(final.relations):
            fh.write(json.dumps({'src': s, 'dst': o, 'label': p, 'props': {}}, ensure_ascii=False) + '\n')

    meta = {
        'tool': 'kg-gen',
        'versions': {'kg-gen': f'git {COMMIT[:7]}, env from its uv.lock', **{p: md.version(p) for p in ('dspy', 'litellm', 'openai', 'semhash')}},
        'data': str(args.data), 'knowledge_model': str(KM_PATH),
        'settings': {'model': MODEL, 'reasoning_effort': REASONING, 'temperature': 1.0, 'max_tokens': 16000,
                     'dspy_cache': False, 'context': context, 'chunk_size': None,
                     'generate_deduplication': 'SEMHASH (default)',
                     'corpus_deduplication': 'FULL (default of deduplicate): SemHash 0.95 + LLM within k-means groups',
                     'retrieval_model': 'text-embedding-3-small (baselines/openai_embed.py)',
                     'doc_concurrency': args.doc_concurrency},
        'n_docs': len(docs), 'failed_docs': failures,
        'wall_seconds': round(time.time() - t0, 1), 'wall_generate_seconds': round(t_gen, 1),
        'wall_deduplicate_seconds': round(t_dedup, 1),
        'wall_note': 'this invocation only; cached documents are not re-generated',
        'aggregate': {'entities': len(agg.entities), 'edge_labels': len(agg.edges), 'relations': len(agg.relations)},
        'final': {'entities': len(final.entities), 'edge_labels': len(final.edges), 'relations': len(final.relations)},
    }
    (out / 'meta.json').write_text(json.dumps(meta, indent=2))
    log.info('done: %s', meta['final'])


if __name__ == '__main__':
    main()
