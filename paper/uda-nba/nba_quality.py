"""Quality of the NBA graphs: content against gold, schema conformance and hallucination, for every system.

    envs/graphrag/bin/python nba_quality.py      # -> runs/quality/{runs.csv,summary.csv}, report/nba_quality_table.tex

Systems: Wukong with the NBA schema (workspace-x6-s5, three runs), the schema-based extractors (neo4j-graphrag,
LlamaIndex, OntoGPT), built three times from the same schema, and the schema-free graphs (LightRAG, GraphRAG,
KGGen; one run each).

Content against gold (the 216 subject entities; matching as in e1_analysis.py):
  entities      found, and split (matched by more than one node). As P/R/F1 of resolution over a one-to-one
                alignment of gold entities and nodes (entity-level CEAF): recall = aligned / 216, precision =
                aligned / distinct nodes matched to gold entities (one node per entity is 100%). A split costs
                precision; a node shared by several gold entities (a merge) is aligned to one, costing recall
  attributes    typed graphs: a gold attribute is filled if a matched node has the field; correct if the value
                equals the gold value in any form (x6_analysis.lenient_equal); exact if in the gold's form, so a
                query can compare it. One-to-one: the right value counts once in any form, each distinct wrong value of
                the matched nodes (a split entity can hold several) once. Precision = correct / (correct + wrong
                values); recall = correct / 955; exact recall = exact / 955. Schema-free graphs have no fields: recall is whether the value appears in the text of the
                matched nodes or their edges (an upper bound), and precision is undefined.
  relations     the 135 gold relations between gold entities (player's team, team's city, team's owners; ownership
                is listed from both sides and counted once), aligned one-to-one with edges: found if an edge of the right type joins the matched nodes (any edge, for schema-free graphs), and split
                if stored as more than one edge (as an entity split over several nodes). As P/R/F1: recall =
                aligned / 135, precision = aligned / distinct edges matched to them.
  single-valued the benchmark defines a player's team as the current one and a team's location as the latest
                city, so these 119 gold relations have one value: precision over the values a typed graph marks
                (current team: the Player.current_team field of schema s5, in every typed graph; city: every
                LocatedIn edge of the team), recall over the 119 facts; the right value counts once (in any form, or
                over a split target), each wrong one once. is_current() reads PlaysFor tenure,
                for graphs without the field.

Schema conformance (typed graphs, against the schema they were built from, with Player.current_team for s5):
  edges         the endpoint types are those the relationship type declares
  values        every node and edge property is a field the schema declares for that type and, where the schema
                constrains it (regex, closed options; 15 of 26 fields), satisfies the constraint. Reported over all
                values and over the constrained ones.

Hallucination, the share of extracted items not supported by the articles they were extracted from:
  entities      node names none of whose source articles contains all the name's words (normalized; words of
                one or two letters ignored, so 'A.C. Green' needs 'green')
  values        typed property values not found in their node's source articles: dates in any written form,
                numbers as digits or words, positions through forward/center/guard, other values by their words.
                Zero counts ('0 MVP awards') state an absence and are not checked; values that fail conformance
                are checked like any other.
  Sources: the node's own article if it is a gold subject (LlamaIndex keeps one source chunk per node), plus
  Wukong's ExtractedFrom/ChunkOf export, neo4j-graphrag's and LlamaIndex's source chunks, OntoGPT's
  articles, LightRAG's file_path, GraphRAG's text units, KGGen's per-document graphs (through its clusters).
"""

import json
import re
from collections import Counter, defaultdict

import pandas as pd
from dateutil import parser as dateparser

import e1_analysis as A
import x6_analysis as X

HERE = A.RUNS.parent
DOCS = HERE / 'data' / 'docs'
OUT = A.RUNS / 'quality'
KM = json.loads((HERE / 'workspace-x6-s5' / 'knowledge_model.json').read_text())
WUKONG = ['x6-s5-r1', 'x6-s5-r2', 'x6-s5-r3']
# the schema-based extractors, built three times from the same schema as Wukong (workspace-x6-s5)
TYPED = {name: [f'{tool}-s5-r{r}' for r in (1, 2, 3)]
         for name, tool in (('Neo4j-GraphRAG', 'neo4j-graphrag'), ('LlamaIndex', 'llamaindex'), ('OntoGPT', 'ontogpt'))}
UNTYPED = ['LightRAG', 'GraphRAG', 'KGGen']
COUNTS = {'nba_championships', 'mvp_awards', 'olympic_gold_medals', 'fiba_world_cup', 'championships'}
POS = {'Frontcourt': r'forward|center|centre', 'Backcourt': r'guard'}

_text = {}


def article(key: str) -> str:
    """'player/1' -> normalized text of data/docs/player/player/1.txt (cached)."""
    if key not in _text:
        kind, n = key.split('/')
        _text[key] = A.norm((DOCS / kind / kind / f'{n}.txt').read_text())
    return _text[key]


_raw = {}


def raw_article(key: str) -> str:
    if key not in _raw:
        kind, n = key.split('/')
        _raw[key] = (DOCS / kind / kind / f'{n}.txt').read_text()
    return _raw[key]


def words(s) -> list[str]:
    return [w for w in A.norm(s).split() if len(w) > 2 or w.isdigit()]


def name_supported(name, docs) -> bool:
    ws = words(name)
    if not ws:
        return True  # nothing checkable (e.g. a one-letter name)
    return any(all(re.search(rf'(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])', article(d)) for w in ws) for d in docs)


def value_supported(field: str, value, docs) -> bool | None:
    """True/False, or None when not checked (zero counts)."""
    v = str(value).strip()
    raw = [raw_article(d) for d in docs]
    if field in COUNTS or field in ('draft_pick', 'mvp_awards'):
        n = A.num(v) if A.num(v) is not None else X.lenient_num(v)
        if n == 0:
            return None
    if field in ('birth_date', 'death_date'):
        try:
            d = dateparser.parse(v, default=None, fuzzy=True)
        except (ValueError, OverflowError, TypeError):
            d = None
        if d is not None and d.year and d.month and d.day:
            return any(A.value_in_text(f'{d.year}/{d.month}/{d.day}', t) for t in raw)
    if field == 'position' and v in POS:
        return any(re.search(POS[v], t, re.I) for t in raw)
    n = A.num(v)
    if n is None and field in COUNTS | {'draft_pick', 'draft_year', 'founded_year', 'since_year', 'population', 'area'}:
        n = X.lenient_num(v)
    if n is not None and field != 'gdp':
        s = f'{n:,.0f}' if n >= 1000 and n == int(n) else (str(int(n)) if n == int(n) else str(n))
        forms = {s, s.replace(',', '')}
        if n == int(n) and n < len(A.NUMBER_WORDS):
            forms.add(A.NUMBER_WORDS[int(n)])
        if n == int(n) and 0 < n < len(A.ORDINALS) and A.ORDINALS[int(n)]:
            forms.add(A.ORDINALS[int(n)])
        if field == 'area':  # stored in square miles, often written in km2 too
            forms |= {f'{n * 2.589988:,.0f}', f'{n * 2.589988:.0f}', f'{n:.1f}', f'{n:,.1f}'}
        return any(re.search(rf'(?<![\d.,]){re.escape(f)}(?![\d]|[.,]\d)', t, re.I) for t in raw for f in forms)
    return name_supported(v, docs)


# --------------------------------------------------------------------- provenance per system


def wukong_docs(run: str) -> tuple[dict, dict]:
    """(node id -> articles, edge (src, dst, label) -> articles) from the engine's provenance export."""
    d = A.RUNS / run / 'exports' / 'neo4j'
    doc = {r['_id:ID']: '/'.join(r['source_uri:string'].split('/')[-3::2]).replace('.txt', '')
           for r in pd.read_csv(d / 'entities' / 'Document.csv', dtype=str).to_dict('records')}
    chunk_doc = {r[':START_ID']: doc[r[':END_ID']] for r in pd.read_csv(d / 'relationships' / 'ChunkOf.csv', dtype=str).to_dict('records')}
    where = lambda x: doc.get(x) or chunk_doc.get(x)  # noqa: E731
    nodes = defaultdict(set)
    for r in pd.read_csv(d / 'relationships' / 'ExtractedFrom.csv', dtype=str).to_dict('records'):
        if where(r[':END_ID']):
            nodes[r[':START_ID']].add(where(r[':END_ID']))
    return nodes, {}


def common_docs(system: str, run: str, nodes_raw: list[dict]) -> dict:
    if system == 'Neo4j-GraphRAG':
        return {n['id']: {c.split('#')[0] for c in n.get('chunks', [])} for n in nodes_raw}
    if system == 'LlamaIndex':
        doc = {c['id']: c['doc'] for c in map(json.loads, (A.RUNS / run / 'graph' / 'chunks.jsonl').open())}
        return {n['id']: {doc[c] for c in n.get('chunks', []) if c in doc} for n in nodes_raw}
    return {n['id']: {x.replace('_', '/') for x in n.get('docs', [])} for n in nodes_raw}


def untyped_docs(system: str, nodes: dict) -> dict:
    key = lambda f: f.replace('.txt', '').replace('_', '/')  # noqa: E731  'player_1.txt' -> 'player/1'
    if system == 'LightRAG':
        import xml.etree.ElementTree as ET
        ns = '{http://graphml.graphdrawing.org/xmlns}'
        root = ET.parse(A.RUNS / 'lightrag-full/storage/graph_chunk_entity_relation.graphml').getroot()
        kid = {k.get('attr.name'): k.get('id') for k in root.findall(ns + 'key')}
        out = {}
        for n in root.iter(ns + 'node'):
            fp = next((x.text for x in n.findall(ns + 'data') if x.get('key') == kid['file_path']), '') or ''
            out[n.get('id')] = {key(f) for f in fp.split('<SEP>') if f.endswith('.txt')}
        return out
    if system == 'GraphRAG':
        o = A.RUNS / 'graphrag-full/output'
        tu = pd.read_parquet(o / 'text_units.parquet')
        title = dict(pd.read_parquet(o / 'documents.parquet')[['id', 'title']].itertuples(index=False))
        tu_doc = {r.id: key(title[r.document_id]) for r in tu.itertuples()}
        ent = pd.read_parquet(o / 'entities.parquet')
        return {r.title: {tu_doc[t] for t in r.text_unit_ids if t in tu_doc} for r in ent.itertuples()}
    # KGGen: an entity's articles are those whose own graph contains it or a member of its cluster
    g = json.loads((A.RUNS / 'kggen-full' / 'graph.json').read_text())
    members = {a: set(m) | {a} for a, m in (g.get('entity_clusters') or {}).items()}
    seen = defaultdict(set)
    for f in (A.RUNS / 'kggen-full' / 'docs').glob('*.json'):
        for e in json.loads(f.read_text())['entities']:
            seen[e].add(key(f.stem))
    return {n: set().union(*(seen[m] for m in members.get(n, {n}))) for n in nodes}


# --------------------------------------------------------------------- metrics


def conformance(nodes: dict, edges_raw: list[tuple[str, str, str, dict]], types: dict) -> dict:
    ok_e = sum(1 for s, d, l, _ in edges_raw
               if l in KM['relationship_types'] and (types.get(s), types.get(d)) in
               {(a, b) for a, bs in KM['relationship_types'][l]['endpoints'].items() for b in bs})
    vals = []  # (declared, constrained, valid)
    for n in nodes.values():
        fields = KM['entity_types'].get(n['type'], {}).get('fields', {})
        vals += [check(fields, k, v) for k, v in n['attrs'].items() if v not in (None, '')]
    for s, d, l, props in edges_raw:
        fields = KM['relationship_types'].get(l, {}).get('fields', {})
        vals += [check(fields, k, v) for k, v in props.items() if v not in (None, '')]
    cons = [v for v in vals if v[1]]
    return {'edges_conforming_pct': round(100 * ok_e / len(edges_raw), 1) if edges_raw else None,
            'values_conforming_pct': round(100 * sum(v[2] for v in vals) / len(vals), 1) if vals else None,
            'constrained_values': len(cons),
            'constrained_conforming_pct': round(100 * sum(v[2] for v in cons) / len(cons), 1) if cons else None}


def check(fields: dict, k: str, v) -> tuple[bool, bool, bool]:
    fd = fields.get(k)
    if fd is None:
        return (False, False, False)
    if fd.get('options'):
        return (True, True, str(v) in fd['options'])
    if fd.get('regex'):
        return (True, True, re.fullmatch(fd['regex'], str(v).strip()) is not None)
    return (True, False, True)


def with_own_articles(matcher_name: str, nodes: dict, docs: dict, gold: list) -> dict:
    """Add to each node matched to a gold subject that subject's own article: LlamaIndex keeps one source chunk
    per node, so a player's values may come from his article while the node only records another one. The same
    for every system."""
    m = A.Matcher(matcher_name, nodes)
    docs = {i: set(d) for i, d in docs.items()}
    for e in gold:
        for i in set().union(*m.match(e)):
            docs.setdefault(i, set()).add(f"{e['kind']}/{e['id']}")
    return docs


def hallucination(nodes: dict, docs: dict, typed: bool) -> dict:
    ent = [name_supported(n['name'], docs.get(i, ())) for i, n in nodes.items() if docs.get(i)]
    out = {'entities_checked': len(ent), 'entities_unsupported_pct': round(100 * (1 - sum(ent) / len(ent)), 1),
           'nodes_without_provenance': sum(1 for i in nodes if not docs.get(i))}
    if typed:
        keys = {t: d['primary_key'] for t, d in KM['entity_types'].items()}
        res = [value_supported(k, v, docs[i]) for i, n in nodes.items() if docs.get(i)
               for k, v in n['attrs'].items() if v not in (None, '') and k != keys.get(n['type'])]
        res = [r for r in res if r is not None]
        out |= {'values_checked': len(res), 'values_unsupported_pct': round(100 * (1 - sum(res) / len(res)), 1)}
    return out


TARGET = {'plays_for': 'team', 'located_in': 'city', 'owned_by': 'owner', 'owns': 'team'}
LABEL = {'plays_for': 'PlaysFor', 'located_in': 'LocatedIn', 'owned_by': 'Owns', 'owns': 'Owns'}
CURRENT = re.compile(r'\b(latest|current|yes|true)\b', re.I)
NOT_CURRENT = re.compile(r'\b(not|no|former|earlier|false|historical)\b', re.I)


def is_current(tenure) -> bool:
    """A PlaysFor edge marks the current team: OntoGPT and Wukong use the schema's value 'latest'; neo4j-graphrag
    and LlamaIndex had no slot for the closed set and wrote free text ('latest NBA team', 'true', 'yes')."""
    t = str(tenure or '')
    return bool(CURRENT.search(t)) and not NOT_CURRENT.search(t)


def align(matched: dict) -> int:
    """Size of a maximum one-to-one alignment between gold entities and their matched nodes (entity-level CEAF):
    a node shared by several gold entities counts for one of them, extra nodes of a split entity for none."""
    owner = {}

    def augment(k, seen):
        for i in matched[k]:
            if i not in seen:
                seen.add(i)
                if i not in owner or augment(owner[i], seen):
                    owner[i] = k
                    return True
        return False
    return sum(augment(k, set()) for k in matched)


def relations(matcher_name: str, nodes: dict, edges: list, gold: list, typed: bool, field_team: bool) -> dict:
    """Relations between gold entities: found, and split (stored as several edges, mirroring an entity stored
    as several nodes). Single-valued relations (the benchmark defines a player's team as the current one and a
    team's location as the latest city): precision over the values a typed graph marks (the current team: the
    Player.current_team field for Wukong s5, PlaysFor edges marked current for the others; the city: every
    LocatedIn edge of the team), recall over the 119 gold facts. Every typed graph is built from schema s5, which
    states the current team as the Player.current_team field, so the field is what is scored."""
    m = A.Matcher(matcher_name, nodes)
    matched = {(e['kind'], e['id']): set().union(*m.match(e)) for e in gold}
    names = {(e['kind'], n): e for e in gold for n in e['names']}
    adj = defaultdict(list)
    for e in edges:
        adj[e['src']].append(e)
        adj[e['dst']].append(e)
    split = split_pairs = 0
    ent_found = align(matched)
    ent_nodes = len(set().union(*matched.values()))
    ent_merged = sum(len({k for k, v in matched.items() if i in v}) > 1 for i in set().union(*matched.values()))
    fv = {'pred': 0, 'right': 0, 'gold': 0, 'hit': 0}
    rel_hits, seen = {}, set()
    for g in gold:
        src = matched[(g['kind'], g['id'])]
        for r, ts in g['rels'].items():
            for t in ts:
                te = names.get((TARGET[r], A.norm(t))) if t else None
                if te is None:
                    continue
                # the gold lists ownership from both sides (team owned_by, owner owns): one fact, one edge
                fact = (('own',) + tuple(sorted([(g['kind'], g['id']), (te['kind'], te['id'])])) if r in ('owns', 'owned_by')
                        else (r, g['kind'], g['id'], te['id']))
                if fact in seen:
                    continue
                seen.add(fact)
                dst = matched[(TARGET[r], te['id'])]
                hits = {id(x): x for i in src for x in adj[i] if (x['src'] in dst or x['dst'] in dst)
                        and (not typed or x['label'] == LABEL[r])}
                rel_hits[fact] = set(hits)
                split += len(hits) > 1
                split_pairs += len({(x['src'], x['dst']) for x in hits.values()}) > 1
                if not typed or r not in ('plays_for', 'located_in'):
                    continue
                # one-to-one: the right value counts once (in any form, or over a split target), each wrong one once
                fv['gold'] += 1
                if r == 'plays_for' and field_team:
                    vals = {A.norm(nodes[i]['attrs']['current_team']) for i in src if nodes[i]['attrs'].get('current_team')}
                    hit, wrong = bool(vals & set(te['names'])), len(vals - set(te['names']))
                else:
                    marked = {x['dst'] if x['src'] in src else x['src'] for i in src for x in adj[i]
                              if x['label'] == LABEL[r] and (r == 'located_in' or is_current(x['props'].get('tenure')))}
                    hit, wrong = bool(marked & dst), len(marked - dst)
                fv['pred'] += hit + wrong
                fv['right'] += hit
                fv['hit'] += hit
    n_rel = len(rel_hits)
    found = align(rel_hits)
    rel_edges = len(set().union(*rel_hits.values()))
    prf = lambda p, r: (round(100 * p, 1), round(100 * r, 1), round(100 * 2 * p * r / (p + r), 1) if p + r else 0.0)  # noqa: E731
    ep, er, ef = prf(ent_found / ent_nodes if ent_nodes else 0.0, ent_found / len(gold))
    rp, rr, rf = prf(found / rel_edges if rel_edges else 0.0, found / n_rel)
    out = {'rel_found': found, 'rel_gold': n_rel, 'rel_split': split, 'rel_split_pairs': split_pairs,
           'ent_matched_nodes': ent_nodes, 'ent_aligned': ent_found, 'ent_merged_nodes': ent_merged,
           'ent_precision': ep, 'ent_recall': er, 'ent_f1': ef,
           'rel_edges': rel_edges, 'rel_precision': rp, 'rel_recall': rr, 'rel_f1': rf}
    if typed:
        p = fv['right'] / fv['pred'] if fv['pred'] else 0.0
        rc = fv['hit'] / fv['gold']
        out |= {'sv_precision': round(100 * p, 1), 'sv_recall': round(100 * rc, 1),
                'sv_f1': round(100 * 2 * p * rc / (p + rc), 1) if p + rc else 0.0, 'sv_gold': fv['gold'],
                'sv_marked': fv['pred']}
    return out


def gold_typed(run, gold, load, usage) -> dict:
    r = X.score_run(run, gold, load=load, usage=usage)
    correct = r['attr_filled'] - r['attr_wrong']
    p, rec = correct / r['attr_pred'], correct / r['attr_gold']
    is_s5 = r.get('current_team_field_marked', 0) > 0
    return {'entities_found': r['entities_found'], 'entities_split': r['entities_split'],
            'attr_precision': round(100 * p, 1), 'attr_recall': round(100 * rec, 1),
            'attr_f1': round(100 * 2 * p * rec / (p + rec), 1), 'attr_exact_recall': round(100 * r['attr_exact'] / r['attr_gold'], 1),
            'rel_found': r['rel_found'], 'rel_gold': r['rel_gold'],
            'current_team_found': r['current_team_field_found'] if is_s5 else r['current_team_found'],
            'current_team_precision': r['current_team_field_precision'] if is_s5 else r['current_team_precision']}


def gold_untyped(name) -> dict:
    f = pd.read_csv(A.RUNS / 'e1' / f'{name}_facts.csv')
    e = pd.read_csv(A.RUNS / 'e1' / f'{name}_entities.csv')
    rel = f[f.fact.isin(['plays_for', 'located_in', 'owned_by', 'owns']) & (f.nba_target == True)]  # noqa: E712
    att = f[~f.fact.isin(['plays_for', 'located_in', 'owned_by', 'owns'])]
    n = e.exact + e.variants
    return {'entities_found': int((n > 0).sum()), 'entities_split': int((n > 1).sum()),
            'attr_recall': round(100 * att.covered.mean(), 1), 'rel_found': int(rel.covered.sum()), 'rel_gold': len(rel)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    gold = A.load_gold()
    rows = []
    for run in WUKONG:
        nodes, edges, _ = A.load_wukong(run)
        types = {i: n['type'] for i, n in nodes.items()}
        ndocs, _ = wukong_docs(run)
        rows.append({'system': 'Wukong s5', 'run': run, **gold_typed(run, gold, A.load_wukong, A.wukong_usage),
                     **relations('Wukong', nodes, edges, gold, typed=True, field_team=True),
                     **conformance(nodes, [(e['src'], e['dst'], e['label'], e['props']) for e in edges], types),
                     **hallucination(nodes, with_own_articles('Wukong', nodes, ndocs, gold), typed=True)})
    for name, run in ((n, r) for n, rs in TYPED.items() for r in rs):
        raw_n = [json.loads(line) for line in (A.RUNS / run / 'graph' / 'nodes.jsonl').open()]
        raw_e = [json.loads(line) for line in (A.RUNS / run / 'graph' / 'edges.jsonl').open()]
        nodes, edges, _ = A.load_common(run)
        types = {n['id']: n['type'] for n in raw_n}
        rows.append({'system': name, 'run': run, **gold_typed(run, gold, A.load_common, A.common_usage),
                     **relations('Wukong', nodes, edges, gold, typed=True, field_team=True),
                     **conformance(nodes, [(e['src'], e['dst'], e['label'], e.get('props', {})) for e in raw_e], types),
                     **hallucination(nodes, with_own_articles('Wukong', nodes, common_docs(name, run, raw_n), gold),
                                     typed=True)})
    for name in UNTYPED:
        nodes, edges, _ = A.SYSTEMS[name]()
        rows.append({'system': name, 'run': name, **gold_untyped(name),
                     **relations(name, nodes, edges, gold, typed=False, field_team=False),
                     **hallucination(nodes, with_own_articles(name, nodes, untyped_docs(name, nodes), gold),
                                     typed=False)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / 'runs.csv', index=False)
    num = df.select_dtypes('number').columns
    summary = df.groupby('system', sort=False)[list(num)].agg(['mean', 'min', 'max'])
    summary.to_csv(OUT / 'summary.csv')
    with pd.option_context('display.width', 250, 'display.max_columns', 40):
        print(df.drop(columns=['run']).groupby('system', sort=False).mean(numeric_only=True).round(1).T)
    write_tex(df)


def write_tex(df: pd.DataFrame) -> None:
    def cell(sys, col, fmt='{:.0f}', pct=False):
        v = df[df.system == sys][col].dropna()
        if v.empty:
            return '--'
        return fmt.format(v.mean()) + (r'\%' if pct else '')  # spread across builds: runs/quality/summary.csv

    order = ['Wukong s5', 'Neo4j-GraphRAG', 'LlamaIndex', 'OntoGPT', 'LightRAG', 'GraphRAG', 'KGGen']
    label = {'Wukong s5': r'\wk{}', 'Neo4j-GraphRAG': 'Neo4j GraphRAG'}
    lines = []
    for s in order:
        lines.append(' & '.join([label.get(s, s),
                                 cell(s, 'ent_precision'), cell(s, 'ent_recall'), cell(s, 'ent_f1'),
                                 cell(s, 'rel_precision'), cell(s, 'rel_recall'), cell(s, 'rel_f1'),
                                 cell(s, 'attr_precision'), cell(s, 'attr_recall'), cell(s, 'attr_f1'),
                                 cell(s, 'sv_precision'), cell(s, 'sv_recall'), cell(s, 'sv_f1'),
                                 cell(s, 'edges_conforming_pct', '{:.1f}'), cell(s, 'constrained_conforming_pct'),
                                 cell(s, 'entities_unsupported_pct', '{:.1f}'), cell(s, 'values_unsupported_pct', '{:.1f}')]) + r' \\')
        if s == 'OntoGPT':
            lines.append(r'\midrule')
    (HERE / 'report' / 'nba_quality_table.tex').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
