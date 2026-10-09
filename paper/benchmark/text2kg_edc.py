"""Run EDC (Extract-Define-Canonicalize) in target-schema mode on the Text2KGBench test sentences (X1b).

EDC (clear-nus/edc, EMNLP 2024) extracts open triples, writes a definition for each relation, and canonicalizes
each relation onto a provided target schema: it retrieves the closest schema relations by embedding similarity
and lets the LLM pick one, or drops the triple. Every output relation is therefore in the ontology. Setup:

    - target schema: one CSV per ontology (`<onto>_schema.csv` in --inputs), each relation with its Wikidata
      property description plus its subject and object types; no schema enrichment, no refinement round;
    - LLM: the same model and reasoning effort as WUKONG, for every stage (patched to the Responses API, with
      bounded retries and token accounting: edc-luna.patch);
    - embedder: a small sentence-transformers model instead of the paper's 7B e5-mistral (not practical without a
      GPU); the paper's fine-tuned schema retriever is not used (it was trained on TekGen, the source of the test
      sentences);
    - few-shot examples: EDC's own Wiki-NRE examples.

EDC makes its calls one after another, so each ontology is split into shards run as parallel processes. Writes,
under --out:

    - `llm/ont_<onto>_llm_responses.jsonl`: `{"id", "triples"}`, relations with spaces replaced by underscores
      (score with text2kg_eval.py --sys-pattern 'ont_$$onto$$_llm_responses.jsonl');
    - `runs/<onto>.json`: setup, shards, failed shards, LLM calls and tokens, wall clock;
    - `edc/<onto>/shard_<n>/`: EDC's own output per shard (result at each stage, canonical triples).

A shard whose output exists is skipped, so an interrupted run resumes.

Example:
    OPENAI_API_KEY=... edc-venv/bin/python paper/benchmark/text2kg_edc.py --edc ../baselines/edc \
        --inputs ../baselines/edc-inputs --out paper/benchmark/results-x1-edc-r1
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ONTOLOGIES = ('1_movie', '2_music', '3_sport', '4_book', '5_military', '6_computer', '7_space', '8_politics',
              '9_nature', '10_culture')
FEW_SHOT = 'wiki-nre'


def run_shard(args: argparse.Namespace, onto: str, index: int, sentences: list[str]) -> tuple[int, list | None, dict]:
    """Run EDC on one shard of sentences.

    Returns:
        The shard index, its canonical triples per sentence (None if the shard failed), and its usage.
    """
    shard_dir = (args.out / 'edc' / onto / f'shard_{index:03d}').resolve()
    result = shard_dir / 'out' / f'iter{1 if args.refine else 0}' / 'canon_kg.txt'
    usage_path = shard_dir / 'usage.json'
    if not result.exists():
        shard_dir.mkdir(parents=True, exist_ok=True)
        (shard_dir / 'input.txt').write_text(''.join(s + '\n' for s in sentences))
        if (shard_dir / 'out').exists():  # EDC refuses an existing output directory: clear a failed attempt
            subprocess.run(['rm', '-rf', str(shard_dir / 'out')], check=True)  # noqa: S603, S607
        edc = args.edc.resolve()
        command = [
            sys.executable, 'run.py',
            '--oie_llm', args.model, '--sd_llm', args.model, '--sc_llm', args.model,
            '--oie_few_shot_example_file_path', f'./few_shot_examples/{FEW_SHOT}/oie_few_shot_examples.txt',
            '--sd_few_shot_example_file_path', f'./few_shot_examples/{FEW_SHOT}/sd_few_shot_examples.txt',
            '--sc_embedder', args.embedder,
            '--input_text_file_path', str(shard_dir / 'input.txt'),
            '--target_schema_path', str((args.inputs / f'{onto}_schema.csv').resolve()),
            '--output_dir', str(shard_dir / 'out'),
        ]
        if args.refine:  # EDC+R: one refinement round, with schema relations retrieved as hints for re-extraction
            command += [
                '--refinement_iterations', '1', '--ee_llm', args.model, '--sr_embedder', args.embedder,
                '--oie_refine_few_shot_example_file_path', f'./few_shot_examples/{FEW_SHOT}/oie_few_shot_refine_examples.txt',
                '--ee_few_shot_example_file_path', f'./few_shot_examples/{FEW_SHOT}/ee_few_shot_examples.txt',
            ]
        env = {**os.environ, 'EDC_USAGE_PATH': str(usage_path), 'EDC_REASONING_EFFORT': args.effort,
               'TOKENIZERS_PARALLELISM': 'false'}
        with (shard_dir / 'log.txt').open('w') as log:
            subprocess.run(command, cwd=edc, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)  # noqa: S603
    if not result.exists():
        return index, None, {}
    lines = result.read_text().split('\n')
    triples = [ast.literal_eval(line) if line.strip() else [] for line in lines[:len(sentences)]]
    triples += [[] for _ in range(len(sentences) - len(triples))]
    usage = json.loads(usage_path.read_text()) if usage_path.exists() else {}
    return index, triples, usage


def submit_ontology(args: argparse.Namespace, onto: str, pool: ThreadPoolExecutor) -> dict | None:
    """Submit every shard of one ontology to the shared pool.

    Returns:
        What assemble_ontology needs, or None if the ontology is already done.
    """
    out_file = args.out / 'llm' / f'ont_{onto}_llm_responses.jsonl'
    if out_file.exists():
        print(f'{onto:12s} already done -> {out_file}')
        return None
    sentences = (args.inputs / f'{onto}_sentences.txt').read_text().splitlines()
    ids = json.loads((args.inputs / f'{onto}_ids.json').read_text())
    assert len(sentences) == len(ids), onto
    shards = [sentences[i:i + args.shard_size] for i in range(0, len(sentences), args.shard_size)]
    futures = [pool.submit(run_shard, args, onto, index, shard) for index, shard in enumerate(shards)]
    return {'onto': onto, 'sentences': sentences, 'ids': ids, 'shards': shards, 'futures': futures,
            'out_file': out_file, 'started': time.monotonic()}


def assemble_ontology(args: argparse.Namespace, job: dict) -> bool:
    """Wait for one ontology's shards, then write its responses and run record."""
    onto, sentences, ids, shards, out_file = job['onto'], job['sentences'], job['ids'], job['shards'], job['out_file']
    results = sorted(future.result() for future in job['futures'])
    seconds = round(time.monotonic() - job['started'])

    failed = [index for index, triples, _ in results if triples is None]
    usage: dict[str, int] = {}
    for _, _, u in results:
        for key, value in u.items():
            usage[key] = usage.get(key, 0) + value
    record = {
        'ontology': onto,
        'system': 'EDC+R (target schema, one refinement round)' if args.refine else 'EDC (target schema, no refinement)',
        'recorded_at': datetime.now(UTC).isoformat(timespec='seconds'),
        'model': args.model,
        'reasoning_effort': args.effort,
        'embedder': args.embedder,
        'few_shot_examples': FEW_SHOT,
        'sentences': len(sentences),
        'shards': len(shards),
        'failed_shards': failed,
        'usage': usage,
        'seconds': seconds,
    }
    (args.out / 'runs').mkdir(parents=True, exist_ok=True)
    if failed:
        (args.out / 'runs' / f'{onto}.json').write_text(json.dumps(record, indent=2) + '\n')
        print(f'{onto:12s} shards failed: {failed}; see edc/{onto}/shard_*/log.txt; re-run to retry', file=sys.stderr)
        return False
    per_sentence = [t for _, triples, _ in results for t in triples]
    rows = [
        {'id': sid, 'triples': [[str(s).strip(), re.sub(r'\s+', '_', str(p).strip()), str(o).strip()]
                                for s, p, o in (t for t in triplets if t and len(t) == 3)]}
        for sid, triplets in zip(ids, per_sentence, strict=True)
    ]
    record['with_triples'] = sum(bool(row['triples']) for row in rows)
    record['triples'] = sum(len(row['triples']) for row in rows)
    (args.out / 'runs' / f'{onto}.json').write_text(json.dumps(record, indent=2) + '\n')
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    print(f'{onto:12s} sentences={len(sentences)} triples={record["triples"]} calls={usage.get("calls", 0)} '
          f'seconds={seconds}', flush=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--edc', type=Path, required=True, help='Patched EDC checkout')
    parser.add_argument('--inputs', type=Path, required=True, help='Schemas, sentences and ids per ontology')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--onto', action='append', choices=ONTOLOGIES)
    parser.add_argument('--model', default='gpt-5.6-luna')
    parser.add_argument('--effort', default='low')
    parser.add_argument('--embedder', default='BAAI/bge-small-en-v1.5')
    parser.add_argument('--refine', action='store_true', help='EDC+R: one refinement round')
    parser.add_argument('--shard-size', type=int, default=100)
    parser.add_argument('--processes', type=int, default=16)
    parser.add_argument('--limit', type=int, help='Only the first N sentences of each ontology (pilot)')
    args = parser.parse_args()
    if args.limit:  # a pilot writes its own inputs, cut to the first N sentences
        cut = args.out / 'inputs'
        cut.mkdir(parents=True, exist_ok=True)
        for onto in args.onto or ONTOLOGIES:
            (cut / f'{onto}_schema.csv').write_text((args.inputs / f'{onto}_schema.csv').read_text())
            lines = (args.inputs / f'{onto}_sentences.txt').read_text().splitlines()[:args.limit]
            (cut / f'{onto}_sentences.txt').write_text(''.join(line + '\n' for line in lines))
            ids = json.loads((args.inputs / f'{onto}_ids.json').read_text())[:args.limit]
            (cut / f'{onto}_ids.json').write_text(json.dumps(ids))
        args.inputs = cut
    with ThreadPoolExecutor(max_workers=args.processes) as pool:
        jobs = [submit_ontology(args, onto, pool) for onto in (args.onto or ONTOLOGIES)]  # all shards share the pool
        ok = [assemble_ontology(args, job) for job in jobs if job is not None]
    return 0 if all(ok) else 1


if __name__ == '__main__':
    sys.exit(main())
