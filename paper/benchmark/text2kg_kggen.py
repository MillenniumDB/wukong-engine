"""Run KGGen on the Text2KGBench test sentences (evidence, outside the paper's main comparison).

KGGen (stair-lab/kg-gen) extracts open triples with free-text predicates and has no schema constraint; its only
way to steer extraction is a free-text `context` hint. Two variants:

    - `plain`: KGGen as its authors use it, no context;
    - `context`: the ontology's relations (with their subject and object types) passed as the context hint, the same
      information the benchmark's own prompt gives.

Each sentence is one KGGen call (entities, then relations: two LLM calls), with deduplication off (one sentence at a
time) and the dspy cache disabled, so repetitions are independent. Run with KGGen's own environment (built from its
uv.lock). Writes, under --out:

    - `llm/ont_<onto>_llm_responses.jsonl`: `{"id", "triples"}`, predicates with spaces replaced by underscores
      (score with text2kg_eval.py --sys-pattern 'ont_$$onto$$_llm_responses.jsonl');
    - `runs/<onto>.json`: model, variant, context, calls, failed sentences, tokens, wall clock, and the predicate
      vocabulary: distinct predicates, and how many of them (and of the triples) use an ontology relation.

Example:
    OPENAI_API_KEY=... kggen-venv/bin/python paper/benchmark/text2kg_kggen.py \
        --benchmark ../benchmarks/Text2KGBench --variant plain --out paper/benchmark/results-kggen-plain-r1
"""

import argparse
import collections
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from kg_gen import KGGen

ONTOLOGIES = ('1_movie', '2_music', '3_sport', '4_book', '5_military', '6_computer', '7_space', '8_politics',
              '9_nature', '10_culture')
ATTEMPTS = 4
_local = threading.local()


def ontology_context(ontology: dict) -> str:
    """Describe the ontology's relations for KGGen's context hint.

    Args:
        ontology: Text2KGBench ontology with concepts and relations.

    Returns:
        A context string listing each relation with its subject and object types.
    """
    concept = {c['qid']: c['label'] for c in ontology['concepts']}
    relations = '; '.join(
        f"{r['label'].strip()} ({concept.get(r['domain'], 'any')} -> {concept.get(r['range'], 'value')})"
        for r in ontology['relations']
    )
    return (f'Sentences from Wikipedia about the domain "{ontology["title"]}". Use only these relations, written '
            f'exactly as given: {relations}.')


def _client(args: argparse.Namespace) -> KGGen:
    """One KGGen per worker thread, so that no LM state is shared between threads."""
    if not hasattr(_local, 'kg'):
        _local.kg = KGGen(model=f'openai/{args.model}', temperature=1.0, max_tokens=16000, reasoning_effort=args.effort,
                          api_key=os.environ['OPENAI_API_KEY'], disable_cache=True)
    return _local.kg


def _extract(args: argparse.Namespace, sentence: str, context: str) -> tuple[list | None, list[dict]]:
    """Run KGGen on one sentence, retrying with backoff.

    Returns:
        The (subject, predicate, object) triples, or None if every attempt failed, and the usage of the calls made.
    """
    kg = _client(args)
    for attempt in range(ATTEMPTS):
        start = len(kg.lm.history)
        try:
            graph = kg.generate(input_data=sentence, context=context, deduplication_method=None)
            usage = [h.get('usage') or {} for h in kg.lm.history[start:]]
            return sorted(graph.relations), usage
        except Exception as error:  # noqa: BLE001
            if attempt == ATTEMPTS - 1:
                print(f'    gave up: {type(error).__name__}: {error}', file=sys.stderr)
                return None, []
            time.sleep(5 * 2 ** attempt)
    return None, []


def _tokens(usages: list[dict]) -> dict[str, int]:
    """Sum Responses API usage entries (dicts or objects)."""
    def get(obj, key):
        return (obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)) if obj is not None else None
    total = collections.Counter()
    for u in usages:
        total['calls'] += 1
        total['input_tokens'] += get(u, 'input_tokens') or 0
        total['cached_tokens'] += get(get(u, 'input_tokens_details'), 'cached_tokens') or 0
        total['output_tokens'] += get(u, 'output_tokens') or 0
        total['reasoning_tokens'] += get(get(u, 'output_tokens_details'), 'reasoning_tokens') or 0
    return dict(total)


def run_ontology(args: argparse.Namespace, onto: str) -> bool:
    """Run every test sentence of one ontology; return whether all sentences succeeded."""
    out_file = args.out / 'llm' / f'ont_{onto}_llm_responses.jsonl'
    if out_file.exists():
        print(f'{onto:12s} already done -> {out_file}')
        return True
    dataset = args.benchmark / 'data' / args.dataset
    test = [json.loads(line) for line in (dataset / 'test' / f'ont_{onto}_test.jsonl').read_text().splitlines() if line.strip()]
    ontology = json.loads((dataset / 'ontologies' / f'{onto}_ontology.json').read_text())
    context = ontology_context(ontology) if args.variant == 'context' else ''
    ontology_relations = {re.sub(r'(_|\s+)', '', r['label']).lower() for r in ontology['relations']}

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda row: _extract(args, row['sent'], context), test))
    seconds = round(time.monotonic() - started)

    failed = sum(triples is None for triples, _ in results)
    rows = [{'id': row['id'], 'triples': [[s, re.sub(r'\s+', '_', p.strip()), o] for s, p, o in (triples or [])]}
            for row, (triples, _) in zip(test, results, strict=True)]
    predicates = collections.Counter(p for row in rows for _, p, _ in row['triples'])
    in_ontology = {p for p in predicates if re.sub(r'(_|\s+)', '', p).lower() in ontology_relations}
    record = {
        'ontology': onto,
        'system': f'KGGen ({args.variant})',
        'recorded_at': datetime.now(UTC).isoformat(timespec='seconds'),
        'model': args.model,
        'reasoning_effort': args.effort,
        'context': context,
        'sentences': len(test),
        'failed': failed,
        'with_triples': sum(bool(row['triples']) for row in rows),
        'triples': sum(predicates.values()),
        'distinct_predicates': len(predicates),
        'distinct_predicates_in_ontology': len(in_ontology),
        'triples_with_ontology_predicate': sum(predicates[p] for p in in_ontology),
        'top_predicates': predicates.most_common(15),
        'usage': _tokens([u for _, usages in results for u in usages]),
        'seconds': seconds,
    }
    (args.out / 'runs').mkdir(parents=True, exist_ok=True)
    (args.out / 'runs' / f'{onto}.json').write_text(json.dumps(record, indent=2) + '\n')
    if failed:
        print(f'{onto:12s} {failed} sentences failed; responses not written, re-run to retry', file=sys.stderr)
        return False
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    print(f'{onto:12s} sentences={len(test)} triples={record["triples"]} predicates={len(predicates)} '
          f'(in ontology: {len(in_ontology)}) seconds={seconds}', flush=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--benchmark', type=Path, required=True)
    parser.add_argument('--dataset', default='wikidata_tekgen')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--variant', choices=('plain', 'context'), required=True)
    parser.add_argument('--onto', action='append', choices=ONTOLOGIES)
    parser.add_argument('--model', default='gpt-5.6-luna')
    parser.add_argument('--effort', default='low')
    parser.add_argument('--concurrency', type=int, default=15)
    args = parser.parse_args()
    args.benchmark = args.benchmark.resolve()
    ok = [run_ontology(args, onto) for onto in (args.onto or ONTOLOGIES)]
    return 0 if all(ok) else 1


if __name__ == '__main__':
    sys.exit(main())
