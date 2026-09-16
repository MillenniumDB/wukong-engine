"""Run the official Text2KGBench evaluator over converted WUKONG output.

Writes an evaluation config pointing at the converted system outputs and invokes
the benchmark's own `run_eval.py`, so the reported numbers come from the
benchmark authors' implementation rather than a reimplementation.

The evaluator appends to its average metrics file, so any previous copy is
removed first to keep runs from accumulating.

Example:
    python paper/benchmark/text2kg_eval.py \
        --benchmark ../benchmarks/Text2KGBench \
        --responses paper/benchmark/results/wukong \
        --out paper/benchmark/results/eval \
        --python /path/to/env/bin/python
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from text2kg_setup import ONTOLOGIES  # noqa: E402


def build_config(args: argparse.Namespace, ontologies: list[str]) -> dict[str, object]:
    """Build the evaluator config with absolute paths.

    Paths are absolute because run_eval.py resolves them against its own working
    directory, which must be the benchmark's evaluation source directory.
    """
    dataset = Path(args.benchmark).resolve() / 'data' / args.dataset
    responses = Path(args.responses).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    patterns = {
        'sys': str(responses / args.sys_pattern),
        'gt': str(dataset / 'ground_truth' / 'ont_$$onto$$_ground_truth.jsonl'),
        'onto': str(dataset / 'ontologies' / '$$onto$$_ontology.json'),
        'output': str(out_dir / 'ont_$$onto$$_stats.jsonl'),
    }

    # The manually verified subset only exists for the main test split
    selected = dataset / 'manually_verified_sentences'
    if selected.is_dir():
        patterns['selected_ids'] = str(selected / 'selected_ont_$$onto$$.txt')

    return {
        'onto_list': ontologies,
        'path_patterns': patterns,
        'avg_out_file': str(out_dir / 'ont_avg_stats.jsonl'),
    }


def main() -> int:
    """Generate the evaluation config and run the benchmark evaluator."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--benchmark', type=Path, required=True, help='Path to the Text2KGBench repository')
    parser.add_argument('--dataset', default='wikidata_tekgen', help='Benchmark dataset directory name')
    parser.add_argument('--onto', action='append', choices=[*ONTOLOGIES], help='Ontology to evaluate (repeatable)')
    parser.add_argument('--responses', type=Path, default=Path('paper/benchmark/results/wukong'))
    parser.add_argument(
        '--sys-pattern',
        default='ont_$$onto$$_wukong_responses.jsonl',
        help='System output filename pattern, for re-scoring a published baseline under this harness',
    )
    parser.add_argument('--out', type=Path, default=Path('paper/benchmark/results/eval'))
    parser.add_argument('--python', default=sys.executable, help='Interpreter with nltk available')
    args = parser.parse_args()

    ontologies = args.onto or [*ONTOLOGIES]
    config = build_config(args, ontologies)

    out_dir = Path(args.out).resolve()
    config_path = out_dir / 'eval_config.json'
    config_path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')

    # run_eval.py appends, so stale averages would be mixed into this run
    Path(str(config['avg_out_file'])).unlink(missing_ok=True)

    evaluation_dir = Path(args.benchmark).resolve() / 'src' / 'evaluation'
    result = subprocess.run(  # noqa: S603
        [args.python, 'run_eval.py', '--eval_config_path', str(config_path)],
        cwd=evaluation_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout[-4000:])
        print(result.stderr[-4000:], file=sys.stderr)
        return result.returncode

    print(f'Evaluation complete. Metrics written to: {out_dir}\n')
    for line in Path(str(config['avg_out_file'])).read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        name = record.get('onto', record.get('id', '?'))
        print(
            f'{name:12s} {record["type"]:20s} '
            f'P={record["avg_precision"]} R={record["avg_recall"]} F1={record["avg_f1"]} '
            f'OC={record["avg_onto_conf"]} SH={record["avg_sub_halluc"]} '
            f'RH={record["avg_rel_halluc"]} OH={record["avg_obj_halluc"]}',
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
