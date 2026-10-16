"""Check the M1 scoring path with an oracle: the evaluator's own gold answers, in the format systems produce.

For each query, the evaluator is first run on an empty prediction to obtain its gold result (gold_result.csv,
executed by UDA-Bench's own GT runner). Its rows become {"col<i>", "name_<table>"} objects exactly as a system must
answer (the names looked up from the gold tables by id), and they go through the same conversion (names -> document
ids) and the same evaluator. Scores near 1.0 mean the harness loses nothing on its own; what it loses is reported.
Queries whose gold SQL the evaluator itself cannot run are reported as unscorable (for every system).
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import ENTITY, GOLD_DIR, WORK, NameIndex, evaluate, key_tables, load_queries, rows_to_csv  # noqa: E402


def gold_names() -> dict[str, dict[int, str]]:
    out = {}
    for t, (col, _) in ENTITY.items():
        df = pd.read_csv(GOLD_DIR / f'{t}.csv', dtype=str, keep_default_na=False)
        out[t] = {int(r['ID']): r[col] for _, r in df.iterrows()}
    return out


def main() -> int:
    names, gn = NameIndex(), gold_names()
    out = WORK / 'oracle'
    results = {}
    for q in load_queries():
        safe = q['uid'].replace('#', '_')
        empty = out / safe / 'empty.csv'
        rows_to_csv(q, [], names, empty)
        first = evaluate(q, empty, out / safe / 'gold')
        gold_csv = out / safe / 'gold' / 'gold_result.csv'
        if 'error' in first or not gold_csv.exists() or not q.get('scorable', True):
            results[q['uid']] = {'type': q['type'], 'unscorable': (first.get('error') or 'no gold')[-300:]}
            continue
        gold = pd.read_csv(gold_csv, dtype=str, keep_default_na=False)
        id_cols = ['id'] if q['primary_keys'] == ['id'] else [k for k in q['primary_keys'] if k.endswith('.id')]
        rows = []
        for _, r in gold.iterrows():
            row = {f'col{i + 1}': (r[c] if c in gold.columns and r[c] != '' else None) for i, c in enumerate(q['pred_columns'] or q['output_columns'])}
            for col, t in zip(id_cols, key_tables(q), strict=False):
                v = r.get(col, '')
                row[f'name_{t}'] = gn[t].get(int(float(v))) if v not in ('', None) else None
            rows.append(row)
        stats = rows_to_csv(q, rows, names, out / safe / 'result.csv')
        acc = evaluate(q, out / safe / 'result.csv', out / safe / 'acc')
        results[q['uid']] = {'type': q['type'], 'gold_rows': len(gold), **stats, 'macro_f1': acc.get('macro_f1'),
                             'error': acc.get('error')}
    (out / 'summary.json').write_text(json.dumps(results, indent=1))
    by = {}
    for r in results.values():
        by.setdefault(r['type'], []).append(r)
    for t, rs in by.items():
        f1 = [r['macro_f1'] for r in rs if r.get('macro_f1') is not None]
        print(f"{t:7s} queries {len(rs):3d} | unscorable {sum(1 for r in rs if 'unscorable' in r):2d} | "
              f"empty gold {sum(1 for r in rs if r.get('gold_rows') == 0):2d} | mean macro F1 {sum(f1) / max(1, len(f1)):.3f} "
              f"over {len(f1)} | unmatched names {sum(r.get('unmatched_names', 0) for r in rs)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
