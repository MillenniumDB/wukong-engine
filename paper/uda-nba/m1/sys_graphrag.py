"""M1, GraphRAG answering natively: local search and global search.

Uses the full GraphRAG index Juan built (graphrag 3.2.0, gpt-5.6-luna at low effort, text-embedding-3-small) and
its settings.yaml. The question is the query; the answer instruction is GraphRAG's response_type, which its prompts
insert as the target response format. Local search runs at its defaults (community level 2). Global search runs
with dynamic community selection: at the default static level 2 it maps over ~4,400 community reports (3.8M tokens)
per question, about $75 for M1; dynamic selection is GraphRAG's documented way to restrict the map step to the
relevant communities. No Cypher is ever run against this graph.

Run with the GraphRAG environment. Writes work/answers/graphrag-<method>/<uid>.json; usage (from litellm, which
graphrag calls the model through) to work/usage/graphrag.jsonl.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import litellm
import pandas as pd
from graphrag import api
from graphrag.config.load_config import load_config

sys.path.insert(0, str(Path(__file__).parent))
from common import SHARE, WORK, answer_instruction, load_queries, load_questions, log_usage, parse_rows  # noqa: E402
from sys_floor import pilot_uids  # noqa: E402

ROOT = SHARE / 'graphrag-full'
USAGE = WORK / 'usage' / 'graphrag.jsonl'
METHODS = ('local', 'global')


def _log(u, secs: float) -> None:
    if u is None or not getattr(u, 'prompt_tokens', None):
        return
    pd_ = getattr(u, 'prompt_tokens_details', None)
    cd = getattr(u, 'completion_tokens_details', None)
    log_usage(USAGE, 'graphrag', u.prompt_tokens, getattr(pd_, 'cached_tokens', 0) or 0, u.completion_tokens or 0,
              getattr(cd, 'reasoning_tokens', 0) or 0, secs)


_acompletion = litellm.acompletion


async def acompletion_with_usage(*args, **kwargs):
    """litellm.acompletion, recording token usage. Local search streams its answer, and a stream only reports usage
    in a final chunk when asked to (stream_options.include_usage); this changes what is measured, not the prompt."""
    t0 = time.time()
    if kwargs.get('stream'):
        kwargs['stream_options'] = {**(kwargs.get('stream_options') or {}), 'include_usage': True}
        stream = await _acompletion(*args, **kwargs)

        async def relay():
            last = None
            async for chunk in stream:
                last = getattr(chunk, 'usage', None) or last
                yield chunk
            _log(last, time.time() - t0)

        return relay()
    response = await _acompletion(*args, **kwargs)
    _log(getattr(response, 'usage', None), time.time() - t0)
    return response


async def main_async(args) -> int:
    litellm.acompletion = acompletion_with_usage
    config = load_config(root_dir=ROOT)
    out_dir = ROOT / 'output'
    tables = {n: pd.read_parquet(out_dir / f'{n}.parquet')
              for n in ('entities', 'communities', 'community_reports', 'text_units', 'relationships')}
    queries = {q['uid']: q for q in load_queries()}
    questions = load_questions()
    uids = pilot_uids(questions) if args.pilot else list(questions)
    for method in args.methods:
        out = WORK / 'answers' / f'graphrag-{method}'
        out.mkdir(parents=True, exist_ok=True)
        for u in uids:
            f = out / f'{u.replace("#", "_")}.json'
            if f.exists():
                continue
            q = questions[u]
            instruction = answer_instruction(queries[u], q['meanings'])
            t0 = time.time()
            try:
                if method == 'local':
                    reply, _ = await api.local_search(
                        config=config, entities=tables['entities'], communities=tables['communities'],
                        community_reports=tables['community_reports'], text_units=tables['text_units'],
                        relationships=tables['relationships'], covariates=None, community_level=2,
                        response_type=instruction, query=q['question'])
                else:
                    reply, _ = await api.global_search(
                        config=config, entities=tables['entities'], communities=tables['communities'],
                        community_reports=tables['community_reports'], community_level=2,
                        dynamic_community_selection=True, response_type=instruction, query=q['question'])
            except Exception as e:  # noqa: BLE001
                if 'insufficient_quota' in str(e):
                    raise
                reply = None
                print(f'{method} {u}: {type(e).__name__}: {str(e)[:200]}', file=sys.stderr)
            reply = reply if isinstance(reply, str) else (None if reply is None else json.dumps(reply))
            f.write_text(json.dumps({'uid': u, 'method': method, 'reply': reply, 'rows': parse_rows(reply),
                                     'secs': round(time.time() - t0, 1)}, indent=1))
        print(f'graphrag-{method}: {len(uids)} questions answered', flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--methods', nargs='+', default=list(METHODS), choices=METHODS)
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == '__main__':
    sys.exit(main())
