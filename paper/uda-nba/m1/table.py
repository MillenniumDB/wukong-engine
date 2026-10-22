"""M1 results table from work/scores/*.json (run score.py first): macro F1 per question type and overall, for
every system, plus "LightRAG (best mode)", which takes, per question type, the mode with the highest mean F1. That
choice is made with the gold answers, so it is an upper bound in LightRAG's favour, not a configuration LightRAG
could pick by itself. Systems run several times (<name>_r1, _r2, ...) are reported as one row: the mean over
runs, with half the range of the overall score as +-. Prints Markdown and writes work/m1_table.tex (a tabular body).
"""

import json
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import WORK, cost  # noqa: E402

TYPES = ('Select', 'Filter', 'Agg', 'Join', 'Mixed')
LABELS = {'floor': 'LLM alone (floor)', 'wukong_s4': 'Wukong + Cypher agent', 'graphrag-local': 'GraphRAG local',
          'lightrag-local': 'LightRAG local', 'lightrag-global': 'LightRAG global',
          'lightrag-hybrid': 'LightRAG hybrid', 'lightrag-mix': 'LightRAG mix',
          'neo4j_s4': 'Neo4j-GraphRAG + Cypher agent', 'llamaindex_s4': 'LlamaIndex + Cypher agent',
          'ontogpt_s4': 'OntoGPT + Cypher agent'}
# Graphs built from the NBA schema (s4), three runs each; the RAG systems and the floor ran once
ORDER = ('floor', 'lightrag-local', 'lightrag-global', 'lightrag-hybrid', 'lightrag-mix', 'lightrag-best',
         'graphrag-local', 'neo4j_s4', 'llamaindex_s4', 'ontogpt_s4', 'wukong_s4')


def main() -> int:
    scores = {p.stem: json.loads(p.read_text()) for p in (WORK / 'scores').glob('*.json')}
    rows = {}
    for s, res in scores.items():
        by = {t: [r['macro_f1'] for r in res.values() if r['type'] == t] for t in TYPES}
        rows[s] = {t: (st.mean(v) if v else None) for t, v in by.items()}
        rows[s]['all'] = st.mean(r['macro_f1'] for r in res.values())
        rows[s]['n'] = len(res)
    runs = {}
    for s in list(rows):
        m = re.fullmatch(r'(.+)_r\d+', s)
        if m:
            runs.setdefault(m.group(1), []).append(rows[s])
    for g, rs in runs.items():
        rows[g] = {k: (st.mean(r[k] for r in rs) if rs[0][k] is not None else None) for k in (*TYPES, 'all')}
        rows[g]['n'] = rs[0]['n']
        rows[g]['runs'] = len(rs)
        rows[g]['half_range'] = (max(r['all'] for r in rs) - min(r['all'] for r in rs)) / 2
    modes = [s for s in rows if s.startswith('lightrag-')]
    if modes:
        best = {t: max(modes, key=lambda m: rows[m][t] or 0) for t in TYPES}
        n = {t: sum(r['type'] == t for r in scores[modes[0]].values()) for t in TYPES}
        rows['lightrag-best'] = {t: rows[best[t]][t] for t in TYPES}
        rows['lightrag-best']['all'] = sum(rows['lightrag-best'][t] * n[t] for t in TYPES) / sum(n.values())
        rows['lightrag-best']['n'] = sum(n.values())
        LABELS['lightrag-best'] = 'LightRAG best mode per type' + ' (' + ', '.join(f'{t}: {best[t].split("-")[1]}' for t in TYPES) + ')'
    usage = {p.stem: cost(p) for p in (WORK / 'usage').glob('*.jsonl')}
    fmt = lambda v: '-' if v is None else f'{v:.2f}'  # noqa: E731
    print('| System | ' + ' | '.join(TYPES) + ' | All | n | runs |')
    print('|---' * (len(TYPES) + 4) + '|')
    tex = []
    for s in [s for s in ORDER if s in rows]:
        r = rows[s]
        pm = f' ±{r["half_range"]:.2f}' if r.get('runs', 1) > 1 else ''
        print(f'| {LABELS[s]} | ' + ' | '.join(fmt(r[t]) for t in TYPES) + f' | **{fmt(r["all"])}**{pm} | {r["n"]} | '
              f'{r.get("runs", 1)} |')
        label = LABELS[s].split(' (')[0] if s == 'lightrag-best' else LABELS[s]
        tpm = f'\\textsuperscript{{$\\pm${r["half_range"]:.2f}}}' if r.get('runs', 1) > 1 else ''
        tex.append(f'{label} & ' + ' & '.join(fmt(r[t]) for t in TYPES) + f' & {fmt(r["all"])}{tpm} \\\\')
    print('\nSpend by log (USD): ' + ', '.join(f'{k} {v:.2f}' for k, v in sorted(usage.items())) +
          f'; total {sum(usage.values()):.2f}')
    (WORK / 'm1_table.tex').write_text('\n'.join(tex) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
