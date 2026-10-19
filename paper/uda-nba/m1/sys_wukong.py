"""M1, Wukong: its graph in an embedded Cypher database (Kuzu), queried by an LLM agent that writes Cypher.

The graph is E1's full-schema run 1 (s4), as exported by the engine (exports/neo4j); its domain nodes and edges
are loaded into Kuzu with every value a string (fields are strings in Wukong; queries cast where needed). The
agent sees the graph schema derived from the extraction schema (types, fields with their descriptions,
relationship types with their endpoints) and the same question and answer keys as every system. It writes one
Cypher query whose RETURN columns are the answer keys; the harness runs it and returns the rows. If the query
fails, or returns no rows, the agent sees that and may write another one: at most 4 LLM calls per question.
The rows of the last query that ran are the answer.

Writes work/answers/wukong/<uid>.json and logs usage to work/usage/wukong.jsonl.
"""

import argparse
import csv
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import kuzu
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from common import SCOPE, SHARE, WORK, answer_keys, chat, load_queries, load_questions  # noqa: E402
from sys_floor import pilot_uids  # noqa: E402

RUN = SHARE / 'wukong-e1-r1'
DB = WORK / 'kuzu' / 'wukong.kz'
ATTEMPTS = 4


def clean_csv(src: Path, dst: Path, drop_prefix: tuple[str, ...]) -> list[str]:
    """Neo4j import CSV -> plain CSV for Kuzu: strip ':type' suffixes, drop internal and provenance columns."""
    with src.open() as f, dst.open('w', newline='') as g:
        reader, writer = csv.reader(f), csv.writer(g)
        header = next(reader)
        names = [h.split(':')[0] if not h.startswith(':') else h[1:].split('_')[0].lower() for h in header]
        keep = [i for i, n in enumerate(names) if not n.startswith(drop_prefix) or n in ('_id', 'start', 'end')]
        names = ['uid' if n == '_id' else n for n in names]  # Kuzu reserves _id
        writer.writerow([names[i] for i in keep])
        for row in reader:
            writer.writerow([row[i] if i < len(row) else '' for i in keep])
    return [names[i] for i in keep]


def load_graph(km: dict) -> kuzu.Connection:
    if DB.parent.exists():
        shutil.rmtree(DB.parent)
    DB.parent.mkdir(parents=True)
    conn = kuzu.Connection(kuzu.Database(str(DB)))
    tmp = DB.parent / 'csv'
    tmp.mkdir()
    exports = RUN / 'exports' / 'neo4j'
    for name in km['entity_types']:
        cols = clean_csv(exports / 'entities' / f'{name}.csv', tmp / f'{name}.csv', ('_',))
        props = ', '.join(f'{c} STRING' for c in cols if c != 'uid')
        conn.execute(f'CREATE NODE TABLE {name}(uid STRING, {props}, PRIMARY KEY(uid))')
        conn.execute(f'COPY {name} FROM "{tmp / (name + ".csv")}" (header=true)')
    # Provenance the engine exports natively: an entity extracted from a whole document (document level) is linked
    # to that Document; under this schema's bindings it is the subject of the article. Chunk-level links are omitted.
    docs = {r['_id:ID']: Path(r['source_uri:string']).parts[-3] for r in csv.DictReader((exports / 'entities' / 'Document.csv').open())}
    with (tmp / 'Document.csv').open('w', newline='') as g:
        w = csv.writer(g)
        w.writerow(['uid', 'collection'])
        w.writerows(docs.items())
    conn.execute('CREATE NODE TABLE Document(uid STRING, collection STRING, PRIMARY KEY(uid))')
    conn.execute(f'COPY Document FROM "{tmp / "Document.csv"}" (header=true)')
    ids = {name: {r['_id:ID'] for r in csv.DictReader((exports / 'entities' / f'{name}.csv').open())} for name in km['entity_types']}
    pairs = ', '.join(f'FROM {name} TO Document' for name in km['entity_types'])
    conn.execute(f'CREATE REL TABLE ExtractedFrom({pairs})')
    links = [(r[':START_ID'], r[':END_ID']) for r in csv.DictReader((exports / 'relationships' / 'ExtractedFrom.csv').open()) if r[':END_ID'] in docs]
    for name in km['entity_types']:
        part = tmp / f'ExtractedFrom_{name}.csv'
        with part.open('w', newline='') as g:
            w = csv.writer(g)
            w.writerow(['from', 'to'])
            w.writerows([l for l in links if l[0] in ids[name]])
        conn.execute(f'COPY ExtractedFrom FROM "{part}" (header=true, from="{name}", to="Document")')
    for name, rt in km['relationship_types'].items():
        (src, targets), = rt['endpoints'].items()
        (dst, _), = targets.items()
        cols = clean_csv(exports / 'relationships' / f'{name}.csv', tmp / f'{name}.csv', ('_',))
        props = ''.join(f', {c} STRING' for c in cols if c not in ('start', 'end', 'uid'))
        conn.execute(f'CREATE REL TABLE {name}(FROM {src} TO {dst}{props})')
        # Kuzu reads the first two columns as FROM/TO keys; the rest must match the table's properties
        rows = list(csv.reader((tmp / f'{name}.csv').open()))
        keep = [i for i, c in enumerate(rows[0]) if c != 'uid']
        with (tmp / f'{name}.rel.csv').open('w', newline='') as g:
            csv.writer(g).writerows([[r[i] for i in keep] for r in rows])
        conn.execute(f'COPY {name} FROM "{tmp / (name + ".rel.csv")}" (header=true)')
    return conn


def schema_text(km: dict) -> str:
    """The graph schema the agent sees: what the extraction schema says about the graph (no extraction hints)."""
    lines = ['Node types (every property value is a string; a missing value is null):']
    for name, et in km['entity_types'].items():
        lines.append(f'- {name}: {et.get("description", "")}')
        for f, fd in et['fields'].items():
            lines.append(f'    {f}: {fd.get("description", "")}')
    lines.append('- Document: an article of the collection; collection is one of player, team, city, owner.')
    lines.append('Relationship types (direction as written):')
    lines.append('- (:Player|Team|City|Owner)-[:ExtractedFrom]->(:Document): the entity was extracted from the whole '
                 'article, so it is the subject of that article (the player, team, city or owner the article is about).')
    for name, rt in km['relationship_types'].items():
        (src, targets), = rt['endpoints'].items()
        (dst, _), = targets.items()
        lines.append(f'- (:{src})-[:{name}]->(:{dst}): {rt.get("description", "")}')
        for f, fd in rt.get('fields', {}).items():
            lines.append(f'    {f}: {fd.get("description", "")}' + (f' One of: {fd["options"]}.' if fd.get('options') else ''))
    return '\n'.join(lines)


SYSTEM = """You answer questions by querying a knowledge graph with Cypher, in the Kuzu dialect.

{schema}

Kuzu notes: all property values are strings, so cast before comparing or aggregating numbers, e.g.
CAST(p.draft_pick AS INT64) or CAST(c.area AS DOUBLE); CAST of null gives null. Dates are strings like 1998/3/3.
Today is {today}. Use OPTIONAL MATCH when a related node may be missing. Name every returned column with AS.

Reply with only a JSON object {{"cypher": "<one Cypher query>"}}. The query's RETURN columns must be exactly the
answer keys you are given, with those names, one row per answer item."""


def run_cypher(conn: kuzu.Connection, cypher: str) -> tuple[list[dict] | None, str | None]:
    try:
        res = conn.execute(cypher)
        cols = res.get_column_names()
        rows = []
        while res.has_next():
            rows.append(dict(zip(cols, res.get_next(), strict=True)))
        return rows, None
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:500]


def answer(client, conn, system: str, q: dict, query: dict, usage: str = 'wukong') -> dict:
    keys = '\n'.join(f'- "{k}": {m}' for k, m in answer_keys(query, q['meanings']))
    messages = [{'role': 'system', 'content': system},
                {'role': 'user', 'content': f'{SCOPE}\n\nQuestion: {q["question"]}\n\nAnswer keys (RETURN columns):\n{keys}'}]
    rows, trace = None, []
    for attempt in range(ATTEMPTS):
        reply = chat(client, messages, WORK / 'usage' / f'{usage}.jsonl', 'agent', response_format={'type': 'json_object'})
        try:
            cypher = json.loads(reply)['cypher']
        except (json.JSONDecodeError, KeyError, TypeError):
            messages += [{'role': 'assistant', 'content': reply}, {'role': 'user', 'content': 'Reply with {"cypher": "..."} only.'}]
            trace.append({'attempt': attempt + 1, 'error': 'unparsable reply'})
            continue
        result, error = run_cypher(conn, cypher)
        trace.append({'attempt': attempt + 1, 'cypher': cypher, 'error': error, 'rows': None if result is None else len(result)})
        if result is not None:
            rows = result
        if error:
            feedback = f'The query failed: {error}\nWrite a corrected query.'
        elif not result and attempt < ATTEMPTS - 1:
            feedback = ('The query returned no rows. If the answer is really empty, send the same query again; '
                        'otherwise write a corrected one.')
        else:
            break
        messages += [{'role': 'assistant', 'content': reply}, {'role': 'user', 'content': feedback}]
        if not error and not result and len(trace) >= 2 and trace[-1].get('cypher') == trace[-2].get('cypher'):
            break  # the agent confirmed an empty answer
    return {'uid': q['uid'], 'rows': rows, 'trace': trace}


def main() -> int:
    global RUN, DB
    ap = argparse.ArgumentParser()
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--reload', action='store_true', help='rebuild the Kuzu database from the export')
    ap.add_argument('--run', type=Path, help='another Wukong run directory (default: the share\'s E1 run 1)')
    ap.add_argument('--name', default='wukong', help='system name: answers/<name>/, usage/<name>.jsonl')
    ap.add_argument('--today', help='the date the agent is told (default: today)')
    args = ap.parse_args()
    if args.run:
        RUN = args.run
    if args.name != 'wukong':
        DB = WORK / 'kuzu' / args.name / 'graph.kz'
    km = json.loads((RUN / 'knowledge_model.json').read_text())
    conn = load_graph(km) if args.reload or not DB.exists() else kuzu.Connection(kuzu.Database(str(DB)))
    system = SYSTEM.format(schema=schema_text(km), today=args.today or date.today().isoformat())
    (WORK / f'{args.name}_system_prompt.txt').write_text(system)
    queries = {q['uid']: q for q in load_queries()}
    questions = load_questions()
    uids = pilot_uids(questions) if args.pilot else list(questions)
    client = OpenAI()
    out = WORK / 'answers' / args.name
    out.mkdir(parents=True, exist_ok=True)
    for u in uids:
        f = out / f'{u.replace("#", "_")}.json'
        if not f.exists():
            f.write_text(json.dumps(answer(client, conn, system, questions[u], queries[u], usage=args.name),
                                    indent=1, default=str))
    print(f'{args.name}: {len(uids)} questions answered')
    return 0


if __name__ == '__main__':
    sys.exit(main())
