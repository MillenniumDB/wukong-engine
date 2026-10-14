"""Turn each UDA-Bench NBA SQL query into one plain-language question, once, for every system.

One LLM call per query (the model and effort every system uses) gets the SQL, the benchmark's own description of
every column, and how the tables relate, and returns the question a person would ask plus a plain description of
each output column. No system ever sees the SQL or a column name: they get the question and the descriptions,
under neutral keys (common.answer_instruction). Writes work/questions.json, and work/questions.md for a human check.
"""

import json
import sys
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from common import ATTRIBUTES, WORK, chat, load_queries  # noqa: E402

SYSTEM = """You write questions for a benchmark over NBA data. You get an SQL query over four tables, the meaning of
every column, and how the tables relate. Rewrite the query as ONE question a person would ask, in plain English.

Rules:
- Keep every condition exactly: the same values, the same comparisons (greater than, at most, ...), the same AND/OR
  structure and grouping. Quote literal values as they appear in the query.
- Never mention tables, columns, SQL, identifiers, keys or file names. Describe each attribute in plain words, using
  the column meanings given (say "number of NBA MVP awards", never "mvp_awards").
- Relations between tables, in plain words: player.team = team.team_name means "the team the player currently plays
  for (or last played for)"; team.location = city.city_name means "the city where the team is located";
  manager.nba_team = team.team_name means "the team the owner owns". The manager table holds NBA team owners.
- An aggregation with GROUP BY becomes "for each <group>, ...".
- Also describe, for each output column of the query IN ORDER, what the answer must contain in that column, in a few
  plain words (no column names). An aggregate is described as such ("the lowest number of Olympic gold medals").

Return only a JSON object: {"question": "...", "columns": ["...", "..."]}."""


def describe(attrs: dict, tables: list[str]) -> str:
    return '\n'.join(f'{t}.{c}: {v.get("description", "")}' for t in tables for c, v in attrs.get(t, {}).items())


def main() -> int:
    attrs = json.loads(ATTRIBUTES.read_text())
    client = OpenAI()
    usage = WORK / 'usage' / 'translate.jsonl'
    out_file = WORK / 'questions.json'
    done = {q['uid']: q for q in json.loads(out_file.read_text())} if out_file.exists() else {}
    for q in load_queries():
        if q['uid'] in done or not q['in_m1']:
            continue
        cols = q['pred_columns']
        user = (f'Column meanings:\n{describe(attrs, q["tables"])}\n\nSQL: {q["sql"]}\n\n'
                f'Output columns, in order ({len(cols)}): {", ".join(cols)}')
        for _ in range(3):
            reply = chat(client, [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}], usage,
                         'translate', response_format={'type': 'json_object'})
            try:
                data = json.loads(reply)
            except json.JSONDecodeError:
                continue
            if isinstance(data.get('question'), str) and isinstance(data.get('columns'), list) and len(data['columns']) == len(cols):
                break
        else:
            print(f'{q["uid"]}: no valid translation', file=sys.stderr)
            continue
        done[q['uid']] = {'uid': q['uid'], 'type': q['type'], 'question': data['question'], 'meanings': data['columns'],
                          'sql': q['sql']}
        out_file.write_text(json.dumps(list(done.values()), indent=1))
    lines = [f'### {u} ({q["type"]})\n\n- SQL: `{q["sql"]}`\n- Question: {q["question"]}\n- Columns: ' +
             '; '.join(q['meanings']) + '\n' for u, q in done.items()]
    (WORK / 'questions.md').write_text('# M1 questions (generated once, same for every system)\n\n' + '\n'.join(lines))
    print(f'{len(done)} questions')
    return 0


if __name__ == '__main__':
    sys.exit(main())
