"""Build a knowledge graph over the UDA-Bench NBA corpus with OntoGPT's SPIRES extractor.

    envs/ontogpt/bin/python baselines/ontogpt_build.py --data data/docs --out runs/ontogpt-full

The LinkML template (baselines/ontogpt_nba.yaml) is generated mechanically from
workspace-v1/knowledge_model.json: each key of our schema goes into the matching
LinkML/OntoGPT slot, or nowhere (see mapping.md in the run dir). There is one
root class per article type (PlayerArticle, TeamArticle, CityArticle,
OwnerArticle), used as the target class (`ontogpt extract -T`) for its collection.

SPIRES runs with its defaults (whole document per call, recursive parsing of
compound objects, AUTO: grounding, no annotators) except:
  - the LLM call gets reasoning_effort (OntoGPT has no option for it) and litellm
    caching is off (OntoGPT hardcodes it on);
  - term validation is off (--no-validate-terms), as there are no ontologies;
  - `pattern` (our regex) stays in the template but is not enforced: OntoGPT turns it
    into pydantic validators, and one non-matching value rejects the whole document
    (ValidationError). With enforcement 0/8 pilot documents survived; --enforce-patterns
    restores it;
  - each document gets a fresh engine, so input_id is set and OntoGPT's
    process-wide named-entity cache does not leak across documents;
  - documents run concurrently in threads, one document per thread.

Output in --out:
  raw/<type>_<n>.json   OntoGPT's ExtractionResult per document
  graph/nodes.jsonl     {id, type, name, attrs, docs}; ids are OntoGPT's AUTO: ids
  graph/edges.jsonl     {src, dst, label, props, docs}
  usage.jsonl           one line per LLM call
  meta.json, mapping.md, ontogpt_nba.yaml
"""

import argparse
import json
import platform
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote

import inflection
import yaml

HERE = Path(__file__).parent
UDA = HERE.parent
TYPES = {'player': 'Player', 'team': 'Team', 'city': 'City', 'owner': 'Owner'}
MULTI_PREFIX = 'semicolon-separated list of '
TEMPLATE_NAME = 'ontogpt_nba'  # unique basename: OntoGPT copies the file into its templates package

# Binding of our relationship types to article root classes, mirroring the endpoints
# of knowledge_model.json (Player->Team, Team->City, Owner->Team, each binding
# document level on either side). Each entry: (root type, slot, relationship,
# other endpoint type, our type is the relationship's source).
BINDINGS = [
    ('Player', 'plays_for', 'PlaysFor', 'Team', True),
    ('Team', 'players', 'PlaysFor', 'Player', False),
    ('Team', 'located_in', 'LocatedIn', 'City', True),
    ('Team', 'owned_by', 'Owns', 'Owner', False),
    ('City', 'teams', 'LocatedIn', 'Team', False),
    ('Owner', 'owns', 'Owns', 'Team', True),
]


# ---------------------------------------------------------------- template

def _field_slot(field: dict, enum_name: str, enums: dict, notes: list, where: str) -> dict:
    """Map one field of our schema to a LinkML attribute (strictly key by key)."""
    slot: dict = {}
    for key, value in field.items():
        if key == 'data_type':
            slot['range'] = value
            notes.append((f'{where}.data_type', 'range'))
        elif key == 'description':
            slot['description'] = value
            notes.append((f'{where}.description', 'description'))
        elif key == 'instructions':
            slot['annotations'] = {'prompt': value}
            notes.append((f'{where}.instructions', 'annotations: prompt'))
        elif key == 'examples':
            slot['examples'] = [{'value': v} for v in value]
            notes.append((f'{where}.examples', 'examples'))
        elif key == 'options':
            enums[enum_name] = {'permissible_values': {v: {} for v in value}}
            slot['range'] = enum_name
            notes.append((f'{where}.options', f'range: enum {enum_name}'))
        elif key == 'regex':
            slot['pattern'] = value
            notes.append((f'{where}.regex', 'pattern'))
        elif key == 'required':
            slot['required'] = value
            notes.append((f'{where}.required', 'required'))
        else:
            notes.append((f'{where}.{key}', None))
    return slot


def build_template(km: dict) -> tuple[dict, list]:
    """Return the LinkML schema for SPIRES and the (schema key, LinkML slot) mapping notes."""
    notes: list = []
    enums: dict = {}
    classes: dict = {}
    cfg = km.get('extraction_config', {}).get('llm', {})
    schema = {
        'id': 'http://w3id.org/ontogpt/ontogpt_nba',
        'name': TEMPLATE_NAME,
        'prefixes': {'linkml': 'https://w3id.org/linkml/', 'nba': 'http://w3id.org/ontogpt/ontogpt_nba/'},
        'default_prefix': 'nba',
        'default_range': 'string',
        'imports': ['linkml:types', 'core'],
    }
    for key, value in cfg.items():
        if key == 'domain':
            schema['description'] = value
            notes.append(('extraction_config.llm.domain', 'schema description'))
        elif key == 'language':
            schema['in_language'] = value
            notes.append(('extraction_config.llm.language', 'schema in_language'))
        else:
            notes.append((f'extraction_config.llm.{key}', None))

    for tname, t in km['entity_types'].items():
        entity = {'is_a': 'NamedEntity'}  # mentions of the type, grounded to AUTO: ids
        root: dict = {'attributes': {}}  # the article about one instance of the type
        for key, value in t.items():
            where = f'entity_types.{tname}.{key}'
            if key == 'description':
                entity['description'] = value
                notes.append((where, f'class {tname} description'))
            elif key == 'instructions':
                root['annotations'] = {'prompt': value['document']}
                entity['annotations'] = {'prompt': value['chunk']}
                notes.append((f'{where}.document', f'class {tname}Article annotations: prompt'))
                notes.append((f'{where}.chunk', f'class {tname} annotations: prompt'))
            elif key == 'primary_key':
                notes.append((where, f'key: true on {tname}Article.{value}'))
            elif key == 'fields':
                for fname, field in value.items():
                    root['attributes'][fname] = _field_slot(
                        field, f'{tname}{fname.title().replace("_", "")}Options', enums, notes,
                        f'{where}.{fname}')
            else:
                notes.append((where, None))
        if 'primary_key' in t:
            root['attributes'][t['primary_key']]['key'] = True
        classes[f'{tname}Article'] = root
        classes[tname] = entity

    rels = km['relationship_types']
    for root_type, slot_name, rname, other, is_source in BINDINGS:
        r = rels[rname]
        slot: dict = {'multivalued': True}
        if 'description' in r:
            # OntoGPT's convention for multivalued slots (its generic prompt is
            # "semicolon-separated list of {slot}s", as in its bundled templates); its parser
            # splits on ';', so without it the model lists items with commas and they merge
            slot['description'] = f"{MULTI_PREFIX}{inflection.pluralize(other.lower())}. {r['description']}"
        if 'instructions' in r:
            slot['annotations'] = {'prompt': r['instructions']}
        if r.get('fields'):
            # a relationship with fields is a compound object: other endpoint + fields
            cname = f'{rname}{other}'
            attrs = {other.lower(): {'range': other}}
            for fname, field in r['fields'].items():
                attrs[fname] = _field_slot(field, f'{rname}{fname.title().replace("_", "")}Options',
                                           enums, [], '')
            classes[cname] = {'attributes': attrs}
            slot.update({'range': cname, 'inlined': True, 'inlined_as_list': True})
        else:
            slot['range'] = other
        classes[f'{root_type}Article']['attributes'][slot_name] = slot

    for rname, r in rels.items():
        slots = [f'{t}Article.{s}' for t, s, rn, _, _ in BINDINGS if rn == rname]
        for key, value in r.items():
            where = f'relationship_types.{rname}.{key}'
            if key == 'description':
                notes.append((where, 'description of ' + ', '.join(slots) + ', prefixed with'
                              f' "{MULTI_PREFIX}<plural of the other endpoint type>. "'
                              ' (OntoGPT convention for multivalued slots)'))
            elif key == 'instructions':
                notes.append((where, 'annotations: prompt of ' + ', '.join(slots)))
            elif key == 'endpoints':
                notes.append((where, 'slot ranges / root classes (' + ', '.join(slots) + ')'
                              + '; context levels: no slot'))
            elif key == 'fields':
                for fname, field in value.items():
                    _field_slot(field, f'{rname}{fname.title().replace("_", "")}Options', {}, notes,
                                f'{where}.{fname}')
            elif key == 'primary_key':
                notes.append((where, None))
            else:
                notes.append((where, None))
    schema['classes'] = classes
    schema['enums'] = enums
    return schema, notes


def write_mapping(path: Path, notes: list) -> None:
    lines = [
        '# knowledge_model.json -> OntoGPT 1.2.0 template (ontogpt_nba.yaml)',
        '',
        '| schema key | LinkML / OntoGPT slot |',
        '|---|---|',
    ]
    lines += [f'| `{k}` | {v or "no slot"} |' for k, v in notes]
    lines += [
        '',
        '## What reaches the prompt in OntoGPT 1.2.0',
        '',
        'SPIRES builds one line `slot: <text>` per attribute of the target class (and, for each',
        'item of a compound slot, one recursive call over the attributes of the compound class).',
        '',
        '- attribute `description`: **yes** (used when there is no `prompt` annotation);',
        '- enum range: **yes**, appended as `Must be one of: ...`;',
        '- attribute `annotations: prompt`: **no**. OntoGPT reads it (it takes precedence over the',
        '  description), but in 1.2.0 `_annotation_entries` only accepts a `dict` and linkml-runtime',
        '  1.12 gives a `JsonObj`, so every annotation (`prompt`, `prompt.skip`, `annotators`,',
        '  `ner.recurse`, `prompt.examples`) is silently ignored;',
        '- class `description`, class annotations, schema `description`, `in_language`: **no**',
        '  (never read by SPIRES);',
        '- `examples`, `pattern`, `key`: **no**. OntoGPT turns `pattern` and `required` into',
        '  pydantic validation after parsing, where a violation rejects the whole document. This',
        '  runner keeps `pattern` in the template but loads a copy without it (with it, 0/8 pilot',
        '  documents survived; `--enforce-patterns` restores it). `required` is kept and also makes',
        '  an empty `slot:` line an error;',
        '- multivalued relationship slots: description prefixed with',
        '  `semicolon-separated list of <plural of the other endpoint type>. ` (OntoGPT convention',
        '  for multivalued slots: its generic prompt is `semicolon-separated list of {slot}s`, as in',
        '  its bundled templates, and its parser splits on `;`);',
        '- attributes without a description get `the value for <slot>` or',
        '  `semicolon-separated list of <slot>s`.',
    ]
    path.write_text('\n'.join(lines) + '\n')


# ---------------------------------------------------------------- LLM wrapper

_local = threading.local()
_lock = threading.Lock()


def patch_llm(reasoning_effort: str | None, usage_log: Path, num_retries: int, stats: dict) -> None:
    """Wrap litellm.completion as OntoGPT calls it: reasoning_effort, no cache, usage log."""
    import litellm
    import ontogpt.clients.llm_client as lc

    orig = lc.completion

    def completion(**kw):
        if reasoning_effort:
            kw['reasoning_effort'] = reasoning_effort
        kw['caching'] = False
        kw['num_retries'] = num_retries
        t0 = time.time()
        try:
            r = orig(**kw)
        except Exception as e:
            with _lock:
                stats['llm_errors'].append({'doc': getattr(_local, 'doc', None), 'error': repr(e)[:500]})
            raise
        u = r.usage
        record = {
            'doc': getattr(_local, 'doc', None),
            'secs': round(time.time() - t0, 2),
            'input': u.prompt_tokens,
            'cached': getattr(u.prompt_tokens_details, 'cached_tokens', 0) or 0,
            'output': u.completion_tokens,
            'reasoning': getattr(u.completion_tokens_details, 'reasoning_tokens', 0) or 0,
        }
        with _lock, usage_log.open('a') as f:
            f.write(json.dumps(record) + '\n')
        return r

    lc.completion = completion
    litellm.cache = None


# ---------------------------------------------------------------- extraction

def run_doc(path: Path, doc: str, tname: str, template_details, args, out: Path):
    """Extract one document with a fresh engine; return (doc, type, result dict, root id) or an error."""
    from ontogpt.clients.llm_client import LLMClient
    from ontogpt.engines.spires_engine import SPIRESEngine
    from ontogpt.io.json_wrapper import dump_minimal_json
    from ontogpt.io.utils import read_text_with_fallbacks

    _local.doc = doc
    try:
        client = LLMClient(model=args.model, cache_db_path=str(out / '.litellm_cache'))
        ke = SPIRESEngine(template_details=template_details, model=args.model, client=client,
                          auto_prefix='AUTO', validate_terms=False, mappers=args.mappers)
        cls = template_details[3].get_class(f'{tname}Article')
        # same as ke.extract_from_file, which has no target-class argument
        ke.last_text = read_text_with_fallbacks(path)
        result = ke.extract_from_text(ke.last_text, cls=cls)
        result.input_id = str(path)
        (out / 'raw' / f'{doc}.json').write_text(dump_minimal_json(result))
        obj = result.extracted_object.model_dump() if result.extracted_object else {}
        labels = {ne.id: ne.label for ne in result.named_entities or [] if hasattr(ne, 'label')}
        key = template_details[3].get_identifier_slot(f'{tname}Article', use_key=True)
        name = obj.get(key.name) if key else None
        # the id OntoGPT's normalizer gives the name of the article's subject
        root_id = ke.normalize_named_entity(name, tname) if name else None
        return {'doc': doc, 'type': tname, 'obj': obj, 'labels': labels, 'root_id': root_id}
    except BaseException as e:  # OntoGPT calls sys.exit on some API errors
        (out / 'raw' / f'{doc}.error.txt').write_text(traceback.format_exc())
        return {'doc': doc, 'type': tname, 'error': f'{type(e).__name__}: {e}'[:1000]}


# ---------------------------------------------------------------- graph export

def export_graph(results: list, km: dict, out: Path) -> dict:
    from ontogpt.utils.parse_utils import is_null_like_value

    nodes: dict = {}
    edges: dict = {}
    dropped: list = []

    def null_like(v) -> bool:
        return v is None or (isinstance(v, str) and is_null_like_value(v))

    def label_of(i: str, labels: dict) -> str:
        return labels.get(i) or unquote(i.split(':', 1)[1] if i.startswith('AUTO:') else i)

    def add_node(i, t, name, attrs, doc):
        n = nodes.setdefault(i, {'id': i, 'type': t, 'name': name, 'attrs': {}, 'docs': []})
        for k, v in attrs.items():
            n['attrs'].setdefault(k, v)
        if doc not in n['docs']:
            n['docs'].append(doc)

    def add_edge(src, dst, label, props, doc):
        k = (src, dst, label, json.dumps(props, sort_keys=True))
        e = edges.setdefault(k, {'src': src, 'dst': dst, 'label': label, 'props': props, 'docs': []})
        if doc not in e['docs']:
            e['docs'].append(doc)

    for r in results:
        if 'error' in r:
            continue
        doc, t, obj, labels = r['doc'], r['type'], r['obj'], r['labels']
        fields = km['entity_types'][t]['fields']
        attrs = {}
        for f in fields:
            v = obj.get(f)
            if v is None:
                continue
            if null_like(v):
                dropped.append({'doc': doc, 'slot': f, 'value': v})
                continue
            attrs[f] = v.value if hasattr(v, 'value') else v
        root = r['root_id']
        if root is None:
            continue
        add_node(root, t, attrs.get(km['entity_types'][t]['primary_key']), attrs, doc)
        for root_type, slot, rname, other, is_source in BINDINGS:
            if root_type != t:
                continue
            for item in obj.get(slot) or []:
                if isinstance(item, dict):
                    ref = item.get(other.lower())
                    props = {k: (v.value if hasattr(v, 'value') else v)
                             for k, v in item.items() if k != other.lower() and v is not None}
                else:
                    ref, props = item, {}
                if ref is None:
                    continue
                label = label_of(ref, labels)
                if null_like(label):
                    dropped.append({'doc': doc, 'slot': slot, 'value': label})
                    continue
                add_node(ref, other, label, {}, doc)
                src, dst = (root, ref) if is_source else (ref, root)
                add_edge(src, dst, rname, props, doc)

    g = out / 'graph'
    g.mkdir(exist_ok=True)
    (g / 'nodes.jsonl').write_text(''.join(json.dumps(n) + '\n' for n in nodes.values()))
    (g / 'edges.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in edges.values()))
    return {'nodes': len(nodes), 'edges': len(edges), 'null_like_dropped': dropped}


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, required=True, help='dir with {player,team,city,owner}/{type}/N.txt')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--schema', type=Path, default=UDA / 'workspace-v1' / 'knowledge_model.json')
    ap.add_argument('--model', default='gpt-5.6-luna')
    ap.add_argument('--reasoning-effort', default='low', help="'' to use the model default")
    ap.add_argument('--workers', type=int, default=16, help='documents in flight')
    ap.add_argument('--num-retries', type=int, default=3, help='litellm retries per call')
    ap.add_argument('--enforce-patterns', action='store_true',
                    help='load the template with `pattern`, so the generated pydantic classes reject'
                         ' a document with any value that misses its regex (0/8 pilot docs survived)')
    args = ap.parse_args()

    out = args.out
    (out / 'raw').mkdir(parents=True, exist_ok=True)
    (out / 'usage.jsonl').write_text('')

    km = json.loads(args.schema.read_text())
    schema, notes = build_template(km)
    template_text = yaml.safe_dump(schema, sort_keys=False, allow_unicode=True, width=100)
    template_path = HERE / f'{TEMPLATE_NAME}.yaml'
    template_path.write_text(template_text)
    (out / f'{TEMPLATE_NAME}.yaml').write_text(template_text)
    write_mapping(out / 'mapping.md', notes)

    from oaklib import get_adapter
    from ontogpt.io.template_loader import get_template_details

    stats: dict = {'llm_errors': []}
    patch_llm(args.reasoning_effort or None, out / 'usage.jsonl', args.num_retries, stats)
    load_path = template_path
    if not args.enforce_patterns:
        unenforced = json.loads(json.dumps(schema))
        unenforced['name'] = f'{TEMPLATE_NAME}_nopattern'
        for c in unenforced['classes'].values():
            for a in c.get('attributes', {}).values():
                a.pop('pattern', None)
        load_path = out / f'{TEMPLATE_NAME}_nopattern.yaml'
        load_path.write_text(yaml.safe_dump(unenforced, sort_keys=False, allow_unicode=True, width=100))
    template_details = get_template_details(str(load_path))
    args.mappers = [get_adapter('translator:')]  # SPIRES default mapper, created once

    docs = [(p, f'{d}_{p.stem}', TYPES[d])
            for d in TYPES
            for p in sorted((args.data / d / d).glob('*.txt'), key=lambda p: int(p.stem))]
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda x: run_doc(*x, template_details, args, out), docs))
    wall = time.time() - t0

    graph = export_graph(results, km, out)
    usage = [json.loads(line) for line in (out / 'usage.jsonl').read_text().splitlines()]
    versions = {p: metadata.version(p) for p in ('ontogpt', 'litellm', 'linkml', 'linkml-runtime', 'oaklib')}
    versions['python'] = platform.python_version()
    meta = {
        'system': 'OntoGPT SPIRES',
        'versions': versions,
        'settings': {
            'model': args.model,
            'reasoning_effort': args.reasoning_effort or None,
            'temperature': 'OntoGPT default (1.0)',
            'schema': str(args.schema),
            'template': f'{TEMPLATE_NAME}.yaml',
            'target_classes': {d: f'{t}Article' for d, t in TYPES.items()},
            'recurse': True,
            'max_text_length': None,
            'auto_prefix': 'AUTO',
            'validate_terms': False,
            'annotators': None,
            'litellm_caching': False,
            'litellm_num_retries': args.num_retries,
            'documents_in_flight': args.workers,
            'engine_per_document': True,
            'pattern_validation': args.enforce_patterns,
        },
        'notes': [
            '`pattern` is kept in ontogpt_nba.yaml but the template is loaded from a copy without it'
            ' (ontogpt_nba_nopattern.yaml) unless --enforce-patterns: OntoGPT generates pydantic'
            ' validators from it and a single non-matching value rejects the whole document'
            ' (ValidationError). With enforcement, 0/8 pilot documents survived.',
            'Multivalued relationship slots: description = "semicolon-separated list of <plural of'
            ' the other endpoint type>. " + our description (OntoGPT convention; its parser splits on ";").',
            'Tenure (PlaysFor) comes from SPIRES\'s recursive call on each list item, which sees only'
            ' the item text (e.g. "Larry Bird" or "Dallas Mavericks"), not the article; left as the'
            ' tool does it. In the pilot every PlaysFor edge, team side and player side, got "latest".',
        ],
        'post_processing': (
            'Top-level values that OntoGPT\'s is_null_like_value() flags (e.g. "N/A", "none",'
            ' "unknown", empty) are dropped from node attributes and entity references;'
            ' OntoGPT itself only filters them before recursing into compound objects.'
            ' Values nested inside compound objects are kept as extracted.'
        ),
        'n_docs': len(docs),
        'n_ok': sum('error' not in r for r in results),
        'failures': [r for r in results if 'error' in r],
        'llm_errors': stats['llm_errors'],
        'wall_secs': round(wall, 1),
        'llm_calls': len(usage),
        'tokens': {k: sum(u[k] for u in usage) for k in ('input', 'cached', 'output', 'reasoning')},
        'graph': {'nodes': graph['nodes'], 'edges': graph['edges']},
        'null_like_dropped': graph['null_like_dropped'],
    }
    (out / 'meta.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(f"{meta['n_ok']}/{len(docs)} docs, {len(usage)} calls, {wall:.0f}s, "
          f"{graph['nodes']} nodes, {graph['edges']} edges")


if __name__ == '__main__':
    main()
