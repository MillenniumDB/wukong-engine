"""M1, LightRAG answering natively: every query mode (local, global, hybrid, mix), default parameters.

Uses the full LightRAG store Juan built (lightrag-hku 1.5.7, gpt-5.6-luna at low effort, text-embedding-3-small),
initialized exactly as lightrag_build.py does (same LLM wrapper, so usage is logged per call). The question is the
query; the answer instruction goes in QueryParam.user_prompt, LightRAG's slot for output instructions, so it does not
pollute keyword extraction or retrieval. No Cypher is ever run against this graph.

Run with the LightRAG environment. Writes work/answers/lightrag-<mode>/<uid>.json; usage to work/usage/lightrag.jsonl
(LLM calls only; the embedding calls for retrieval are not logged and cost a fraction of a cent).
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_embed
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent))
from common import EFFORT, MODEL, SHARE, WORK, answer_instruction, load_queries, load_questions, log_usage, parse_rows  # noqa: E402
from sys_floor import pilot_uids  # noqa: E402

MODES = ('local', 'global', 'hybrid', 'mix')
USAGE = WORK / 'usage' / 'lightrag.jsonl'


def make_llm():
    """lightrag_build.make_llm, with usage going to the M1 log."""
    client = AsyncOpenAI()

    async def llm(prompt, system_prompt=None, history_messages=None, keyword_extraction=False, **kwargs):
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.extend(history_messages or [])
        messages.append({'role': 'user', 'content': prompt})
        params = {'model': MODEL, 'messages': messages, 'reasoning_effort': EFFORT}
        if kwargs.get('response_format') is not None:
            params['response_format'] = kwargs['response_format']
        elif keyword_extraction:
            params['response_format'] = {'type': 'json_object'}
        t0 = time.time()
        resp = await client.chat.completions.create(**params)
        u = resp.usage
        log_usage(USAGE, 'keywords' if keyword_extraction else 'answer', u.prompt_tokens,
                  getattr(u.prompt_tokens_details, 'cached_tokens', 0) or 0, u.completion_tokens,
                  getattr(u.completion_tokens_details, 'reasoning_tokens', 0) or 0, time.time() - t0)
        return resp.choices[0].message.content

    return llm


async def main_async(args) -> int:
    rag = LightRAG(working_dir=str(SHARE / 'lightrag-full' / 'storage'), llm_model_func=make_llm(), llm_model_name=MODEL,
                   llm_model_max_async=8, embedding_func=openai_embed)
    await rag.initialize_storages()
    queries = {q['uid']: q for q in load_queries()}
    questions = load_questions()
    uids = pilot_uids(questions) if args.pilot else list(questions)
    for mode in args.modes:
        out = WORK / 'answers' / f'lightrag-{mode}'
        out.mkdir(parents=True, exist_ok=True)
        for u in uids:
            f = out / f'{u.replace("#", "_")}.json'
            if f.exists():
                continue
            q = questions[u]
            param = QueryParam(mode=mode, user_prompt=answer_instruction(queries[u], q['meanings']))
            try:
                reply = await rag.aquery(q['question'], param=param)
            except Exception as e:  # noqa: BLE001
                if 'insufficient_quota' in str(e):
                    raise
                reply = None
                print(f'{mode} {u}: {type(e).__name__}: {str(e)[:200]}', file=sys.stderr)
            reply = reply if isinstance(reply, str) else (None if reply is None else str(reply))
            f.write_text(json.dumps({'uid': u, 'mode': mode, 'reply': reply, 'rows': parse_rows(reply)}, indent=1))
        print(f'lightrag-{mode}: {len(uids)} questions answered', flush=True)
    await rag.finalize_storages()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--modes', nargs='+', default=list(MODES), choices=MODES)
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == '__main__':
    sys.exit(main())
