"""Type conformance on Text2KGBench: do triples respect their relation's declared subject and object types?

The benchmark's "ontology conformance" only checks that a triple's relation label is in the ontology. This script
also checks the declared domain and range. Systems output untyped strings, so every subject and object is typed by
one judge, applied identically to every system and to the gold standard:

    - one LLM call per test sentence (same model as the systems, low effort, strict JSON output) gets the sentence,
      the ontology's concepts and a numbered list of every phrase any system (or the gold) used as a subject or
      object in that sentence, and answers which concepts each phrase's referent is an instance of (several, or
      none). It never sees the relations, so it cannot be swayed by them;
    - judgements are cached per sentence and phrase (`cache/<onto>.json`), so adding a system later only types its
      new phrases.

Per system, over all test sentences, it reports: triples; vocabulary conformance (the benchmark's metric); domain
conformance (subject typed as the relation's declared domain, over triples whose relation is in the ontology and
declares a domain concept); range conformance (likewise for objects, where the range is a declared concept); and
type conformance (both declared sides conform). Writes `summary.json` and `sample.csv` (random judgements, for a
hand check) under --out.

Example:
    OPENAI_API_KEY=... python paper/benchmark/text2kg_typecheck.py --benchmark ../benchmarks/Text2KGBench \
        --system "Wukong props=paper/benchmark/results-x2-r1-props" --out paper/benchmark/results-typecheck
"""

import argparse
import asyncio
import csv
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from text2kg_setup import ONTOLOGIES  # noqa: E402

from wukong_engine.app.llm.elements import LLMRequest  # noqa: E402
from wukong_engine.app.llm.elements.values import ReasoningEffort  # noqa: E402
from wukong_engine.app.llm.elements.values.prompt import LLMPrompt  # noqa: E402
from wukong_engine.app.llm.model import LLM  # noqa: E402
from wukong_engine.infrastructure.config.env import load_env_config  # noqa: E402
from wukong_engine.infrastructure.llm.openai.client import OpenAIClient  # noqa: E402
from wukong_engine.infrastructure.llm.openai.config import OpenAIConfig  # noqa: E402

NONE = 'none of these'
ATTEMPTS = 4
INSTRUCTIONS = (
    'You classify what phrases refer to. For each numbered phrase, say which of the listed concepts the thing it '
    'refers to, in the given sentence, is an instance of. Read each concept broadly: a thing counts as an instance '
    'of a concept if it belongs to it or to a narrower kind of it (a scientific journal is a kind of literature, an '
    'astronaut is a kind of human, a football club is a kind of sports team). A thing can be an instance of several concepts; if it is '
    f'an instance of none of them (for example a date, a number or a role), answer "{NONE}". Judge only what each '
    'phrase refers to, not whether any statement about it is true.'
)


def norm(label: str) -> str:
    """Normalize a relation label the way the benchmark's evaluator does."""
    return re.sub(r'(_|\s+)', '', label).lower()


def load_triples(path: Path, gold: bool) -> dict[str, list[tuple[str, str, str]]]:
    """Read one ontology's triples per sentence id, from a system output or the ground truth."""
    out: dict[str, list[tuple[str, str, str]]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        triples = row.get('triples') or []
        if gold:
            out[row['id']] = [(t['sub'], t['rel'], t['obj']) for t in triples]
        else:
            out[row['id']] = [tuple(str(x) for x in t[:3]) for t in triples if isinstance(t, list) and len(t) >= 3]
    return out


def system_files(args: argparse.Namespace) -> dict[str, tuple[Path, str]]:
    """Map each system to its per-ontology response file pattern (`{onto}` placeholder) and kind."""
    baselines = args.benchmark / 'data' / args.dataset / 'baselines'
    files = {
        'Gold standard': (args.benchmark / 'data' / args.dataset / 'ground_truth' / 'ont_{onto}_ground_truth.jsonl', 'gold'),
        'Vicuna-13B': (baselines / 'Vicuna-13B' / 'llm_responses' / 'ont_{onto}_llm_responses.jsonl', 'system'),
        'Alpaca-LoRA-13B': (baselines / 'Alpaca-LoRA-13B' / 'llm_responses' / 'ont_{onto}_lora-13b_responses_v2.jsonl', 'system'),
    }
    for spec in args.system:
        name, _, directory = spec.partition('=')
        d = Path(directory)
        files[name] = ((d / 'wukong' / 'ont_{onto}_wukong_responses.jsonl') if (d / 'wukong').is_dir()
                       else (d / 'llm' / 'ont_{onto}_llm_responses.jsonl'), 'system')
    return files


async def judge(client: OpenAIClient, sentence: str, concepts: list[str], phrases: list[str]) -> dict[str, list[str]]:
    """Type the phrases of one sentence; returns phrase -> concepts (empty list for none)."""
    numbered = '\n'.join(f'{i + 1}. {p}' for i, p in enumerate(phrases))
    content = f'Sentence: {sentence}\n\nConcepts: {", ".join(concepts)}\n\nPhrases:\n{numbered}'
    schema = {
        'type': 'object',
        'properties': {'types': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'index': {'type': 'integer'},
                           'concepts': {'type': 'array', 'items': {'type': 'string', 'enum': [*concepts, NONE]}}},
            'required': ['index', 'concepts'], 'additionalProperties': False}}},
        'required': ['types'], 'additionalProperties': False,
    }
    request = LLMRequest(prompt=LLMPrompt(content=content, instructions=INSTRUCTIONS, schema=schema),
                         reasoning_effort=ReasoningEffort.LOW)
    for attempt in range(ATTEMPTS):
        try:
            data = json.loads((await client.generate(request)).content)
            result = {p: [] for p in phrases}
            for item in data['types']:
                if 1 <= item['index'] <= len(phrases):
                    result[phrases[item['index'] - 1]] = [c for c in item['concepts'] if c != NONE]
            return result
        except Exception as error:  # noqa: BLE001
            if attempt == ATTEMPTS - 1:
                print(f'    judge failed: {type(error).__name__}: {error}', file=sys.stderr)
                return {}
            await asyncio.sleep(5 * 2 ** attempt)
    return {}


async def type_ontology(args, client, onto, files) -> tuple[dict, dict, dict, list]:
    """Type every phrase of one ontology (cached) and return its ontology, sentences, typings and system triples."""
    dataset = args.benchmark / 'data' / args.dataset
    ontology = json.loads((dataset / 'ontologies' / f'{onto}_ontology.json').read_text())
    concepts = sorted({c['label'].strip() for c in ontology['concepts']})
    sentences = {json.loads(l)['id']: json.loads(l)['sent'] for l in (dataset / 'test' / f'ont_{onto}_test.jsonl').read_text().splitlines() if l.strip()}
    triples = {name: load_triples(Path(str(pattern).format(onto=onto)), kind == 'gold') for name, (pattern, kind) in files.items()}

    cache_file = args.out / 'cache' / f'{onto}.json'
    cache: dict[str, dict[str, list[str]]] = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    todo = {}
    for sid in sentences:
        phrases = {p.strip() for per_system in triples.values() for s, _, o in per_system.get(sid, []) for p in (s, o) if p.strip()}
        missing = sorted(p for p in phrases if p not in cache.get(sid, {}))
        if missing:
            todo[sid] = missing
    semaphore = asyncio.Semaphore(args.concurrency)

    async def one(sid):
        async with semaphore:
            return sid, await judge(client, sentences[sid], concepts, todo[sid])

    for sid, typed in await asyncio.gather(*(one(sid) for sid in todo)):
        cache.setdefault(sid, {}).update(typed)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    print(f'{onto:12s} sentences judged now: {len(todo)}', flush=True)
    return ontology, sentences, cache, triples


def score(ontology: dict, cache: dict, per_sentence: dict, sample: list, name: str, onto: str) -> dict[str, int]:
    """Count vocabulary, domain, range and full type conformance for one system on one ontology."""
    concept = {c['qid']: c['label'].strip() for c in ontology['concepts']}
    relations = {}
    for r in ontology['relations']:
        relations.setdefault(norm(r['label']), []).append((concept.get(r['domain']), concept.get(r['range'])))
    c = dict.fromkeys(('triples', 'in_vocabulary', 'domain_checked', 'domain_ok', 'range_checked', 'range_ok',
                       'type_checked', 'type_ok', 'untyped'), 0)
    for sid, triples in per_sentence.items():
        typed = cache.get(sid, {})
        for s, r, o in triples:
            c['triples'] += 1
            options = relations.get(norm(r))
            if options is None:
                continue
            c['in_vocabulary'] += 1
            if s.strip() not in typed or o.strip() not in typed:
                c['untyped'] += 1
                continue
            s_types, o_types = set(typed[s.strip()]), set(typed[o.strip()])
            # A relation declared more than once (e.g. with two ranges) conforms if any declaration fits
            best = max(options, key=lambda dr: ((dr[0] is None or dr[0] in s_types) + (dr[1] is None or dr[1] in o_types)))
            domain, range_ = best
            d_ok = domain is None or domain in s_types
            r_ok = range_ is None or range_ in o_types
            if domain is not None:
                c['domain_checked'] += 1
                c['domain_ok'] += d_ok
            if range_ is not None:
                c['range_checked'] += 1
                c['range_ok'] += r_ok
            if domain is not None or range_ is not None:
                c['type_checked'] += 1
                c['type_ok'] += d_ok and r_ok
                sample.append([name, onto, sid, s, r, o, '|'.join(sorted(s_types)), domain or '', '|'.join(sorted(o_types)),
                               range_ or '', 'yes' if d_ok and r_ok else 'no'])
    return c


async def main_async(args) -> int:
    client = OpenAIClient(OpenAIConfig(api_key=load_env_config().openai_api_key, model=LLM(name=args.model)))
    files = system_files(args)
    totals = {name: {} for name in files}
    per_onto = {name: {} for name in files}
    sample: list = []
    for onto in args.onto or ONTOLOGIES:
        ontology, _, cache, triples = await type_ontology(args, client, onto, files)
        for name in files:
            counts = score(ontology, cache, triples[name], sample, name, onto)
            per_onto[name][onto] = counts
            for k, v in counts.items():
                totals[name][k] = totals[name].get(k, 0) + v
    rate = lambda a, b: round(a / b, 4) if b else None
    summary = {name: {**t, 'vocabulary_conformance': rate(t['in_vocabulary'], t['triples']),
                      'domain_conformance': rate(t['domain_ok'], t['domain_checked']),
                      'range_conformance': rate(t['range_ok'], t['range_checked']),
                      'type_conformance': rate(t['type_ok'], t['type_checked'])}
               for name, t in totals.items()}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'summary.json').write_text(json.dumps({'totals': summary, 'per_ontology': per_onto}, indent=2))
    random.Random(0).shuffle(sample)
    with (args.out / 'sample.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['system', 'ontology', 'sentence', 'subject', 'relation', 'object', 'subject types (judge)',
                         'declared domain', 'object types (judge)', 'declared range', 'type conformant'])
        writer.writerows(sample[:args.sample])
    print(f'\n{"system":22s} {"triples":>7s} {"vocab":>6s} {"domain":>6s} {"range":>6s} {"types":>6s}')
    for name, s in summary.items():
        f = lambda x: f'{x:.3f}' if x is not None else '   -'
        print(f'{name:22s} {s["triples"]:7d} {f(s["vocabulary_conformance"]):>6s} {f(s["domain_conformance"]):>6s} '
              f'{f(s["range_conformance"]):>6s} {f(s["type_conformance"]):>6s}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--benchmark', type=Path, required=True)
    parser.add_argument('--dataset', default='wikidata_tekgen')
    parser.add_argument('--system', action='append', default=[], metavar='NAME=DIR',
                        help='A results directory holding wukong/ or llm/ (repeatable); gold and both published baselines are always included')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--onto', action='append', choices=[*ONTOLOGIES])
    parser.add_argument('--model', default='gpt-5.6-luna')
    parser.add_argument('--concurrency', type=int, default=15)
    parser.add_argument('--sample', type=int, default=60)
    args = parser.parse_args()
    args.benchmark = args.benchmark.resolve()
    return asyncio.run(main_async(args))


if __name__ == '__main__':
    sys.exit(main())
