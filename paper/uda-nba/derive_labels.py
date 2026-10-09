"""Derive a relation label for every LightRAG / GraphRAG edge from its free-text description.

GraphRAG edges carry no label, only a description; LightRAG edges carry keywords. To measure
the relation vocabulary of both the same way, an LLM reads each edge description and names
the relation as a short predicate, with its direction (which endpoint is the subject).
This is the post-processing a user would need before querying such a graph by relation.

    envs/graphrag/bin/python derive_labels.py GraphRAG [--limit 300] [--out runs/labels]

Same model as the graph builds (gpt-5.6-luna, low reasoning). Resumable: results are
appended to <out>/<system>.jsonl and edges already labeled are skipped. Token usage is
appended to <out>/<system>.usage.jsonl.
"""

import argparse
import asyncio
import json
import random
from pathlib import Path

from openai import AsyncOpenAI

import e1_analysis as A

SYSTEM = 'You turn free-text descriptions of graph edges into relation labels.'
PROMPT = """Each item below describes the relationship between two entities, X and Y.
For each item, name the single main relation between them as a short predicate:
- lower_snake_case, 1 to 3 words, based on a verb where possible
- general rather than specific: no dates, numbers or entity names in the predicate
- always in the present tense, third person: owns (not own / owned), defeats, plays_for, located_in
Also give the subject of the predicate: "X" if it reads "X <predicate> Y", "Y" if it reads "Y <predicate> X".

Examples from an unrelated domain:
- X = Marie Curie, Y = polonium, "Marie Curie discovered polonium in 1898." -> subject X, predicate discovers
- X = Mona Lisa, Y = Louvre, "The Louvre has housed the Mona Lisa since 1797." -> subject Y, predicate houses

Return JSON: {{"labels": [{{"id": <id>, "subject": "X" or "Y", "predicate": "<predicate>"}}, ...]}}, one entry per item.

Items:
{items}"""

LOADERS = {'LightRAG': A.load_lightrag, 'GraphRAG': A.load_graphrag}


async def label_batch(client, args, batch, out, usage, sem, lock):
    items = '\n'.join(json.dumps({'id': i, 'X': x, 'Y': y, 'description': d[:600]}, ensure_ascii=False)
                      for i, x, y, d in batch)
    async with sem:
        for attempt in range(4):
            try:
                resp = await client.chat.completions.create(
                    model=args.model, reasoning_effort=args.reasoning_effort,
                    response_format={'type': 'json_object'},
                    messages=[{'role': 'system', 'content': SYSTEM},
                              {'role': 'user', 'content': PROMPT.format(items=items)}])
                got = json.loads(resp.choices[0].message.content)['labels']
                break
            except Exception as e:  # rate limits, malformed JSON
                if attempt == 3:
                    print('batch failed:', batch[0][0], e)
                    return
                await asyncio.sleep(5 * (attempt + 1))
    ids = {i for i, *_ in batch}
    rows = [r for r in got if isinstance(r, dict) and r.get('id') in ids and r.get('predicate')]
    u = resp.usage
    async with lock:
        with out.open('a') as f:
            for r in rows:
                f.write(json.dumps({'id': r['id'], 'subject': r.get('subject'),
                                    'predicate': str(r['predicate']).strip().lower()}) + '\n')
        with usage.open('a') as f:
            f.write(json.dumps({'input': u.prompt_tokens, 'output': u.completion_tokens,
                                'cached': getattr(u.prompt_tokens_details, 'cached_tokens', 0) or 0,
                                'reasoning': getattr(u.completion_tokens_details, 'reasoning_tokens', 0) or 0,
                                'items': len(batch), 'labeled': len(rows)}) + '\n')


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('system', choices=list(LOADERS))
    ap.add_argument('--out', type=Path, default=A.RUNS / 'labels')
    ap.add_argument('--limit', type=int, help='label a random sample of this many edges (pilot)')
    ap.add_argument('--batch', type=int, default=100)
    ap.add_argument('--max-async', type=int, default=16)
    ap.add_argument('--model', default='gpt-5.6-luna')
    ap.add_argument('--reasoning-effort', default='low')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = f'.pilot{args.limit}' if args.limit else ''
    out = args.out / f'{args.system}{suffix}.jsonl'
    usage = args.out / f'{args.system}{suffix}.usage.jsonl'

    nodes, edges, _ = LOADERS[args.system]()
    todo = list(range(len(edges)))  # edge id = position in the loader's edge list
    if args.limit:
        todo = sorted(random.Random(0).sample(todo, args.limit))
    done = {json.loads(line)['id'] for line in out.open()} if out.exists() else set()
    todo = [i for i in todo if i not in done]
    print(f'{args.system}: {len(edges)} edges, {len(done)} already labeled, {len(todo)} to go')
    batches = [[(i, nodes[edges[i]['src']]['name'], nodes[edges[i]['dst']]['name'], edges[i]['text'])
                for i in todo[k:k + args.batch]] for k in range(0, len(todo), args.batch)]
    client, sem, lock = AsyncOpenAI(), asyncio.Semaphore(args.max_async), asyncio.Lock()
    await asyncio.gather(*(label_batch(client, args, b, out, usage, sem, lock) for b in batches))
    n = sum(1 for _ in out.open())
    print(f'labeled {n} edges -> {out}')


if __name__ == '__main__':
    asyncio.run(main())
