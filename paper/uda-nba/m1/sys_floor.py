"""M1 floor: the LLM alone, no retrieval and no graph. Same question and answer instruction as every system.

Writes work/answers/floor/<uid>.json ({"reply", "rows"}) and logs usage to work/usage/floor.jsonl.
"""

import argparse
import json
import sys
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from common import WORK, answer_instruction, chat, load_queries, load_questions, parse_rows  # noqa: E402


def pilot_uids(questions: dict) -> list[str]:
    """The pilot: the first question of each type, the same for every system."""
    first = {}
    for u, q in questions.items():
        first.setdefault(q['type'], u)
    return list(first.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pilot', action='store_true')
    args = ap.parse_args()
    queries = {q['uid']: q for q in load_queries()}
    questions = load_questions()
    uids = pilot_uids(questions) if args.pilot else list(questions)
    client = OpenAI()
    out = WORK / 'answers' / 'floor'
    out.mkdir(parents=True, exist_ok=True)
    for u in uids:
        f = out / f'{u.replace("#", "_")}.json'
        if f.exists():
            continue
        q = questions[u]
        prompt = f'{q["question"]}\n\nAnswer from your own knowledge.\n{answer_instruction(queries[u], q["meanings"])}'
        reply = chat(client, [{'role': 'user', 'content': prompt}], WORK / 'usage' / 'floor.jsonl', 'answer')
        f.write_text(json.dumps({'uid': u, 'reply': reply, 'rows': parse_rows(reply)}, indent=1))
    print(f'floor: {len(uids)} questions answered')
    return 0


if __name__ == '__main__':
    sys.exit(main())
