"""X6 / E3, coupling ablation: score the Wukong runs of workspace-x6-s0..s4 against the gold tables.

    envs/graphrag/bin/python x6_analysis.py            # -> runs/x6/{runs.csv,summary.csv}

Per run: cost, graph size, and extraction quality on the 216 subject entities (matching as in
e1_analysis.py). An attribute value is scored twice:
  exact    the typed field holds the gold value in the gold's form (as in E1): the value can be
           compared and filtered in a query as it is
  lenient  the field holds the gold value in any form ("December 30, 1984" for 1984/12/30,
           "third pick" for 3, "power forward" for Frontcourt): the value was extracted, but
           may need cleaning before it can be queried
Wrong values are fields that are filled but not leniently equal to the gold value.
Relations are scored by edge type between the matched entities; a player's current team also
needs tenure "latest", and its precision counts every team marked "latest" for the gold players
(marking every team as latest finds every current team). The schema-based baselines
(baselines/*_build.py) are scored the same way. Summary: mean and min-max over the repetitions.
"""
import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from dateutil import parser as dateparser

import e1_analysis as A

VARIANTS = ['s0', 's1', 's2', 's3', 's4', 's5']
NAMES = {'s0': 'core', 's1': '+bindings', 's2': '+guidance', 's3': '+validation', 's4': '+identity (full)', 's5': '+current_team'}
# runs during which the Mac slept (lid closed, 14:25-14:52 on 2026-10-09, pmset log): extraction
# resumed unharmed, but their wall time is not a measurement
SLEPT = {'x6-s2-r2', 'x6-s3-r2', 'x6-s4-r2', 'x6-s5-r2'}
WORDS = {w: i for i, w in enumerate(A.NUMBER_WORDS)} | {w: i for i, w in enumerate(A.ORDINALS) if w}
FIELD = {'championships': 'championships'}  # gold column -> Wukong field, where names differ


def lenient_num(s):
    s = str(s).lower().replace(',', '')
    m = re.search(r'\d+(?:\.\d+)?', s)
    if m:
        return float(m.group())
    for w, i in WORDS.items():
        if re.search(rf'\b{w}\b', s):
            return float(i)
    if re.search(r'\bnone\b|\bno\b|\bnever\b', s):
        return 0.0
    return None


def lenient_equal(gold, got, field):
    if got is None or str(got).strip() == '':
        return False
    g = str(gold).strip()
    if re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}', g):
        try:
            d = dateparser.parse(str(got), default=None, fuzzy=True)
        except (ValueError, OverflowError, TypeError):
            return False
        return d is not None and (d.year, d.month, d.day) == tuple(int(x) for x in g.split('/'))
    if field == 'position':
        return re.search(A.POSITION.get(A.norm(g), re.escape(g)), str(got), re.I) is not None
    gn = A.num(g)
    if gn is not None:
        v = lenient_num(got)
        return v is not None and any(abs(gn - v * u) <= 0.01 * max(abs(gn), 1) for u in A.UNITS.get(field, (1,)))
    a, b = A.norm(g), A.norm(got)
    return bool(a and b) and (a in b or b in a)


def score_run(run, gold, load=A.load_wukong, usage=A.wukong_usage):
    nodes, edges, _ = load(run)
    m = A.Matcher('Wukong', nodes)  # typed graph: nodes matched by type
    adj = defaultdict(list)
    for e in edges:
        adj[e['src']].append(e)
        adj[e['dst']].append(e)
    matched = {(e['kind'], e['id']): set().union(*m.match(e)) for e in gold}
    out = Counter()
    for e in gold:
        ids = matched[(e['kind'], e['id'])]
        out['entities'] += 1
        out['entities_found'] += bool(ids)
        out['entities_split'] += len(ids) > 1
        for k, v in e['attrs'].items():
            if A.empty(v):
                continue
            if k == 'own_year':
                got = [x['props'].get('since_year') for i in ids for x in adj[i] if x['label'] == 'Owns']
            else:
                got = [nodes[i]['attrs'].get(FIELD.get(k, k)) for i in ids]
            got = [g for g in got if g]
            out['attr_gold'] += 1
            out['attr_filled'] += bool(got)
            out['attr_exact'] += any(A.value_equal(v, g, field=k) for g in got)
            ok = any(lenient_equal(v, g, k) for g in got)
            out['attr_lenient'] += ok
            out['attr_wrong'] += bool(got) and not ok
    names = {(e['kind'], n): e for e in gold for n in e['names']}
    target = {'plays_for': 'team', 'located_in': 'city', 'owned_by': 'owner', 'owns': 'team'}
    label = {'plays_for': 'PlaysFor', 'located_in': 'LocatedIn', 'owned_by': 'Owns', 'owns': 'Owns'}
    for e in gold:
        src = matched[(e['kind'], e['id'])]
        for r, ts in e['rels'].items():
            for t in ts:
                te = names.get((target[r], A.norm(t)))
                if not t or te is None:  # only relations between gold entities (NBA teams)
                    continue
                dst = matched[(target[r], te['id'])]
                hits = [x for i in src for x in adj[i] if x['label'] == label[r]
                        and (x['src'] in dst or x['dst'] in dst)]
                out['rel_gold'] += 1
                out['rel_found'] += bool(hits)
                if r == 'plays_for':
                    out['current_team_gold'] += 1
                    out['current_team_found'] += any(x['props'].get('tenure') == 'latest' for x in hits)
                    # precision: every team marked latest for this player, right or wrong
                    marked = {x['dst'] if x['src'] in src else x['src'] for i in src for x in adj[i]
                              if x['label'] == 'PlaysFor' and x['props'].get('tenure') == 'latest'}
                    out['current_team_marked'] += len(marked)
                    out['current_team_marked_right'] += len(marked & dst)
                    # s5: the current team as a document-level Player field (a team name)
                    values = {A.norm(nodes[i]['attrs']['current_team']) for i in src
                              if nodes[i]['attrs'].get('current_team')}
                    out['current_team_field_marked'] += len(values)
                    out['current_team_field_found'] += bool(values & set(te['names']))
    out['current_team_precision'] = round(100 * out['current_team_marked_right'] / out['current_team_marked'], 1) \
        if out['current_team_marked'] else None
    out['current_team_field_precision'] = round(
        100 * out['current_team_field_found'] / out['current_team_field_marked'], 1) \
        if out['current_team_field_marked'] else None
    types = Counter(n['type'] for n in nodes.values())
    labels = Counter(e['label'] for e in edges)
    u = usage(run)
    if run in SLEPT:
        u['wall_min'] = None
    row = {'run': run, 'calls': u.get('calls'), 'input_M': round(u.get('input', 0) / 1e6, 2),
           'output_M': round((u.get('output', 0) + u.get('reasoning', 0)) / 1e6, 2), 'wall_min': u.get('wall_min'),
           'nodes': len(nodes), 'edges': len(edges),
           **{f'n_{t}': types[t] for t in ('Player', 'Team', 'City', 'Owner')},
           **{f'e_{t}': labels[t] for t in ('PlaysFor', 'LocatedIn', 'Owns')}, **out}
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=A.RUNS / 'x6')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    gold = A.load_gold()
    rows = []
    for v in VARIANTS:
        for d in sorted(A.RUNS.glob(f'x6-{v}-r*')):
            if (d / 'exports/neo4j/relationships').is_dir():
                rows.append({'variant': v, **score_run(d.name, gold)})
    # schema-based baselines (baselines/*_build.py), one run each, same scoring
    for name, run in A.BASELINES.items():
        if (A.RUNS / run / 'graph/edges.jsonl').exists() and (A.RUNS / run / 'meta.json').exists():
            rows.append({'variant': name, **score_run(run, gold, load=A.load_common, usage=A.common_usage)})
    df = pd.DataFrame(rows)
    df.to_csv(args.out / 'runs.csv', index=False)

    show = ['calls', 'input_M', 'output_M', 'wall_min', 'nodes', 'edges', 'n_Player', 'n_Team', 'n_City',
            'n_Owner', 'e_PlaysFor', 'e_LocatedIn', 'e_Owns', 'entities_found', 'entities_split', 'attr_filled',
            'attr_exact', 'attr_lenient', 'attr_wrong', 'rel_found', 'current_team_found', 'current_team_marked',
            'current_team_precision', 'current_team_field_found', 'current_team_field_marked',
            'current_team_field_precision']
    totals = {k: int(df[k].iloc[0]) for k in ('entities', 'attr_gold', 'rel_gold', 'current_team_gold')}

    def cell(s):
        s = s.dropna()
        if s.empty:
            return '–'
        mean = s.mean()
        fmt = (lambda x: f'{x:.2f}') if s.dtype == float and mean < 100 else (lambda x: f'{x:,.0f}')
        return fmt(mean) if s.min() == s.max() else f'{fmt(mean)} [{fmt(s.min())}-{fmt(s.max())}]'

    order = [v for v in VARIANTS + list(A.BASELINES) if v in set(df.variant)]
    summary = pd.DataFrame({NAMES.get(v, v): {k: cell(df[df.variant == v][k]) for k in show}
                            | {'runs': int((df.variant == v).sum())} for v in order})
    summary.to_csv(args.out / 'summary.csv')
    print('gold totals:', totals)
    with pd.option_context('display.width', 250, 'display.max_colwidth', 30):
        print(summary.to_string())


if __name__ == '__main__':
    main()
