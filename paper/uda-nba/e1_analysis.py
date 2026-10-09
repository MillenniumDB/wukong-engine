"""E1: structure of the graphs built by Wukong, LightRAG and GraphRAG over UDA-Bench NBA.

    envs/graphrag/bin/python e1_analysis.py [--out runs/e1]

Three parts, same procedure for every system:
  1. structure: size, type / relation-label vocabularies, singleton labels, free text
  2. duplicates: nodes whose names collapse after normalization, and aliases of the
     216 subject entities (one per document)
  3. gold coverage: entities, attribute values and relations of the UDA-Bench tables.
     Wukong is scored on its typed fields and edges. LightRAG and GraphRAG have no
     typed fields, so a value counts as covered if it appears anywhere in the
     description text of a matched node or of its incident edges (upper bound:
     such a value is in the graph but cannot be queried by structure).

Gold row ID = document number, and the first line of each document is the entity's
common name, which we use as the anchor name (the gold names are often legal names).
"""

import argparse
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
RUNS = HERE / 'runs'
GOLD = HERE / 'data/ground_truth/Player'
DOCS = HERE / 'data/docs'

# --------------------------------------------------------------------- names


def norm(s):
    s = unicodedata.normalize('NFKD', str(s))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    return re.sub(r'^the ', '', s)


NICK = {'steve': 'steven', 'stephen': 'steven', 'dan': 'daniel', 'joe': 'joseph', 'jim': 'james',
        'bill': 'william', 'mike': 'michael', 'bob': 'robert', 'tom': 'thomas', 'herb': 'herbert',
        'josh': 'joshua', 'stan': 'stanley', 'dave': 'david', 'chris': 'christopher', 'tony': 'anthony',
        'larry': 'lawrence', 'magic': 'earvin', 'shaq': 'shaquille', 'nate': 'nathaniel'}


def same_person(node, gold_names):
    """Loose person match: same surname, compatible first name (prefix or nickname)."""
    t = node.split()
    if len(t) < 2:
        return False
    for g in gold_names:
        gt = g.split()
        if len(gt) < 2 or t[-1] != gt[-1]:
            continue
        if len(t[0].rstrip('.')) < 2:  # "A.C. Green" is not "Kenneth Green"
            continue
        f = NICK.get(t[0], t[0])
        if any(x.startswith(t[0]) or x.startswith(f) or NICK.get(x, x) == f for x in gt[:-1]):
            return True
    return False


# --------------------------------------------------------------------- loading
# Unified form: nodes {id: dict(name, type, attrs, text)}, edges [dict(src, dst, label, text, props)]


def load_wukong(run='wukong-full'):
    d = RUNS / run / 'exports/neo4j'
    nodes, edges, prov = {}, [], Counter()
    for f in sorted((d / 'entities').glob('*.csv')):
        t = f.stem
        df = pd.read_csv(f, dtype=str, keep_default_na=False)
        if t in ('Chunk', 'Document'):
            prov[t] = len(df)
            continue
        for r in df.to_dict('records'):
            attrs = {k.split(':')[0]: v for k, v in r.items() if not k.startswith('_') and v != ''}
            key = 'team_name' if t == 'Team' else 'city_name' if t == 'City' else 'name'
            nodes[r['_id:ID']] = dict(name=attrs.get(key, ''), type=t, attrs=attrs, text='')
    for f in sorted((d / 'relationships').glob('*.csv')):
        t = f.stem
        df = pd.read_csv(f, dtype=str, keep_default_na=False)
        if t in ('ChunkOf', 'ExtractedFrom'):
            prov[t] = len(df)
            continue
        for r in df.to_dict('records'):
            props = {k.split(':')[0]: v for k, v in r.items() if not k.startswith(('_', ':')) and v != ''}
            edges.append(dict(src=r[':START_ID'], dst=r[':END_ID'], label=t, text='', props=props))
    return nodes, edges, prov


def load_lightrag():
    ns = '{http://graphml.graphdrawing.org/xmlns}'
    root = ET.parse(RUNS / 'lightrag-full/storage/graph_chunk_entity_relation.graphml').getroot()
    keys = {k.get('id'): k.get('attr.name') for k in root.findall(ns + 'key')}

    def data(el):
        return {keys[x.get('key')]: x.text or '' for x in el.findall(ns + 'data')}

    nodes, edges = {}, []
    for n in root.iter(ns + 'node'):
        a = data(n)
        nodes[n.get('id')] = dict(name=n.get('id'), type=a.get('entity_type', ''), attrs={},
                                  text=a.get('description', ''))
    for e in root.iter(ns + 'edge'):
        a = data(e)
        kw = ','.join(sorted({k.strip().lower() for k in a.get('keywords', '').split(',') if k.strip()}))
        edges.append(dict(src=e.get('source'), dst=e.get('target'), label=kw or None,
                          text=a.get('description', ''), props={}))
    return nodes, edges, {}


def load_graphrag():
    o = RUNS / 'graphrag-full/output'
    ent = pd.read_parquet(o / 'entities.parquet')
    rel = pd.read_parquet(o / 'relationships.parquet')
    nodes = {r.title: dict(name=r.title, type=r.type, attrs={}, text=r.description or '')
             for r in ent.itertuples()}
    # GraphRAG relationships have no type: only a free-text description and a weight
    edges = [dict(src=r.source, dst=r.target, label=None, text=r.description or '', props={})
             for r in rel.itertuples()]
    return nodes, edges, {'community_reports': len(pd.read_parquet(o / 'community_reports.parquet'))}


def load_common(run):
    """Graphs exported by the schema-based baselines (baselines/*_build.py): graph/nodes.jsonl
    and graph/edges.jsonl, already typed with our entity and relationship type names."""
    d = RUNS / run / 'graph'
    nodes, edges = {}, []
    for line in (d / 'nodes.jsonl').open():
        r = json.loads(line)
        nodes[r['id']] = dict(name=r['name'], type=r['type'], attrs=r.get('attrs', {}), text='')
    for line in (d / 'edges.jsonl').open():
        r = json.loads(line)
        if r['src'] in nodes and r['dst'] in nodes:
            edges.append(dict(src=r['src'], dst=r['dst'], label=r['label'], text='', props=r.get('props', {})))
    return nodes, edges, {}


def common_usage(run):
    """Calls and tokens from usage.jsonl (one line per LLM call), wall time from meta.json."""
    tot = Counter()
    for line in (RUNS / run / 'usage.jsonl').open():
        r = json.loads(line)
        tot['calls'] += 1
        tot['input'] += r.get('input', 0)
        tot['output'] += r.get('output', 0) - r.get('reasoning', 0)  # as in Wukong: output without reasoning
        tot['reasoning'] += r.get('reasoning', 0)
    meta = json.loads((RUNS / run / 'meta.json').read_text())
    wall = meta.get('wall_time_s') or meta.get('wall_seconds') or meta.get('wall_secs') or meta.get('wall_time_seconds')
    tot['wall_min'] = round(wall / 60, 1) if wall else None
    return dict(tot)


# graphs with typed nodes and edges: matched by type, scored on typed fields
TYPED = ('Wukong', 'Neo4j', 'LlamaIndex', 'OntoGPT')


def typed(system):
    return system.startswith(TYPED)


BASELINES = {'Neo4j-GraphRAG': 'neo4j-graphrag-full', 'LlamaIndex': 'llamaindex-full', 'OntoGPT': 'ontogpt-full'}

# Wukong runs, by name. E1 reports Wukong-r1..r3: the full schema (workspace-x6-s4) on the current
# engine, three runs (run_x6.sh). The others are kept for reference: Wukong-orig used the original
# schema, whose examples leaked gold values; Wukong-v1..v3 used the first clean schemas on engine
# 99d591e, and their Team.team_name instruction still named a subject team (make_schema_variants.py).
WUKONG_RUNS = {'Wukong-orig': 'wukong-full', 'Wukong-v1': 'wukong-v1', 'Wukong-v2': 'wukong-v2',
               'Wukong-v3': 'wukong-v3', 'Wukong-r1': 'x6-s4-r1', 'Wukong-r2': 'x6-s4-r2', 'Wukong-r3': 'x6-s4-r3'}

SYSTEMS = {'LightRAG': load_lightrag, 'GraphRAG': load_graphrag}
for _name, _run in WUKONG_RUNS.items():
    if (RUNS / _run / 'exports/neo4j/relationships').is_dir():
        SYSTEMS[_name] = lambda _run=_run: load_wukong(_run)
for _name, _run in BASELINES.items():
    if (RUNS / _run / 'graph/edges.jsonl').exists():
        SYSTEMS[_name] = lambda _run=_run: load_common(_run)

# --------------------------------------------------------------------- 1. structure


def wukong_usage(run):
    """Calls and tokens from the last metrics snapshot of each extraction stage, plus wall time."""
    lines = (RUNS / f'{run}.log').read_text().splitlines()
    tot, sec, snap = Counter(), 0, {}
    for i, line in enumerate(lines):
        if 'Now tracking' in line:
            sec += 1
        if line.strip() == 'Total Jobs:' or line.strip().startswith('Total Jobs:'):
            snap.setdefault(sec, {})['calls'] = int(line.split(':')[1].replace(',', ''))
        if line.strip() == 'Total Tokens':
            for x in lines[i + 1:i + 8]:
                m = re.match(r'\s+(Input|Output|Reasoning):\s+([\d,]+)', x)
                if m:
                    snap.setdefault(sec, {})[m.group(1).lower()] = int(m.group(2).replace(',', ''))
    for v in snap.values():
        tot.update(v)
    wall = re.findall(r'^real ([\d.]+)', '\n'.join(lines), re.M)
    tot['wall_min'] = round(float(wall[-1]) / 60, 1) if wall else None
    return dict(tot)


def structure(nodes, edges):
    labels = Counter(e['label'] for e in edges if e['label'])
    types = Counter(n['type'] for n in nodes.values())
    deg = Counter()
    for e in edges:
        deg[e['src']] += 1
        deg[e['dst']] += 1
    kw = Counter(k for e in edges if e['label'] for k in e['label'].split(','))
    txt = [len(e['text']) for e in edges if e['text']]
    ntxt = [len(n['text']) for n in nodes.values() if n['text']]
    nattr = sum(len(n['attrs']) for n in nodes.values())
    return {
        'nodes': len(nodes),
        'edges': len(edges),
        'entity_types': len(types),
        'entity_types_singleton': sum(1 for c in types.values() if c == 1),
        'top_types': dict(types.most_common(6)),
        'edges_unlabeled': sum(1 for e in edges if not e['label']),
        'relation_labels': len(labels),
        'relation_labels_singleton': sum(1 for c in labels.values() if c == 1),
        'edges_with_singleton_label': sum(c for c in labels.values() if c == 1),
        'distinct_keywords': len(kw) if any(',' in l for l in labels) or len(labels) > 10 else None,
        'top_labels': dict(labels.most_common(8)),
        'typed_attribute_values': nattr,
        'nodes_with_description': len(ntxt),
        'median_node_description_chars': int(pd.Series(ntxt).median()) if ntxt else 0,
        'edges_with_description': len(txt),
        'median_edge_description_chars': int(pd.Series(txt).median()) if txt else 0,
        'isolated_nodes': sum(1 for n in nodes if deg[n] == 0),
        'degree_1_nodes': sum(1 for n in nodes if deg[n] == 1),
    }


# --------------------------------------------------------------------- gold


def doc_title(kind, n):
    with open(DOCS / kind / kind / f'{n}.txt', encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.strip():  # drop Wikipedia disambiguators: "Ken Green (basketball, born 1959)"
                return re.sub(r'\s*\(.*?\)', '', line).strip()


def load_gold():
    """One record per document: kind, anchor names, attribute facts, relation facts."""
    ents = []
    p = pd.read_csv(GOLD / 'player.csv', dtype=str, keep_default_na=False)
    for r in p.to_dict('records'):
        attrs = {k: r[k] for k in ('birth_date', 'nationality', 'position', 'draft_pick', 'draft_year',
                                   'college', 'nba_championships', 'mvp_awards', 'olympic_gold_medals',
                                   'fiba_world_cup')}
        ents.append(dict(kind='player', id=int(r['ID']), names=[doc_title('player', r['ID']), r['name']],
                         attrs=attrs, rels={'plays_for': [r['team']]}))
    t = pd.read_csv(GOLD / 'team.csv', dtype=str, keep_default_na=False)
    for r in t.to_dict('records'):
        ents.append(dict(kind='team', id=int(r['ID']), names=[doc_title('team', r['ID']), r['team_name']],
                         attrs={'founded_year': r['founded_year'], 'championships': r['championship']},
                         rels={'located_in': [r['location']],
                               'owned_by': [x.strip() for x in r['ownership'].split('||') if x.strip()]}))
    c = pd.read_csv(GOLD / 'city.csv', dtype=str, keep_default_na=False)
    for r in c.to_dict('records'):
        ents.append(dict(kind='city', id=int(r['ID']), names=[doc_title('city', r['ID']), r['city_name']],
                         attrs={'state_name': r['state_name'], 'population': r['population'],
                                'area': r['area']}, rels={}))
    m = pd.read_csv(GOLD / 'manager.csv', dtype=str, keep_default_na=False)
    for r in m.to_dict('records'):
        ents.append(dict(kind='owner', id=int(r['ID']), names=[doc_title('owner', r['ID']), r['name']],
                         attrs={'nationality': r['nationality'], 'own_year': r['own_year']},
                         rels={'owns': [r['nba_team']]}))
    for e in ents:
        e['names'] = [x for x in dict.fromkeys(norm(n) for n in e['names']) if x]
    return ents


def empty(v):
    """Gold cells that state nothing: blank, or a zero count (0 MVPs is the default)."""
    v = str(v).strip()
    return v == '' or re.fullmatch(r'0+(\.0+)?', v) is not None


WUKONG_TYPE = {'player': 'Player', 'team': 'Team', 'city': 'City', 'owner': 'Owner'}


class Matcher:
    """Maps a gold entity to graph nodes: exact (normalized name equals an anchor name) and
    variants (aliases that a navigating user would have to know are the same entity)."""

    def __init__(self, system, nodes):
        self.system = system
        self.nodes = nodes
        self.by_norm = defaultdict(list)
        for i, n in nodes.items():
            self.by_norm[norm(n['name'])].append(i)

    def candidates(self, kind, i):
        # Wukong nodes are typed, so a Player is only matched against Player nodes;
        # RAG node types are unreliable, so any node may match (lenient to them)
        return not typed(self.system) or self.nodes[i]['type'] == WUKONG_TYPE[kind]

    def match(self, e):
        exact = {i for a in e['names'] for i in self.by_norm.get(a, []) if self.candidates(e['kind'], i)}
        variants = set()
        if e['kind'] in ('player', 'owner'):
            gold_surnames = {a.split()[-1] for a in e['names']}
            for k, ids in self.by_norm.items():
                if k.split() and k.split()[-1] in gold_surnames and same_person(k, e['names']):
                    variants |= {i for i in ids if self.candidates(e['kind'], i)}
        elif e['kind'] == 'team':
            nick = e['names'][0].split()[-1]  # "lakers"; "76ers"
            for k in (nick, *(f'{a} basketball' for a in e['names'])):
                variants |= {i for i in self.by_norm.get(k, []) if self.candidates('team', i)}
        elif e['kind'] == 'city':
            city = e['names'][0]
            for k, ids in self.by_norm.items():
                if k in (f'city of {city}', f'{city} city') or (
                        k.startswith(city + ' ') and len(k.split()) <= len(city.split()) + 2
                        and k.split()[len(city.split())] in STATES):
                    variants |= {i for i in ids if self.candidates('city', i)}
        return exact, variants - exact


STATES = {norm(s) .split()[0] for s in (
    'alabama alaska arizona arkansas california colorado connecticut delaware florida georgia hawaii '
    'idaho illinois indiana iowa kansas kentucky louisiana maine maryland massachusetts michigan '
    'minnesota mississippi missouri montana nebraska nevada new north ohio oklahoma oregon '
    'pennsylvania rhode south tennessee texas utah vermont virginia washington west wisconsin wyoming '
    'ontario quebec tx ca ny il fl ga ma mi mn wi co az ut or wa tn la ok in oh pa nc dc').split()}

# --------------------------------------------------------------------- value matching

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
          'October', 'November', 'December']


def num(v):
    try:
        return float(str(v).replace(',', '').strip())
    except ValueError:
        return None


# gold city areas mix square miles and km²; 1% tolerance for population and area
UNITS = {'area': (1, 2.58999, 1 / 2.58999)}

# counts in free text must sit next to what they count: a bare "1" is in every long description
COUNT_CONTEXT = {'nba_championships': r'champion|title|ring', 'championships': r'champion|title',
                 'mvp_awards': r'MVP|Most Valuable', 'olympic_gold_medals': r'Olympic|gold',
                 'fiba_world_cup': r'World Cup|World Championship|FIBA', 'draft_pick': r'pick|draft|select'}
NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
                'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen']
ORDINALS = ['', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth']
POSITION = {'frontcourt': r'forward|center|centre|frontcourt', 'backcourt': r'guard|backcourt'}


def value_equal(gold, got, field=None):
    """Typed comparison for Wukong's structured fields."""
    if gold is None or got is None:
        return False
    a, b = num(gold), num(got)
    if a is not None and b is not None:
        return any(abs(a - b * u) <= 0.01 * max(abs(a), 1) for u in UNITS.get(field, (1,)))
    if a is not None:  # a number must be stored as a number: "3rd overall" is not 3
        return False
    if re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}', str(gold)):
        return [int(x) for x in str(gold).split('/')] == [int(x) for x in re.findall(r'\d+', str(got))[:3]]
    a, b = norm(gold), norm(got)
    return bool(a and b) and (a in b or b in a)


def value_in_text(gold, text, field=None):
    """Does the gold value appear in free text? (for LightRAG / GraphRAG)"""
    g = str(gold).strip()
    if field == 'position':
        return re.search(POSITION.get(norm(g), re.escape(g)), text, re.I) is not None
    if field in COUNT_CONTEXT:
        n = int(num(g))
        forms = [str(n)] + ([NUMBER_WORDS[n]] if n < len(NUMBER_WORDS) else [])
        forms += [ORDINALS[n], f'{n}(?:st|nd|rd|th)'] if field == 'draft_pick' and 0 < n < len(ORDINALS) else []
        if field == 'mvp_awards' and n == 1:
            forms += ['an', 'a']
        num_re = r'(?<![\w.,])(?:' + '|'.join(forms) + r')(?![\w]|[.,]\d)'
        ctx = COUNT_CONTEXT[field]
        return re.search(rf'{num_re}.{{0,60}}(?:{ctx})|(?:{ctx}).{{0,60}}{num_re}', text, re.I | re.S) is not None
    if re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}', g):
        y, m, d = (int(x) for x in g.split('/'))
        mon = MONTHS[m - 1]
        pats = [rf'{mon} {d}, {y}', rf'{d} {mon},? {y}', rf'{y}-{m:02d}-{d:02d}']
        return any(re.search(p, text) for p in pats)
    n = num(g)
    if n is not None:
        s = f'{n:,.0f}' if n >= 1000 and n == int(n) else (str(int(n)) if n == int(n) else str(n))
        variants = {s, s.replace(',', '')}
        return any(re.search(rf'(?<![\d.,]){re.escape(v)}(?![\d]|[.,]\d)', text) for v in variants)
    return norm(g) in norm(text)


# --------------------------------------------------------------------- 2+3. duplicates and coverage


def coverage(system, nodes, edges, gold):
    m = Matcher(system, nodes)
    adj = defaultdict(list)
    for e in edges:
        adj[e['src']].append(e)
        adj[e['dst']].append(e)
    matched = {}
    rows = []
    for e in gold:
        exact, var = m.match(e)
        matched[(e['kind'], e['id'])] = exact | var
        rows.append(dict(kind=e['kind'], id=e['id'], name=e['names'][0], exact=len(exact), variants=len(var),
                         variant_names='; '.join(sorted({nodes[i]['name'] for i in var}))[:300]))
    ent = pd.DataFrame(rows)

    # attribute facts
    facts = []
    for e in gold:
        ids = matched[(e['kind'], e['id'])]
        text = ' '.join([nodes[i]['text'] for i in ids] + [x['text'] for i in ids for x in adj[i]])
        for k, v in e['attrs'].items():
            if empty(v):
                continue
            if typed(system):
                field = {'championships': 'championships', 'own_year': None}.get(k, k)
                got = [nodes[i]['attrs'].get(field) for i in ids] if field else []
                if k == 'own_year':  # stored on the Owns edge
                    got = [x['props'].get('since_year') for i in ids for x in adj[i] if x['label'] == 'Owns']
                ok = any(value_equal(v, g, field=k) for g in got)
            else:
                ok = value_in_text(v, text, field=k)
            facts.append(dict(kind=e['kind'], id=e['id'], fact=k, gold=v, covered=ok))

    # relation facts: an edge between the matched endpoints
    names = {(e['kind'], n): e for e in gold for n in e['names']}
    rel_target = {'plays_for': 'team', 'located_in': 'city', 'owned_by': 'owner', 'owns': 'team'}
    wk_label = {'plays_for': 'PlaysFor', 'located_in': 'LocatedIn', 'owned_by': 'Owns', 'owns': 'Owns'}
    for e in gold:
        src = matched[(e['kind'], e['id'])]
        for r, targets in e['rels'].items():
            for t in targets:
                if not t:
                    continue
                tk = rel_target[r]
                te = names.get((tk, norm(t)))
                if te is not None:
                    dst = matched[(tk, te['id'])]
                else:  # target outside the gold tables (e.g. a non-NBA club): match by name
                    dst = set(m.by_norm.get(norm(t), []))
                    if tk in ('owner',):
                        dst |= {i for k, ids in m.by_norm.items() if same_person(k, [norm(t)]) for i in ids}
                hits = [x for i in src for x in adj[i]
                        if (x['src'] in dst or x['dst'] in dst) and (x['src'] in src or x['dst'] in src)]
                if typed(system):
                    hits = [x for x in hits if x['label'] == wk_label[r]]
                    current = [x for x in hits if x['props'].get('tenure', 'latest') == 'latest']
                else:
                    current = hits  # no way to tell current from former team
                facts.append(dict(kind=e['kind'], id=e['id'], fact=r, gold=t, covered=bool(hits),
                                  current=bool(current) if r == 'plays_for' and typed(system) else None,
                                  nba_target=te is not None))
    return ent, pd.DataFrame(facts)


def surface_duplicates(nodes):
    """Groups of distinct nodes whose names collapse to the same normalized string."""
    g = defaultdict(set)
    for i, n in nodes.items():
        g[norm(n['name'])].add(i)
    groups = {k: v for k, v in g.items() if len(v) > 1 and k}
    return {'groups': len(groups), 'nodes_in_groups': sum(len(v) for v in groups.values()),
            'examples': sorted((sorted(nodes[i]['name'] for i in v) for v in groups.values()), key=lambda g: (len(g), g))[-3:]}


# --------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=RUNS / 'e1')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    gold = load_gold()
    report = {}
    for name, load in SYSTEMS.items():
        nodes, edges, extra = load()
        s = structure(nodes, edges)
        s.update(extra)
        if name.startswith('Wukong'):
            s['usage'] = wukong_usage(WUKONG_RUNS[name])
        elif name in BASELINES:
            s['usage'] = common_usage(BASELINES[name])
        s['surface_duplicates'] = surface_duplicates(nodes)
        ent, facts = coverage(name, nodes, edges, gold)
        ent.to_csv(args.out / f'{name}_entities.csv', index=False)
        facts.to_csv(args.out / f'{name}_facts.csv', index=False)
        cov = {}
        for kind, d in ent.groupby('kind'):
            cov[kind] = dict(n=len(d), found=int(((d.exact + d.variants) > 0).sum()),
                             found_exact=int((d.exact > 0).sum()),
                             with_aliases=int(((d.exact + d.variants) > 1).sum()),
                             mean_nodes_when_found=round(float((d.exact + d.variants)[(d.exact + d.variants) > 0].mean()), 2))
        s['entity_coverage'] = cov
        s['fact_coverage'] = {f'{k}.{f}': dict(n=len(d), covered=int(d.covered.sum()))
                              for (k, f), d in facts.groupby(['kind', 'fact'])}
        pf = facts[facts.fact == 'plays_for']
        s['plays_for_split'] = {('nba' if k else 'non_nba'): f"{int(d.covered.sum())}/{len(d)}"
                                for k, d in pf.groupby('nba_target')}
        s['plays_for_current'] = int(pf.current.fillna(False).astype(bool).sum()) if typed(name) else 'n/a'
        report[name] = s
    (args.out / 'report.json').write_text(json.dumps(report, indent=1, default=str))
    print_report(report)


def print_report(R):
    sys_ = list(R)

    def row(label, f):
        print(f'{label:<42}' + ''.join(f'{str(f(R[s])):>16}' for s in sys_))

    print(f'{"":<42}' + ''.join(f'{s:>16}' for s in sys_))
    print('-- cost (Wukong only; see usage_summary.py for the others)')
    for k in ('calls', 'input', 'output', 'reasoning', 'wall_min'):
        row(k, lambda r, k=k: r['usage'].get(k) if 'usage' in r else '')
    print('-- structure')
    for k in ('nodes', 'edges', 'entity_types', 'entity_types_singleton', 'relation_labels',
              'relation_labels_singleton', 'edges_with_singleton_label', 'edges_unlabeled',
              'distinct_keywords', 'typed_attribute_values', 'nodes_with_description',
              'median_node_description_chars', 'median_edge_description_chars', 'isolated_nodes',
              'degree_1_nodes'):
        row(k, lambda r, k=k: r.get(k))
    print('-- duplicates')
    row('surface duplicate groups', lambda r: r['surface_duplicates']['groups'])
    row('nodes in those groups', lambda r: r['surface_duplicates']['nodes_in_groups'])
    for kind in ('player', 'team', 'city', 'owner'):
        row(f'{kind}: subject has >1 node', lambda r, k=kind: f"{r['entity_coverage'][k]['with_aliases']}/{r['entity_coverage'][k]['found']}")
        row(f'{kind}: mean nodes per subject', lambda r, k=kind: r['entity_coverage'][k]['mean_nodes_when_found'])
    print('-- gold coverage (Wukong: typed value; RAG: value anywhere in text)')
    for kind in ('player', 'team', 'city', 'owner'):
        row(f'{kind}: entity found (exact name)', lambda r, k=kind: f"{r['entity_coverage'][k]['found']} ({r['entity_coverage'][k]['found_exact']}) /{r['entity_coverage'][k]['n']}")
    for f in R[sys_[0]]['fact_coverage']:
        row(f, lambda r, f=f: f"{r['fact_coverage'][f]['covered']}/{r['fact_coverage'][f]['n']}")
    row('  plays_for, gold team in NBA table', lambda r: r['plays_for_split'].get('nba'))
    row('  plays_for, gold team outside NBA', lambda r: r['plays_for_split'].get('non_nba'))
    row('player.plays_for, marked current', lambda r: r['plays_for_current'])


if __name__ == '__main__':
    main()
