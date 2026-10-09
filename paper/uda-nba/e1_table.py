"""E1 summary table: domain-agnostic structure statistics, with recall against gold as a control.

    envs/graphrag/bin/python e1_analysis.py && envs/graphrag/bin/python relation_vocab.py
    envs/graphrag/bin/python e1_table.py           # -> runs/e1/summary.csv, printed table

Wukong is the full schema (workspace-x6-s4) on the current engine, three runs (Wukong-r1..r3):
a cell shows the mean, with the range when the runs differ. LightRAG and GraphRAG ran once.
"""
import json

import pandas as pd

import e1_analysis as A

E1 = A.RUNS / 'e1'
R = json.loads((E1 / 'report.json').read_text())
V = json.loads((E1 / 'relation_vocab.json').read_text())
SYS = {'Wukong': (['Wukong-r1', 'Wukong-r2', 'Wukong-r3'], 'Wukong', 'Wukong'),   # (reports, vocab raw, vocab derived)
       'LightRAG': (['LightRAG'], 'LightRAG-keywords', 'LightRAG-derived'),
       'GraphRAG': (['GraphRAG'], None, 'GraphRAG-derived')}
RELATIONS = {'plays_for', 'located_in', 'owned_by', 'owns'}


def metrics(rep):
    """Numbers of one run that come from report.json and the facts/entities CSVs."""
    r = R[rep]
    f = pd.read_csv(E1 / f'{rep}_facts.csv')
    ent = pd.read_csv(E1 / f'{rep}_entities.csv')
    att, rel = f[~f.fact.isin(RELATIONS)], f[f.fact.isin(RELATIONS)]
    return {'nodes': r['nodes'], 'edges': r['edges'], 'types': r['entity_types'],
            'types_once': r['entity_types_singleton'],
            'props_per_node': r['typed_attribute_values'] / r['nodes'],
            'free_text_pct': 100 * r['nodes_with_description'] / r['nodes'],
            'entities': int(((ent.exact + ent.variants) > 0).sum()), 'entities_n': len(ent),
            'attrs': int(att.covered.sum()), 'attrs_n': len(att),
            'rels': int(rel.covered.sum()), 'rels_n': len(rel)}


def cell(values, fmt):
    lo, hi, mean = min(values), max(values), sum(values) / len(values)
    return fmt(mean) if lo == hi else f'{fmt(mean)} ({fmt(lo)}–{fmt(hi)})'


def pct(x):
    return f'{x:.0f}%' if x is not None else '–'


def num(x):
    return f'{x:,.0f}' if isinstance(x, (int, float)) else ('–' if x is None else str(x))


rows = []
for name, (reps, raw, der) in SYS.items():
    m = [metrics(rep) for rep in reps]
    col = lambda k, fmt=num: cell([x[k] for x in m], fmt)
    vr = V[raw]['raw'] if raw else {}
    vd = V[der]['raw']
    vm = V[der].get('merged_0.85', vd)
    wk = name == 'Wukong'
    back = 0.0 if wk else vd.get('edges_stored_backwards_pct')
    both = 0.0 if wk else vd.get('labels_10plus_both_directions_pct')
    rows.append({
        'system': name,
        ('Size', 'Nodes'): col('nodes'),
        ('Size', 'Edges'): col('edges'),
        ('Node vocabulary', 'Node types'): col('types'),
        ('Node vocabulary', 'Node types used once'): col('types_once'),
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
        ('Properties', 'Typed property values per node'): col('props_per_node', lambda x: f'{x:.1f}'),
        ('Properties', 'Nodes described only by free text'): col('free_text_pct', pct),
        ('Control: recall vs gold', 'Entities found'): f"{col('entities')}/{m[0]['entities_n']}",
        ('Control: recall vs gold', 'Attribute values found'): f"{col('attrs')}/{m[0]['attrs_n']}",
        ('Control: recall vs gold', 'Relations found'): f"{col('rels')}/{m[0]['rels_n']}",
    })

df = pd.DataFrame(rows).set_index('system').T
df.index = pd.MultiIndex.from_tuples(df.index)
df.to_csv(E1 / 'summary.csv')
with pd.option_context('display.max_colwidth', 40, 'display.width', 200):
    print(df.to_string())
