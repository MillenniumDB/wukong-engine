# Tests

None of these tests needs an API key or makes an LLM call. Run them from the repository root with the environment of
[paper/REPRODUCE.md](/paper/REPRODUCE.md) (Python 3.14, the engine installed, plus `pandas<3` and `nltk`). Each test
prints one line per check and exits with status 0 when every check passes.

| Test | What it checks | Time |
|---|---|---|
| `test_pipeline_fake_llm.py` | See below. | ~20 s |
| `check_paper_files.py` | Every Python file under `paper/` and `tests/` compiles and every shell script parses. Every JSON, JSON Lines and TOML file parses. Every knowledge model under `paper/` and `workspaces/` loads and validates in the engine. | ~3 s |
| `check_paper_numbers.py` | See below. | <1 min; +3 min with `--text2kgbench`, +10 min with `--uda-bench` |

## `test_pipeline_fake_llm.py`

The test runs the real `wukong run` pipeline on a two-document corpus, in both execution modes (real-time and
batch). An OpenAI client that returns scripted responses stands in for the model.

The scripted responses contain:
- one case of every validation rejection;
- a primary key made only of symbols;
- a response that fails to decode and is retried;
- document-level responses with several candidates.

The test then checks:
- the staging database: jobs, rejections per reason, entities, relationships;
- that every request carries the configured reasoning effort;
- that each regular expression appears in the prompts of its own kind of job;
- that document-level prompts stop at the configured prefix;
- both export formats (QM file and Neo4j CSV files).

## `check_paper_numbers.py`

The test compares every number of the paper's result tables with the committed summaries. It also re-runs the
scripts that build results from committed files: the structure table, the five schemas of Table 6, the
question-answering table and the paired differences.

- **`--text2kgbench DIR`:** also re-scores every Text2KGBench system with the benchmark's own evaluator, and re-runs
  the type check from its committed judge cache.
- **`--uda-bench DIR`:** also re-scores every question-answering answer with UDA-Bench's evaluator. It leaves out
  the 14 answers the repository keeps only in part (their first 1,000 rows), whose scores were computed on all the rows.

Both options compare the results value by value with the committed scores.
