"""M1, the schema-based extractors: their graphs in Kuzu, queried by Wukong's Cypher agent.

Neo4j's neo4j-graphrag, LlamaIndex's SchemaLLMPathExtractor and OntoGPT's SPIRES built typed graphs over the same
corpus from the same extraction schema (workspace-x6-s4; baselines/*_build.py, graph/nodes.jsonl and
graph/edges.jsonl in each run). Each graph is loaded into Kuzu like Wukong's: one node table per entity type, one
relationship table per relationship type, every value a string. The agent is sys_wukong.answer, unchanged (same
prompt, same 4 attempts), and sees the same schema text, built from the same extraction schema. Only what links
entities to articles differs, and each graph gets what its tool records:

  - OntoGPT extracts one root object per article, its subject: (entity)-[:ExtractedFrom]->(:Document), with the
    same description as Wukong's document-level link.
  - neo4j-graphrag and LlamaIndex record the chunk each entity was extracted from (neo4j-graphrag's lexical graph,
    LlamaIndex's triplet_source_id), and no subject: (entity)-[:MentionedIn]->(:Document) for every article with
    such a chunk. OntoGPT gets it too, from the articles each object was extracted from.

Properties a tool filled outside the schema (LlamaIndex gives some nodes fields of another type) are kept as
columns and listed after the schema fields. Edges whose endpoint types do not match the relationship type are not
loaded (counted in the log).

    python sys_typed.py neo4j|llamaindex|ontogpt [--pilot] [--reload]

Writes work/answers/<system>/<uid>.json and logs usage to work/usage/<system>.jsonl.
"""

import argparse
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import kuzu
import pandas as pd
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from common import WORK, load_queries, load_questions  # noqa: E402
from sys_floor import pilot_uids  # noqa: E402
from sys_wukong import SYSTEM, answer, schema_text  # noqa: E402

RUNS = Path(os.environ.get('UDA_NBA_RUNS', Path(__file__).resolve().parent.parent / 'runs'))
KM = Path(__file__).resolve().parent.parent / 'workspace-x6-s4' / 'knowledge_model.json'
GRAPHS = {'neo4j': 'neo4j-graphrag-s4-r1', 'llamaindex': 'llamaindex-s4-r1', 'ontogpt': 'ontogpt-s4-r1'}

SUBJECT = ('- (:Player|Team|City|Owner)-[:ExtractedFrom]->(:Document): the entity was extracted from the whole '
           'article, so it is the subject of that article (the player, team, city or owner the article is about).')
MENTION = ('- (:Player|Team|City|Owner)-[:MentionedIn]->(:Document): the entity was extracted from a passage of that '
           'article (it is mentioned there; it is not necessarily what the article is about).')


def documents(system: str, run: Path, nodes: list[dict], km: dict) -> tuple[dict, dict]:
    """(node id -> articles it was extracted from, node id -> the article it is the subject of)."""
    mentions, subject = defaultdict(set), {}
    if system == 'neo4j':  # chunk ids are '<collection>/<n>#<chunk>'
        for n in nodes:
            mentions[n['id']] = {c.split('#')[0] for c in n.get('chunks', [])}
    elif system == 'llamaindex':  # chunk ids are uuids; chunks.jsonl maps them to articles
        doc = {c['id']: c['doc'] for c in map(json.loads, (run / 'graph' / 'chunks.jsonl').open())}
        for n in nodes:
            mentions[n['id']] = {doc[c] for c in n.get('chunks', []) if c in doc}
    else:  # ontogpt: per-article output; its root object is the article's subject
        for n in nodes:
            mentions[n['id']] = {d.replace('_', '/') for d in n.get('docs', [])}
        by_name = {(n['type'], n['name']): n['id'] for n in nodes}
        for f in sorted((run / 'raw').glob('*.json')):
            r = json.loads(f.read_text())
            collection = f.stem.split('_')[0]
            t = collection.capitalize()
            root = (r.get('extracted_object') or {}).get(km['entity_types'][t]['primary_key'])
            if root and (t, root) in by_name:
                subject[by_name[(t, root)]] = f.stem.replace('_', '/')
    return mentions, subject


def load_graph(system: str, db: Path, km: dict, run: Path | None = None) -> tuple[kuzu.Connection, dict]:
    run = run or RUNS / GRAPHS[system]
    nodes = [json.loads(line) for line in (run / 'graph' / 'nodes.jsonl').open()]
    edges = [json.loads(line) for line in (run / 'graph' / 'edges.jsonl').open()]
    mentions, subject = documents(system, run, nodes, km)
    if db.parent.exists():
        shutil.rmtree(db.parent)
    db.parent.mkdir(parents=True)
    tmp = db.parent / 'csv'
    tmp.mkdir()
    conn = kuzu.Connection(kuzu.Database(str(db)))

    def val(v):
        """A value as a string; missing or empty is null (as in Wukong's graph, and as the agent is told)."""
        return None if v is None or str(v).strip() == '' else str(v)

    def write(name, header, rows):
        """Parquet, not CSV: Kuzu's CSV reader rejects names with quotes ('Kenneth "Apple" Green')."""
        path = tmp / f'{name}.parquet'
        pd.DataFrame(rows, columns=header, dtype=object).astype({c: 'string' for c in header}).to_parquet(path)
        return path

    for n in nodes:  # the key field holds the entity's name (OntoGPT keeps it only as the label of mentioned objects)
        if n['type'] in km['entity_types']:
            n['attrs'].setdefault(km['entity_types'][n['type']]['primary_key'], n['name'])
    types = {n['id']: n['type'] for n in nodes}
    extra = {}
    for t, et in km['entity_types'].items():
        mine = [n for n in nodes if n['type'] == t]
        cols = list(et['fields']) + sorted({k for n in mine for k in n['attrs']} - set(et['fields']))
        extra[t] = cols[len(et['fields']):]
        conn.execute(f'CREATE NODE TABLE {t}(uid STRING, ' + ', '.join(f'{c} STRING' for c in cols) +
                     ', PRIMARY KEY(uid))')
        path = write(t, ['uid', *cols], [[n['id'], *(val(n['attrs'].get(c))
                                                     for c in cols)] for n in mine])
        conn.execute(f'COPY {t} FROM "{path}"')
    docs = sorted({d for ds in mentions.values() for d in ds} | set(subject.values()))
    conn.execute('CREATE NODE TABLE Document(uid STRING, collection STRING, PRIMARY KEY(uid))')
    conn.execute(f'COPY Document FROM "{write("Document", ["uid", "collection"], [[d, d.split("/")[0]] for d in docs])}"')
    pairs = ', '.join(f'FROM {t} TO Document' for t in km['entity_types'])
    links = {'MentionedIn': [(i, d) for i, ds in mentions.items() for d in sorted(ds)],
             'ExtractedFrom': sorted(subject.items())}
    for rel, pairs_ in links.items():
        if not pairs_:
            continue
        conn.execute(f'CREATE REL TABLE {rel}({pairs})')
        for t in km['entity_types']:
            path = write(f'{rel}_{t}', ['from', 'to'], [p for p in pairs_ if types.get(p[0]) == t])
            conn.execute(f'COPY {rel} FROM "{path}" (from="{t}", to="Document")')
    dropped = 0
    for name, rt in km['relationship_types'].items():
        (src, targets), = rt['endpoints'].items()
        (dst, _), = targets.items()
        mine = [e for e in edges if e['label'] == name]
        ok = [e for e in mine if types.get(e['src']) == src and types.get(e['dst']) == dst]
        dropped += len(mine) - len(ok)
        props = list(rt.get('fields', {})) + sorted({k for e in ok for k in e['props']} - set(rt.get('fields', {})))
        conn.execute(f'CREATE REL TABLE {name}(FROM {src} TO {dst}' + ''.join(f', {p} STRING' for p in props) + ')')
        path = write(name, ['from', 'to', *props], [[e['src'], e['dst'], *(val(e['props'].get(p)) for p in props)]
                                                    for e in ok])
        conn.execute(f'COPY {name} FROM "{path}"')
    info = {'nodes': len(nodes), 'edges_loaded': len(edges) - dropped, 'edges_dropped_wrong_endpoints': dropped,
            'documents': len(docs), 'subject_links': len(subject), 'mention_links': len(links['MentionedIn']),
            'extra_properties': {t: c for t, c in extra.items() if c}}
    (db.parent / 'load.json').write_text(json.dumps(info, indent=1))
    return conn, info


def schema_for(system: str, km: dict, info: dict) -> str:
    """Wukong's schema text, with this graph's links to articles instead of Wukong's, and its extra properties."""
    lines = schema_text(km).splitlines()
    out = []
    for line in lines:
        if line.startswith('- (:Player|Team|City|Owner)-[:ExtractedFrom]'):
            if info['subject_links']:
                out.append(SUBJECT)
            out.append(MENTION)
            continue
        out.append(line)
    for t, cols in info['extra_properties'].items():
        i = next(k for k, line in enumerate(out) if line.startswith(f'- {t}:'))
        n = len(km['entity_types'][t]['fields'])
        out.insert(i + n + 1, f'    (also present on some {t} nodes: {", ".join(cols)})')
    return '\n'.join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('system', choices=list(GRAPHS))
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--reload', action='store_true', help='rebuild the Kuzu database from the graph files')
    ap.add_argument('--run', type=Path, help='another build of the tool (default: its E1 build)')
    ap.add_argument('--schema', type=Path, default=KM, help='the knowledge_model.json the build was made from')
    ap.add_argument('--name', help='system name: answers/<name>/, usage/<name>.jsonl (default: the tool)')
    ap.add_argument('--today', help='the date the agent is told (default: today)')
    args = ap.parse_args()
    name = args.name or args.system
    km = json.loads(args.schema.read_text())
    db = WORK / 'kuzu' / name / 'graph.kz'
    if args.reload or not db.exists():
        conn, info = load_graph(args.system, db, km, args.run)
    else:
        conn, info = kuzu.Connection(kuzu.Database(str(db))), json.loads((db.parent / 'load.json').read_text())
    print(name, info)
    system = SYSTEM.format(schema=schema_for(args.system, km, info), today=args.today or date.today().isoformat())
    (WORK / f'{name}_system_prompt.txt').write_text(system)
    queries = {q['uid']: q for q in load_queries()}
    questions = load_questions()
    uids = pilot_uids(questions) if args.pilot else list(questions)
    client = OpenAI()
    out = WORK / 'answers' / name
    out.mkdir(parents=True, exist_ok=True)
    for u in uids:
        f = out / f'{u.replace("#", "_")}.json'
        if not f.exists():
            f.write_text(json.dumps(answer(client, conn, system, questions[u], queries[u], usage=name),
                                    indent=1, default=str))
    print(f'{name}: {len(uids)} questions answered')
    return 0


if __name__ == '__main__':
    sys.exit(main())
