"""M1 (E2 midpoint): shared pieces, used identically for every system.

Every system gets the same plain-language question and the same answer instruction, and every answer goes
through the same conversion before UDA-Bench's own evaluator scores it:

    - answers are JSON rows with neutral keys (col1, col2, ...), one per output column of the benchmark's SQL,
      plus name_<table> keys naming the entity a row is about; no system sees the SQL or its column names;
    - the harness maps col<i> back to the SQL's output columns, and each name_<table> to the document id the
      evaluator aligns rows on, through one fixed table of document titles and gold names (the gold uses legal
      names, the articles common ones, so both are accepted, for every system alike);
    - a row whose entity name matches no document keeps an empty id, so it cannot align: a miss, for any system.

Paths: M1_ROOT is the working folder (input graphs under input/uda-nba-share, answers, scores, logs under work/),
UDA_BENCH a checkout of the UDA-Bench repository; they default to ~/wukong-runs/m1 and
~/wukong-runs/benchmarks/UDA-Bench.
"""

import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd

M1 = Path(os.environ.get('M1_ROOT', Path.home() / 'wukong-runs/m1'))
UDA = Path(os.environ.get('UDA_BENCH', Path.home() / 'wukong-runs/benchmarks/UDA-Bench'))
SHARE = M1 / 'input/uda-nba-share'
WORK = M1 / 'work'
GOLD_DIR = UDA / 'Query/Player'
ATTRIBUTES = GOLD_DIR / 'Player_attributes.json'
MODEL = 'gpt-5.6-luna'
EFFORT = 'low'

# Gold table -> (name column, plain noun used in questions and answer keys)
ENTITY = {'player': ('name', 'player'), 'team': ('team_name', 'team'), 'city': ('city_name', 'city'),
          'manager': ('name', 'team owner')}
# $ per million tokens (gpt-5.6-luna), as in the Text2KGBench runs
RATES = {'input': 0.20, 'cached': 0.02, 'output': 1.20}


def load_queries() -> list[dict]:
    return json.loads((WORK / 'queries.json').read_text())


def load_questions() -> dict[str, dict]:
    return {q['uid']: q for q in json.loads((WORK / 'questions.json').read_text())}


# ------------------------------------------------------------------------------------------- answer keys


def key_tables(query: dict) -> list[str]:
    """Tables whose rows the evaluator aligns on by id: their entity names must be in the answer."""
    keys = query['primary_keys']
    if keys == ['id']:
        return [query['tables'][0]]
    return [k.split('.')[0] for k in keys if k.endswith('.id')]


# Closed vocabularies stated in the benchmark's own attribute descriptions (Player_attributes.json): every system is
# told the allowed values of an answer column, since the gold uses them
VOCABULARY = {'position': 'one of: Frontcourt, Backcourt'}


def answer_keys(query: dict, meanings: list[str]) -> list[tuple[str, str]]:
    """(key, meaning) pairs a system's rows must carry, in order."""
    cols = query.get('pred_columns') or query['output_columns']
    keys = []
    for i, m in enumerate(meanings):
        base = cols[i].split('.')[-1] if i < len(cols) else ''
        keys.append((f'col{i + 1}', f'{m} ({VOCABULARY[base]})' if base in VOCABULARY else m))
    for t in key_tables(query):
        keys.append((f'name_{t}', f'the full name of the {ENTITY[t][1]} this row is about'))
    return keys


# What every system is told about the scope of the questions (the gold tables have one row per article)
SCOPE = ('The document collection has one article per NBA player, team, city and team owner. Questions are about '
         'the players, teams, cities and owners that have their own article, not about others merely mentioned.')


def answer_instruction(query: dict, meanings: list[str]) -> str:
    """The one answer-format instruction every system receives."""
    lines = '\n'.join(f'- "{k}": {m}' for k, m in answer_keys(query, meanings))
    return (
        SCOPE + '\n'
        'Answer with a JSON object of the form {"rows": [ ... ]} and nothing else. Each row is an object with '
        f'exactly these keys:\n{lines}\n'
        'Give one row per answer item. Write numbers as plain numbers (no units, no thousands separators) and '
        'dates as YYYY/M/D. Use null for a value you cannot determine. If nothing satisfies the question, '
        'answer {"rows": []}.'
    )


# ------------------------------------------------------------------------------------------- parsing


def parse_rows(text: str | None) -> list[dict] | None:
    """Extract {"rows": [...]} (or a bare list of rows) from a reply; None if it cannot be parsed."""
    if not text:
        return None
    candidates = [text]
    fence = re.findall(r'```(?:json)?\s*(.*?)```', text, re.S)
    candidates += fence
    start = min((i for i in (text.find('{'), text.find('[')) if i >= 0), default=-1)
    if start >= 0:
        candidates.append(text[start:])
    for c in candidates:
        c = c.strip()
        for end in range(len(c), 0, -1):  # tolerate trailing prose after the JSON
            if c[end - 1] not in '}]':
                continue
            try:
                data = json.loads(c[:end])
            except json.JSONDecodeError:
                continue
            rows = data.get('rows') if isinstance(data, dict) else data
            if isinstance(rows, list) and all(isinstance(r, dict) for r in rows):
                return rows
            break
    return None


# ------------------------------------------------------------------------------------------- names -> ids


def norm_name(s: str) -> str:
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.sub(r'[^a-z0-9 ]+', ' ', s).split())


class NameIndex:
    """Document title and gold name of every row, per table; the same index for every system."""

    def __init__(self) -> None:
        titles = json.loads((WORK / 'titles.json').read_text())
        self.aliases: dict[str, dict[int, set[str]]] = {}
        for table, (name_col, _) in ENTITY.items():
            gold = pd.read_csv(GOLD_DIR / f'{table}.csv', dtype=str, keep_default_na=False)
            per_id = {}
            for _, r in gold.iterrows():
                i = int(r['ID'])
                per_id[i] = {norm_name(r[name_col]), norm_name(titles[table].get(str(i), ''))} - {''}
            self.aliases[table] = per_id

    def match(self, table: str, name) -> int | None:
        """Exact match on a title or gold name; else the single row whose alias contains all the name's
        words, or whose words are all in the name."""
        n = norm_name(name or '')
        if not n:
            return None
        exact = [i for i, a in self.aliases[table].items() if n in a]
        if len(exact) == 1:
            return exact[0]
        words = set(n.split())
        partial = [i for i, a in self.aliases[table].items()
                   if any(words <= set(x.split()) or set(x.split()) <= words for x in a)]
        if len(partial) == 1:
            return partial[0]
        # A formal first name for a short one (Timothy/Tim, Clayton/Clay): same last word, one first word a prefix
        # of the other. Nicknames that are not prefixes (Earvin/Magic) stay unmatched.
        w = n.split()

        def short_form(x: str) -> bool:
            v = x.split()
            return len(w) >= 2 and len(v) >= 2 and v[-1] == w[-1] and (v[0].startswith(w[0]) or w[0].startswith(v[0]))

        formal = [i for i, a in self.aliases[table].items() if any(short_form(x) for x in a)]
        return formal[0] if len(formal) == 1 else None


def rows_to_csv(query: dict, rows: list[dict] | None, names: NameIndex, path: Path) -> dict:
    """Write a system's rows as the prediction CSV the evaluator reads; return counts for the report."""
    out_cols = query.get('pred_columns') or query['output_columns']  # the evaluator's names (table-qualified in joins)
    id_cols = ['id'] if query['primary_keys'] == ['id'] else [k for k in query['primary_keys'] if k.endswith('.id')]
    tables = key_tables(query)
    records, unmatched = [], 0
    for r in rows or []:
        rec = {c: r.get(f'col{i + 1}') for i, c in enumerate(out_cols)}
        for col, t in zip(id_cols, tables, strict=False):
            i = names.match(t, r.get(f'name_{t}'))
            unmatched += i is None
            # An unmatched name gets its own negative id: it matches no gold row (a wrong prediction, like any
            # other), and keeps the id column integer; an empty cell would turn it into floats ('7.0') and
            # make the evaluator match no row at all
            rec[col] = i if i is not None else -(unmatched + 1)
        records.append(rec)
    df = pd.DataFrame(records, columns=[*out_cols, *id_cols])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return {'rows': len(records), 'unmatched_names': unmatched}


# ------------------------------------------------------------------------------------------- scoring


def evaluate(query: dict, result_csv: Path, out_dir: Path) -> dict:
    """UDA-Bench's own evaluator, deterministic (no LLM matching); returns its acc.json (or an error)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sql_file = out_dir / 'sql.json'
    sql_file.write_text(json.dumps({'sql': query['sql']}))
    cmd = [sys.executable, '-m', 'evaluation.run_eval', '--dataset', 'Player', '--task', query['type'],
           '--sql-file', str(sql_file), '--result-csv', str(result_csv), '--attributes-file', str(ATTRIBUTES),
           '--gt-dir', str(GOLD_DIR), '--output-dir', str(out_dir), '--llm-provider', 'none', '--log-level', 'WARNING']
    proc = subprocess.run(cmd, cwd=UDA, capture_output=True, text=True, check=False)
    acc = out_dir / 'acc.json'
    if proc.returncode != 0 or not acc.exists():
        return {'error': (proc.stderr or proc.stdout)[-1500:]}
    return json.loads(acc.read_text())


# ------------------------------------------------------------------------------------------- LLM + usage


def chat(client, messages: list[dict], usage_log: Path, kind: str, **extra) -> str:
    """One chat-completions call with the model and effort every system uses; usage appended to usage_log."""
    params = {'model': MODEL, 'messages': messages, 'reasoning_effort': EFFORT, **extra}
    for attempt in range(5):
        try:
            t0 = time.time()
            resp = client.chat.completions.create(**params)
            break
        except Exception as e:  # noqa: BLE001
            if 'insufficient_quota' in str(e):
                raise
            if attempt == 4:
                raise
            time.sleep(5 * 2 ** attempt)
    u = resp.usage
    log_usage(usage_log, kind, u.prompt_tokens, getattr(u.prompt_tokens_details, 'cached_tokens', 0) or 0,
              u.completion_tokens, getattr(u.completion_tokens_details, 'reasoning_tokens', 0) or 0, time.time() - t0)
    return resp.choices[0].message.content or ''


def log_usage(usage_log: Path, kind: str, inp: int, cached: int, out: int, reasoning: int, secs: float) -> None:
    usage_log.parent.mkdir(parents=True, exist_ok=True)
    with usage_log.open('a') as f:
        f.write(json.dumps({'kind': kind, 'input': inp, 'cached': cached, 'output': out, 'reasoning': reasoning,
                            'secs': round(secs, 2)}) + '\n')


def cost(usage_log: Path) -> float:
    """Dollars from a usage log (chat completions: prompt includes cached, completion includes reasoning)."""
    if not usage_log.exists():
        return 0.0
    total = 0.0
    for line in usage_log.read_text().splitlines():
        u = json.loads(line)
        total += ((u['input'] - u['cached']) * RATES['input'] + u['cached'] * RATES['cached'] + u['output'] * RATES['output']) / 1e6
    return total
