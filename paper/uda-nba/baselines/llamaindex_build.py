"""Build a LlamaIndex property graph (SchemaLLMPathExtractor + PropertyGraphIndex)
over (a subset of) the UDA-Bench NBA corpus, with our schema translated into the
tool's own schema slots, and export it to nodes/edges JSONL.

Versions: llama-index-core 0.14.25, llama-index-llms-openai 0.8.2,
llama-index-embeddings-openai 0.7.0 (envs/llamaindex). LLM: gpt-5.6-luna,
reasoning_effort=low.

Why a typed schema class instead of the stock property slots. The stock
SchemaLLMPathExtractor takes possible_entity_props / possible_relation_props as
(name, description) pairs and asks the model for `properties: Dict[str, Any]`.
With gpt-5.6-luna both stock routes fail:
  * llama-index-llms-openai sends gpt-5* structured predictions as Chat Completions
    with a strict json_schema response_format. A Dict field becomes
    `additionalProperties: true`, which the API rejects (400 "'additionalProperties'
    is required to be supplied and to be false"). With allow_additional_properties=False
    the request goes through, but `properties` is then an object with no allowed keys,
    so no property can ever be filled (smoke test: zero properties).
  * Function calling (pydantic_program_mode=FUNCTION) is rejected for this model
    together with reasoning_effort (400 "Function tools with reasoning_effort are not
    supported for gpt-5.6-luna in /v1/chat/completions").
So we pass kg_schema_cls: the same Entity/Relation/Triplet/KGSchema models the stock
extractor builds (same names, same field descriptions), except that `properties` is a
sub-model with one Optional[str] field per property, described by the property's
description. A small subclass turns that sub-model back into the dict the stock
pruning/insert code expects. Everything else is stock: default extraction prompt,
SentenceSplitter(1024, 20), max_triplets_per_chunk=10, strict=True, name-only node
ids with the store's overwrite semantics, SimplePropertyGraphStore. KG nodes are not
embedded (embed_kg_nodes=False): we only need the graph, not retrieval.

Slot rule: every key of the knowledge model goes into the tool's matching slot if one
exists, never into another one; mapping.md (written to the run dir) lists each key.

Every LLM call's raw usage (incl. cached and reasoning tokens) is appended to
usage.jsonl via an instrumentation handler.

    set -a; source ../../../.env; set +a
    envs/llamaindex/bin/python baselines/llamaindex_build.py \\
        --data runs/x6-pilot-data --out runs/llamaindex-pilot
"""

import argparse
import json
import logging
import time
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, create_model

from llama_index.core import Document, PropertyGraphIndex
from llama_index.core.graph_stores import SimplePropertyGraphStore
from llama_index.core.graph_stores.types import (
    ChunkNode,
    EntityNode,
    KG_NODES_KEY,
    KG_RELATIONS_KEY,
)
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.core.instrumentation import get_dispatcher
from llama_index.core.instrumentation.event_handlers import BaseEventHandler
from llama_index.core.instrumentation.events.llm import LLMChatEndEvent
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from llama_index.llms.openai import OpenAI

HERE = Path(__file__).resolve().parent.parent
KM_PATH = HERE / 'workspace-v1' / 'knowledge_model.json'
TYPES = ('player', 'team', 'city', 'owner')
TRIPLET_SOURCE_KEY = 'triplet_source_id'


def upper(name: str) -> str:
    """Stock label convention: the stock validator upper-cases types (spaces -> _)."""
    out = ''
    for i, c in enumerate(name):
        if c.isupper() and i and not name[i - 1].isupper():
            out += '_'
        out += c.upper()
    return out


# ---------------------------------------------------------------- schema translation
def translate(km: dict):
    """Our knowledge model -> the extractor's slots (see module docstring)."""
    ents = km['entity_types']
    rels = km['relationship_types']
    ent_label = {t: upper(t) for t in ents}            # Player -> PLAYER
    rel_label = {r: upper(r) for r in rels}            # PlaysFor -> PLAYS_FOR
    key_field = {t: e['primary_key'] for t, e in ents.items()}

    def props(fields_by_owner):
        """Flat union of fields -> {name: [descriptions]} (stock: one flat list)."""
        out: dict[str, list[str]] = {}
        for _, fields in fields_by_owner:
            for fname, f in (fields or {}).items():
                d = out.setdefault(fname, [])
                if f.get('description') and f['description'] not in d:
                    d.append(f['description'])
        return out

    ent_props = props(
        (t, {k: v for k, v in e['fields'].items() if k != key_field[t]}) for t, e in ents.items()
    )
    rel_props = props((r, rt.get('fields')) for r, rt in rels.items())
    triples = [
        (ent_label[s], rel_label[r], ent_label[o])
        for r, rt in rels.items()
        for s, tgts in rt['endpoints'].items()
        for o in tgts
    ]
    return ent_label, rel_label, key_field, ent_props, rel_props, triples


def build_schema_cls(ent_labels, rel_labels, ent_props, rel_props):
    """Mirror of core/indices/property_graph/transformations/utils.py get_entity_class /
    get_relation_class, with `properties` typed instead of Dict[str, Any]."""
    E = Literal[tuple(ent_labels)]  # type: ignore[valid-type]
    R = Literal[tuple(rel_labels)]  # type: ignore[valid-type]

    def desc_lines(p):  # stock: "Property label `k` with description (v)"
        return [f'Property label `{k}` with description ({" / ".join(v)})' for k, v in p.items()]

    EntityProps = create_model(
        'EntityProperties',
        **{k: (Optional[str], Field(None, description=' / '.join(v))) for k, v in ent_props.items()},
    )
    RelationProps = create_model(
        'RelationProperties',
        **{k: (Optional[str], Field(None, description=' / '.join(v))) for k, v in rel_props.items()},
    )
    Entity = create_model(
        'Entity',
        type=(E, Field(..., description='Entity in a knowledge graph. Only extract entities with '
                                        'types that are listed as valid: ' + str(E))),
        name=(str, ...),
        properties=(Optional[EntityProps], Field(  # type: ignore[valid-type]
            None, description='Properties of the entity. Only extract the following valid '
                              'properties: ' + '\n'.join(desc_lines(ent_props)))),
    )
    Relation = create_model(
        'Relation',
        type=(R, Field(..., description='Relation in a knowledge graph. Only extract relations '
                                        'with types that are listed as valid: ' + str(R))),
        properties=(Optional[RelationProps], Field(  # type: ignore[valid-type]
            None, description='Properties of the relation. Only extract the following valid '
                              'properties: ' + '\n'.join(desc_lines(rel_props)))),
    )
    Triplet = create_model('Triplet', subject=(Entity, ...), relation=(Relation, ...), object=(Entity, ...))
    KGSchema = create_model('KGSchema', triplets=(List[Triplet], ...))  # type: ignore[valid-type]
    KGSchema.__doc__ = 'Knowledge Graph Schema.'
    return KGSchema


# ---------------------------------------------------------------- extractor + counters
STATS = {'chunks_extracted': 0, 'chunks_error': 0, 'chunks_empty': 0, 'errors': []}


class TypedSchemaLLMPathExtractor(SchemaLLMPathExtractor):
    """Stock extractor; typed properties are converted back to plain dicts."""

    def _prune_invalid_triplets(self, kg_schema):
        def d(x):
            p = x.properties
            return {k: v for k, v in p.model_dump().items() if v is not None} if p is not None else {}

        conv = SimpleNamespace(triplets=[
            SimpleNamespace(
                subject=SimpleNamespace(name=t.subject.name, type=t.subject.type, properties=d(t.subject)),
                relation=SimpleNamespace(type=t.relation.type, properties=d(t.relation)),
                object=SimpleNamespace(name=t.object.name, type=t.object.type, properties=d(t.object)),
            )
            for t in kg_schema.triplets
        ])
        return super()._prune_invalid_triplets(conv)

    async def _aextract(self, node):
        # Stock catches ValueError/TypeError/AttributeError (logged, counted by
        # ErrorCounter below); anything else (e.g. an API error after retries) would
        # abort the whole build, so we count it and leave the chunk empty instead.
        try:
            node = await super()._aextract(node)
        except Exception as e:  # noqa: BLE001
            STATS['chunks_error'] += 1
            STATS['errors'].append(f'{node.ref_doc_id}: {type(e).__name__}: {e}'[:500])
            node.metadata[KG_NODES_KEY] = []
            node.metadata[KG_RELATIONS_KEY] = []
        STATS['chunks_extracted'] += 1
        if not node.metadata.get(KG_RELATIONS_KEY):
            STATS['chunks_empty'] += 1
        return node


class ErrorCounter(logging.Handler):
    def emit(self, record):
        if 'Error during extraction' in record.getMessage():
            STATS['chunks_error'] += 1
            STATS['errors'].append(record.getMessage()[:500])


class UsageHandler(BaseEventHandler):
    path: str

    @classmethod
    def class_name(cls) -> str:
        return 'UsageHandler'

    def handle(self, event, **kwargs):
        if not isinstance(event, LLMChatEndEvent) or event.response is None:
            return
        u = getattr(event.response.raw, 'usage', None)
        if u is None:
            return
        ptd, ctd = u.prompt_tokens_details, u.completion_tokens_details
        rec = {
            'input': u.prompt_tokens,
            'cached': (getattr(ptd, 'cached_tokens', 0) or 0) if ptd else 0,
            'output': u.completion_tokens,
            'reasoning': (getattr(ctd, 'reasoning_tokens', 0) or 0) if ctd else 0,
        }
        with open(self.path, 'a') as f:
            f.write(json.dumps(rec) + '\n')


# ---------------------------------------------------------------- mapping.md
def write_mapping(km: dict, path: Path, ent_label, rel_label) -> None:
    rows = []

    def row(key, where):
        rows.append(f'| `{key}` | {where} |')

    def walk_cfg(d, prefix):
        for k, v in d.items():
            if isinstance(v, dict):
                walk_cfg(v, f'{prefix}.{k}')
            else:
                row(f'{prefix}.{k}', 'no slot (dropped)')

    walk_cfg(km.get('extraction_config', {}), 'extraction_config')
    for t, e in km['entity_types'].items():
        p = f'entity_types.{t}'
        row(p, f'`possible_entities` / `Entity.type` Literal value `{ent_label[t]}`')
        for k in e:
            if k == 'fields':
                continue
            row(f'{p}.{k}', {
                'primary_key': f'`Entity.name` (the key field `{e[k]}` is the node name)',
            }.get(k, 'no slot (dropped)'))
        for fname, f in e['fields'].items():
            fp = f'{p}.fields.{fname}'
            is_key = fname == e['primary_key']
            row(fp, '`Entity.name`' if is_key else
                f'entity property `{fname}` (flat union over all entity types)')
            for k in f:
                if k == 'description':
                    where = 'no slot (`Entity.name` has no description)' if is_key else \
                        f'description of property `{fname}` (Field description; joined with " / " if several types share the name)'
                elif k == 'data_type':
                    where = '`str` (Entity.name)' if is_key else 'property type `Optional[str]`'
                else:
                    where = 'no slot (dropped)'
                row(f'{fp}.{k}', where)
    for r, rt in km['relationship_types'].items():
        p = f'relationship_types.{r}'
        row(p, f'`possible_relations` / `Relation.type` Literal value `{rel_label[r]}`')
        for k in rt:
            if k == 'fields':
                continue
            row(f'{p}.{k}', '`kg_validation_schema` triples (endpoint types only; context levels dropped)'
                if k == 'endpoints' else 'no slot (dropped)')
        for fname, f in (rt.get('fields') or {}).items():
            fp = f'{p}.fields.{fname}'
            row(fp, f'relation property `{fname}` (flat union over all relation types)')
            for k in f:
                row(f'{fp}.{k}', {
                    'description': f'description of property `{fname}` (Field description)',
                    'data_type': 'property type `Optional[str]`',
                }.get(k, 'no slot (dropped)'))
    path.write_text(
        '# Knowledge model -> LlamaIndex SchemaLLMPathExtractor\n\n'
        'Every key of `workspace-v1/knowledge_model.json` (dict-valued keys such as '
        '`instructions` or `retrieval_mode` are listed as one key).\n\n'
        '| key | slot in the tool |\n|---|---|\n' + '\n'.join(rows) + '\n'
    )


# ---------------------------------------------------------------- main
def list_docs(data: Path) -> list[tuple[str, Path]]:
    return [
        (f'{t}/{p.stem}', p)
        for t in TYPES
        for p in sorted((data / t / t).glob('*.txt'), key=lambda p: int(p.stem))
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, required=True, help='dir with {player,team,city,owner}/{type}/N.txt')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--model', default='gpt-5.6-luna')
    ap.add_argument('--reasoning-effort', default='low')
    ap.add_argument('--num-workers', type=int, default=16, help='concurrent extraction calls')
    args = ap.parse_args()

    out = args.out
    (out / 'graph').mkdir(parents=True, exist_ok=True)
    usage_path = out / 'usage.jsonl'
    usage_path.unlink(missing_ok=True)

    km = json.loads(KM_PATH.read_text())
    ent_label, rel_label, key_field, ent_props, rel_props, triples = translate(km)
    write_mapping(km, out / 'mapping.md', ent_label, rel_label)
    kg_schema_cls = build_schema_cls(list(ent_label.values()), list(rel_label.values()), ent_props, rel_props)
    (out / 'kg_schema.json').write_text(json.dumps(kg_schema_cls.model_json_schema(), indent=1))

    get_dispatcher().add_event_handler(UsageHandler(path=str(usage_path)))
    logging.getLogger('llama_index.core.indices.property_graph.transformations.schema_llm') \
        .addHandler(ErrorCounter())

    # timeout/max_retries only make the run robust to slow or throttled calls; they
    # do not change what is extracted
    llm_settings = dict(model=args.model, reasoning_effort=args.reasoning_effort or None,
                        timeout=300.0, max_retries=5)
    llm = OpenAI(**llm_settings)
    extractor = TypedSchemaLLMPathExtractor(
        llm=llm,
        kg_schema_cls=kg_schema_cls,
        kg_validation_schema=triples,
        possible_entity_props=list(ent_props),
        possible_relation_props=list(rel_props),
        strict=True,
        num_workers=args.num_workers,
    )

    docs = [Document(text=p.read_text(), id_=doc_id) for doc_id, p in list_docs(args.data)]
    print(f'{len(docs)} docs', flush=True)
    store = SimplePropertyGraphStore()
    t0 = time.time()
    PropertyGraphIndex.from_documents(
        docs,
        llm=llm,
        kg_extractors=[extractor],
        property_graph_store=store,
        transformations=[SentenceSplitter()],
        embed_kg_nodes=False,
        use_async=True,
        show_progress=True,
    )
    wall = time.time() - t0
    store.persist(str(out / 'property_graph_store.json'))

    # ---- export
    g = store.graph
    valid_ent = {f for t, e in km['entity_types'].items() for f in e['fields']}
    valid_rel = {f for rt in km['relationship_types'].values() for f in (rt.get('fields') or {})}
    from_ent = {v: k for k, v in ent_label.items()}
    from_rel = {v: k for k, v in rel_label.items()}
    stripped: dict[str, int] = {}

    def split_props(props, valid):
        attrs, chunks = {}, []
        for k, v in props.items():
            if k == TRIPLET_SOURCE_KEY:
                chunks.append(v)
            elif k in valid:
                attrs[k] = v
            else:
                stripped[k] = stripped.get(k, 0) + 1
        return attrs, chunks

    n_nodes = n_edges = 0
    chunk_rows = []
    with (out / 'graph' / 'nodes.jsonl').open('w') as f:
        for n in g.nodes.values():
            if isinstance(n, ChunkNode):
                chunk_rows.append({'id': n.id, 'doc': n.properties.get('ref_doc_id'), 'text': n.text})
                continue
            if not isinstance(n, EntityNode):
                continue
            typ = from_ent.get(n.label, n.label)
            attrs, chunks = split_props(dict(n.properties), valid_ent)
            if typ in key_field:
                attrs[key_field[typ]] = n.name
            f.write(json.dumps({'id': n.id, 'type': typ, 'name': n.name, 'attrs': attrs, 'chunks': chunks}) + '\n')
            n_nodes += 1
    with (out / 'graph' / 'edges.jsonl').open('w') as f:
        for r in g.relations.values():
            props, chunks = split_props(dict(r.properties), valid_rel)
            f.write(json.dumps({'src': r.source_id, 'dst': r.target_id,
                                'label': from_rel.get(r.label, r.label), 'props': props, 'chunks': chunks}) + '\n')
            n_edges += 1
    with (out / 'graph' / 'chunks.jsonl').open('w') as f:
        for c in chunk_rows:
            f.write(json.dumps(c) + '\n')

    calls = [json.loads(line) for line in usage_path.read_text().splitlines()] if usage_path.exists() else []
    meta = {
        'tool': 'llama-index SchemaLLMPathExtractor + PropertyGraphIndex',
        'versions': {p: version(p) for p in ('llama-index-core', 'llama-index-llms-openai',
                                             'llama-index-embeddings-openai', 'openai', 'pydantic')},
        'why_typed_schema_cls': (
            'Stock possible_entity_props/possible_relation_props yield properties: Dict[str, Any]. '
            'With gpt-5.6-luna the OpenAI LLM uses a strict json_schema response_format: '
            "allow_additional_properties=True -> 400 \"'additionalProperties' is required to be supplied "
            "and to be false\"; allow_additional_properties=False -> request succeeds but properties can only "
            'be {} (never filled). pydantic_program_mode=FUNCTION -> 400 "Function tools with reasoning_effort '
            'are not supported for gpt-5.6-luna in /v1/chat/completions". So kg_schema_cls mirrors the stock '
            'models with properties typed as Optional[str] fields described by the field description.'),
        'settings': {
            'llm': {**llm_settings, 'api': 'chat.completions, strict json_schema response_format'},
            'extract_prompt': 'stock DEFAULT_SCHEMA_PATH_EXTRACT_PROMPT',
            'max_triplets_per_chunk': extractor.max_triplets_per_chunk,
            'strict': True,
            'num_workers': args.num_workers,
            'node_parser': f'SentenceSplitter(chunk_size={DEFAULT_CHUNK_SIZE}, chunk_overlap={DEFAULT_CHUNK_OVERLAP})',
            'graph_store': 'SimplePropertyGraphStore (in memory; persisted to property_graph_store.json)',
            'embed_kg_nodes': False,
            'embed_kg_nodes_note': 'no embeddings: only the graph is evaluated, retrieval is not used',
            'possible_entities': list(ent_label.values()),
            'possible_relations': list(rel_label.values()),
            'kg_validation_schema': triples,
            'possible_entity_props': list(ent_props),
            'possible_relation_props': list(rel_props),
            'node_identity': 'stock: EntityNode id = name; later upserts overwrite; relations keyed src_label_dst, first wins',
        },
        'data': str(args.data),
        'n_docs': len(docs),
        'n_chunks': len(chunk_rows),
        'n_nodes': n_nodes,
        'n_edges': n_edges,
        'chunks_extracted': STATS['chunks_extracted'],
        'chunks_with_error': STATS['chunks_error'],
        'chunks_without_triplets': STATS['chunks_empty'],
        'errors': STATS['errors'],
        'stripped_property_keys': stripped,
        'llm_calls': len(calls),
        'tokens': {k: sum(c[k] for c in calls) for k in ('input', 'cached', 'output', 'reasoning')},
        'wall_seconds': round(wall, 1),
    }
    (out / 'meta.json').write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: meta[k] for k in ('n_docs', 'n_chunks', 'n_nodes', 'n_edges', 'llm_calls',
                                           'tokens', 'chunks_with_error', 'wall_seconds')}), flush=True)


if __name__ == '__main__':
    main()
