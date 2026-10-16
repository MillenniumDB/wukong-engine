"""X6 / E3, coupling ablation: Wukong schemas for UDA-Bench NBA, from the schema core alone up to
the full extraction schema, adding one family of annotations at a time.

    python3 make_coupling_variants.py        # -> workspace-x6-s0 ... workspace-x6-s4

The full schema is workspace-v1 (the clean schema of E1). Every key of it belongs to exactly one
family; s<k> keeps the core and the first k families:

  s0 core       types and their descriptions, fields (data type, description), the primary key
                of each entity type (the engine requires one), relationship endpoints, the
                corpus language. Not bound to any source: every entity and relationship type is
                extracted from every chunk of every collection, never at document level, and no
                relationship identity is declared (deduplication "none").
  s1 +bindings  where each type and field is found: document_collections per context level,
                field retrieval modes per level, endpoint context levels
  s2 +guidance  the corpus domain statement, type / field / relationship instructions, examples
  s3 +validation options, regex, required (other than the entity primary keys)
  s4 +identity  relationship deduplication policies and primary keys, merge strategies
                (s4 must equal workspace-v1, which the script checks)
  s5 = s4 + Player.current_team, a schema revision made after X6 rather than an annotation
                family. In s4 the current team is the PlaysFor tenure, decided by every chunk that
                mentions a player and a team, so players got ~1.9 "latest" teams. A player article
                *is* the player, so its current team is a document-level fact: a field read once
                from the start of the player's own article and skipped in chunks.

Examples are checked for contamination as in make_schema_variants.py.
"""
import copy
import json
from pathlib import Path

import make_schema_variants as M

HERE = Path(__file__).parent
FULL = json.loads((HERE / 'workspace-v1/knowledge_model.json').read_text())
FAMILIES = ['bindings', 'guidance', 'validation', 'identity']

# family of each key, by where it occurs
ENTITY_KEYS = {'description': 'core', 'primary_key': 'core', 'deduplication': 'core', 'fields': 'core',
               'instructions': 'guidance', 'document_collections': 'bindings',
               'default_merge_strategy': 'identity'}
FIELD_KEYS = {'data_type': 'core', 'description': 'core', 'instructions': 'guidance', 'examples': 'guidance',
              'options': 'validation', 'regex': 'validation', 'required': 'validation',
              'retrieval_mode': 'bindings', 'merge_strategy': 'identity', 'default_value': 'validation'}
REL_KEYS = {'description': 'core', 'endpoints': 'core', 'fields': 'core', 'instructions': 'guidance',
            'primary_key': 'identity', 'deduplication': 'identity', 'default_merge_strategy': 'identity',
            'irreflexive': 'validation'}
CONFIG_KEYS = {'language': 'core', 'domain': 'guidance'}


def family(table, key, where):
    if key not in table:
        raise SystemExit(f'unclassified key {key!r} in {where}')
    return table[key]


def strip(km, keep):
    """Keep the core plus the families in `keep`."""
    km = copy.deepcopy(km)
    llm = km.get('extraction_config', {}).get('llm', {})
    for k in list(llm):
        if family(CONFIG_KEYS, k, 'extraction_config.llm') not in keep:
            del llm[k]
    for t, d in km['entity_types'].items():
        for k in list(d):
            if family(ENTITY_KEYS, k, t) not in keep:
                del d[k]
        if 'document_collections' not in d:  # unbound: every collection, chunk level only
            d['document_collections'] = {'chunk': ['players', 'teams', 'cities', 'owners']}
        for f, fd in d['fields'].items():
            for k in list(fd):
                if family(FIELD_KEYS, k, f'{t}.{f}') not in keep and not (k == 'required' and f == d['primary_key']):
                    del fd[k]
    for t, d in km['relationship_types'].items():
        for k in list(d):
            if family(REL_KEYS, k, t) not in keep:
                del d[k]
        if 'identity' not in keep:
            d['deduplication'] = 'none'
        if 'bindings' not in keep:  # unbound: both endpoints found in the same chunk
            d['endpoints'] = {s: {o: [{'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}]
                                  for o in targets} for s, targets in d['endpoints'].items()}
        for f, fd in d.get('fields', {}).items():
            for k in list(fd):
                if family(FIELD_KEYS, k, f'{t}.{f}') not in keep:
                    del fd[k]
    return km


CURRENT_TEAM = {
    'data_type': 'string',
    'description': "The player's current NBA team or, if the player is no longer active in the NBA, "
                   'the last NBA team the player played for.',
    'instructions': 'Full name of the team: location and nickname, never the nickname alone.',
    'examples': ['Vancouver Grizzlies', 'Kansas City Kings'],
    'retrieval_mode': {'document': 'extract', 'chunk': 'skip'},
}


def main():
    bad = M.forbidden()
    variants = {f's{k}': strip(FULL, {'core', *FAMILIES[:k]}) for k in range(len(FAMILIES) + 1)}
    if variants['s4'] != FULL:
        raise SystemExit('s4 differs from workspace-v1: some key is lost or added by strip()')
    variants['s5'] = copy.deepcopy(variants['s4'])
    variants['s5']['entity_types']['Player']['fields']['current_team'] = CURRENT_TEAM
    errors = [e for n, km in variants.items() for e in M.check(n, km, bad)]
    if errors:
        raise SystemExit('contamination:\n  ' + '\n  '.join(errors))
    for name, km in variants.items():
        d = HERE / f'workspace-x6-{name}'
        d.mkdir(exist_ok=True)
        (d / 'knowledge_model.json').write_text(json.dumps(km, indent=4, ensure_ascii=False) + '\n')
        (d / 'document_collections.json').write_text((HERE / 'workspace/document_collections.json').read_text())
        print(name, f'{len(json.dumps(km)):>6} chars ->', d)


if __name__ == '__main__':
    main()
