"""Schema-component ablation (Table 6 of the paper): Wukong schemas for UDA-Bench NBA, from the schema core alone up
to the full extraction schema, adding one family of annotations at a time.

    python3 make_coupling_variants.py        # -> workspace-x6-s0 ... workspace-x6-s4

The full schema is workspace-x6-s4, the NBA schema of the paper. Every key of it belongs to exactly one family; s<k>
keeps the core and the first k families:

  s0 core       types and their descriptions, fields (data type, description), the primary key
                of each entity type (the engine requires one), relationship endpoints, the
                corpus language. Not bound to any source: every entity and relationship type is
                extracted from every chunk of every collection, never at document level, and no
                relationship identity is declared (deduplication "none").
  s1 +bindings  where each type and field is found: document_collections per context level,
                field retrieval modes per level, endpoint context levels
  s2 +guidance  the corpus domain statement, type / field / relationship instructions, examples
  s3 +validation options, regex, required (other than the entity primary keys)
  s4 full       + identity: relationship deduplication policies and primary keys, merge strategies;
                and Player.current_team. A player article *is* the player, so its current team is a
                document-level fact: a field read once from the start of the player's own article and
                skipped in chunks (without it, the current team is the PlaysFor tenure, decided by every
                chunk that mentions a player and a team). The script checks that s4 equals the full schema.

Examples and free text are checked for contamination: no example may equal a gold value or name one of the 216
subject entities (small counts excepted), and no free text may name a gold value. The script refuses to write a
schema that fails the check.
"""
import copy
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
FULL = json.loads((HERE / 'workspace-x6-s4/knowledge_model.json').read_text())
# s0-s3 are taken from the full schema without the current-team field, which s4 adds
BASE = copy.deepcopy(FULL)
del BASE['entity_types']['Player']['fields']['current_team']
GOLD = HERE / 'data/ground_truth/Player'
DOCS = HERE / 'data/docs'
COUNT_FIELDS = {'nba_championships', 'mvp_awards', 'olympic_gold_medals', 'fiba_world_cup',
                'championships', 'draft_pick'}


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9/.$ ]', ' ', str(s).lower())).strip()


def forbidden():
    """Every gold cell (multi-valued ownership split), plus every subject's document title."""
    bad = {}
    for f in GOLD.glob('*.csv'):
        for r in csv.DictReader(open(f, encoding='utf-8', errors='replace')):
            for k, v in r.items():
                if k == 'ID':
                    continue
                parts = re.split(r'\|\||,| and ', v) if k == 'ownership' else [v]
                for x in parts + [v]:
                    x = norm(x)
                    if x:
                        bad.setdefault(x, f'gold {f.stem}.{k}')
                    if re.fullmatch(r'\d+\.0', x):  # 1981.0 in the CSV is the value 1981
                        bad.setdefault(x[:-2], f'gold {f.stem}.{k}')
    for f in DOCS.glob('*/*/*.txt'):
        with open(f, encoding='utf-8', errors='replace') as fh:
            title = next(line for line in fh if line.strip())
        bad.setdefault(norm(re.sub(r'\(.*?\)', '', title)), f'subject {f.parent.name}/{f.name}')
    return bad


def check(name, km, bad):
    errors = []
    sections = [('entity_types', t, d) for t, d in km['entity_types'].items()]
    sections += [('relationship_types', t, d) for t, d in km['relationship_types'].items()]
    for _, t, d in sections:
        for fname, fld in d.get('fields', {}).items():
            for ex in fld.get('examples', []):
                if fname in COUNT_FIELDS and re.fullmatch(r'\d', ex):
                    continue
                if ex in fld.get('options', []):  # declared vocabulary (e.g. Frontcourt), not an instance value
                    continue
                if norm(ex) in bad:
                    errors.append(f'{name}: {t}.{fname} example {ex!r} is {bad[norm(ex)]}')
    # free text (descriptions, instructions, the domain statement) must not name a gold value
    # either; a field may mention its own declared options
    for where, text, allowed in schema_texts(km):
        n = norm(text)
        for k, why in bad.items():
            if len(k) >= 4 and not k.isdigit() and k not in TEXT_ALLOWED and k not in allowed \
                    and re.search(rf'(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])', n):
                errors.append(f'{name}: {where} mentions {k!r} ({why})')
    return errors


# generic words that happen to equal a gold cell ("Canadian province" in City.state_name), and the
# target vocabulary of Player.position, used on purpose (it also appears where its options are stripped)
TEXT_ALLOWED = {'canadian', 'frontcourt', 'backcourt'}


def schema_texts(km):
    """(location, text, allowed values) for every description and instruction in the schema."""
    def strings(v):
        return list(v.values()) if isinstance(v, dict) else [v] if isinstance(v, str) else []
    for k, v in km.get('extraction_config', {}).get('llm', {}).items():
        yield f'extraction_config.llm.{k}', v, set()
    for kind in ('entity_types', 'relationship_types'):
        for t, d in km.get(kind, {}).items():
            for key in ('description', 'instructions'):
                for text in strings(d.get(key)):
                    yield f'{t}.{key}', text, set()
            for f, fd in d.get('fields', {}).items():
                allowed = {norm(o) for o in fd.get('options', [])}
                for key in ('description', 'instructions'):
                    for text in strings(fd.get(key)):
                        yield f'{t}.{f}.{key}', text, allowed

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
    bad = forbidden()
    variants = {f's{k}': strip(BASE, {'core', *FAMILIES[:k]}) for k in range(len(FAMILIES))}
    full = strip(BASE, {'core', *FAMILIES})
    full['entity_types']['Player']['fields']['current_team'] = CURRENT_TEAM
    if full != FULL:
        raise SystemExit('s4 differs from workspace-x6-s4: some key is lost or added by strip()')
    variants['s4'] = full
    errors = [e for n, km in variants.items() for e in check(n, km, bad)]
    if errors:
        raise SystemExit('contamination:\n  ' + '\n  '.join(errors))
    for name, km in variants.items():
        d = HERE / f'workspace-x6-{name}'
        d.mkdir(exist_ok=True)
        (d / 'knowledge_model.json').write_text(json.dumps(km, indent=4, ensure_ascii=False) + '\n')
        (d / 'document_collections.json').write_text((HERE / 'workspace-x6-s4/document_collections.json').read_text())
        print(name, f'{len(json.dumps(km)):>6} chars ->', d)


if __name__ == '__main__':
    main()
