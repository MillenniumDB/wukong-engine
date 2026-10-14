"""Score every system's M1 answers with UDA-Bench's evaluator, the same way for all.

For each system folder in work/answers/ and each answered question: rows -> prediction CSV (common.rows_to_csv:
neutral keys back to the evaluator's columns, entity names to document ids), then the evaluator in deterministic
mode. A reply that cannot be parsed scores 0 (an empty prediction) and is counted. Writes work/scores/<system>.json
and prints macro F1 per question type and overall, with parse failures, unmatched names, and cost.
"""

import argparse
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import WORK, NameIndex, cost, evaluate, load_queries, rows_to_csv  # noqa: E402

TYPES = ('Select', 'Filter', 'Agg', 'Join', 'Mixed')


def score_system(system: str, names: NameIndex, queries: dict) -> dict:
    results = {}
    for f in sorted((WORK / 'answers' / system).glob('*.json')):
        a = json.loads(f.read_text())
        q = queries[a['uid']]
        d = WORK / 'scores' / system / f.stem
        stats = rows_to_csv(q, a.get('rows') or [], names, d / 'result.csv')
        acc = evaluate(q, d / 'result.csv', d / 'acc')
        results[a['uid']] = {'type': q['type'], 'parsed': a.get('rows') is not None, **stats,
                             'macro_f1': acc.get('macro_f1', 0.0) if 'error' not in acc else 0.0,
                             'eval_error': acc.get('error')}
    (WORK / 'scores').mkdir(exist_ok=True)
    (WORK / 'scores' / f'{system}.json').write_text(json.dumps(results, indent=1))
    return results


def summary(system: str, results: dict) -> str:
    cells = []
    for t in (*TYPES, 'all'):
        rs = [r for r in results.values() if t == 'all' or r['type'] == t]
        cells.append(f'{t} {st.mean(r["macro_f1"] for r in rs):.3f} ({len(rs)})' if rs else f'{t} -')
    unparsed = sum(not r['parsed'] for r in results.values())
    errors = sum(bool(r['eval_error']) for r in results.values())
    unmatched = sum(r['unmatched_names'] for r in results.values())
    usage = WORK / 'usage' / f'{system.split("-")[0]}.jsonl'  # one log per system (all modes)
    return (f'{system:22s} ' + ' | '.join(cells) + f' || unparsed {unparsed}, eval errors {errors}, '
            f'unmatched names {unmatched}, cost so far ${cost(usage):.2f} (all modes)')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('systems', nargs='*', help='answer folders under work/answers (default: all)')
    args = ap.parse_args()
    queries = {q['uid']: q for q in load_queries()}
    names = NameIndex()
    systems = args.systems or sorted(p.name for p in (WORK / 'answers').iterdir() if p.is_dir())
    for s in systems:
        print(summary(s, score_system(s, names, queries)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
