"""Build a LightRAG graph over (a subset of) the UDA-Bench NBA corpus.

Uses LightRAG defaults except for the LLM, which is wrapped so that every
call's token usage (including reasoning tokens) is appended to usage.jsonl.

    envs/lightrag/bin/python lightrag_build.py --workdir runs/lightrag-pilot --limit 5
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from openai import AsyncOpenAI

from lightrag import LightRAG
from lightrag.llm.openai import openai_embed

HERE = Path(__file__).parent
DOCS = HERE / 'data' / 'docs'
TYPES = ('player', 'team', 'city', 'owner')


def list_docs(manifest: Path | None, limit: int | None) -> list[Path]:
    if manifest:
        return [DOCS / line.strip() for line in manifest.read_text().splitlines() if line.strip()]
    # with a limit, take the first N documents of each type, so a pilot covers all types
    return [
        p
        for t in TYPES
        for p in sorted((DOCS / t / t).glob('*.txt'), key=lambda p: int(p.stem))[:limit]
    ]


def make_llm(model: str, reasoning_effort: str | None, usage_log: Path):
    client = AsyncOpenAI()

    async def llm(prompt, system_prompt=None, history_messages=None, keyword_extraction=False, **kwargs):
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.extend(history_messages or [])
        messages.append({'role': 'user', 'content': prompt})
        params = {'model': model, 'messages': messages}
        if reasoning_effort:
            params['reasoning_effort'] = reasoning_effort
        if kwargs.get('response_format') is not None:
            params['response_format'] = kwargs['response_format']
        elif keyword_extraction:
            params['response_format'] = {'type': 'json_object'}
        t0 = time.time()
        resp = await client.chat.completions.create(**params)
        u = resp.usage
        record = {
            'ts': t0,
            'secs': round(time.time() - t0, 2),
            'input': u.prompt_tokens,
            'cached': getattr(u.prompt_tokens_details, 'cached_tokens', 0) or 0,
            'output': u.completion_tokens,
            'reasoning': getattr(u.completion_tokens_details, 'reasoning_tokens', 0) or 0,
            'kind': 'keywords' if keyword_extraction else 'index',
        }
        with usage_log.open('a') as f:
            f.write(json.dumps(record) + '\n')
        return resp.choices[0].message.content

    return llm


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--workdir', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, help='file with doc paths relative to data/docs')
    ap.add_argument('--limit', type=int, help='first N docs of each type (pilot)')
    ap.add_argument('--model', default='gpt-5.6-luna')
    ap.add_argument('--reasoning-effort', default='low', help="'' to use the model default")
    ap.add_argument('--max-async', type=int, default=8)
    args = ap.parse_args()

    args.workdir.mkdir(parents=True, exist_ok=True)
    docs = list_docs(args.manifest, args.limit)
    (args.workdir / 'docs.txt').write_text('\n'.join(str(p.relative_to(DOCS)) for p in docs) + '\n')
    (args.workdir / 'config.json').write_text(json.dumps(vars(args), default=str, indent=2))

    rag = LightRAG(
        working_dir=str(args.workdir / 'storage'),
        llm_model_func=make_llm(args.model, args.reasoning_effort or None, args.workdir / 'usage.jsonl'),
        llm_model_name=args.model,
        llm_model_max_async=args.max_async,
        embedding_func=openai_embed,
    )
    await rag.initialize_storages()
    t0 = time.time()
    # LightRAG treats documents with the same file name as duplicates, and every
    # type folder has a 1.txt, so name them <type>_<n>.txt (as in the GraphRAG input)
    names = [f'{p.parent.name}_{p.name}' for p in docs]
    await rag.ainsert([p.read_text(errors='ignore') for p in docs], ids=names, file_paths=names)
    await rag.finalize_storages()
    print(f'{len(docs)} docs indexed in {time.time() - t0:.0f}s')


if __name__ == '__main__':
    asyncio.run(main())
