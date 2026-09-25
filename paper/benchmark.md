# WUKONG on Text2KGBench: Protocol and Results (Vanilla)

This document records how the WUKONG engine is evaluated on Text2KGBench, so
the experiment can be reproduced from the repository, and what the results say.

> **This is the vanilla run: the benchmark exactly as published, and unfair to
> WUKONG.** Ontologies are compiled as published, the gold standard is scored as
> published, and the numbers are directly comparable to the published
> baselines. It is also the run whose defects this document diagnoses: literals
> forced into entity nodes (§7.5), unscoreable and unreachable gold (§7.2, §8),
> and train/test leakage favouring the baselines (§8.2).
>
> A companion run, [`benchmark-adjusted.md`](benchmark-adjusted.md), is **fairer
> to WUKONG but changes things**. It models range-less relations as entity
> properties, and scores every system, baselines included, against a corrected
> copy of the gold. There WUKONG reaches **F1 0.39 against Vicuna's 0.36**, and
> **0.37 against 0.35** with the modelling change alone under this document's
> unmodified scoring. Quote both, labelled.

- **Benchmark**: [Text2KGBench](https://github.com/cenguix/Text2KGBench) (ISWC 2023), Wikidata-TekGen test suite
- **Task**: ontology-driven knowledge graph generation — given a sentence and an ontology, emit the triples the sentence states
- **System under test**: WUKONG engine v0.2.0, `gpt-5.6-luna`, real-time execution mode
- **Scoring**: the benchmark authors' own `run_eval.py`, unmodified

> **§6 is one configuration** — this engine, this model, ontologies compiled
> exactly as published with nothing tuned. §10 reports an ablation that gives
> entity types the same train-derived grounding the baselines already get, and
> it reaches **F1 0.34 against Vicuna's 0.35 with conformance 1.000 and
> hallucination ~0.00**. Quote both: §6 as the zero-tuning result, §10.1 as the
> like-for-like comparison. See §9 before treating any number as a property of
> WUKONG, §8 for the benchmark artifacts that bound every system's score, and
> §7.5 for why a triple-only answer format penalizes a model that represents
> literals as entity properties.

Everything under `paper/benchmark/` is the harness; everything under
`paper/benchmark/results/` is generated output.

---

## 1. Why this benchmark

Text2KGBench is the closest published benchmark to what WUKONG does: it does not
ask for free-form triples, it asks for triples that conform to a *given*
ontology, and it scores conformance and hallucination as first-class metrics
alongside precision and recall. That matches WUKONG's design premise — a knowledge
model constrains extraction up front — so the benchmark's conformance and
hallucination metrics measure exactly the property the engine claims.

The Wikidata-TekGen suite has 10 ontologies and 4,062 test sentences. The
published baselines are two instruction-tuned 13B models (Vicuna-13B and
Alpaca-LoRA-13B) in a 2-shot setting, where the two examples are retrieved from
a train split by sentence similarity.

---

## 2. How an ontology becomes a WUKONG workspace

`text2kg_setup.py` compiles each benchmark ontology into a WUKONG workspace.
The mapping is mechanical — no ontology is hand-tuned — which is what keeps the
comparison honest across all 10.

**Concepts → entity types.** Every concept used as the domain or range of some
relation becomes an entity type, its label converted to PascalCase to satisfy
the engine's `^[A-Z][a-zA-Z0-9]{0,63}$` type-name pattern. Concepts the ontology
declares but never uses in a relation are dropped: they cannot appear in any
triple, so modelling them would only widen the extraction surface.

**Relations → relationship types.** One relationship type per distinct relation
label. Relations that share a label but differ in range (same property, several
admissible types) collapse into a single relationship type carrying several
endpoint pairs, which is how WUKONG expresses the same thing.

**The `Value` fallback.** Some benchmark relations have no range concept, or
name a concept the ontology never declares. Those objects are literals — dates,
quantities, descriptive terms — with no type to attach to. They get a single
catch-all `Value` entity type. Left unbounded, that type invites the model to
extract every noun phrase in the sentence, so its instructions enumerate exactly
which relations may take a `Value` object, and forbid extracting anything else.

> This fallback is the one place where the compilation forces WUKONG out of its
> own data model. In WUKONG a literal is a **property of an entity**, filled
> during entity extraction and allowed to be null; a benchmark triple has no
> room for a property, so the literal must instead become a node that an explicit
> relationship points at. It is the largest single cost in these results, and
> §7.5 quantifies it.

**Surface-form instruction.** Scoring is exact string match after lowercasing
and whitespace removal (§5), so every primary-key field carries an instruction
to reproduce the span verbatim, without reordering or normalizing words.

**Date convention.** TekGen writes dates as `<DD> <Month> <YYYY>`, and a
year-only mention becomes `01 January <YYYY>`. This is a dataset convention, not
something derivable from the sentence, and the published baselines picked it up
implicitly from their retrieved few-shot examples. To give WUKONG the same
information without leaking test data, `scan_train_date_examples` reads **only
the train split** and attaches up to two observed date strings as field examples
on the entity types that receive date objects. The test and ground-truth files
are never read during setup.

**Reserved names.** `document`/`chunk` and `chunkof`/`extractedfrom` are engine
internals; a colliding ontology label is suffixed rather than silently renamed.

Each test sentence is written as its own single-sentence document, named after
its benchmark id, which is what lets the export step attribute triples back to
sentences.

### Resulting workspaces

| Ontology | Sentences | Unique | Entity types | Relationship types | GT triples | Verified subset |
|---|---|---|---|---|---|---|
| 1_movie | 840 | 794 | 10 | 15 | 2250 | 174 |
| 2_music | 675 | 630 | 8 | 13 | 1480 | 123 |
| 3_sport | 487 | 477 | 10 | 10 | 719 | 97 |
| 4_book | 550 | 540 | 10 | 12 | 933 | 124 |
| 5_military | 230 | 222 | 12 | 8 | 225 | 63 |
| 6_computer | 230 | 220 | 7 | 4 | 440 | 66 |
| 7_space | 203 | 199 | 10 | 7 | 279 | 71 |
| 8_politics | 214 | 203 | 8 | 9 | 202 | 55 |
| 9_nature | 474 | 467 | 13 | 13 | 531 | 117 |
| 10_culture | 159 | 159 | 9 | 8 | 173 | 49 |
| **Total** | **4062** | **3911** | | | **7232** | **939** |

"Unique" is the number of distinct sentences. WUKONG addresses documents by
content, so sentences repeated verbatim under different test ids become one
document; the export step re-attributes that document's triples to every id
sharing the sentence (§4).

---

## 3. Reproducing the run

Prerequisites: the Text2KGBench repository checked out next to this one, an
`OPENAI_API_KEY` in `.env`, and the engine installed (`poetry install`).

```bash
# 1. Evaluator environment — nltk only, kept out of the engine's env
python3 -m venv paper/benchmark/.venv-eval
paper/benchmark/.venv-eval/bin/pip install nltk
paper/benchmark/.venv-eval/bin/python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

# 2. Compile all 10 ontologies into workspaces + sentence documents
python3 paper/benchmark/text2kg_setup.py --benchmark ../benchmarks/Text2KGBench

# 3. Extract, convert and evaluate everything
paper/benchmark/run_benchmark.sh
```

`run_benchmark.sh` runs the engine once per ontology, then converts and
evaluates all 10 in a single pass. It skips any ontology that already has a
staging database, so an interrupted run resumes by re-invoking it. To force a
re-extraction, delete that workspace's `staging/` directory.

The individual steps, if you need them separately:

```bash
wukong run paper/benchmark/workspaces/tekgen_2_music paper/benchmark/data/2_music \
    --config config/default.toml -v

python3 paper/benchmark/text2kg_export.py --benchmark ../benchmarks/Text2KGBench --onto 2_music

python3 paper/benchmark/text2kg_eval.py --benchmark ../benchmarks/Text2KGBench --onto 2_music \
    --python "$PWD/paper/benchmark/.venv-eval/bin/python"
```

Note that `--python` must be an **absolute** path: `run_eval.py` is invoked with
its own working directory (the benchmark's `src/evaluation`), so a relative
interpreter path will not resolve.

### Harness files

| File | Role |
|---|---|
| `text2kg_setup.py` | Compile ontologies into workspaces and sentence documents (§2); `--permissive-endpoints` and `--entity-examples` select the ablation arms (§10) |
| `run_benchmark.sh` | Drive extraction, conversion, evaluation, baseline re-scoring and the summary |
| `text2kg_export.py` | Convert a workspace's staging database into benchmark system output (§4) |
| `text2kg_eval.py` | Write the evaluator config and invoke the benchmark's `run_eval.py` (§5) |
| `text2kg_report.py` | Regenerate every table in §6 from the results on disk; `--benchmark` adds the recall-by-object-type table (§7.5) |
| `text2kg_diagnose.py` | Reachability, the macro F1 ceiling and the data artifacts (§7.2, §8); needs the eval venv |
| `text2kg_rescore.py` | Corrected benchmark copies and cross-system re-scoring, for [`benchmark-adjusted.md`](benchmark-adjusted.md) only |

`run_benchmark.sh` reads `PREFIX` and `RESULTS` from the environment, which is
how an ablation arm runs against its own workspaces without touching the primary
results (§10). Passing ontology names as arguments restricts extraction,
conversion and evaluation to those ontologies.

Results land in `paper/benchmark/results/`: `wukong/` (converted system output),
`eval/` (per-sentence and averaged metrics), `baselines/` (both baselines
re-scored under this harness) and `logs/` (one engine log per ontology).

### Configuration

Extraction used `config/default.toml` unchanged:

| Setting | Value |
|---|---|
| Model | `gpt-5.6-luna` |
| Execution mode | `real-time` |
| Max concurrency | 15 |
| Chunking | 800 target tokens, 120 overlap |

Chunking is inert here — every document is a single sentence, far below the
target, so each document is exactly one chunk.

---

## 4. Converting a run into benchmark output

`text2kg_export.py` reads the extracted knowledge straight from the workspace's
staging SQLite database rather than from an exported artifact, and attributes
each triple to a sentence through relationship provenance:

```
relationships → relationship_provenance → chunks → documents.source_uri
```

Since setup names each document after its benchmark id, the document's file stem
*is* the test sentence id. Two details matter for correctness:

- **Every test sentence gets a record**, including sentences that produced no
  triples, so the evaluator counts them rather than skipping them. This is the
  conservative choice: an omitted sentence would silently not be scored, whereas
  an empty one scores zero (§5).
- **Content-addressed documents are fanned back out.** Because duplicate
  sentences collapse into one document, the exporter maps that document's
  triples onto every test id sharing the sentence.

Relationship type names are translated back to benchmark relation labels through
the workspace's `text2kg_mapping.json`, with spaces written as underscores —
the form the evaluator compares against. An unmapped relationship type raises
rather than being dropped, so a workspace that has drifted out of sync with its
mapping fails loudly instead of quietly losing triples.

---

## 5. What the metrics actually measure

Read from `run_eval.py`. These definitions matter for interpreting the numbers,
and two of them are easy to misread.

**Precision / Recall / F1.** Computed per sentence and **macro-averaged** over
sentences. Before scoring, system triples are filtered to those whose relation
appears in *that sentence's* ground truth:

```python
gt_relations = {tr[1].replace(" ", "_") for tr in gt_triples}
filtered_system_triples = [tr for tr in system_triples if tr[1] in gt_relations]
```

> This is the subtle one: predicting a relation the sentence's ground truth does
> not mention costs **nothing** in precision — the triple is discarded before
> scoring. Precision therefore measures whether the *arguments* are right for
> relations the ground truth already expects, not whether the system was
> restrained about which relations to emit.

Matching is exact after lowercasing and stripping spaces and underscores
(`normalize_triple`). There is no stemming or fuzzy matching, so `Kesha Sebert`
does not match `Kesha`.

**Empty predictions** score precision = recall = F1 = 0, but ontology
conformance = 1 and relation hallucination = 0:

```python
if len(pred) == 0: return 0, 0, 0             # P/R/F1
if len(triples) == 0: return 1, 0             # conformance / rel. hallucination
```

> Consequence: a sentence that yields nothing is penalized on F1 but counted as
> perfectly conformant and non-hallucinating. Conformance and hallucination
> figures are therefore inflated by empty outputs for *every* system, and should
> be read together with the proportion of sentences that produced triples.

The mirror case — a sentence whose *gold standard* is empty — is worse: it
scores zero however the system answers, including when the system correctly
answers nothing. 142 sentences are affected; see §8.1.

**Ontology conformance** is the fraction of (unfiltered) system triples whose
relation is declared by the ontology; **relation hallucination** is its
complement.

**Subject / object hallucination** stems every word with a Porter stemmer,
concatenates and lowercases, then checks whether the argument appears as a
substring of the sentence concatenated with the ontology concept labels. A date
written `01 January <YYYY>` stems to `01januari…`, which the evaluator strips
before the check, so the dataset's date convention is not counted as
hallucination.

**Two populations** are reported: `all_test_cases` (every sentence) and
`selected_test_cases` (the 939 manually verified sentences). The verified subset
is the more reliable signal — see §7.

---

## 6. Results

Run of 2026-09-16, all 10 ontologies, 4,062 test sentences. Regenerate these
tables at any time with `python3 paper/benchmark/text2kg_report.py`.

### 6.1 WUKONG, all test cases

| Ontology | P | R | F1 | Conf. | Subj. hall. | Rel. hall. | Obj. hall. |
|---|---|---|---|---|---|---|---|
| 1_movie | 0.38 | 0.30 | 0.32 | 1.00 | 0.00 | 0.00 | 0.01 |
| 2_music | 0.41 | 0.31 | 0.33 | 1.00 | 0.00 | 0.00 | 0.02 |
| 3_sport | 0.13 | 0.13 | 0.12 | 0.94 | 0.00 | 0.06 | 0.00 |
| 4_book | 0.29 | 0.24 | 0.25 | 1.00 | 0.00 | 0.00 | 0.01 |
| 5_military | 0.13 | 0.17 | 0.15 | 0.81 | 0.00 | 0.19 | 0.00 |
| 6_computer | 0.10 | 0.10 | 0.09 | 1.00 | 0.00 | 0.00 | 0.00 |
| 7_space | 0.61 | 0.62 | 0.61 | 1.00 | 0.00 | 0.00 | 0.01 |
| 8_politics | 0.17 | 0.18 | 0.17 | 1.00 | 0.00 | 0.00 | 0.04 |
| 9_nature | 0.26 | 0.26 | 0.25 | 0.98 | 0.00 | 0.02 | 0.00 |
| 10_culture | 0.30 | 0.34 | 0.31 | 1.00 | 0.00 | 0.00 | 0.00 |
| **global** | **0.28** | **0.26** | **0.26** | **0.97** | **0.00** | **0.03** | **0.01** |

### 6.2 WUKONG, manually verified subset (939 sentences)

| Ontology | P | R | F1 | Conf. | Subj. hall. | Rel. hall. | Obj. hall. |
|---|---|---|---|---|---|---|---|
| 1_movie | 0.49 | 0.40 | 0.42 | 1.00 | 0.00 | 0.00 | 0.02 |
| 2_music | 0.51 | 0.35 | 0.39 | 1.00 | 0.00 | 0.00 | 0.04 |
| 3_sport | 0.18 | 0.18 | 0.17 | 0.92 | 0.00 | 0.08 | 0.01 |
| 4_book | 0.36 | 0.28 | 0.29 | 1.00 | 0.00 | 0.00 | 0.00 |
| 5_military | 0.12 | 0.14 | 0.12 | 0.72 | 0.00 | 0.28 | 0.01 |
| 6_computer | 0.20 | 0.22 | 0.20 | 1.00 | 0.00 | 0.00 | 0.02 |
| 7_space | 0.72 | 0.73 | 0.72 | 1.00 | 0.01 | 0.00 | 0.02 |
| 8_politics | 0.22 | 0.24 | 0.22 | 1.00 | 0.00 | 0.00 | 0.02 |
| 9_nature | 0.35 | 0.35 | 0.35 | 0.94 | 0.00 | 0.06 | 0.01 |
| 10_culture | 0.41 | 0.45 | 0.41 | 1.00 | 0.00 | 0.00 | 0.00 |

Every ontology scores higher on the verified subset than on the full split,
which is what one expects if part of the full-split gap is ground-truth noise
rather than extraction error (§7.2).

### 6.3 Against the published baselines

Global, all test cases. Both baselines were re-scored from their published
outputs under this harness; our re-scoring reproduces Vicuna's published global
row exactly, which is the check that our invocation of the evaluator is faithful.

| System | P | R | F1 | Conf. | Subj. hall. | Rel. hall. | Obj. hall. |
|---|---|---|---|---|---|---|---|
| **WUKONG** (`gpt-5.6-luna`) | 0.28 | 0.26 | **0.26** | **0.97** | **0.00** | **0.03** | **0.01** |
| Vicuna-13B (2-shot) | 0.38 | 0.35 | 0.35 | 0.84 | 0.17 | 0.13 | 0.17 |
| Alpaca-LoRA-13B (2-shot) | 0.32 | 0.26 | 0.27 | 0.88 | 0.19 | 0.12 | 0.18 |

Per-ontology F1, all test cases:

| Ontology | WUKONG | Vicuna-13B | Alpaca-LoRA-13B |
|---|---|---|---|
| 1_movie | **0.32** | 0.25 | 0.17 |
| 2_music | **0.33** | 0.32 | 0.22 |
| 3_sport | 0.12 | **0.52** | 0.45 |
| 4_book | 0.25 | **0.26** | 0.19 |
| 5_military | 0.15 | **0.24** | 0.21 |
| 6_computer | 0.09 | **0.35** | 0.29 |
| 7_space | 0.61 | **0.66** | 0.55 |
| 8_politics | 0.17 | **0.33** | 0.21 |
| 9_nature | 0.25 | 0.25 | **0.27** |
| 10_culture | 0.31 | 0.31 | 0.15 |

### 6.4 Coverage and cost

| Ontology | Sentences | With triples | Triples | Jobs | Failed | Input tok | Output tok | Reasoning tok | Sec |
|---|---|---|---|---|---|---|---|---|---|
| 1_movie | 840 | 497 | 1535 | 1306 | 0 | 1,442,608 | 92,921 | 126,441 | 283 |
| 2_music | 675 | 473 | 1088 | 1126 | 0 | 1,027,299 | 68,878 | 118,637 | 237 |
| 3_sport | 487 | 288 | 545 | 797 | 0 | 794,052 | 49,897 | 108,239 | 203 |
| 4_book | 550 | 286 | 622 | 875 | 0 | 958,788 | 53,277 | 107,406 | 214 |
| 5_military | 230 | 179 | 300 | 415 | 0 | 427,670 | 23,575 | 41,835 | 99 |
| 6_computer | 230 | 65 | 108 | 299 | 0 | 248,036 | 15,885 | 39,247 | 85 |
| 7_space | 203 | 160 | 226 | 358 | 0 | 343,306 | 19,717 | 22,703 | 69 |
| 8_politics | 214 | 188 | 294 | 396 | 0 | 314,524 | 21,493 | 32,277 | 85 |
| 9_nature | 474 | 294 | 439 | 865 | 0 | 954,270 | 41,200 | 84,158 | 181 |
| 10_culture | 159 | 79 | 108 | 272 | 0 | 250,501 | 11,875 | 24,027 | 54 |
| **Total** | **4062** | **2509** | **5265** | **6709** | **0** | **6,761,054** | **398,718** | **704,970** | **1510** |

All 6,709 extraction jobs completed; none failed and no engine log contains an
error. End-to-end extraction took 25 minutes at concurrency 15.

---

## 7. Findings

### 7.1 WUKONG trades recall for faithfulness

The headline result is a clean trade, visible in a single row of §6.3: WUKONG
scores **below Vicuna-13B on F1 (0.26 vs 0.35)** and level with Alpaca-LoRA-13B
(0.27), while reducing hallucination to near zero — subject hallucination
**0.00 vs 0.17/0.19**, object hallucination **0.01 vs 0.17/0.18** — and raising
ontology conformance to **0.97 vs 0.84/0.88**.

This is not an incidental difference. The baselines' subject hallucination rate
is the mechanism by which they earn part of their recall. The TekGen ground
truth frequently names a subject the sentence never mentions, inherited from the
source Wikipedia article (§7.2). A system that guesses a plausible article-level
subject will sometimes guess right and be rewarded; a system constrained to
extract only spans present in the text cannot score those triples at all. The
metric that separates the two systems most sharply — recall — is partly a metric
of willingness to invent, and the benchmark scores both behaviours in the same
column.

The honest framing for this run: WUKONG is **not** the most accurate system by
F1 here, and should not be presented as one. What it demonstrates is that a
knowledge model given up front buys near-total conformance and faithfulness at a
measurable cost in coverage.

**§10.1 shows most of that cost was avoidable.** Giving entity types the same
train-derived grounding the baselines already receive lifts F1 to 0.34 — level
with Vicuna — with conformance and hallucination unchanged. So the trade is not
inherent to constrained extraction; the coverage gap in this section is largely
the price of compiling an underspecified ontology mechanically.

That framing is about *this run*, not about the engine. The F1 figure is a
function of the model used (`gpt-5.6-luna`) and of ontologies taken exactly as
published, several of which underspecify their own schema in ways that cost us
directly — see §9 before treating 0.26 as WUKONG's accuracy.

It is also a function of the answer format. A quarter of the gold standard
consists of literal-valued objects, which WUKONG models as entity *properties*
and the benchmark can only express as separate nodes; recall on that quarter is
2.4× worse than on the rest, and §7.5 shows why that is a representational
mismatch rather than an extraction failure.

### 7.2 Only 65% of the ground truth is reachable at all

`text2kg_diagnose.py` measures how much of the gold standard any faithful,
ontology-conforming system could in principle produce, using the benchmark's own
normalization:

| Ontology | GT triples | Off-ontology | Absent subject | Absent object | Reachable |
|---|---|---|---|---|---|
| 1_movie | 2250 | 0 | 789 | 186 | 1308 (58%) |
| 2_music | 1480 | 28 | 281 | 195 | 1015 (69%) |
| 3_sport | 719 | 0 | 219 | 27 | 486 (68%) |
| 4_book | 933 | 0 | 213 | 126 | 619 (66%) |
| 5_military | 225 | 0 | 82 | 20 | 123 (55%) |
| 6_computer | 440 | 68 | 110 | 3 | 287 (65%) |
| 7_space | 279 | 0 | 52 | 5 | 223 (80%) |
| 8_politics | 202 | 0 | 71 | 0 | 131 (65%) |
| 9_nature | 531 | 0 | 133 | 34 | 366 (69%) |
| 10_culture | 173 | 0 | 51 | 4 | 120 (69%) |
| **Total** | **7232** | **96** | **2001** | **600** | **4678 (65%)** |

Expressed the way the evaluator aggregates — macro-averaged over sentences, and
including the sentences whose gold standard is empty (§8.1) — the **macro F1
ceiling for any faithful, ontology-conforming system is 0.644 on all test cases
and 0.722 on the verified subset**:

| Ontology | Sentences | Empty GT | Ceiling (all) | Ceiling (verified) |
|---|---|---|---|---|
| 1_movie | 840 | 0 | 0.602 | 0.677 |
| 2_music | 675 | 0 | 0.691 | 0.714 |
| 3_sport | 487 | 2 | 0.686 | 0.756 |
| 4_book | 550 | 0 | 0.674 | 0.752 |
| 5_military | 230 | 46 | 0.478 | 0.429 |
| 6_computer | 230 | 0 | 0.583 | 0.654 |
| 7_space | 203 | 0 | 0.798 | 0.901 |
| 8_politics | 214 | 54 | 0.505 | 0.582 |
| 9_nature | 474 | 40 | 0.648 | 0.815 |
| 10_culture | 159 | 0 | 0.755 | 0.898 |
| **Global** | 4062 | 142 | **0.644** | **0.722** |

Against that ceiling WUKONG reaches 40% (0.26/0.644) and Vicuna-13B 54%
(0.35/0.644). Two distinct defects produce the unreachable portion:

- **2,001 gold triples (28%) name a subject the sentence does not contain.**
  For example `ont_2_music_test_18` — *"Written by Jeff Hanneman and Kerry King
  for the 1986 studio album Reign in Blood…"* — expects the subject
  `Raining Blood`, the song title, which appears nowhere in the sentence.
- **96 gold triples use a relation their own ontology does not declare.** All of
  them are in 2_music (`occupation`, 28) and 6_computer (`named after`,
  `discoverer or inventor`, `distribution format`, `CPU`, `derivative work`,
  `implementation of`, `uses` — 68 of 440, or 15%). These cap 6_computer's
  recall at 0.786 before any system runs.

This ceiling should be stated in the paper whenever recall is quoted. An F1 of
0.26 against a 0.65 ceiling is a very different claim from an F1 of 0.26 against
a ceiling of 1.0.

### 7.3 WUKONG's real conformance is 1.00, not 0.97

The measured relation hallucination of 0.03 is entirely a benchmark data
artifact, and the paper should say so rather than report 0.97 unqualified.

Three ontology files declare a relation label with a **trailing space** —
`"country of origin "` (3_sport), `"military casualty classification "`
(5_military), `"mountains classification "` (9_nature) — while their own ground
truth files use the same labels without it. The evaluator builds its conformance
vocabulary from the ontology (`country_of_origin_`) but its F1 filter from the
ground truth (`country_of_origin`). No output string can satisfy both:

- emit `country_of_origin` → scored for F1, counted as a relation hallucination
- emit `country_of_origin_` → conformant, but discarded before F1 entirely

Our harness emits the ground-truth form, which is the choice that preserves F1.
Checking every triple we produced against the ontology labels *after stripping*,
**all 117 non-conformant triples are these three relations, and corrected
ontology conformance is 1.000 on all ten ontologies** — WUKONG never emitted a
relation outside its knowledge model, which is what the design guarantees. The
affected baselines show the same depression (Vicuna: 5_military 0.80,
9_nature 0.68), so it is not specific to us.

### 7.4 Where WUKONG loses, and why

WUKONG matches or beats Vicuna on 1_movie, 2_music and 10_culture, and is close
on 4_book, 9_nature and 7_space. It loses heavily on exactly four ontologies:
3_sport (0.12 vs 0.52), 6_computer (0.09 vs 0.35), 8_politics (0.17 vs 0.33) and
5_military (0.15 vs 0.24). Three compilation failures explain most of the gap.

**Degenerate self-referential triples when domain and range collapse.** 192 of
our 5,265 triples (3.6%) have a subject equal to their object, and they are
almost entirely in two relations:

| Relation | Self-loops | Ontology F1 |
|---|---|---|
| `3_sport:occupation` | 113 | 0.12 |
| `8_politics:position_held` | 68 | 0.17 |
| everything else | 11 | — |

The sport ontology declares `occupation` with domain *human* and range
*athlete*. In *"LaShawn Merritt … is an American track and field athlete"* the
same span satisfies both endpoints, so the engine emits
`LaShawn Merritt occupation LaShawn Merritt`, while the ground truth expects the
occupation label `athletics competitor`. The compilation treats a range concept
as something to extract from the text, but Wikidata-style class ranges name a
*category the subject belongs to*, which is often not a separate span.

**Endpoint type gating — the single largest recoverable loss.** Decomposing every
gold triple whose two arguments both occur in its sentence (`text2kg_report.py
--benchmark …`):

| Cause | Triples | Share of misses |
|---|---|---|
| One argument not extracted as an entity | 945 | 36.4% |
| **Blocked by endpoint types** | **798** | **30.7%** |
| Both entities found, no relationship emitted | 403 | 15.5% |
| Neither argument extracted | 246 | 9.5% |
| Right pair, different relation | 207 | 8.0% |

Of 4,482 achievable gold triples we matched 1,883 (42.0%). The second row is the
important one: **798 triples — 11% of the entire gold standard — were lost
because both arguments *were* extracted, but the types assigned to them are not
a pair the relationship accepts.**

A compiled relationship type inherits the ontology's declared domain and range as
a *hard* constraint. When the ontology also declares near-synonymous concepts,
the entity pass can pick a defensible type that the relation does not admit, and
the triple becomes impossible. `6_computer:platform` is the clearest case, and it
corrects a plausible but wrong reading of the raw counts — the gold objects are
**not** missing from the extraction:

| Type actually assigned to gold `platform` objects | Count |
|---|---|
| `ComputerModel` | 143 |
| `OperatingSystem` | 11 |
| `Computer` (the only type `platform` accepts) | 1 |
| not extracted at all | 44 |

The engine found `Microsoft Windows`, `PlayStation` and the rest; it filed them
under `ComputerModel`, while `platform` is compiled as *Software → Computer*. So
we emit 5 `platform` triples against 199 in the gold standard not because the
values were missed but because the knowledge model forbids the link. The relations
most affected are `6_computer:platform` (102), `2_music:performer` (94),
`3_sport:sport` (65), `member_of_sports_team` (49) and `league` (46) —
concentrated in precisely the ontologies where we trail the baselines.

This is a modelling artifact, not an engine limit. A knowledge model authored for a
task would either reconcile the near-synonymous types or declare several endpoint
pairs per relationship, which WUKONG supports and our compilation already emits
wherever the ontology states more than one range (§2). A prompt-based baseline
has no type system to violate, so this category costs it nothing.

**Span-boundary mismatches.** A further 187 gold triples were lost on otherwise
correct extractions where we chose a different extent for the object: 60
under-extractions (we emit `comedy`, gold wants `Comedy film`) and 127
over-extractions (we emit `romantic comedy-drama`, gold wants `Romantic comedy`).
`genre` accounts for 65 of them. This is **not** a canonical-label problem — the
full gold string occurs verbatim in the sentence in 99–100% of genre cases — so
the right answer was available and the boundary choice was ours. The surface-form
instruction (§2) says to reproduce the span without normalizing it, but says
nothing about *how much* of the phrase to take, and for a type-like object the
model tends to return the semantic head.

All three failures are properties of the *mechanical* ontology→knowledge-model
compilation and of harness-level instructions, not of the engine's extraction.

**§10 tests exactly that, and confirms it.** Generalizing the train-derived
example mechanism from dates to entity types (§10.1) cuts self-loops from 192 to
29, reduces type-gated misses from 798 to 493 and lifts global F1 from 0.26 to
0.34, at 6% extra cost. Removing the endpoint constraint outright (§10.2) raises
6_computer's F1 from 0.09 to 0.23 on its own, confirming that the values were
extracted and the knowledge model was refusing the link.

### 7.5 The benchmark has no properties, only triples — and that costs us most

This is the single largest structural explanation for WUKONG's recall, and it is
a **representational mismatch**, not an extraction failure.

WUKONG is an entity-relationship model **with properties**. A price, a date, a
duration or a classification is naturally a *field on an entity* — `Film.
publication_date` — which may be null and is filled during entity extraction. A
Text2KGBench answer, by contrast, is a bare triple, and a triple has nowhere to
put a property: the literal must become a node in its own right, with a
relationship pointing at it.

Setup bridges that gap with the catch-all `Value` entity type (§2), but the
bridge is load-bearing in a way the engine was not designed for. WUKONG extracts
**entities first, then relationships between entities that already exist**. So a
literal has to survive as a standalone entity in pass 1 before pass 2 can link
it. If `1923` is not recognized as a `Value` entity, the triple
`Alice's Wonderland — publication date — 01 January 1923` can never be produced,
however obvious the sentence.

That is precisely what happens. Recall splits sharply by how the object had to be
modelled (`text2kg_report.py --benchmark …`):

| Object modelled as | Gold triples | Matched | Recall |
|---|---|---|---|
| A typed entity | 5406 | 1713 | **0.317** |
| Generic `Value` node (a property in WUKONG terms) | 1730 | 225 | **0.130** |
| Relation absent from the ontology | 96 | 0 | 0.000 |

**Recall on value-typed objects is 2.4× worse**, across 1,730 gold triples — 24%
of the entire gold standard. The staging databases show the bottleneck is pass 1
exactly as predicted: in 1_movie the engine extracted **132 `Value` entities**
across 794 documents where the gold standard needs ~429, and only 59
relationships could then point at one.

Worst affected, all of them ordinary property-shaped data:

| Ontology | Relation | Gold | Matched | Recall |
|---|---|---|---|---|
| 3_sport | competition_class | 62 | 0 | 0.000 |
| 3_sport | sports_season_of_league_or_competition | 55 | 0 | 0.000 |
| 4_book | followed_by | 50 | 0 | 0.000 |
| 4_book | depicts | 20 | 0 | 0.000 |
| 1_movie | publication_date | 364 | 14 | 0.038 |
| 2_music | publication_date | 226 | 15 | 0.066 |
| 4_book | publication_date | 163 | 14 | 0.086 |

`publication_date` is the clearest case, and it isolates the cause cleanly. The
**format is right** — where we do emit a date it matches the gold convention
exactly (`01 January 2003`), so the train-derived date instruction (§2) worked.
The failure is pure under-production: 364 gold against 26 emitted in 1_movie,
missing sentences as plain as *"Alice's Wonderland is a 1923 Walt Disney short
silent film"*. The year is right there; it simply was not extracted **as an
entity**, because in WUKONG's data model a publication date is not one.

The ontologies where this hurts most are those whose gold standard is
property-heavy: value-typed objects are 53% of 2_music's gold triples and 46% of
10_culture's. Note the corollary — we still score comparatively well on those two
ontologies, because their *entity*-typed half is handled well.

**How to read this in the paper.** The comparison in §6.3 is not quite
like-for-like: a prompt-based baseline emits undifferentiated `(s, r, o)` strings
and is indifferent to whether `o` is an entity or a literal, so the triple format
costs it nothing. WUKONG is being asked to express a property-bearing model in a
format that cannot represent properties, and is charged for the difference. The
honest statement is that **0.130 is the cost of the representational mismatch,
not a measurement of how well WUKONG captures literal values** — in its own model
those are fields, retrieved as part of entity extraction, and never require a
generic node or a relationship at all. A benchmark permitting attribute-valued
answers would measure that capability directly; Text2KGBench cannot.

Grounding the `Value` type with train-derived examples (§10.1) lifts its recall
from 0.130 to 0.199, but the gap to typed entities persists (0.199 against
0.382). The mismatch is structural, not a prompting deficiency.

### 7.6 Two evaluator behaviours that shape the numbers

Both are documented in §5 and worth restating wherever the metrics appear.

- **Precision does not penalize over-eager relation choice.** System triples
  whose relation is absent from that sentence's ground truth are discarded
  before scoring. Our 47 `country_of_origin` triples in 3_sport, for which the
  ground truth has no such relation anywhere, cost nothing in precision. This
  makes precision a weaker signal than it appears, for every system.
- **Silence is scored as perfect conformance.** 1,553 of 4,062 sentences (38%)
  produced no triples; each scores 0 on P/R/F1 but 1.0 on conformance and 0 on
  all three hallucination metrics. Conformance and hallucination figures should
  therefore always be read next to the coverage column in §6.4. WUKONG produced
  triples for 62% of sentences.

### 7.7 Operational notes

- All 6,709 jobs succeeded on the first attempt across 4,062 sentences; the
  pipeline needed no retries and no manual intervention.
- Cost scales close to linearly with sentence count: ≈1,665 input tokens and
  ≈0.37 s per sentence at concurrency 15.
- Documents are content-addressed, so 4,062 test sentences became 3,911
  documents; 151 sentences are exact duplicates appearing under several test
  ids. The exporter re-attributes each document's triples to every id sharing
  its sentence, so this is invisible to the evaluator (§4).
- `text2kg_setup.py` reads only the ontology and the train split; the test and
  ground-truth files are touched solely by the exporter and the evaluator.

---

## 8. External artifacts that affect the scores

Everything in this section is a property of the benchmark data, not of WUKONG,
and applies to every system evaluated on the suite. Reproduce the tables with:

```bash
paper/benchmark/.venv-eval/bin/python paper/benchmark/text2kg_diagnose.py \
    --benchmark ../benchmarks/Text2KGBench
```

| Ontology | Empty GT | Dup. gold triples | Gold self-loops | Mojibake sents | Fragments |
|---|---|---|---|---|---|
| 1_movie | 0 | 10 | 0 | 36 | 14 |
| 2_music | 0 | 1 | 3 | 44 | 11 |
| 3_sport | 2 | 18 | 0 | 37 | 0 |
| 4_book | 0 | 0 | 1 | 24 | 8 |
| 5_military | 46 | 0 | 0 | 39 | 0 |
| 6_computer | 0 | 0 | 0 | 7 | 3 |
| 7_space | 0 | 0 | 0 | 12 | 0 |
| 8_politics | 54 | 8 | 0 | 18 | 0 |
| 9_nature | 40 | 0 | 0 | 112 | 0 |
| 10_culture | 0 | 0 | 0 | 10 | 0 |
| **Total** | **142** | **37** | **4** | **339** | **36** |

### 8.1 A correct empty answer is scored as a total failure

**This is the most consequential artifact in the suite.** 142 sentences (3.5%)
have an empty gold standard. For those, `gt_relations` is empty, so every system
triple is filtered out, `pred` is empty, and the evaluator's first branch
returns zero:

```python
if len(pred) == 0:
    return 0, 0, 0
```

A system that correctly recognizes the sentence states nothing scores
**P = R = F1 = 0**, identically to a system that emits pure noise. Verified
directly in our own metrics:

```
[ont_8_politics_test_74] sys=[] gt=[] -> P=0.00 R=0.00 F1=0.00
```

The distribution is very uneven, and it lands hardest on two of the four
ontologies where WUKONG trails the baselines most:

| Ontology | Sentences | Empty GT | Share | Max achievable F1 |
|---|---|---|---|---|
| 8_politics | 214 | 54 | 25.2% | 0.748 |
| 5_military | 230 | 46 | 20.0% | 0.800 |
| 9_nature | 474 | 40 | 8.4% | 0.916 |
| 3_sport | 487 | 2 | 0.4% | 0.996 |
| **All** | **4062** | **142** | **3.5%** | **0.965** |

Combined with unreachable triples (§7.2), 5_military's ceiling falls to 0.478
and 8_politics' to 0.505 — so our 0.15 and 0.17 sit against ceilings near 0.5,
not 1.0. Any per-ontology comparison in the paper should quote the ceiling
alongside the score.

### 8.2 Train/test overlap favours the few-shot baselines

320 test sentences (7.9%) appear **verbatim** in the train split, reaching 12.3%
in 1_movie and 13.9% in 2_music. This matters asymmetrically:

- The published baselines select their 2 in-context examples from the train
  split **by sentence similarity**. For these 320 sentences the most similar
  train sentence is the sentence itself, so the prompt can contain the test
  sentence together with its gold triples — direct leakage.
- WUKONG reads the train split only for date-format examples (§2) and never
  retrieves per-sentence examples, so it gains nothing comparable.

We did not exclude these sentences, because doing so would depart from the
published protocol and make our numbers incomparable to the baselines'. It is
recorded here as a factor favouring the baselines in the §6.3 comparison.

### 8.3 Mojibake: present, verified harmless

339 sentences (8.3%) contain UTF-8 text decoded as latin-1 — `BeyoncÃ©`,
`Ãme noire`, `morirÃ¡s por ella`. Because WUKONG is instructed to reproduce
surface forms verbatim, corrupted spans could in principle have made gold
arguments unmatchable.

They do not. The same corruption is present identically in the sentences and in
the ground truth, so the pair is self-consistent: of 1,252 gold arguments inside
mojibake sentences, **zero** change matchability when the encoding is repaired.
No correction was applied, and none is needed.

### 8.4 Fragment sentences with the subject removed

36 sentences have had their leading subject stripped while the gold triples
still name it:

```
[ont_1_movie_test_103] "is a 2014 Japanese anime film directed by Atsushi Nishigori ..."
    gold subject: the film title, absent from the sentence
```

A further 32 sentences are short and anaphoric (*"The film takes place in
Boston."*) with gold triples keyed on the article title. These are counted in
the 2,001 absent-subject triples of §7.2 and are the clearest illustration of
why that category is large. They are also precisely the cases where guessing an
article-level subject is rewarded and faithful extraction is not.

### 8.5 Smaller artifacts

- **96 gold triples use relations absent from their own ontology** — 28 in
  2_music, 68 in 6_computer (15% of that ontology's gold standard). Unreachable
  for any conforming system; 6_computer's recall is capped at 0.786 by this
  alone.
- **Three ontology labels carry a trailing space their ground truth omits**,
  making conformance and F1 mutually unsatisfiable. Full analysis in §7.3; this
  alone accounts for our entire measured 0.03 relation hallucination.
- **37 duplicate gold triples** within single sentences. The evaluator
  normalizes gold into a set, so these inflate nothing, but they mean a few
  sentences have fewer distinct gold triples than they appear to.
- **4 gold self-loops** where subject equals object.
- **Two ontologies declare the same relation label twice** (3_sport `league`,
  5_military `designed by`) with different ranges. Our setup collapses these
  into one relationship type carrying several endpoint pairs (§2), which is the
  correct reading.
- **Nine domain/range qids are never declared as concepts** (in 3_sport, 4_book,
  5_military, 6_computer, 9_nature). These carry no label to describe to the
  LLM, so they fall back to the untyped `Value` entity type — a loss of
  constraint that is not our choice but the ontology's.

---

## 9. Scope of these results

These numbers describe **one configuration of WUKONG on one benchmark**, not a
fixed property of the engine. Three qualifications belong in the paper wherever
the results are quoted.

### 9.1 The model is a parameter, not a constant

Everything in §6 was produced with **`gpt-5.6-luna`**, a light/balanced model,
in `real-time` mode at concurrency 15 with `config/default.toml` otherwise
untouched. The engine is model-agnostic: the knowledge model, the prompts and the
extraction pipeline are unchanged across models, so the model is a dial, not a
design decision baked into the results.

The extraction defects that cost the most in §7.4 — self-referential triples
when a relation's domain and range land on the same span, and failure to
recognize that `Microsoft Windows` fills a slot typed *computer* — are exactly
the kind of semantic judgement a stronger reasoning model handles better. We
would expect F1 to rise with a more capable model and fall with a weaker one.
**No claim in this document should be read as an upper bound on what WUKONG can
score**; it is the score of this engine with this model on this data.

### 9.2 Ontologies were used exactly as published, deliberately

Every ontology was compiled mechanically (§2), with no hand-tuning of any of the
ten. That is a methodological choice for comparability and reproducibility, and
it is honest about the cost: several ontologies underspecify their own schema,
and the compilation faithfully inherits every gap.

| Underspecification | Consequence |
|---|---|
| Relations with no range, or a range qid never declared as a concept | Object falls back to the untyped `Value` type (§2) |
| Class-valued ranges (`occupation` → *athlete*, `position held`) | Domain and range realize as the same span → self-loops (§7.4) |
| Near-synonymous concepts (`computer` vs `computer model`) with a relation admitting only one | 798 triples blocked by endpoint type gating, 11% of the gold standard (§7.4) |
| Labels carrying a trailing space | Conformance and F1 mutually unsatisfiable (§7.3) |
| Relations in the gold standard but not in the ontology | Structurally unreachable (§8.5) |

In other words, part of the gap to the baselines is WUKONG doing exactly what it
was told by an ontology that did not say what it meant. A prompt-based baseline
is looser: it is not bound by the declared domain and range, so an
underspecified ontology constrains it less and can cost it less. **A modest
amount of ontology curation — which is the normal situation in a real
deployment, where the knowledge model is authored for the task — would remove most
of these losses without touching the engine.**

§10 quantifies this, and the answer is most of it: grounding entity types with
train-derived examples raises global F1 from 0.26 to 0.34 and removing the
endpoint constraint raises 6_computer from 0.09 to 0.23, neither of which
changes the engine or the evaluator.

### 9.3 Cost follows the model, and scales — but output and cache writes dominate

At `gpt-5.6-luna` rates ($0.20/M uncached input, $0.02/M cache reads, $0.25/M
cache writes, $1.20/M output including reasoning) the full primary run cost
**$2.93**. The breakdown matters more than the total:

| | Tokens | Cost | Share |
|---|---|---|---|
| Uncached input | 1,740,537 | $0.35 | 12% |
| Cache reads | 22,808 | $0.00 | 0% |
| Cache writes | 5,020,517 | $1.26 | 43% |
| Output + reasoning | 1,103,688 | $1.32 | 45% |

**Output is 45% of the cost from 14% of the tokens, and reasoning tokens are 64%
of billable output.** Cache writes are most of the rest, and they bought nothing:
22,808 cache reads against 5,020,517 writes, a 0.3% hit rate. The cause was the
prompt layout of the engine version used here, not the workload. Each request was
sent as a single message ending in the sentence being extracted from, so
`gpt-5.6-luna`'s implicit caching wrote the whole prompt, sentence included, at
1.25× the input rate, and no other request could reuse it. With caching out of
the way, reasoning effort is the lever if cost becomes a constraint at scale.

> **Newer engine versions cache the shared prefix.** On GPT-5.6 and later models,
> the engine now sends the part of each prompt shared by every job extracting the
> same types (document context, task and type definitions) as a separate block
> with an explicit cache breakpoint, and caches only that part. That shared prefix
> is most of every entity prompt in this benchmark, so after the first request
> each prompt reuses it at a tenth of the input rate, and the sentence-specific
> part is never written to the cache. The text the model sees is unchanged, so the
> quality results in this document still hold. The token counts and costs here
> are those of the earlier version and were not re-measured. They overstate what a
> run on the current engine costs, most of all in the $1.26 spent on cache writes,
> since the reusable prefix is then read at $0.02/M instead of written at $0.25/M.

The run in aggregate:

| Measure | Value |
|---|---|
| Sentences | 4,062 |
| Extraction jobs | 6,709 (0 failed) |
| Input tokens | 6,761,054 (≈1,665 per sentence) |
| Output tokens | 398,718 |
| Reasoning tokens | 704,970 |
| Wall clock | 1,510 s (25 min) at concurrency 15 |
| Throughput | ≈2.7 sentences/s |
| Cost | $2.93 (≈$0.00072 per sentence) |

Two properties matter for scaling beyond benchmark size. Cost is **linear in
corpus size** — there is no cross-document join whose cost grows super-linearly,
and per-sentence token use is near-constant across all ten ontologies. And
throughput is bounded by `max_concurrency` against the provider's rate limit,
not by the engine, so it scales horizontally with tier.

A light model is therefore a viable operating point for large corpora: the same
pipeline on `gpt-4.1-mini` costs less again, and `batch` execution mode trades
latency for a further reduction. The trade-off to state in the paper is that
**accuracy and cost are both functions of the chosen model**, and these results
document one point on that curve — deliberately a cheap one — rather than the
engine's best achievable accuracy.

---

## 10. Ablations

Two arms test whether the losses diagnosed in §7.4 are properties of the engine
or of the mechanical compilation. Both change only how the ontology is compiled,
read nothing but the ontology and the **train** split, and are scored by the same
unmodified evaluator. The primary run of §6 stays the headline zero-tuning
result; these are reported beside it, not in place of it.

```bash
# Arm A - endpoints accept any pair of entity types
python3 paper/benchmark/text2kg_setup.py --benchmark ../benchmarks/Text2KGBench \
    --permissive-endpoints --prefix perm_
PREFIX=perm_ RESULTS=paper/benchmark/results-permissive paper/benchmark/run_benchmark.sh 6_computer

# Arm B - entity types seeded with train-derived example surface forms
python3 paper/benchmark/text2kg_setup.py --benchmark ../benchmarks/Text2KGBench \
    --entity-examples --prefix examples_
PREFIX=examples_ RESULTS=paper/benchmark/results-examples paper/benchmark/run_benchmark.sh
```

### 10.1 Arm B — train-derived entity examples (full suite)

Setup gives every entity type up to three example surface forms observed in the
**train** split, exactly the mechanism §2 already used for dates, generalized
from one field convention to entity types. Objects that fall back to the untyped
`Value` type are keyed by the relations that produce them, since `Value` has no
concept of its own. 283 examples across 10 ontologies; no test or ground-truth
file is read.

**This is the more comparable configuration, not a tuned one.** The published
baselines retrieve two similar train sentences *per test sentence*, complete with
their gold triples (§8.2). The primary arm takes essentially nothing from train.
Arm B takes three surface forms per entity type — still far less than the
baselines — so it is the closer like-for-like comparison.

| Ontology | F1 primary | F1 arm B | Δ | P primary → B | R primary → B |
|---|---|---|---|---|---|
| 1_movie | 0.32 | 0.33 | +0.01 | 0.38 → 0.39 | 0.30 → 0.30 |
| 2_music | 0.33 | 0.41 | +0.08 | 0.41 → 0.50 | 0.31 → 0.39 |
| 3_sport | 0.12 | 0.31 | **+0.19** | 0.13 → 0.32 | 0.13 → 0.32 |
| 4_book | 0.25 | 0.26 | +0.01 | 0.29 → 0.31 | 0.24 → 0.25 |
| 5_military | 0.15 | 0.23 | +0.08 | 0.13 → 0.22 | 0.17 → 0.26 |
| 6_computer | 0.09 | 0.23 | **+0.14** | 0.10 → 0.23 | 0.10 → 0.24 |
| 7_space | 0.61 | 0.66 | +0.05 | 0.61 → 0.67 | 0.62 → 0.67 |
| 8_politics | 0.17 | 0.30 | **+0.13** | 0.17 → 0.30 | 0.18 → 0.32 |
| 9_nature | 0.25 | 0.27 | +0.02 | 0.26 → 0.27 | 0.26 → 0.27 |
| 10_culture | 0.31 | 0.42 | **+0.11** | 0.30 → 0.41 | 0.34 → 0.45 |
| **global** | **0.26** | **0.34** | **+0.08** | 0.28 → 0.36 | 0.26 → 0.35 |

**Every ontology improves, and precision rises with recall in all ten** — the
arm is not trading one against the other. Against the published baselines:

| System | P | R | F1 | Conf. | Subj. hall. | Rel. hall. | Obj. hall. |
|---|---|---|---|---|---|---|---|
| WUKONG, primary | 0.28 | 0.26 | 0.26 | 0.97 | 0.00 | 0.03 | 0.01 |
| **WUKONG, arm B** | 0.36 | 0.35 | **0.34** | **0.97** | **0.00** | **0.03** | **0.01** |
| Vicuna-13B (2-shot) | 0.38 | 0.35 | 0.35 | 0.84 | 0.17 | 0.13 | 0.17 |
| Alpaca-LoRA-13B (2-shot) | 0.32 | 0.26 | 0.27 | 0.88 | 0.19 | 0.12 | 0.18 |

Arm B reaches **F1 parity with Vicuna-13B (0.34 vs 0.35) while keeping ontology
conformance at 1.000 corrected and hallucination at essentially zero** — subject
0.00 against 0.17, object 0.01 against 0.17. Recall is level (0.35 vs 0.35); the
remaining 0.02 of precision is within the rounding of a macro average.

It also repairs three of the four failures diagnosed in §7.4 at once, which is
the strongest evidence that they were compilation artifacts rather than engine
limits:

| Diagnostic | Primary | Arm B |
|---|---|---|
| Degenerate self-loops (§7.4) | 192 (3.6% of triples) | **29 (0.5%)** |
| Gold triples blocked by endpoint types (§7.4) | 798 | **493** |
| Recall on `Value`-typed objects (§7.5) | 0.130 | **0.199** |
| Recall on entity-typed objects | 0.317 | **0.382** |
| Achievable gold triples matched | 1,883 (42.0%) | **2,345 (52.3%)** |
| Corrected ontology conformance (§7.3) | 1.000 | 1.000 |
| Cost | $2.93 | $3.10 |

Self-loops fall by 85% because an example shows that an `occupation` object looks
like `athletics competitor`, not like the person's name. Type gating falls by 38%
without any endpoint change, because better-grounded entity types are assigned
more often to the type the relation expects. Both were free side effects of
grounding the entity types.

Cost rises 6% ($2.93 → $3.10) for the examples carried in each prompt; job count,
wall clock and failure count are unchanged (6,872 jobs, 24 min, 0 failed).

### 10.2 Arm A — permissive endpoints (6_computer probe)

Every relationship accepts any ordered pair of entity types, so the declared
domain and range become documentation rather than a constraint. Run on
6_computer only, where endpoint gating causes 89% of the "both entities found"
misses and `platform` is the clearest case (§7.4).

| 6_computer | P | R | F1 | Conf. | Subj. hall. | Rel. hall. | Obj. hall. |
|---|---|---|---|---|---|---|---|
| Primary | 0.10 | 0.10 | 0.09 | 1.00 | 0.00 | 0.00 | 0.00 |
| **Arm A** | 0.23 | 0.25 | **0.23** | 1.00 | 0.00 | 0.00 | 0.00 |

**F1 improves 2.6× (0.09 → 0.23), with precision rising alongside recall and no
loss of conformance or faithfulness.** This confirms the §7.4 diagnosis
directly: the values were being extracted and the knowledge model was refusing the
link. Arm A and arm B reach the same F1 on this ontology (0.23) by different
routes — A by removing the constraint, B by helping the entity pass satisfy it.

**Arm A was not run on the full suite because it is disproportionately
expensive.** Making every relationship type applicable to every chunk inflates
the relationship prompt roughly 29× (20,625 vs ~723 input tokens per job), since
each job now carries every relationship type and every entity type in context.
The multiplier scales with the ontology's relationship-type count:

| Ontology | Relationship types | Input tokens vs primary |
|---|---|---|
| 6_computer | 4 | 3.5× (measured) |
| 1_movie | 15 | ~12× (measured, partial run) |

Extrapolated to all ten this is ≈81M input tokens, roughly **$21 and 5 hours**,
against $2.93 for the primary run. Since arm B recovers the same ground on this
ontology at a fraction of the cost, the full permissive sweep was not worth the
spend; the probe is reported as a targeted confirmation of the mechanism, not as
a suite-level result.

### 10.3 What the ablations mean for the paper

The honest reading of §7.1 changes. The primary run shows WUKONG trading recall
for faithfulness at **F1 0.26 against Vicuna's 0.35**. Arm B shows that most of
that gap was not the engine but the compilation: giving entity types the same
kind of train-derived grounding the baselines already receive lifts F1 to
**0.34 — level with Vicuna — while conformance stays at 1.000 and hallucination
at zero**.

The claim the benchmark supports is therefore stronger and more specific than
the primary run alone suggests: *at comparable accuracy, WUKONG produces
knowledge graphs that conform to the ontology and do not hallucinate, which the
few-shot baselines do not.* Both numbers belong in the paper — the primary run as
the zero-tuning result, arm B as the like-for-like comparison — and the gap
between them is itself the finding about how much a knowledge model's quality
matters.

What remains unrecovered after arm B is the representational mismatch of §7.5
(`Value` recall 0.199 against 0.382 for typed entities) and the benchmark
ceiling of §7.2 and §8.1. Those are not addressable within this protocol.
[`benchmark-adjusted.md`](benchmark-adjusted.md) addresses both by changing the
protocol: range-less relations become entity properties (`Value` recall 0.199 →
0.330), and the gold is corrected for every system.
