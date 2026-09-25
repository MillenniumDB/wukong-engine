"""Re-score every system under corrected copies of the Text2KGBench data.

The benchmark's data carries defects that distort the scores of every system
(paper/benchmark.md section 8). This script corrects them on a *copy* of the
benchmark and re-runs the unmodified `run_eval.py` over every system's published
or converted output, so a correction is always applied identically to WUKONG and
to the baselines. Neither the benchmark repository nor its evaluator is touched.

Corrections, applied cumulatively in this order so their effects can be read
one at a time:

    B1 strip_labels         strip the trailing space from ontology relation labels
    B2 drop_empty           drop sentences whose gold standard is empty
    B3 drop_off_ontology    drop gold triples whose relation the ontology lacks
    B4 normalize_dates      rewrite zero-day gold dates ("00  <YYYY>", "00 <Month> <YYYY>")
                            in the train split's "01 January <YYYY>" / "01 <Month> <YYYY>"
    B5 drop_train_overlap   drop test sentences that appear verbatim in train
    B6 drop_absent_subject  drop gold triples whose subject the sentence lacks

B1-B5 is the adjusted protocol; B6 is reported only as a secondary view. B2 is
applied after the triple-level corrections, so a sentence emptied by B3 or B6 is
dropped as well.

Each variant is materialized as a benchmark-shaped directory whose `src/` and
unchanged data directories are symlinks to the real benchmark, so it can be
passed as `--benchmark` to any harness script.

Run it with the evaluator environment, which has nltk:

    paper/benchmark/.venv-eval/bin/python paper/benchmark/text2kg_rescore.py \
        --benchmark ../benchmarks/Text2KGBench
"""

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from nltk.stem import PorterStemmer

sys.path.insert(0, str(Path(__file__).parent))

from text2kg_diagnose import normalize, read_jsonl  # noqa: E402
from text2kg_setup import ONTOLOGIES  # noqa: E402

CORRECTIONS = (
    'strip_labels',
    'drop_empty',
    'drop_off_ontology',
    'normalize_dates',
    'drop_train_overlap',
    'drop_absent_subject',
)

# Cumulative variants: each applies every correction before it
VARIANTS = {
    '0_vanilla': (),
    **{f'{index}_{name}': CORRECTIONS[:index] for index, name in enumerate(CORRECTIONS, start=1)},
}
ADJUSTED = '5_drop_train_overlap'
REACHABLE = '6_drop_absent_subject'

# The only benchmark files a correction rewrites; everything else is symlinked
REWRITTEN = ('ontologies', 'ground_truth', 'manually_verified_sentences')

# Gold dates with a zero day ("00  1913", "00 June 1962"), a convention the train
# split never shows: there, a year-only date is "01 January <YYYY>" and a
# month-and-year date is "01 <Month> <YYYY>"
ZERO_DAY_DATE = re.compile(r'^00\s+(?:([A-Za-z]+)\s+)?(\d{4})$')


def normalize_date(value: str) -> str:
    """Rewrite a zero-day gold date in the convention the train split uses.

    Args:
        value: Gold object string, possibly a zero-day date such as "00 June 1962".

    Returns:
        The date rewritten with day "01" (and month "January" when absent), or ``value`` unchanged if it isn't a
        zero-day date.
    """
    match = ZERO_DAY_DATE.match(value)
    if match is None:
        return value
    return f'01 {match.group(1) or "January"} {match.group(2)}'

METRICS = ('avg_precision', 'avg_recall', 'avg_f1', 'avg_onto_conf', 'avg_sub_halluc', 'avg_rel_halluc', 'avg_obj_halluc')


def systems(root: Path, benchmark: Path, dataset: str) -> dict[str, tuple[Path, str]]:
    """Map each system name to its output directory and filename pattern.

    Args:
        root: Harness directory holding the WUKONG result directories.
        benchmark: Path to the Text2KGBench repository, which holds the baseline outputs.
        dataset: Benchmark dataset name, e.g. "wikidata_tekgen".

    Returns:
        Mapping from system name to a tuple of its responses directory and its response filename pattern, where
        ``$$onto$$`` stands for the ontology name.
    """
    baselines = benchmark / 'data' / dataset / 'baselines'
    wukong = 'ont_$$onto$$_wukong_responses.jsonl'
    return {
        'WUKONG primary': (root / 'results' / 'wukong', wukong),
        'WUKONG arm B': (root / 'results-examples' / 'wukong', wukong),
        'WUKONG properties': (root / 'results-properties' / 'wukong', wukong),
        'Vicuna-13B': (baselines / 'Vicuna-13B' / 'llm_responses', 'ont_$$onto$$_llm_responses.jsonl'),
        'Alpaca-LoRA-13B': (baselines / 'Alpaca-LoRA-13B' / 'llm_responses', 'ont_$$onto$$_lora-13b_responses_v2.jsonl'),
    }


def slug(name: str) -> str:
    """Turn a system name into a directory name.

    Args:
        name: Display name of the system.

    Returns:
        The lowercased name with every run of non-alphanumeric characters replaced by a single underscore.
    """
    return re.sub(r'[^0-9A-Za-z]+', '_', name).strip('_').lower()


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Write records as ASCII-escaped JSONL, as the benchmark ships them.

    Escaping matters: raw U+2028/U+0085 inside a string would split the line for
    any reader using `str.splitlines()`.

    Args:
        path: Output file; its parent directories are created if missing.
        records: Records to write, one per line.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as out_file:
        for record in records:
            out_file.write(json.dumps(record) + '\n')


def correct_ontology(
    onto: str,
    source: Path,
    target: Path,
    corrections: tuple[str, ...],
    stemmer: PorterStemmer,
) -> dict[str, int]:
    """Write the corrected ontology, ground truth and verified subset for one ontology.

    Args:
        onto: Ontology name.
        source: Original dataset directory to read from.
        target: Variant dataset directory to write the corrected files into.
        corrections: Names of the corrections to apply (see ``CORRECTIONS``).
        stemmer: Stemmer used to match gold subjects against the sentence, as the evaluator does.

    Returns:
        Counts of the kept sentences (``sentences``), verified sentences (``verified``) and gold triples
        (``triples``).
    """
    ontology = json.loads((source / 'ontologies' / f'{onto}_ontology.json').read_text(encoding='utf-8'))
    if 'strip_labels' in corrections:
        for relation in ontology['relations']:
            relation['label'] = relation['label'].strip()
    (target / 'ontologies').mkdir(parents=True, exist_ok=True)
    (target / 'ontologies' / f'{onto}_ontology.json').write_text(
        json.dumps(ontology, indent=2, ensure_ascii=False) + '\n', encoding='utf-8',
    )

    labels = {relation['label'].strip() for relation in ontology['relations']}
    concepts = ' '.join(concept['label'] for concept in ontology['concepts'])
    train_path = source / 'train' / f'ont_{onto}_train.jsonl'
    train = {record.get('sent', '').strip() for record in read_jsonl(train_path)} if train_path.exists() else set()

    kept: list[dict[str, Any]] = []
    for record in read_jsonl(source / 'ground_truth' / f'ont_{onto}_ground_truth.jsonl'):
        if 'drop_train_overlap' in corrections and record['sent'].strip() in train:
            continue
        haystack = normalize(stemmer, record['sent'] + ' ' + concepts)
        triples = []
        for triple in record['triples']:
            triple = dict(triple)
            if 'drop_off_ontology' in corrections and triple['rel'].strip() not in labels:
                continue
            if 'drop_absent_subject' in corrections and haystack.find(normalize(stemmer, triple['sub'])) == -1:
                continue
            if 'normalize_dates' in corrections:
                triple['obj'] = normalize_date(triple['obj'])
            triples.append(triple)
        if 'drop_empty' in corrections and not triples:
            continue
        kept.append({**record, 'triples': triples})
    write_jsonl(target / 'ground_truth' / f'ont_{onto}_ground_truth.jsonl', kept)

    # run_eval.py divides the verified-subset sums by the size of this list, so
    # it must only name sentences that survive in the ground truth
    kept_ids = {record['id'] for record in kept}
    selected_path = source / 'manually_verified_sentences' / f'selected_ont_{onto}.txt'
    selected = [line.strip() for line in selected_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    selected = [sentence_id for sentence_id in selected if sentence_id in kept_ids]
    (target / 'manually_verified_sentences').mkdir(parents=True, exist_ok=True)
    (target / 'manually_verified_sentences' / f'selected_ont_{onto}.txt').write_text(
        ''.join(f'{sentence_id}\n' for sentence_id in selected), encoding='utf-8',
    )
    return {
        'sentences': len(kept),
        'verified': len(selected),
        'triples': sum(len(record['triples']) for record in kept),
    }


def build_variant(
    name: str,
    corrections: tuple[str, ...],
    benchmark: Path,
    dataset: str,
    out_root: Path,
    stemmer: PorterStemmer,
) -> tuple[Path, dict[str, dict[str, int]]]:
    """Materialize one corrected, benchmark-shaped directory.

    Args:
        name: Variant name, used as the directory name under ``out_root``.
        corrections: Names of the corrections to apply.
        benchmark: Path to the Text2KGBench repository.
        dataset: Benchmark dataset name.
        out_root: Directory under which the variant is created.
        stemmer: Stemmer passed on to the ground-truth corrections.

    Returns:
        A tuple of the variant's root directory and the per-ontology counts from ``correct_ontology``.
    """
    root = out_root / name
    source = benchmark / 'data' / dataset
    target = root / 'data' / dataset
    target.mkdir(parents=True, exist_ok=True)

    links = [(root / 'src', benchmark / 'src')]
    links += [(target / entry.name, entry) for entry in source.iterdir() if entry.name not in REWRITTEN]
    for link, destination in links:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(destination.resolve(), target_is_directory=destination.is_dir())

    counts = {onto: correct_ontology(onto, source, target, corrections, stemmer) for onto in ONTOLOGIES}
    return root, counts


def evaluate(
    variant_root: Path,
    responses: Path,
    pattern: str,
    out: Path,
    python: str,
) -> dict[tuple[str, str], dict[str, float]]:
    """Score one system under one variant with the unmodified evaluator.

    Args:
        variant_root: Benchmark-shaped variant directory to score against.
        responses: Directory holding the system's response files.
        pattern: Response filename pattern, with ``$$onto$$`` standing for the ontology name.
        out: Directory the evaluator writes its outputs to.
        python: Python interpreter used to run the evaluator.

    Returns:
        Mapping from ``(ontology, population)`` to the metric values in ``METRICS``; the global row is keyed
        ``("global", "global")``.

    Raises:
        RuntimeError: If the evaluator exits with a non-zero status.
    """
    result = subprocess.run(  # noqa: S603
        [
            python, str(Path(__file__).parent / 'text2kg_eval.py'),
            '--benchmark', str(variant_root),
            '--responses', str(responses),
            '--sys-pattern', pattern,
            '--out', str(out),
            '--python', python,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f'Evaluation failed for {responses} under {variant_root}:\n{result.stderr[-2000:]}')

    stats: dict[tuple[str, str], dict[str, float]] = {}
    for line in (out / 'ont_avg_stats.jsonl').read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        stats[record.get('onto', record.get('id')), record['type']] = {key: float(record[key]) for key in METRICS}
    return stats


def print_tables(
    counts: dict[str, dict[str, dict[str, int]]],
    scores: dict[str, dict[str, dict[tuple[str, str], dict[str, float]]]],
    names: list[str],
) -> None:
    """Print the data, waterfall, comparison and per-ontology tables.

    Args:
        counts: Per-variant, per-ontology counts from ``build_variant``.
        scores: Per-variant, per-system scores from ``evaluate``.
        names: Systems to include, in column order.
    """
    print('## Scored population per variant\n')
    print('| Variant | Sentences | Verified | Gold triples |')
    print('|---|---|---|---|')
    for variant, per_onto in counts.items():
        totals = {key: sum(item[key] for item in per_onto.values()) for key in ('sentences', 'verified', 'triples')}
        print(f'| {variant} | {totals["sentences"]} | {totals["verified"]} | {totals["triples"]} |')

    print('\n## Global F1 per cumulative correction\n')
    print(f'| Variant | {" | ".join(names)} |')
    print(f'|---|{"---|" * len(names)}')
    for variant in counts:
        row = ' | '.join(f'{scores[variant][name][("global", "global")]["avg_f1"]:.2f}' for name in names)
        print(f'| {variant} | {row} |')

    for variant in (ADJUSTED, REACHABLE):
        print(f'\n## Global comparison, {variant}\n')
        print('| System | P | R | F1 | Conf. | Subj. hall. | Rel. hall. | Obj. hall. |')
        print('|---|---|---|---|---|---|---|---|')
        for name in names:
            row = scores[variant][name][('global', 'global')]
            print(f'| {name} | {" | ".join(f"{row[metric]:.2f}" for metric in METRICS)} |')

        for population in ('all_test_cases', 'selected_test_cases'):
            print(f'\n### Per-ontology F1, {variant}, {population}\n')
            print(f'| Ontology | {" | ".join(names)} |')
            print(f'|---|{"---|" * len(names)}')
            for onto in ONTOLOGIES:
                row = ' | '.join(f'{scores[variant][name][(onto, population)]["avg_f1"]:.2f}' for name in names)
                print(f'| {onto} | {row} |')

    print('\n## Verified-subset F1 per variant\n')
    print(f'| Variant | {" | ".join(names)} |')
    print(f'|---|{"---|" * len(names)}')
    for variant in counts:
        # The evaluator has no global row for the verified subset, so average
        # the per-ontology rows the same way it averages all test cases
        row = ' | '.join(
            f'{sum(scores[variant][name][(onto, "selected_test_cases")]["avg_f1"] for onto in ONTOLOGIES) / len(ONTOLOGIES):.2f}'
            for name in names
        )
        print(f'| {variant} | {row} |')


def main() -> int:
    """Build every variant, score every system under it and print the tables.

    Returns:
        The process exit code, always 0.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--benchmark', type=Path, required=True, help='Path to the Text2KGBench repository')
    parser.add_argument('--dataset', default='wikidata_tekgen')
    parser.add_argument('--root', type=Path, default=Path('paper/benchmark'), help='Harness directory')
    parser.add_argument('--variants-root', type=Path, default=Path('paper/benchmark/scoring'))
    parser.add_argument('--out', type=Path, default=Path('paper/benchmark/results-properties/scoring'))
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()

    benchmark = args.benchmark.resolve()
    stemmer = PorterStemmer()
    all_systems = systems(args.root.resolve(), benchmark, args.dataset)
    names = [name for name, (responses, _) in all_systems.items() if responses.is_dir()]

    roots: dict[str, Path] = {}
    counts: dict[str, dict[str, dict[str, int]]] = {}
    for variant, corrections in VARIANTS.items():
        roots[variant], counts[variant] = build_variant(
            variant, corrections, benchmark, args.dataset, args.variants_root.resolve(), stemmer,
        )

    jobs = {
        (variant, name): (roots[variant], *all_systems[name], args.out.resolve() / variant / slug(name), sys.executable)
        for variant in VARIANTS
        for name in names
    }
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {key: pool.submit(evaluate, *job) for key, job in jobs.items()}
    scores: dict[str, dict[str, dict[tuple[str, str], dict[str, float]]]] = {}
    for (variant, name), future in futures.items():
        scores.setdefault(variant, {})[name] = future.result()

    summary = {
        'counts': counts,
        'scores': {
            variant: {name: {f'{onto}|{kind}': row for (onto, kind), row in table.items()} for name, table in by_name.items()}
            for variant, by_name in scores.items()
        },
    }
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')

    print_tables(counts, scores, names)
    return 0


if __name__ == '__main__':
    sys.exit(main())
