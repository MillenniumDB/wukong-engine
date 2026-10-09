"""E1 summary table: domain-agnostic structure statistics, with recall against gold as a control.

    envs/graphrag/bin/python e1_analysis.py && envs/graphrag/bin/python relation_vocab.py
    envs/graphrag/bin/python e1_table.py           # -> runs/e1/summary.csv, printed table

Wukong is the clean-schema run (Wukong-v1).
"""
import json

import pandas as pd

import e1_analysis as A

E1 = A.RUNS / 'e1'
R = json.loads((E1 / 'report.json').read_text())
V = json.loads((E1 / 'relation_vocab.json').read_text())
SYS = {'Wukong': ('Wukong-v1', 'Wukong', 'Wukong'),          # (report, vocab raw, vocab derived)
       'LightRAG': ('LightRAG', 'LightRAG-keywords', 'LightRAG-derived'),
       'GraphRAG': ('GraphRAG', None, 'GraphRAG-derived')}
RELATIONS = {'plays_for', 'located_in', 'owned_by', 'owns'}


def pct(x):
    return f'{x:.0f}%' if x is not None else '–'


def num(x):
    return f'{x:,}' if isinstance(x, int) else ('–' if x is None else str(x))


rows = []
for name, (rep, raw, der) in SYS.items():
    r = R[rep]
    vr = V[raw]['raw'] if raw else {}
    vd = V[der]['raw'] if name != 'Wukong' else V['Wukong']['raw']
    vm = V[der].get('merged_0.85', {}) if name != 'Wukong' else V['Wukong']['raw']
    f = pd.read_csv(E1 / f'{rep}_facts.csv')
    ent = pd.read_csv(E1 / f'{rep}_entities.csv')
    att, rel = f[~f.fact.isin(RELATIONS)], f[f.fact.isin(RELATIONS)]
    typed = r['typed_attribute_values']
    back = 0.0 if name == 'Wukong' else vd.get('edges_stored_backwards_pct')
    both = 0.0 if name == 'Wukong' else vd.get('labels_10plus_both_directions_pct')
    rows.append({
        'system': name,
        ('Size', 'Nodes'): num(r['nodes']),
        ('Size', 'Edges'): num(r['edges']),
        ('Node vocabulary', 'Node types'): num(r['entity_types']),
        ('Node vocabulary', 'Node types used once'): num(r['entity_types_singleton']),
        ('Relation vocabulary (own labels)', 'Labels'): num(vr.get('labels', 0)) if raw else '0 (edges unlabeled)',
        ('Relation vocabulary (own labels)', 'Labels used once'): pct(vr.get('singleton_labels_pct')) if raw else '–',
        ('Relation vocabulary (own labels)', 'Labels to cover 90% of edges'): num(vr.get('labels_cover_90')) if raw else '–',
        ('Relation vocabulary (derived predicates)', 'Labels'): num(vd['labels']),
        ('Relation vocabulary (derived predicates)', 'Labels used once'): pct(vd['singleton_labels_pct']),
        ('Relation vocabulary (derived predicates)', 'Labels to cover 50% / 90% of edges'): f"{num(vd['labels_cover_50'])} / {num(vd['labels_cover_90'])}",
        ('Relation vocabulary (derived predicates)', 'Labels per node-type pair (mean)'): num(vd['labels_per_type_pair_mean']),
        ('Relation vocabulary (synonyms merged, cos ≥ 0.85)', 'Labels'): num(vm['labels']),
        ('Relation vocabulary (synonyms merged, cos ≥ 0.85)', 'Labels to cover 90% of edges'): num(vm['labels_cover_90']),
        ('Direction', 'Edges stored against their relation'): pct(back) + (' (undirected)' if name == 'LightRAG' else ''),
        ('Direction', 'Frequent labels used in both directions'): pct(both),
        ('Properties', 'Typed property values per node'): f"{typed / r['nodes']:.1f}",
        ('Properties', 'Nodes described only by free text'): pct(100 * r['nodes_with_description'] / r['nodes']),
        ('Control: recall vs gold', 'Entities found'): f"{int(((ent.exact + ent.variants) > 0).sum())}/{len(ent)}",
        ('Control: recall vs gold', 'Attribute values found'): f"{int(att.covered.sum())}/{len(att)}",
        ('Control: recall vs gold', 'Relations found'): f"{int(rel.covered.sum())}/{len(rel)}",
    })

df = pd.DataFrame(rows).set_index('system').T
df.index = pd.MultiIndex.from_tuples(df.index)
df.to_csv(E1 / 'summary.csv')
with pd.option_context('display.max_colwidth', 40, 'display.width', 200):
    print(df.to_string())
