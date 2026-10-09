"""Summarize LLM token usage of a LightRAG run (usage.jsonl written by lightrag_build.py).

    python3 usage_summary.py runs/lightrag-pilot [--scale-to-tokens 1736964]

With --scale-to-tokens, extrapolates linearly from the corpus tokens of the run
(o200k_base, read from corpus_tokens.txt if present) to a target corpus size.
"""

import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('run', type=Path)
ap.add_argument('--corpus-tokens', type=int, help='tokens of the documents in this run')
ap.add_argument('--scale-to-tokens', type=int, help='tokens of the target corpus')
args = ap.parse_args()

rows = [json.loads(line) for line in (args.run / 'usage.jsonl').read_text().splitlines()]
tot = {k: sum(r[k] for r in rows) for k in ('input', 'cached', 'output', 'reasoning')}
print(f'calls={len(rows)}  ' + '  '.join(f'{k}={v:,}' for k, v in tot.items()))
if args.corpus_tokens and args.scale_to_tokens:
    f = args.scale_to_tokens / args.corpus_tokens
    print(f'x{f:.1f} -> ' + '  '.join(f'{k}={int(v * f):,}' for k, v in tot.items()) + f'  calls={int(len(rows) * f):,}')
