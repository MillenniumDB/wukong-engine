"""Build the Wukong schemas of the schema ablation from workspace/ (the original schema).

    python3 make_schema_variants.py

  v1 = workspace/ with every instance-specific example replaced. The original examples
       leaked gold answers (LeBron James's and Antonius Cleveland's birth dates, Denver's
       and Toronto's states, the Hawks' owner, subject names). Formats, options and
       instructions are unchanged.
  v2 = v1 + Owner.name asks for the commonly known name (the original split 8/16 owners
       into a legal-name node and a common-name node)
  v3 = v2 + worked examples on every field

Contamination check: no example may equal a value of the gold tables or the name of one
of the 216 subject entities, except small counts (0-9) in count fields, which no example
can avoid. The script refuses to write a schema that fails the check.

Target-schema knowledge is used on purpose and is not instance leakage: the Frontcourt /
Backcourt options of Player.position, and the YYYY/M/D date format, are the gold tables'
conventions, which a schema author who knows the target schema would write down.
"""
import copy
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
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


base = json.loads((HERE / 'workspace/knowledge_model.json').read_text())


def set_examples(km, table):
    for (t, f), ex in table.items():
        kind = 'entity_types' if t in km['entity_types'] else 'relationship_types'
        km[kind][t]['fields'][f]['examples'] = ex


def add_examples(km, table):
    for (t, f), ex in table.items():
        kind = 'entity_types' if t in km['entity_types'] else 'relationship_types'
        fld = km[kind][t]['fields'][f]
        fld['examples'] = list(dict.fromkeys(fld.get('examples', []) + ex))


# v1: same fields that had examples in the original, same number of examples, clean values
v1 = copy.deepcopy(base)
# the original Team.team_name instruction used a subject team as its format example
v1['entity_types']['Team']['fields']['team_name']['instructions'] = (
    "Always use the full name, even if the text uses only the nickname "
    "(write 'Vancouver Grizzlies', not 'Grizzlies').")
set_examples(v1, {
    ('Player', 'name'): ['Larry Bird', 'Dirk Nowitzki'],
    ('Player', 'birth_date'): ['1978/2/14', '1961/9/5'],
    ('Player', 'nationality'): ['Lithuanian', 'Brazilian', 'Japanese'],
    ('Player', 'college'): ['Georgetown University', 'Wake Forest'],
    ('Team', 'team_name'): ['Vancouver Grizzlies', 'Kansas City Kings', 'Buffalo Braves'],
    ('City', 'city_name'): ['Kansas City', 'Seattle'],
    ('City', 'state_name'): ['Missouri', 'Quebec'],
    ('Owner', 'name'): ['Mikhail Prokhorov', 'Comcast Spectacor'],
    ('Owner', 'nationality'): ['Russian'],
})

v2 = copy.deepcopy(v1)
v2['entity_types']['Owner']['fields']['name']['instructions'] = (
    'The name the owner is commonly known by, as in news coverage, not the full legal name. '
    'For an organization, its usual name.')

v3 = copy.deepcopy(v2)
add_examples(v3, {
    ('Player', 'name'): ['J.J. Redick', 'Hakeem Olajuwon'],
    ('Player', 'death_date'): ['1963/4/11'],
    ('Player', 'nationality'): ['Nigerian'],
    ('Player', 'position'): ['Frontcourt', 'Backcourt'],
    ('Player', 'draft_pick'): ['1', '43'],
    ('Player', 'draft_year'): ['1978', '2004'],
    ('Player', 'nba_championships'): ['0', '3'],
    ('Player', 'mvp_awards'): ['0', '1'],
    ('Player', 'olympic_gold_medals'): ['0', '2'],
    ('Player', 'fiba_world_cup'): ['0', '1'],
    ('Team', 'founded_year'): ['1947', '1969'],
    ('Team', 'championships'): ['0', '3'],
    ('City', 'city_name'): ['Vancouver', 'Buffalo'],
    ('City', 'state_name'): ['British Columbia'],
    ('City', 'population'): ['508090', '737015'],
    ('City', 'area'): ['319.03', '142.5'],
    ('City', 'gdp'): ['$420 billion (2022)'],
    ('Owner', 'name'): ['George Shinn'],
    ('Owner', 'birth_date'): ['1965/5/3', '1941/7/9'],
    ('PlaysFor', 'tenure'): ['latest', 'earlier'],
    ('Owns', 'since_year'): ['1998'],
})

def main():
    bad = forbidden()
    print('original schema:', *check('original', base, bad) or ['clean'], sep='\n  ')
    errors = [e for n, km in (('v1', v1), ('v2', v2), ('v3', v3)) for e in check(n, km, bad)]
    if errors:
        sys.exit('contamination:\n  ' + '\n  '.join(errors))
    for name, km in (('v1', v1), ('v2', v2), ('v3', v3)):
        d = HERE / f'workspace-{name}'
        d.mkdir(exist_ok=True)
        (d / 'knowledge_model.json').write_text(json.dumps(km, indent=4, ensure_ascii=False) + '\n')
        (d / 'document_collections.json').write_text((HERE / 'workspace/document_collections.json').read_text())
        print(name, 'clean ->', d)


if __name__ == '__main__':
    main()
