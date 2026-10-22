# Reproducing the experiments of the paper

This repository holds the engine (`src/`), the scripts of every experiment (`paper/`), and every output and score
behind the paper's tables. You can check the results at three levels:

1. **Without an API key, in minutes:** run the tests. They check that the engine works end to end with a scripted
   fake LLM, and that every committed output gives the numbers printed in the paper.
2. **Without an API key, from the raw outputs:** re-score every Text2KGBench system and every question-answering
   answer with the benchmarks' own evaluators.
3. **With an OpenAI API key:** rebuild any graph or rerun any system.

The graphs built for the NBA experiments (staging databases, LightRAG and GraphRAG stores; several GB) are not
included, so Tables 3 and 6 can only be checked against their committed summaries without rebuilding them.

Every system uses the same model, `gpt-5.6-luna` with low reasoning effort, and `text-embedding-3-small` where
it needs embeddings. Costs below are the token counts in our run records at $0.20 per million input tokens and
$1.20 per million output tokens.

## 1. Setup

The engine needs Python 3.14. With [uv](https://docs.astral.sh/uv/), from the repository root:

```sh
uv venv --python 3.14 .venv
uv pip install -e .
uv pip install 'pandas<3' nltk          # used by the checks and the scoring scripts
.venv/bin/python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

On Apple Silicon, the dependency `blingfire` ships only an x86_64 library. Use an x86_64 Python under Rosetta:
`uv venv --python cpython-3.14-macos-x86_64-none .venv`, and add `--python-platform x86_64-apple-darwin` to each
`uv pip install`.

The benchmarks are cloned next to this repository, at the commits we used:

```sh
git clone https://github.com/cenguix/Text2KGBench ../benchmarks/Text2KGBench
git -C ../benchmarks/Text2KGBench checkout 50a3d25
git clone https://github.com/BIT-DataLab/Bench-U ../benchmarks/UDA-Bench   # UDA-Bench
git -C ../benchmarks/UDA-Bench checkout f2da981
```

UDA-Bench's evaluator needs its own environment: Python 3.12 with `pandas<3`, `duckdb==1.3.2`, `sqlglot`,
`pyyaml` and `tqdm`. pandas 3 changed its string type, and duckdb 1.3.2 rejects it.

The NBA documents and gold tables of UDA-Bench are included in `paper/uda-nba/data/` (see its README).

## 2. Checks without an API key

```sh
.venv/bin/python tests/test_pipeline_fake_llm.py   # engine end to end, both execution modes, both export formats (~20 s)
.venv/bin/python tests/check_paper_files.py        # every script compiles, every data file parses, every schema loads (~3 s)
.venv/bin/python tests/check_paper_numbers.py \
    --text2kgbench ../benchmarks/Text2KGBench \
    --uda-bench ../benchmarks/UDA-Bench --uda-python <python of the UDA-Bench environment>
```

`check_paper_numbers.py` does three things:
- It compares every number of Tables 2–7, Appendix C and the paired differences of Section 4.4 with the committed
  summaries.
- It re-runs the scripts that build those summaries from committed files.
- With the two options, it re-scores the raw outputs with each benchmark's evaluator (about 3 and 10 minutes) and
  compares them value by value with the committed scores.

Without the options, it needs no external data and takes under a minute. See [tests/README.md](/tests/README.md)
for what each check covers.

## 3. Where each result comes from

Folder and file names use our internal experiment names:
- X1: baselines on Text2KGBench;
- X2: Wukong on Text2KGBench, three runs per configuration;
- E1: graph structure;
- X6: schema components;
- M1: question answering.

| Paper | Scripts | Committed outputs | Recomputable without a key |
|---|---|---|---|
| Table 2, Appendix B.3–B.4 (graph structure) | `uda-nba/e1_analysis.py`, `derive_labels.py`, `relation_vocab.py`, `e1_table.py` | `uda-nba/runs/e1/`, `uda-nba/runs/labels/` | the last step (`e1_table.py`); the others read the graphs |
| Table 3 (graph quality) | `uda-nba/nba_quality.py` | `uda-nba/runs/quality/` | no: it reads the graphs |
| Table 4 (Text2KGBench) | `benchmark/text2kg_rescore.py`, `text2kg_typecheck.py` | `benchmark/results-*/`, `results-x2/scoring/`, `results-typecheck/` (with the judge's cache) | yes, everything |
| Table 5, Section 4.4, Appendix C (question answering) | `uda-nba/m1/score.py`, `table.py`, `paired.py` | `uda-nba/m1/results/` (questions, answers, scores, usage) | yes, everything |
| Table 6 (schema components) | `uda-nba/x6_analysis.py` | `uda-nba/runs/x6/` | no: it reads the graphs |
| Table 7 (construction cost) | run logs | `uda-nba/runs/x6/summary.csv` (Wukong), `uda-nba/runs/e1/report.json` (KGGen); LightRAG and GraphRAG: their build logs, summarized in `uda-nba/runs/e1/build_costs.md` | read only |

**The NBA schema of the paper** is `paper/uda-nba/workspace-x6-s4/`.
- Every NBA result uses it, and the schema-based extractors were built from it.
- Table 6's variants s0–s4 are `workspace-x6-s0` to `-s4`. `make_coupling_variants.py` derives s0–s3 from the full
  schema, s4.

**The three Wukong configurations of Table 4** are the workspaces `tekgen_*` (ontology only), `examples_*` (+
entity examples) and `props_*` (+ literal properties), all in `paper/benchmark/workspaces/`. Their three runs
are `results-x2-r{1,2,3}-{primary,examples,props}`. The rows' sources:
- "Prompting, one example": `results-x1-prompt-r{1,2,3}`;
- "Prompting, no example": `results-x1-prompt0shot-r1`;
- EDC and EDC+R: `results-x1-edc-r1` and `results-x1-edcr-r{1,2,3}`;
- KGGen: `results-kggen-context-r1`;
- Vicuna-13B and Alpaca-LoRA-13B: the outputs published with Text2KGBench.

The type-conformance column comes from the first run of each system.

**Outputs no number in the paper uses:**
- `benchmark/results`, `results-examples` and `results-properties`: earlier single runs;
- `results-permissive` and `results-lenient-pilot`: pilots;
- `results-kggen-plain-r{1,2}`: KGGen without the ontology hint, mentioned only in the text;
- the `perm_*` and `lenient_*` workspaces;
- `uda-nba/m1/results/excluded/`: a GraphRAG global-search pilot;

## 4. Rerunning with an API key

Put `OPENAI_API_KEY=...` in `.env` at the repository root (copy `.env.example`), or export it.

### Text2KGBench (Table 4)

`paper/benchmark.md` and `paper/benchmark-adjusted.md` describe the harness in detail. One run of one Wukong
configuration takes about 6,600 LLM calls and costs about $1.70:

```sh
python -m venv paper/benchmark/.venv-eval && paper/benchmark/.venv-eval/bin/pip install nltk   # the evaluator's environment
paper/benchmark/.venv-eval/bin/python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
.venv/bin/python paper/benchmark/text2kg_setup.py --benchmark ../benchmarks/Text2KGBench --entity-examples --literal-properties --prefix props_
PATH=.venv/bin:$PATH PREFIX=props_ RESULTS=paper/benchmark/results-mine-props paper/benchmark/run_benchmark.sh
```

- **The other two configurations:**
  - ontology only: no flags, `--prefix tekgen_`;
  - entity examples: `--entity-examples --prefix examples_`.
- **More runs:** copy the workspaces under a new prefix, because each workspace keeps its own staging database.
- **The baselines.** Each script's docstring gives its command:
  - **Prompting** (`text2kg_prompt_baseline.py`, add `--no-example` for the zero-shot row): 4,062 calls, about $0.90
    per run.
  - **EDC and EDC+R** (`text2kg_edc.py`, add `--refine` for EDC+R): use EDC (https://github.com/clear-nus/edc) at
    commit `02aad17` with `paper/benchmark/baselines/edc-luna.patch` applied, and the inputs in
    `paper/benchmark/baselines/edc-inputs/`. EDC+R takes about 41,600 calls ($9.10) per run, EDC about 21,100
    ($4.40).
  - **KGGen** (`text2kg_kggen.py --variant context`): use KGGen (https://github.com/stair-lab/kg-gen) at commit
    `6259b4c`, installed from its own `uv.lock` (Python 3.12). About 8,100 calls ($1.75) per run.
- **Score everything:** run `text2kg_rescore.py` and `text2kg_typecheck.py` with one `--system NAME=FOLDER` per
  output. The exact lists are in `tests/check_paper_numbers.py`. The type check calls the LLM only for phrases its
  cache lacks.

### NBA graphs (Tables 2, 3, 6 and 7)

Run everything from `paper/uda-nba/`. Each system has its own environment under `envs/<name>/`:
- `wukong`: this engine;
- `lightrag` and `graphrag`: Python 3.12, with the exact pins in `m1/versions.txt`;
- `neo4j-graphrag`, `llamaindex`, `ontogpt` and `kggen`: the versions in each builder's docstring
  (`baselines/*_build.py`).

```sh
./run_x6.sh "1 2 3"                       # Wukong, every schema variant, three runs: runs/x6-s<k>-r<n> (about 4,450 calls, $2.60 per run)
./run_full.sh                             # LightRAG and GraphRAG once each: runs/{lightrag,graphrag}-full
for n in 1 2 3; do RUN=$n baselines/run_baselines.sh "neo4j-graphrag llamaindex ontogpt"; done   # runs/<tool>-s4-r<n>
baselines/run_baselines.sh kggen        # runs/kggen-full
```

- **Rebuilding costs** (estimated from the token counts of Table 7): about $13 for LightRAG, $25 for GraphRAG and
  $5 for KGGen.
- **Analyses, in order:** `e1_analysis.py`, `derive_labels.py` (for LightRAG, GraphRAG and KGGen), `relation_vocab.py`,
  `e1_table.py`, `nba_quality.py` and `x6_analysis.py`, each with the GraphRAG environment's Python. Their
  docstrings give their inputs and outputs.
- **Where the scripts look for runs:** the run names in `e1_analysis.py`, `nba_quality.py` and `x6_analysis.py` are
  those above. Wukong's three runs of the paper's schema are `x6-s4-r{1,2,3}`.

### Question answering (Table 5)

See `m1/README.md` for the protocol and fairness rules. All systems answer the same 101 questions, with every
agent told the date 2026-10-14. Total cost was about $9.

Set `M1_ROOT` (a working folder) and `UDA_BENCH` (the UDA-Bench clone), and put the LightRAG and GraphRAG builds where
the scripts read them: `$M1_ROOT/input/uda-nba-share/lightrag-full` and `.../graphrag-full` (symbolic links to
`paper/uda-nba/runs/` are fine). Then, from `paper/uda-nba/m1/`:

```sh
python sys_floor.py                                   # the model alone
../envs/lightrag/bin/python sys_lightrag.py           # every LightRAG mode
../envs/graphrag/bin/python sys_graphrag.py --methods local
for n in 1 2 3; do
  python sys_wukong.py --run ../runs/x6-s4-r$n --name wukong_s4_r$n --today 2026-10-14 --reload
  for t in neo4j:neo4j-graphrag llamaindex:llamaindex ontogpt:ontogpt; do
    python sys_typed.py ${t%%:*} --run ../runs/${t#*:}-s4-r$n --schema ../workspace-x6-s4/knowledge_model.json \
        --name ${t%%:*}_s4_r$n --today 2026-10-14 --reload
  done
done
python score.py && python table.py && python paired.py --base wukong_s4
```

Here `python` is the harness environment: Python 3.12 with `kuzu==0.11.3`, `duckdb==1.3.2`, `pandas<3`, `sqlglot`,
`pyyaml`, `tqdm` and `openai`. The `../envs/` paths are the environments of the NBA builds.
