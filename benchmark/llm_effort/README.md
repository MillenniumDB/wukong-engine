<!-- omit from toc -->
# 🧠 LLM and Reasoning Effort Benchmark

Measures how well each supported model extracts entities and relationships at each reasoning effort level, and what it costs, to choose each model's default effort level and to decide whether the effort is worth exposing as configuration.

<!-- omit from toc -->
## 📚 Table of Contents
- [❓ Question](#-question)
- [🧪 Method](#-method)
- [💰 Budget](#-budget)
- [▶️ Running It](#️-running-it)
- [📊 Results](#-results)

## ❓ Question

| Model              | Effort levels benchmarked                 |
| ------------------ | ----------------------------------------- |
| `gpt-5.6-luna`     | `none`, `low`                             |
| `gpt-6-luna`       | `none`, `low`                             |
| `claude-haiku-5-5` | `none` (thinking off), `low`              |

`medium` is only added for a model whose `low` level clearly beats `none`, and `high` and above are left out as overkill for extraction. The levels are the engine's generalized ones, set through the experimental `[llm] reasoning_effort` option (see [docs/configuration.md](/docs/configuration.md)).

## 🧪 Method

- **Data**: the crime news dataset (Chilean news, in Spanish), with the knowledge model of its workspace copied to [`knowledge_model.json`](knowledge_model.json). Neither the documents nor the extractions are tracked, as the dataset isn't (see the root `.gitignore`).
- **Samples**: a fixed ordering of the full dataset (the 22 documents of its test set first, then the rest, each shuffled by a seeded hash), from which each suite takes a prefix, listed in [`samples/`](samples/):

  | Suite   | Documents | Chunks | Purpose                                               |
  | ------- | :-------: | :----: | ----------------------------------------------------- |
  | `smoke` |     3     |   3    | Check the whole flow before spending on the main run. |
  | `main`  |    100    |  116   | The benchmark itself (~10% of the full dataset).      |

- **Extraction**: each setting runs in its own workspace (`runs/<suite>/<setting>/`), in real time, with the default chunking (800 tokens, 120 overlap) and its generated configuration in [`configs/`](configs/). All settings chunk the sample identically, which the judge checks.
- **Judge**: `gpt-6.1-sol` at `low` effort, not one of the benchmarked models. It gets one request per chunk and extraction kind with the passage, the type definitions (cached across requests) and the items of **every** setting side by side, anonymized as `S1`, `S2`... in an order shuffled per chunk. It first builds the reference list of items the passage supports, then gives each item a verdict: `correct`, `field_error` (right item, wrong field value) or `invalid`. Scoring all settings in one request makes it ~3x cheaper than one request per setting, and the verdicts consistent across settings.
- **Scores**, per setting and kind, micro-averaged over chunks:

  | Score          | Definition                                                                     |
  | -------------- | ------------------------------------------------------------------------------ |
  | Precision      | `correct` and `field_error` items over all items (unjudged ones count as invalid) |
  | Recall         | Distinct reference items found over all reference items                        |
  | F1             | With a 95% bootstrap interval, resampling chunks                               |
  | Field accuracy | `correct` items over `correct` and `field_error` items                         |

  Relationship scores measure the pipeline at a setting, as each setting extracts relationships between its own entities.

## 💰 Budget

Below **$5** in total, **$10** at most. Estimates before running, at real-time extraction and batch judging:

| Step                    | Estimate |
| ----------------------- | :------: |
| `smoke` extraction      |  ~$0.02  |
| `smoke` judge (real time) | ~$0.10 |
| `main` extraction       |  ~$1.00  |
| `main` judge (batch)    |  ~$2.10  |
| **Total**               | **~$3.2** |

The extraction cost of each run is measured from its staging database (`bench.py cost`), and the judge's from its token counts before submitting, which never happens beyond the `--budget` given.

## ▶️ Running It

Run everything from the repository root, with `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` set (e.g. in `.env`). Only the steps marked 💸 spend money.

```sh
B=benchmark/llm_effort

# 1. Write the sample, data copies, configurations and workspaces (free)
poetry run python $B/bench.py prepare smoke --docs 3
poetry run python $B/bench.py prepare main --docs 100

# 2. Ingest the documents of a setting, which makes no LLM calls (free)
poetry run wukong run $B/runs/main/<setting> $B/data/main --config $B/configs/<setting>.ingest.toml

# 3. 💸 Extract with a setting, then check what the runs cost
poetry run wukong run $B/runs/main/<setting> $B/data/main --config $B/configs/<setting>.toml
poetry run python $B/bench.py cost main

# 4. Estimate the judge cost (free), then 💸 judge (smoke in real time, main as a batch)
poetry run python $B/bench.py judge smoke --mode realtime --budget 0.5
poetry run python $B/bench.py judge smoke --mode realtime --budget 0.5 --submit
poetry run python $B/bench.py judge main --budget 4 --submit
poetry run python $B/bench.py collect main    # Once the batch has completed

# 5. Score the settings, writing results/<suite>/
poetry run python $B/bench.py report main
```

## 📊 Results

Run on 2026-10-21 and 2026-10-22, for **$3.60** in total (plus $0.07 for the Haiku follow-up below): $0.32 for `smoke`, $1.17 for the `main` extraction and $2.11 for its judge. The judge batch stalled at 227 of 232 requests for over an hour, so it was cancelled (keeping its finished judgments) and the last 5 were judged in real time (`judge --missing`). Full tables are in [`results/main/report.md`](results/main/report.md) and [`results/main/scores.json`](results/main/scores.json).

**`main` suite** (116 chunks). F1 with its 95% bootstrap interval, and each setting's extraction cost on the sample:

| Setting                 | Entity F1           | Entity P / R  | Relationship F1     | Relationship P / R | Cost   |
| ----------------------- | ------------------- | ------------- | ------------------- | ------------------ | ------ |
| `gpt-6-luna@none`       | 80.9% [79.1, 82.5]  | 91.2 / 72.7   | **54.3%** [51.5, 57.1] | 85.9 / 39.7     | **$0.106** |
| `gpt-6-luna@low`        | **82.0%** [80.4, 83.5] | 96.3 / 71.3 | 41.5% [38.0, 45.2]  | 96.5 / 26.4        | $0.132 |
| `gpt-5.6-luna@none`     | 78.2% [76.6, 79.7]  | 88.4 / 70.1   | **55.3%** [52.0, 58.6] | 82.8 / 41.5     | $0.235 |
| `gpt-5.6-luna@low`      | 81.6% [80.0, 83.0]  | 95.6 / 71.1   | 44.4% [41.0, 47.9]  | 96.1 / 28.9        | $0.327 |
| `claude-haiku-5-5@none` | 68.7% [66.1, 71.1]  | 96.5 / 53.3   | 29.9% [25.9, 33.9]  | 92.5 / 17.8        | $0.116 |
| `claude-haiku-5-5@low`  | 74.8% [72.8, 76.7]  | 98.3 / 60.3   | 28.1% [24.7, 31.7]  | 98.7 / 16.4        | $0.256 |

Paired differences (same chunks, 95% bootstrap interval):

| Comparison                          | Entity F1             | Relationship F1           |
| ----------------------------------- | --------------------- | ------------------------- |
| `gpt-6-luna`: `low` − `none`        | +1.1 [−0.5, +2.7]     | **−12.8** [−16.1, −9.4]   |
| `gpt-5.6-luna`: `low` − `none`      | **+3.4** [+1.9, +4.9] | **−10.9** [−13.5, −8.2]   |
| `claude-haiku-5-5`: `low` − `none`  | **+6.1** [+3.7, +8.4] | −1.7 [−6.2, +3.0]         |
| `gpt-6-luna` − `gpt-5.6-luna`, `low`  | +0.4 [−1.0, +1.8]   | −2.9 [−6.0, +0.4]         |
| `gpt-6-luna` − `gpt-5.6-luna`, `none` | **+2.7** [+1.3, +4.1] | −1.0 [−4.4, +2.1]       |
| `gpt-6-luna@low` − `claude-haiku-5-5@low` | **+7.2** [+5.3, +9.2] | **+13.4** [+9.6, +17.3] |

**Findings:**

1. **`gpt-6-luna` matches or beats `gpt-5.6-luna` at under half the cost**, at both levels.
2. **For the Lunas, reasoning makes relationship extraction more conservative, not better.** At `none`, `gpt-6-luna` extracts 1,080 valid relationships against 719 at `low` (+50%), and 807 against 667 with every field right (+21%), at a precision of 86% instead of 96%. On entities, `low` is only more precise, with no significant F1 difference for `gpt-6-luna`.
3. **`claude-haiku-5-5` trails both Lunas**, mostly on recall: it finds 54–60% of the reference entities (the Lunas ~71%) and under half the relationships the Lunas find at `none`. Unlike what its tuning assumed, `low` clearly beats `none` on entities (+6.1), at 2.2x the cost. Part of the gap may come from its tighter structured output limits: crime schemas exceed them, so they're sent as instructions instead of enforced.
4. **`gpt-6-luna@none` returned invalid JSON twice** in 116 relationship calls (trailing data after the object). Both were retried successfully, and they're the 2 failed jobs of the report.
5. **`medium` isn't worth benchmarking**: `low` already doesn't help the Lunas overall, and Haiku stays well below `gpt-6-luna@none` while costing more at `low`.

**Haiku follow-up** (2026-10-22, $0.07): its entity requests for the first 20 chunks of `main` were replayed, keeping the raw responses, to explain its lower recall:

| Replay                                                                      | Haiku events | `gpt-6-luna@low` events |
| --------------------------------------------------------------------------- | :----------: | :---------------------: |
| As benchmarked (entity schema too large to enforce, sent as instructions)  |      25      |           59            |
| Split into two schemas small enough to be enforced (`Event`, the rest)     |      25      |            -            |
| `Event` instructions stating that non-criminal occurrences count too       |      40      |           83            |

- Its responses had **no type or format issues** (no booleans, numbers or invalid options): only 9 of 182 items were dropped, for an empty required field. The leniency added afterwards (normalizing values of other JSON types) doesn't change its results.
- **Schema enforcement doesn't matter**: enforcing the schema in two requests returned the same events.
- **It isn't judge bias**: the judge accepts 98% of Haiku's items, and the gap is in how many items it extracts at all (half the events, ~15% fewer people and places).
- **Haiku is more conservative**: it keeps crime-central events and skips other reported occurrences (arrests, hearings, resignations), which the `Event` definition includes. A clearer definition makes both models extract more events, without closing the gap: Haiku extracts about half as many either way.
- **The crime `Event` definition is ambiguous for both models**: `gpt-6-luna` also extracts 40% more events once it says that non-criminal occurrences count.

**Stronger models** (`gpt-6.1-sol`, `claude-sonnet-5-5`, 20x the price of the small ones) were left out for now (2026-10-22): at scale, they cost too much for the default, and the main losses seen here (ambiguous definitions) affect every model. If a quality tier is reconsidered, the proposed check is both of them at `low` on the first 50 documents of `main`, judged side by side with `gpt-6-luna@low` and `claude-haiku-5-5@low` by both `gpt-6.1-sol` and `claude-sonnet-5-5` to expose self-preference, for ~$5.5. They would earn support only by clearly beating their small counterpart (e.g. 5+ relationship F1 points) under both judges.

**Follow-up:** `gpt-5.6-luna` was removed from the engine after this benchmark, replaced by `gpt-6-luna` as the default, so `bench.py` lists a model the engine no longer accepts: drop it from `MODELS` before running the benchmark again.

**Caveats:** the judge's reference lists are generous (about 23 relationships per chunk), so absolute recall is low for every setting: compare settings rather than reading the numbers on their own. Relationship scores measure each setting's whole pipeline, since each one extracts relationships between its own entities. A single judge (`gpt-6.1-sol`) from the same provider as two of the three models scored everything, blind to the settings.
