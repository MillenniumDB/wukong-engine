"""Check the numbers of the paper against the committed results, and re-run the scoring that needs no LLM.

Always (no API key, no external data, under a minute):
    1. every number of the paper's result tables against the committed summaries: Table 2 (graph structure),
       Table 3 (graph quality), Table 4 (Text2KGBench), Table 5 and the paired differences of Section 4.4 (question
       answering), Table 6 (schema components), Table 7 (construction cost), and the LightRAG modes of Appendix C;
    2. the scripts that turn committed outputs into those summaries, re-run on copies: e1_table.py (Table 2),
       m1/table.py (Table 5) and m1/paired.py (paired differences).

With --text2kgbench DIR, a clone of Text2KGBench at commit 50a3d25 (needs nltk; about 3 minutes on 8 cores):
    3. every Text2KGBench system re-scored from its committed outputs with the benchmark's own evaluator, under the
       original and every corrected gold, and the type check re-run from its committed judge cache (no LLM call);
       both compared value by value with the committed summaries.

With --uda-bench DIR, a clone of UDA-Bench at commit f2da981, and --uda-python PYTHON, a Python with pandas<3,
duckdb 1.3.2, sqlglot, pyyaml and tqdm (default: this Python; about 10 minutes):
    4. every question-answering system's committed answers re-scored with UDA-Bench's evaluator and compared
       question by question with the committed scores. The 14 answers kept in the repository only in part (their
       first 1,000 rows; their scores were computed on all the rows) are left out.

The graphs of the NBA experiments are not in the repository, so Tables 3 and 6 and the graph statistics behind
Table 2 can only be compared with their committed summaries here; rebuilding them needs an API key (see
paper/REPRODUCE.md).

Usage (Python 3.14 environment with the engine installed, plus pandas<3 and nltk; see paper/REPRODUCE.md):
    python tests/check_paper_numbers.py [--text2kgbench DIR] [--uda-bench DIR [--uda-python PYTHON]]

Exits with status 0 when every check passes.
"""

import argparse
import csv
import json
import os
import re
import shutil
import statistics as st
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / 'paper' / 'benchmark'
NBA = ROOT / 'paper' / 'uda-nba'
M1 = NBA / 'm1'
FAILURES: list[str] = []

# --- Numbers as printed in the paper -----------------------------------------------------------------------------------
# Table 4: (rescoring names, type-check name, (F1 original gold, F1 corrected gold, P, R, subject hallucination, types))
T2KG = {
    'Wukong, ontology only': (
        ['X2 r1 primary', 'X2 r2 primary', 'X2 r3 primary'],
        'Wukong primary',
        (0.26, 0.27, 0.29, 0.28, 0.00, 0.94),
    ),
    '+ entity examples': (
        ['X2 r1 examples', 'X2 r2 examples', 'X2 r3 examples'],
        'Wukong arm B',
        (0.34, 0.36, 0.38, 0.36, 0.00, 0.95),
    ),
    '+ literal properties': (
        ['X2 r1 props', 'X2 r2 props', 'X2 r3 props'],
        'Wukong props',
        (0.36, 0.38, 0.40, 0.39, 0.00, 0.94),
    ),
    'Prompting, no example': (['X1a zero-shot'], None, (0.32, 0.34, 0.35, 0.34, 0.01, None)),
    'Prompting, one example': (
        ['X1a r1 prompting', 'X1a r2 prompting', 'X1a r3 prompting'],
        'Prompting (luna)',
        (0.47, 0.50, 0.53, 0.50, 0.07, 0.87),
    ),
    'EDC': (['results-x1-edc-r1'], 'EDC', (0.28, 0.30, 0.30, 0.32, 0.02, 0.73)),
    'EDC+R': (
        ['results-x1-edcr-r1', 'results-x1-edcr-r2', 'results-x1-edcr-r3'],
        'EDC+R',
        (0.35, 0.37, 0.37, 0.39, 0.02, 0.74),
    ),
    'KGGen': (['results-kggen-context-r1'], 'KGGen context', (0.29, 0.30, 0.31, 0.31, 0.01, 0.82)),
    'Vicuna-13B': (['Vicuna-13B'], 'Vicuna-13B', (0.35, 0.36, 0.38, 0.36, 0.17, 0.68)),
    'Alpaca-LoRA-13B': (['Alpaca-LoRA-13B'], 'Alpaca-LoRA-13B', (0.27, 0.27, 0.31, 0.27, 0.18, 0.69)),
    'Gold triples': ([], 'Gold standard', (None, None, None, None, None, 0.85)),
}
# Rescoring name -> committed results folder (for --text2kgbench); Vicuna and Alpaca come from the benchmark
T2KG_FOLDERS = {
    **{f'X2 r{r} {a}': f'results-x2-r{r}-{a}' for r in (1, 2, 3) for a in ('primary', 'examples', 'props')},
    **{f'X1a r{r} prompting': f'results-x1-prompt-r{r}' for r in (1, 2, 3)},
    'X1a zero-shot': 'results-x1-prompt0shot-r1',
    **{
        name: name
        for name in (
            'results-kggen-context-r1',
            'results-x1-edc-r1',
            'results-kggen-plain-r1',
            'results-kggen-plain-r2',
            *(f'results-x1-edcr-r{r}' for r in (1, 2, 3)),
        )
    },
}
TYPECHECK_FOLDERS = {
    'Wukong primary': 'results-x2-r1-primary',
    'Wukong arm B': 'results-x2-r1-examples',
    'Wukong props': 'results-x2-r1-props',
    'Prompting (luna)': 'results-x1-prompt-r1',
    'EDC+R': 'results-x1-edcr-r1',
    'EDC': 'results-x1-edc-r1',
    'KGGen plain': 'results-kggen-plain-r1',
    'KGGen plain r2': 'results-kggen-plain-r2',
    'KGGen context': 'results-kggen-context-r1',
}
# Table 2: nodes, node labels, stored labels, stored labels for 90% of edges, derived ones for 90%, typed values per node
STRUCTURE = {
    'Wukong': (2134, 4, 3, 1, 1, 1.5),
    'LightRAG': (34162, 14, 25151, 20747, 1079, 0),
    'GraphRAG': (37917, 99, None, None, 936, 0),
    'KGGen': (21429, None, 4496, 2449, 1113, 0),
}
# Table 3: entities P R F1, relations P R F1, attribute values P R F1, single-valued P R F1, conformance of edges and
# values, unsupported names and values (None: not applicable)
QUALITY_COLUMNS = (
    ('ent_precision', 0),
    ('ent_recall', 0),
    ('ent_f1', 0),
    ('rel_precision', 0),
    ('rel_recall', 0),
    ('rel_f1', 0),
    ('attr_precision', 0),
    ('attr_recall', 0),
    ('attr_f1', 0),
    ('sv_precision', 0),
    ('sv_recall', 0),
    ('sv_f1', 0),
    ('edges_conforming_pct', 1),
    ('constrained_conforming_pct', 0),
    ('entities_unsupported_pct', 1),
    ('values_unsupported_pct', 1),
)
_ = None
QUALITY = {
    'Wukong s5': (96, 99, 98, 92, 92, 92, 98, 91, 94, 79, 89, 84, 100.0, 100, 0.1, 0.3),
    'Neo4j-GraphRAG': (80, 97, 88, 83, 93, 88, 97, 86, 91, 57, 85, 68, 100.0, 42, 0.7, 0.7),
    'LlamaIndex': (91, 99, 95, 93, 96, 95, 96, 35, 51, 61, 61, 61, 98.9, 36, 0.9, 1.5),
    'OntoGPT': (79, 98, 88, 80, 93, 86, 93, 81, 86, 75, 87, 81, 99.7, 90, 0.4, 7.7),
    'LightRAG': (64, 99, 78, 78, 97, 86, _, 75, _, _, _, _, _, _, 1.2, _),
    'GraphRAG': (70, 99, 82, 64, 95, 76, _, 76, _, _, _, _, _, _, 4.4, _),
    'KGGen': (63, 98, 77, 34, 94, 50, _, 51, _, _, _, _, _, _, 1.5, _),
}
# Table 5 and Appendix C: macro F1 per question class and overall; for three-run systems, the range of the overall
QA_TYPES = ('Select', 'Filter', 'Agg', 'Join', 'Mixed')
QA = {
    'wukong_s5': ((0.51, 0.42, 0.80, 0.29, 0.41, 0.44), (0.43, 0.46)),
    'ontogpt_s5': ((0.65, 0.33, 0.37, 0.21, 0.32, 0.34), (0.34, 0.34)),
    'neo4j_s5': ((0.06, 0.12, 0.40, 0.02, 0.14, 0.13), (0.11, 0.15)),
    'llamaindex_s5': ((0.06, 0.07, 0.41, 0.02, 0.08, 0.10), (0.09, 0.11)),
    'lightrag-mix': ((0.13, 0.14, 0.42, 0.06, 0.23, 0.18), None),
    'graphrag-local': ((0.09, 0.07, 0.21, 0.03, 0.15, 0.10), None),
    'floor': ((0.13, 0.27, 0.33, 0.10, 0.30, 0.25), None),
    'lightrag-local': ((0.14, 0.08, 0.33, 0.05, 0.20, 0.13), None),
    'lightrag-global': ((0.10, 0.15, 0.39, 0.02, 0.16, 0.16), None),
    'lightrag-hybrid': ((0.11, 0.13, 0.41, 0.01, 0.19, 0.15), None),
}
# Section 4.4: Wukong minus each system, mean difference and 95% interval (the text gives the intervals of the first
# three, and "0.31 to 0.35" for the other three)
PAIRED = {
    'ontogpt_s5': (0.10, 0.04, 0.17),
    'floor': (0.20, 0.14, 0.26),
    'lightrag-mix': (0.27, 0.21, 0.32),
    'neo4j_s5': (0.31, None, None),
    'llamaindex_s5': (0.35, None, None),
    'graphrag-local': (0.35, None, None),
}
# Table 6: paper label -> (repository variant, output tokens (M), split entities, exact, lenient, wrong values, edges)
ABLATION = {
    's0': ('core', 2.44, 62, 449, 763, 47, 8919),
    's1': ('+bindings', 1.02, 47, 467, 801, 24, 6809),
    's2': ('+guidance', 1.08, 9, 861, 864, 22, 5905),
    's3': ('+validation', 1.10, 8, 870, 870, 19, 5149),
    's4': ('+current_team', 1.11, 8, 871, 871, 21, 3212),  # the paper's full schema is the repository's s5
}
# Table 7 (Appendix B.2): LLM calls, input and output tokens (M), wall time (min); LightRAG and GraphRAG come from
# their build logs, which are not in the repository
COST = {'Wukong': (4447, 6.4, 1.1, 18), 'KGGen': (26025, 13.8, 1.7, 228)}


# --- Helpers -----------------------------------------------------------------------------------------------------------
def check(what: str, ok: bool, detail: str = '') -> None:  # noqa: FBT001
    """Print one check and remember a failure."""
    print(f'  [{"ok" if ok else "FAIL"}] {what}' + ('' if ok or not detail else f'\n         {detail}'))
    if not ok:
        FAILURES.append(what)


def matches(actual: float | None, printed: float | None, decimals: int) -> bool:
    """Whether a value rounds to what the paper prints (None in the paper: not printed, not checked)."""
    if printed is None:
        return True
    return actual is not None and abs(actual - printed) <= 0.5 * 10**-decimals + 1e-9


def compare_row(what: str, actual: list, printed: tuple, decimals: list[int], names: list[str]) -> None:
    """Check a row of printed values against the committed ones."""
    bad = [
        f'{n}: paper {p}, committed {a if a is None else round(a, 4)}'
        for a, p, d, n in zip(actual, printed, decimals, names, strict=True)
        if not matches(a, p, d)
    ]
    check(what, not bad, '; '.join(bad))


def number(cell: str, index: int = 0) -> float | None:
    """Return the index-th number in a formatted cell ('2,134 (2,118-2,152)', '51 / 1,079', '4,447 [4,445-4,448]')."""
    found = re.findall(r'\d[\d,]*(?:\.\d+)?', cell)
    return float(found[index].replace(',', '')) if len(found) > index else None


def run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
    """Run a command, capturing its output."""
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)  # noqa: S603


# --- 1. Committed summaries against the paper --------------------------------------------------------------------------
def check_text2kgbench() -> None:
    """Table 4."""
    print('Table 4 (Text2KGBench) against results-x2/scoring/summary.json and results-typecheck/summary.json:')
    scores = json.loads((BENCH / 'results-x2' / 'scoring' / 'summary.json').read_text())['scores']
    types = json.loads((BENCH / 'results-typecheck' / 'summary.json').read_text())['totals']
    for row, (names, typecheck, printed) in T2KG.items():

        def mean(variant: str, key: str, names: list[str] = names) -> float | None:
            return st.mean(scores[variant][n]['global|global'][key] for n in names) if names else None

        actual = [
            mean('0_vanilla', 'avg_f1'),
            mean('5_drop_train_overlap', 'avg_f1'),
            mean('5_drop_train_overlap', 'avg_precision'),
            mean('5_drop_train_overlap', 'avg_recall'),
            mean('5_drop_train_overlap', 'avg_sub_halluc'),
            types[typecheck]['type_conformance'] if typecheck else None,
        ]
        compare_row(row, actual, printed, [2] * 6, ['F1 orig.', 'F1 corr.', 'P', 'R', 'SH', 'Types'])


def check_structure() -> None:
    """Table 2."""
    print('Table 2 (graph structure) against uda-nba/runs/e1/summary.csv:')
    with (NBA / 'runs' / 'e1' / 'summary.csv').open() as f:
        rows = {
            (r[0], r[1]): dict(zip(header[2:], r[2:], strict=True))
            for header in [next(csv.reader(f))]
            for r in csv.reader(f)
        }
    cells = [
        ('Size', 'Nodes', 0),
        ('Node vocabulary', 'Node types', 0),
        ('Relation vocabulary (own labels)', 'Labels', 0),
        ('Relation vocabulary (own labels)', 'Labels to cover 90% of edges', 0),
        ('Relation vocabulary (derived predicates)', 'Labels to cover 50% / 90% of edges', 1),
        ('Properties', 'Typed property values per node', 0),
    ]
    for system, printed in STRUCTURE.items():
        actual = [number(rows[g, m][system], i) for g, m, i in cells]
        compare_row(
            system,
            actual,
            printed,
            [0, 0, 0, 0, 0, 1],
            ['nodes', 'node labels', 'stored labels', 'stored 90%', 'derived 90%', 'values per node'],
        )


def check_quality() -> None:
    """Table 3."""
    print('Table 3 (graph quality) against uda-nba/runs/quality/summary.csv (means over runs):')
    with (NBA / 'runs' / 'quality' / 'summary.csv').open() as f:
        reader = csv.reader(f)
        metrics, stats = next(reader), next(reader)
        next(reader)
        rows = {
            r[0]: {m: float(v) for m, s, v in zip(metrics, stats, r, strict=True) if s == 'mean' and v} for r in reader
        }
    for system, printed in QUALITY.items():
        actual = [rows[system].get(column) for column, _ in QUALITY_COLUMNS]
        compare_row(system, actual, printed, [d for _, d in QUALITY_COLUMNS], [c for c, _ in QUALITY_COLUMNS])


def qa_rows(scores_dir: Path) -> tuple[dict, dict]:
    """Macro F1 per question class and overall for every system (runs averaged), and each run's overall score."""
    per_system, overall_runs = {}, {}
    for path in sorted(scores_dir.glob('*.json')):
        res = json.loads(path.read_text()).values()
        row = [st.mean(r['macro_f1'] for r in res if r['type'] == t) for t in QA_TYPES]
        row.append(st.mean(r['macro_f1'] for r in res))
        group = re.sub(r'_r\d+$', '', path.stem)
        per_system.setdefault(group, []).append(row)
        overall_runs.setdefault(group, []).append(row[-1])
    return {g: [st.mean(col) for col in zip(*rows, strict=True)] for g, rows in per_system.items()}, overall_runs


def check_qa() -> None:
    """Table 5, Appendix C and the paired differences of Section 4.4."""
    print('Table 5 and Appendix C (question answering) against uda-nba/m1/results/scores:')
    rows, overall_runs = qa_rows(M1 / 'results' / 'scores')
    for system, (printed, printed_range) in QA.items():
        compare_row(system, rows[system], printed, [2] * 6, [*QA_TYPES, 'All'])
        if printed_range:
            actual = [min(overall_runs[system]), max(overall_runs[system])]
            compare_row(f'{system}: range over three runs', actual, printed_range, [2, 2], ['low', 'high'])
    print('Section 4.4 (paired differences) against uda-nba/m1/results/paired.txt:')
    paired = {}
    for line in (M1 / 'results' / 'paired.txt').read_text().splitlines()[1:]:
        name, mean, low, high = re.match(r'\s+(\S+)\s+([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', line).groups()
        paired[name] = (float(mean), float(low), float(high))
    for system, printed in PAIRED.items():
        compare_row(f'Wukong minus {system}', list(paired[system]), printed, [2, 2, 2], ['mean', 'low', 'high'])


def check_ablation() -> None:
    """Table 6."""
    print('Table 6 (schema components) against uda-nba/runs/x6/summary.csv (paper s4 = repository s5):')
    with (NBA / 'runs' / 'x6' / 'summary.csv').open() as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = {r[0]: dict(zip(header[1:], r[1:], strict=True)) for r in reader}
    for label, (variant, *printed) in ABLATION.items():
        actual = [
            number(rows[m][variant])
            for m in ('output_M', 'entities_split', 'attr_exact', 'attr_lenient', 'attr_wrong', 'edges')
        ]
        compare_row(
            f'{label} ({variant})',
            actual,
            tuple(printed),
            [2, 0, 0, 0, 0, 0],
            ['output tokens', 'split entities', 'exact', 'lenient', 'wrong values', 'edges'],
        )


def check_cost() -> None:
    """Table 7, the rows that the committed data covers."""
    print('Table 7 (construction cost) against uda-nba/runs/x6/summary.csv and uda-nba/runs/e1/report.json:')
    with (NBA / 'runs' / 'x6' / 'summary.csv').open() as f:
        reader = csv.reader(f)
        header = next(reader)
        x6 = {r[0]: dict(zip(header[1:], r[1:], strict=True)) for r in reader}
    wukong = [number(x6[m]['+current_team']) for m in ('calls', 'input_M', 'output_M', 'wall_min')]
    usage = json.loads((NBA / 'runs' / 'e1' / 'report.json').read_text())['KGGen']['usage']
    kggen = [usage['calls'], usage['input'] / 1e6, usage['output'] / 1e6, usage['wall_min']]
    names = ['calls', 'input tokens (M)', 'output tokens (M)', 'wall time (min)']
    compare_row(
        'Wukong (mean of three runs; wall time without the run during which the machine slept)',
        wukong,
        COST['Wukong'],
        [0, 1, 1, 0],
        names,
    )
    compare_row('KGGen', kggen, COST['KGGen'], [0, 1, 1, 0], names)


# --- 2. Scripts re-run on copies ---------------------------------------------------------------------------------------
def rerun_scripts(tmp: Path) -> None:
    """Re-run the scripts that need only committed files, and compare their outputs with the committed ones."""
    print('Scripts re-run on copies of the committed outputs:')
    nba = tmp / 'uda-nba'
    shutil.copytree(NBA, nba, ignore=shutil.ignore_patterns('m1', 'workspace*', 'report'))
    result = run([sys.executable, 'e1_table.py'], cwd=nba)
    same = (nba / 'runs' / 'e1' / 'summary.csv').read_bytes() == (NBA / 'runs' / 'e1' / 'summary.csv').read_bytes()
    check('e1_table.py reproduces runs/e1/summary.csv', result.returncode == 0 and same, result.stderr[-500:])

    m1_root = tmp / 'm1-root'
    shutil.copytree(M1 / 'results', m1_root / 'work')
    env = {**os.environ, 'M1_ROOT': str(m1_root)}
    result = run([sys.executable, str(M1 / 'table.py')], env=env)
    same = (m1_root / 'work' / 'm1_table.tex').read_text() == (M1 / 'results' / 'm1_table.tex').read_text()
    check('m1/table.py reproduces results/m1_table.tex', result.returncode == 0 and same, result.stderr[-500:])

    result = run(
        [sys.executable, str(M1 / 'paired.py'), '--base', 'wukong_s5', '--scores', str(M1 / 'results' / 'scores')],
    )
    committed = set((M1 / 'results' / 'paired.txt').read_text().splitlines())
    check(
        'm1/paired.py reproduces results/paired.txt',
        result.returncode == 0 and committed <= set(result.stdout.splitlines()),
        result.stderr[-500:] or 'lines differ',
    )


# --- 3. Text2KGBench re-scored from scratch ----------------------------------------------------------------------------
def rescore_text2kgbench(benchmark: Path, tmp: Path) -> None:
    """Re-score every system with the benchmark's evaluator, and re-run the type check from its cache."""
    print(f'Text2KGBench re-scored from the committed outputs ({benchmark}):')
    systems = [arg for name, folder in T2KG_FOLDERS.items() for arg in ('--system', f'{name}={BENCH / folder}')]
    out = tmp / 'scoring'
    result = run(
        [
            sys.executable,
            str(BENCH / 'text2kg_rescore.py'),
            '--benchmark',
            str(benchmark),
            '--root',
            str(BENCH),
            '--variants-root',
            str(tmp / 'variants'),
            '--out',
            str(out),
            *systems,
        ],
        cwd=ROOT,
    )
    if result.returncode:
        check('text2kg_rescore.py runs', ok=False, detail=result.stderr[-800:])
    else:
        committed = json.loads((BENCH / 'results-x2' / 'scoring' / 'summary.json').read_text())
        fresh = json.loads((out / 'summary.json').read_text())
        values = [
            (v, n, k, x)
            for v, systems_ in committed['scores'].items()
            for n, by in systems_.items()
            for k, x in by.items()
        ]
        diff = [f'{v} {n} {k}' for v, n, k, x in values if fresh['scores'].get(v, {}).get(n, {}).get(k) != x]
        check(
            f'every score equals results-x2/scoring/summary.json ({len(values)} values)',
            not diff,
            '; '.join(diff[:5]),
        )

    out = tmp / 'typecheck'
    shutil.copytree(BENCH / 'results-typecheck', out)
    systems = [arg for name, folder in TYPECHECK_FOLDERS.items() for arg in ('--system', f'{name}={BENCH / folder}')]
    env = {**os.environ, 'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY') or 'not-needed-the-cache-is-complete'}
    result = run(
        [
            sys.executable,
            str(BENCH / 'text2kg_typecheck.py'),
            '--benchmark',
            str(benchmark),
            '--out',
            str(out),
            *systems,
        ],
        env=env,
        cwd=ROOT,
    )
    committed = json.loads((BENCH / 'results-typecheck' / 'summary.json').read_text())['totals']
    fresh = json.loads((out / 'summary.json').read_text())['totals'] if result.returncode == 0 else {}
    check(
        'type check from the judge cache equals results-typecheck/summary.json',
        committed == fresh,
        result.stderr[-800:],
    )


def native(cmd: list[str]) -> list[str]:
    """Start a Python natively on Apple silicon when this process runs under Rosetta (the engine's x86_64 environment).

    A process under Rosetta starts universal binaries as x86_64 too, so an arm64 evaluator environment would fail to
    load its packages. The command is prefixed with `arch -arm64` only if that Python then imports pandas.
    """
    if sys.platform == 'darwin' and run(['sysctl', '-n', 'sysctl.proc_translated']).stdout.strip() == '1':
        if run(['arch', '-arm64', cmd[0], '-c', 'import pandas']).returncode == 0:
            return ['arch', '-arm64', *cmd]
    return cmd


# --- 4. Question answering re-scored with UDA-Bench --------------------------------------------------------------------
def rescore_qa(uda_bench: Path, python: str, tmp: Path) -> None:
    """Re-score every system's committed answers with UDA-Bench's evaluator and compare per question."""
    print(f'Question answering re-scored from the committed answers ({uda_bench}):')
    m1_root = tmp / 'm1-rescore'
    shutil.copytree(M1 / 'results', m1_root / 'work', ignore=shutil.ignore_patterns('scores'))
    env = {**os.environ, 'M1_ROOT': str(m1_root), 'UDA_BENCH': str(uda_bench)}
    result = run(native([python, str(M1 / 'score.py')]), env=env, cwd=M1)
    if result.returncode:
        check('m1/score.py runs', ok=False, detail=result.stderr[-800:])
        return
    # Answers too large for the repository keep only their first 1,000 rows (rows_truncated); their committed scores
    # were computed on all the rows, so they cannot be re-scored from the repository and are left out
    truncated = {
        (a.parent.name, json.loads(a.read_text())['uid'])
        for a in (M1 / 'results' / 'answers').glob('*/*.json')
        if 'rows_truncated' in json.loads(a.read_text())
    }
    for path in sorted((M1 / 'results' / 'scores').glob('*.json')):
        committed = json.loads(path.read_text())
        fresh = json.loads((m1_root / 'work' / 'scores' / path.name).read_text())
        kept = [u for u in committed if (path.stem, u) not in truncated]
        diff = [u for u in kept if committed[u]['macro_f1'] != fresh.get(u, {}).get('macro_f1')]
        left_out = f', {len(committed) - len(kept)} truncated answers left out' if len(kept) < len(committed) else ''
        check(
            f'{path.stem}: per-question scores equal the committed ones ({len(kept)} questions{left_out})',
            not diff,
            f'{len(diff)} differ: {diff[:5]}',
        )


def main() -> int:
    """Run the checks and report."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--text2kgbench', type=Path, help='clone of Text2KGBench at commit 50a3d25')
    parser.add_argument('--uda-bench', type=Path, help='clone of UDA-Bench at commit f2da981')
    parser.add_argument('--uda-python', default=sys.executable, help='Python for the UDA-Bench evaluator')
    args = parser.parse_args()
    check_structure()
    check_quality()
    check_text2kgbench()
    check_qa()
    check_ablation()
    check_cost()
    with tempfile.TemporaryDirectory() as tmp:
        rerun_scripts(Path(tmp))
        if args.text2kgbench:
            rescore_text2kgbench(args.text2kgbench.resolve(), Path(tmp))
        if args.uda_bench:
            rescore_qa(args.uda_bench.resolve(), args.uda_python, Path(tmp))
    print('PASS' if not FAILURES else f'FAIL ({len(FAILURES)} checks)')
    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
