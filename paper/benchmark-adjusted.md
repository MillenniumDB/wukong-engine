# WUKONG on Text2KGBench: Adjusted Protocol and Results

This document records a second evaluation of the WUKONG engine on Text2KGBench,
under a protocol **adjusted to remove benchmark properties that penalize WUKONG
specifically or distort every system's score**. It is a companion to
[`benchmark.md`](benchmark.md), not a replacement for it.

> **Which document to cite for what.**
>
> - [`benchmark.md`](benchmark.md) is the **vanilla** run: the benchmark exactly as
>   published, scored exactly as published. It is the directly comparable number,
>   and it is **unfair to WUKONG** in ways that document itself diagnoses (§7.5,
>   §8 there).
> - This document is the **adjusted** run. It is **fairer to WUKONG, but it changes
>   things**: how WUKONG models the benchmark's ontologies (§2) and which parts of
>   the gold standard are scored (§3). Every scoring change is applied identically
>   to the baselines, and the evaluator itself is never modified, but the numbers
>   here are **not** comparable to anything published elsewhere on Text2KGBench.
>
> Quote both, labelled. Neither is the "real" score. The vanilla run shows how
> WUKONG does on the benchmark as defined; the adjusted run shows how it does once
> the benchmark stops measuring things unrelated to extraction quality.

- **Benchmark**: [Text2KGBench](https://github.com/cenguix/Text2KGBench) (ISWC 2023), Wikidata-TekGen test suite
- **System under test**: WUKONG engine v0.2.0, `gpt-5.6-luna`, real-time execution mode, `config/default.toml` unchanged
- **Scoring**: the benchmark authors' own `run_eval.py`, **unmodified**, over corrected *copies* of the data
- **Run date**: 2026-09-25

## Headline

| Protocol | WUKONG (this run) | WUKONG arm B | Vicuna-13B | Alpaca-LoRA-13B |
|---|---|---|---|---|
| Vanilla modelling, vanilla scoring (`benchmark.md`) | — | 0.34 | 0.35 | 0.27 |
| **Adjusted modelling**, vanilla scoring | **0.37** | 0.34 | 0.35 | 0.27 |
| **Adjusted modelling, adjusted scoring (B1–B5)** | **0.39** | 0.36 | 0.36 | 0.27 |
| Adjusted + reachable gold only (B1–B6, secondary) | **0.54** | 0.50 | 0.46 | 0.35 |

Global macro F1, all test cases. Under the adjusted protocol WUKONG has the
**highest F1 of any system (0.39 vs 0.36)** while keeping **ontology conformance
at 1.00** (baselines 0.84/0.88) and **subject hallucination at 0.00** (0.17/0.18).
In the vanilla run WUKONG was level with Vicuna on F1. The adjusted run puts it
ahead, and the two changes behind that can be measured separately (§5.3).

---

## 1. What was adjusted, and why

The vanilla run's report (`benchmark.md` §7–§9) identified where the benchmark
cost WUKONG points unrelated to the quality of its extraction. Each adjustment
below answers one of those findings. They fall into two groups that must not be
confused:

- **A — modelling changes.** These change *how WUKONG is configured* for the
  benchmark. They only affect WUKONG, just as a baseline's prompt only affects
  that baseline.
- **B — scoring corrections.** These change *what is scored*. They are applied
  to a copy of the benchmark data and hit **every system equally**, including the
  published baselines, which are re-scored from their released outputs.

| # | Adjustment | Answers | Scale | Applied |
|---|---|---|---|---|
| A1 | Relations with no usable range become **properties** of the domain entity type | `benchmark.md` §7.5, the largest structural loss | 25 relations, ~24% of gold | Yes |
| A1a | Applied mechanically to *every* range-less relation, including ones whose objects are really entities (`performer`, `producer`, `developer`) | Hand-picking would be tuning | — | Yes |
| A1b | Multi-valued properties: values separated by `;`, split on export | `instrumentation`, `performer`… | — | Yes |
| A1c | An undeclared relation *domain* gets a generic subject type | 4_book, 5_military, 9_nature | 157 gold triples in 4_book | Yes |
| A1d | A property value is only emitted for a sentence that states it | Entity merging across sentences | 60 values withheld | Yes |
| A2 | Built on arm B (train-derived entity examples) | `benchmark.md` §10.1 | — | Yes |
| A3 | Endpoint relaxation, synonym-type merging | `benchmark.md` §7.4 | — | **No**: cost, or hand-tuning |
| A4 | Model | — | — | **Unchanged**, `gpt-5.6-luna` |
| B1 | Strip trailing spaces from ontology relation labels | `benchmark.md` §7.3 | 3 relations | Yes |
| B2 | Drop sentences whose gold standard is empty | `benchmark.md` §8.1 | 142 sentences (+41 emptied by B3) | Yes |
| B3 | Drop gold triples using a relation their ontology lacks | `benchmark.md` §8.5 | 96 triples | Yes |
| B4 | Rewrite zero-day gold dates in the train split's convention | new, §3.2 | 158 triples | Yes |
| B5 | Drop test sentences that appear verbatim in train | `benchmark.md` §8.2 | 320 sentences | Yes |
| B6 | Drop gold triples whose subject the sentence lacks | `benchmark.md` §7.2 | 1,563 triples | **Secondary view only** |

**Not adjusted:** span-boundary choices (`benchmark.md` §7.4), which were
WUKONG's own; residual self-loops, which arm B had already cut by 85%; and mojibake,
which is verified harmless.

---

## 2. Modelling changes (A)

### 2.1 Range-less relations as entity properties (A1)

In the vanilla compilation, a relation with no range concept, or with a range qid
the ontology never declares, points at a catch-all `Value` entity. WUKONG
extracts entities first and relationships second, so a literal such as `1923`
had to survive pass 1 as a standalone `Value` entity before pass 2 could link it.
Mostly it did not: recall on those objects was 0.130 (0.199 with arm B), against
0.317 (0.382) for typed entities.

With `--literal-properties`, such a relation instead becomes a **string field on
its domain entity type**. That is how WUKONG natively represents a date, a
classification or a quantity. The field is optional, filled during entity
extraction, and carries the same train-derived examples and date convention the
`Value` type used to get:

```json
"Film": {
    "primary_key": "name",
    "fields": {
        "name": { "...": "..." },
        "publication_date": {
            "data_type": "string",
            "description": "The \"publication date\" of this Film, as defined by the Film Ontology.",
            "instructions": "Only fill this field when the source text explicitly states it; ... Dates must be written in the format \"<DD> <Month> <YYYY>\". ...",
            "required": false,
            "examples": ["01 January 2010", "01 January 2003"]
        }
    }
}
```

The exporter turns each property value back into the triple the benchmark
expects, `(entity, relation, value)`, so the evaluator sees the same format as
before.

The `Value` entity type disappears entirely. What the rule touches:

| Ontology | Relations compiled into properties |
|---|---|
| 1_movie | `publication date`, `main subject`, `cost` |
| 2_music | `publication date`, `instrumentation`, `performer`, `producer`, `record label` |
| 3_sport | `sports season of league or competition`, `home venue`, `league`\*, `competition class` |
| 4_book | `publication date`, `followed by`, `place of publication`, `depicts` |
| 5_military | `wing configuration` |
| 6_computer | `developer` |
| 7_space | `spacecraft docking/undocking date` |
| 9_nature | `taxon common name` |
| 10_culture | `inception`, `start time`, `iconographic symbol`, `indigenous to` |

\* 3_sport declares `league` twice, once with a typed range (*professional sports
league*) and once without. The rule is applied per declaration, so `league` is
both a relationship and a property of `Human`; the exporter deduplicates the
resulting triples.

**A1a — mechanical scope.** Several of these relations do not hold literals at
all: `performer`, `producer`, `record label` and `developer` point at people and
companies, and the ontology simply omitted their range. They were converted
anyway. The rule is "no usable range → property" without exception, because
choosing which relations are "really" literals is per-ontology hand-tuning, which
both runs avoid.

**A1b — multi-valued properties.** A property holds one string, but a sentence
may state several values (*"written for oboe, bass clarinet, piano and four
percussionists"*). The field instruction asks for each value to be extracted on
its own and separated by `;`, and the exporter splits on it.

### 2.2 Undeclared domains get a generic subject type (A1c)

A property needs an entity type to live on. Four 4_book relations (`illustrator`,
`followed by`, `place of publication`, `depicts`; 157 gold triples), one
5_military relation and one 9_nature relation have a domain qid the ontology
never declares. In the vanilla run those subjects also fell back to `Value`.

Each such qid now becomes a generic entity type (`SubjectQ47461344` in 4_book).
Since the ontology gives the qid no label, the type is described by the only
thing the ontology does say about it, the relations it is the subject of:

> An entity that is the subject of the "depicts", "followed by", "illustrator",
> "place of publication" relation(s) of the Book Ontology, whose type the ontology
> does not name.

It receives train-derived examples like every other type. A relation from an
undeclared domain to a declared range (`illustrator` → *human*) stays a
relationship, now from the generic type.

### 2.3 Attributing property values to sentences (A1d)

Relationship triples are attributed to sentences through relationship
provenance, exactly as before. Properties have no provenance of their own: an
entity is deduplicated across the whole corpus and its fields are merged, so a
merged value may have been read in a *different* sentence from the one being
exported. Property triples are therefore attributed through **entity
provenance**, and **a value is only emitted for a sentence that states it**
(after the evaluator's own lowercasing and whitespace removal; for a date in the
`<DD> <Month> <YYYY>` convention, the year must occur).

The effect is small but it matters. Only ~3% of film, work and book entities recur
across sentences, and **60 property values** were withheld across the suite.
Without the check, a sentence could be credited with a date read from another
sentence.

### 2.4 Base configuration (A2)

The run is built on arm B of `benchmark.md` §10.1, where every entity type (and now
every property field) carries up to three example surface forms from the
**train** split. That was already the like-for-like configuration against the
2-shot baselines; the adjusted run adds only A1 on top of it, so the difference
between the two is the effect of the property modelling alone.

---

## 3. Scoring corrections (B)

### 3.1 How they are applied

`text2kg_rescore.py` writes a **corrected copy** of the benchmark for each
cumulative combination of corrections, under `paper/benchmark/scoring/<variant>/`.
Only three kinds of file are rewritten: the ontologies, the ground truth and the
verified-subset id lists. Everything else, including `src/evaluation/run_eval.py`
and the train split, is a symlink to the real benchmark. Every system (the three
WUKONG arms and both baselines) is then scored by the unmodified `run_eval.py`
against each copy. The benchmark repository is never written to.

Two checks confirm the copy is faithful. `0_vanilla`, a copy with no corrections,
reproduces the published global F1 of every system exactly (WUKONG 0.26 / 0.34,
Vicuna 0.35, Alpaca 0.27). And the verified-subset id lists are filtered to
surviving sentences, because `run_eval.py` divides the subset's summed scores by
the length of that list.

### 3.2 The corrections

- **B1 — trailing-space labels.** Three ontologies declare `"country of origin "`,
  `"military casualty classification "`, `"mountains classification "` while their
  own ground truth omits the space, making conformance and F1 mutually
  unsatisfiable (`benchmark.md` §7.3). Stripping the labels restores WUKONG's
  measured conformance to the 1.00 it already had in substance, and does not
  change F1 for any system.
- **B2 — empty gold standards.** 142 sentences have no gold triples and score
  P = R = F1 = 0 whatever a system answers, including a correct empty answer.
  They are dropped, together with the 41 sentences that B3 empties.
- **B3 — off-ontology gold.** 96 gold triples (28 in 2_music, 68 in 6_computer)
  use relations their own ontology does not declare, so no conforming system can
  produce them. They are dropped.
- **B4 — zero-day dates.** A new finding of this run. Besides the `01 January <YYYY>`
  convention the train split teaches, **158 gold dates use a "day 00" convention**
  that appears **nowhere in the train split** and nowhere in either baseline's
  output: 139 year-only (`00  1958`, with a double space; 41% of 4_book's dates) and
  19 month-and-year (`00 June 1962`). Train writes those as `01 January 1958` and
  `01 June 1962`, and B4 rewrites the gold into that form. No system could have
  learned the zero-day form, so this only removes an unlearnable target.
- **B5 — train/test leakage.** 320 test sentences appear verbatim in the train
  split, from which the baselines retrieve their 2-shot examples by similarity.
  For those sentences a baseline's prompt can contain the test sentence and its
  gold triples. They are dropped.
- **B6 — absent subjects (secondary).** Gold triples whose subject does not occur
  in the sentence, under the evaluator's own stemmed normalization, are dropped.
  This is by far the largest defect (1,563 triples after B1–B5) and the one that
  most favours systems willing to guess an article-level subject. It also removes
  a quarter of the scored gold, so it is reported as a secondary view and never
  as the headline.

### 3.3 Scored population

| Variant | Corrections | Sentences | Verified | Gold triples |
|---|---|---|---|---|
| `0_vanilla` | — | 4,062 | 939 | 7,232 |
| `1_strip_labels` | B1 | 4,062 | 939 | 7,232 |
| `2_drop_empty` | B1–B2 | 3,920 | 895 | 7,232 |
| `3_drop_off_ontology` | B1–B3 | 3,879 | 881 | 7,136 |
| `4_normalize_dates` | B1–B4 | 3,879 | 881 | 7,136 |
| **`5_drop_train_overlap`** | **B1–B5 (adjusted)** | **3,564** | **822** | **5,974** |
| `6_drop_absent_subject` | B1–B6 (reachable) | 2,573 | 676 | 4,411 |

---

## 4. Reproducing the run

Prerequisites as in `benchmark.md` §3 (the benchmark checked out next to this
repository, `OPENAI_API_KEY`, the evaluator venv).

```bash
# 1. Compile: arm B + literal properties, into props_* workspaces
python3 paper/benchmark/text2kg_setup.py --benchmark ../benchmarks/Text2KGBench \
    --entity-examples --literal-properties --prefix props_

# 2. Extract, convert, score under vanilla scoring, re-score the baselines
PREFIX=props_ RESULTS=paper/benchmark/results-properties paper/benchmark/run_benchmark.sh

# 3. Build every corrected copy and score all five systems under each
paper/benchmark/.venv-eval/bin/python paper/benchmark/text2kg_rescore.py \
    --benchmark ../benchmarks/Text2KGBench

# 4. Reachability and ceiling under a corrected copy
paper/benchmark/.venv-eval/bin/python paper/benchmark/text2kg_diagnose.py \
    --benchmark paper/benchmark/scoring/5_drop_train_overlap
```

Step 3 needs the primary (`results/`) and arm B (`results-examples/`) outputs of
`benchmark.md` to be present; any system whose output directory is missing is
skipped. Its tables are printed to stdout, and every metric is also written to
`results-properties/scoring/<variant>/<system>/` and
`results-properties/scoring/summary.json`.

| File | Role in this run |
|---|---|
| `text2kg_setup.py --literal-properties` | Property compilation and generic subject types (§2) |
| `text2kg_export.py` | Adds property triples through entity provenance, with the stated-in-sentence check (§2.3) |
| `text2kg_rescore.py` | Corrected benchmark copies and cross-system re-scoring (§3) |
| `text2kg_report.py` | Per-ontology tables, recall by object type and miss decomposition for `results-properties` |

The vanilla arms are unaffected by these changes. Re-running setup without
`--literal-properties` regenerates the primary and arm B workspaces
byte-identically, and re-exporting the primary run reproduces its committed
output byte-identically.

---

## 5. Results

### 5.1 Adjusted protocol (B1–B5), global

| System | P | R | F1 | Conf. | Subj. hall. | Rel. hall. | Obj. hall. |
|---|---|---|---|---|---|---|---|
| **WUKONG, adjusted modelling** | **0.41** | **0.40** | **0.39** | **1.00** | **0.00** | **0.00** | **0.01** |
| WUKONG, arm B | 0.38 | 0.37 | 0.36 | 1.00 | 0.00 | 0.00 | 0.01 |
| WUKONG, primary | 0.29 | 0.28 | 0.28 | 1.00 | 0.00 | 0.00 | 0.01 |
| Vicuna-13B (2-shot) | 0.38 | 0.36 | 0.36 | 0.84 | 0.17 | 0.13 | 0.18 |
| Alpaca-LoRA-13B (2-shot) | 0.31 | 0.27 | 0.27 | 0.88 | 0.18 | 0.12 | 0.19 |

WUKONG leads on precision, recall and F1, and on all four faithfulness metrics.
With B1 applied, measured conformance is 1.00 for every WUKONG arm, which is the
corrected figure `benchmark.md` §7.3 had to argue for. The baselines' conformance
barely moves (0.84, 0.88) because their relation hallucinations are real.

### 5.2 Per-ontology F1, adjusted protocol

All test cases:

| Ontology | WUKONG adjusted | WUKONG arm B | WUKONG primary | Vicuna-13B | Alpaca-LoRA-13B |
|---|---|---|---|---|---|
| 1_movie | **0.38** | 0.33 | 0.32 | 0.21 | 0.14 |
| 2_music | 0.40 | **0.43** | 0.34 | 0.29 | 0.20 |
| 3_sport | 0.34 | 0.30 | 0.12 | **0.52** | 0.44 |
| 4_book | **0.32** | 0.25 | 0.24 | 0.25 | 0.18 |
| 5_military | **0.34** | 0.29 | 0.18 | 0.28 | 0.24 |
| 6_computer | 0.27 | 0.24 | 0.13 | **0.35** | 0.31 |
| 7_space | 0.66 | 0.66 | 0.61 | **0.67** | 0.55 |
| 8_politics | **0.43** | 0.41 | 0.20 | 0.41 | 0.25 |
| 9_nature | 0.29 | **0.30** | 0.29 | 0.27 | 0.29 |
| 10_culture | **0.49** | 0.42 | 0.31 | 0.31 | 0.15 |

Manually verified subset:

| Ontology | WUKONG adjusted | WUKONG arm B | WUKONG primary | Vicuna-13B | Alpaca-LoRA-13B |
|---|---|---|---|---|---|
| 1_movie | **0.49** | 0.43 | 0.42 | 0.26 | 0.16 |
| 2_music | 0.48 | **0.51** | 0.40 | 0.30 | 0.24 |
| 3_sport | 0.36 | 0.31 | 0.17 | **0.51** | 0.37 |
| 4_book | **0.42** | 0.32 | 0.30 | 0.27 | 0.21 |
| 5_military | **0.39** | 0.35 | 0.17 | 0.27 | 0.18 |
| 6_computer | 0.25 | 0.23 | 0.26 | **0.39** | 0.27 |
| 7_space | **0.77** | 0.73 | 0.71 | 0.75 | 0.69 |
| 8_politics | 0.56 | **0.57** | 0.22 | 0.49 | 0.32 |
| 9_nature | 0.39 | **0.43** | 0.39 | 0.28 | 0.34 |
| 10_culture | **0.66** | 0.58 | 0.41 | 0.49 | 0.14 |
| **mean** | **0.48** | 0.45 | 0.35 | 0.40 | 0.29 |

WUKONG with adjusted modelling beats Vicuna on seven of ten ontologies on all
test cases, and on eight of ten on the verified subset. Vicuna wins 7_space by
0.01 on all test cases. It still wins 3_sport and 6_computer clearly on both
populations: those are the two ontologies where endpoint type gating costs WUKONG
most (`benchmark.md` §7.4). A3 was deliberately not applied, so that gap is
untouched.

### 5.3 Separating the modelling effect from the scoring effect

Global F1, all test cases, as the corrections accumulate:

| Variant | WUKONG adjusted | WUKONG arm B | WUKONG primary | Vicuna-13B | Alpaca-LoRA-13B |
|---|---|---|---|---|---|
| `0_vanilla` | **0.37** | 0.34 | 0.26 | 0.35 | 0.27 |
| + B1 labels | 0.37 | 0.34 | 0.26 | 0.35 | 0.27 |
| + B2 empty gold | 0.39 | 0.36 | 0.27 | 0.37 | 0.29 |
| + B3 off-ontology gold | 0.39 | 0.37 | 0.28 | 0.37 | 0.29 |
| + B4 zero-day dates | 0.40 | 0.37 | 0.28 | 0.37 | 0.29 |
| **+ B5 train overlap** | **0.39** | 0.36 | 0.28 | 0.36 | 0.27 |
| + B6 absent subjects | 0.54 | 0.50 | 0.37 | 0.46 | 0.35 |

Verified subset, mean of per-ontology F1:

| Variant | WUKONG adjusted | WUKONG arm B | WUKONG primary | Vicuna-13B | Alpaca-LoRA-13B |
|---|---|---|---|---|---|
| `0_vanilla` | **0.44** | 0.41 | 0.33 | 0.39 | 0.29 |
| **B1–B5** | **0.48** | 0.45 | 0.35 | 0.40 | 0.29 |
| B1–B6 | 0.58 | 0.54 | 0.41 | 0.47 | 0.34 |

Reading the tables:

- **The modelling change is worth +0.03 F1 on its own** (arm B 0.34 → 0.37,
  identical scoring). This is the cleanest number in the document: same engine,
  same model, same examples, same evaluator, same gold, and only the
  representation of range-less relations differs. **It alone moves WUKONG from
  level with Vicuna to ahead of it under the benchmark's own, unmodified scoring.**
- **The scoring corrections B1–B5 are nearly neutral between systems.** They add
  +0.02 to every WUKONG arm and +0.01 to Vicuna, and leave Alpaca unchanged. B2
  and B3 lift everyone equally. B4 lifts only the property-modelled arm, the only
  system producing enough year-only dates to be affected. B5 costs between 0.00
  and 0.02 per system: 0.01 for Vicuna and for two of the WUKONG arms, 0.02 for
  Alpaca. B5 does *not* disproportionately hurt the baselines at this granularity,
  which is informative in itself: leakage from verbatim train sentences was a real
  protocol flaw but not a large source of their score.
- **B6 is where the systems separate.** Scoring only gold triples whose subject is
  in the sentence lifts WUKONG by 0.15 and Vicuna by 0.10. That is the expected
  direction: a faithful extractor loses the most to triples it is forbidden to
  invent. It is also why B6 is kept out of the headline, since it is the correction
  most obviously tailored to how WUKONG works.

### 5.4 Reachable-gold view (B1–B6, secondary)

| System | P | R | F1 | Conf. | Subj. hall. | Rel. hall. | Obj. hall. |
|---|---|---|---|---|---|---|---|
| **WUKONG, adjusted modelling** | **0.56** | **0.55** | **0.54** | **1.00** | **0.00** | **0.00** | **0.01** |
| WUKONG, arm B | 0.53 | 0.51 | 0.50 | 1.00 | 0.00 | 0.00 | 0.01 |
| WUKONG, primary | 0.40 | 0.38 | 0.37 | 1.00 | 0.00 | 0.00 | 0.01 |
| Vicuna-13B (2-shot) | 0.49 | 0.47 | 0.46 | 0.85 | 0.07 | 0.13 | 0.17 |
| Alpaca-LoRA-13B (2-shot) | 0.40 | 0.35 | 0.35 | 0.87 | 0.08 | 0.13 | 0.18 |

Per-ontology F1 in this view: WUKONG 0.56 / 0.52 / 0.48 / 0.44 / 0.47 / 0.38 / 0.81
/ 0.66 / 0.39 / 0.65 against Vicuna 0.30 / 0.37 / 0.63 / 0.34 / 0.36 / 0.48 / 0.81 /
0.57 / 0.35 / 0.41, in ontology order 1–10.

Note that Vicuna's subject hallucination falls from 0.17 to 0.07 here. B6 removes
the gold its invented subjects used to match, but its outputs for the surviving
sentences still include invented subjects.

### 5.5 Ceilings

The best macro F1 a faithful, ontology-conforming system could score, from
`text2kg_diagnose.py` against each corrected copy:

| Variant | Reachable gold | Ceiling (all) | Ceiling (verified) |
|---|---|---|---|
| `0_vanilla` | 4,678 / 7,232 (65%) | 0.644 | 0.722 |
| B1–B5 | 4,097 / 5,974 (69%) | 0.685 | 0.781 |
| B1–B6 | 4,097 / 4,411 (93%) | 0.950 | 0.950 |

Under the adjusted protocol WUKONG reaches **57% of the ceiling** (0.39 / 0.685),
against 53% for Vicuna (0.36 / 0.685). Under vanilla scoring, arm B and Vicuna
stood at 53% and 54% of the 0.644 ceiling. The remaining 7% unreachable in B1–B6 are gold objects absent from the sentence:
mostly dates with a specific day that the sentence does not state (§6.2).

### 5.6 Coverage and cost

| Ontology | Sentences | With triples | Triples | Jobs | Failed | Input tok | Output tok | Reasoning tok | Sec |
|---|---|---|---|---|---|---|---|---|---|
| 1_movie | 840 | 503 | 1741 | 1289 | 0 | 1,714,091 | 93,950 | 98,832 | 254 |
| 2_music | 675 | 485 | 1217 | 1002 | 0 | 1,310,601 | 61,345 | 75,967 | 220 |
| 3_sport | 487 | 429 | 888 | 886 | 0 | 1,122,247 | 59,001 | 86,865 | 246 |
| 4_book | 550 | 331 | 723 | 859 | 0 | 1,288,890 | 51,603 | 88,987 | 201 |
| 5_military | 230 | 199 | 364 | 425 | 0 | 498,461 | 24,810 | 34,709 | 93 |
| 6_computer | 230 | 118 | 310 | 276 | 0 | 267,591 | 15,799 | 22,910 | 70 |
| 7_space | 203 | 166 | 236 | 364 | 0 | 381,041 | 20,091 | 16,483 | 70 |
| 8_politics | 214 | 188 | 264 | 394 | 0 | 338,481 | 19,968 | 28,022 | 85 |
| 9_nature | 474 | 303 | 503 | 858 | 0 | 1,109,937 | 39,488 | 72,668 | 187 |
| 10_culture | 159 | 112 | 153 | 246 | 0 | 310,954 | 12,310 | 17,300 | 58 |
| **Total** | **4062** | **2834** | **6399** | **6599** | **0** | **8,342,294** | **398,365** | **542,743** | **1484** |

| | Primary | Arm B | Adjusted modelling |
|---|---|---|---|
| Sentences with triples | 2,509 (62%) | 2,737 (67%) | **2,834 (70%)** |
| Triples emitted | 5,265 | 5,794 | 6,399 |
| Jobs (failed) | 6,709 (0) | 6,872 (0) | 6,599 (0) |
| Wall clock | 25 min | 24 min | 25 min |
| Cost | $2.78 | $2.92 | **$2.94** |

Costs in this table are computed with one formula for all three runs:
$0.20/M input including cache reads, a $0.02/M surcharge on cache writes, and
$1.20/M on output plus reasoning tokens. `benchmark.md` reports $2.81 and $2.95
for the first two runs. The source of that $0.03 gap was not traced, but it is
the same for both runs, so the relative comparison holds either way.

**The property modelling is cost-neutral.** Input tokens rise 8% over arm B,
because entity prompts now carry the property fields. Relationship jobs fall
because there are fewer relationship types, and reasoning tokens fall 15%. Net
cost is +$0.02.

---

## 6. Findings

### 6.1 The representational mismatch was real, and properties largely close it

`benchmark.md` §7.5 argued that WUKONG's weak recall on literal objects was a
representational mismatch, not an extraction failure. This run tests that
directly, because the only change from arm B is the representation.

| Object modelled as | Arm B recall | Adjusted recall |
|---|---|---|
| Typed entity | 0.382 | 0.376 |
| Range-less (`Value` node → **entity property**) | 0.199 | **0.330** |

(Vanilla gold. The range-less bucket grows from 1,730 to 1,853 gold triples
because 3_sport `league` now counts as property-modelled, §2.1.)

**Recall on range-less objects rises by 66%, and the gap to typed entities
shrinks from 0.18 to 0.05.** Recall on typed entities is essentially unchanged,
so the gain is not bought elsewhere. The relations that `benchmark.md` singled
out as the worst cases move the most:

| Ontology | Relation | Gold | Arm B | Adjusted |
|---|---|---|---|---|
| 1_movie | publication_date | 364 | 13 | **140** |
| 3_sport | competition_class | 62 | 0 | **31** |
| 4_book | publication_date | 163 | 13 | **32** |
| 10_culture | inception | 73 | 29 | **40** |
| 3_sport | sports_season_of_league_or_competition | 55 | 1 | **9** |
| 6_computer | developer | 91 | 28 | **36** |
| 2_music | performer | 242 | 114 | **129** |
| 4_book | followed_by | 50 | 0 | 6 |

`1_movie:publication_date` shows it most clearly. The sentence *"Alice's
Wonderland is a 1923 Walt Disney short silent film"* failed in both earlier runs
because `1923` had to be extracted as an entity. Here it is a field on the film,
filled in the same call that extracts the film, and the matches rise tenfold.

### 6.2 Where properties did not help

- **2_music `publication_date` stays flat (17 of 226).** Two causes, neither of
  which the representation can fix. First, 146 of the 226 gold dates carry a specific
  day (`16 September 2008`) that the sentence does not state, so they are
  unreachable. Second, of the reachable year-only dates, 58 received no value at
  all: typically *"a song by Lady Gaga from … the album The Fame (2008)"*, where
  the year is stated for the *album* and the gold attaches it to the song. Not
  transferring the album's year to the song is the faithful reading.
- **The relations whose objects are really entities** (`producer` 20 → 16,
  `record label` 58 → 57, `3_sport:league` 55 → 49) are flat or slightly down.
  This is the cost of the mechanical rule A1a. For an object that is a person or
  a company, a relationship to a typed entity was already the better
  representation, and the rule was applied anyway to avoid per-relation choices.
- **Endpoint type gating is untouched by design**, and it is why 3_sport and
  6_computer still trail Vicuna. The miss decomposition still shows it (328 gold
  triples blocked, led by `3_sport:sport` with 72), though smaller than in arm B
  (493) because the property relations no longer enter that analysis.

### 6.3 A regression that one run cannot explain

2_music falls from 0.43 (arm B) to 0.40 under the adjusted protocol, and 9_nature
from 0.30 to 0.29. The loss in music is almost entirely in **entity-typed**
relations the modelling change did not touch directly: `tracklist` 32 → 17,
`composer` 94 → 86, `genre` 41 → 35. There are two plausible causes, and this
experiment cannot separate them:

1. **Run-to-run variance.** Every configuration here was run once (`benchmark.md`
   §9, RQ7 in the paper).
2. **A real interaction.** Music's entity prompt now carries five property
   fields on `MusicalWork` and `Album`, which may shift how the model allocates
   attention within the same call.

It should be reported as a regression with an unknown cause, not explained away.

### 6.4 Faithfulness is unchanged

Subject hallucination 0.00, object hallucination 0.01, and conformance 1.00 once
B1 is applied: identical to both earlier arms. Degenerate self-loops fall
further, from 29 (arm B) to **17** of 6,399 triples (0.3%). Property values are
checked against their sentence before export (§2.3), which is why emitting 1,589
triples through properties rather than relationships added no hallucination.

---

## 7. Threats to validity

These belong next to the adjusted numbers wherever they are quoted.

- **One instruction was revised after looking at test output.** The first attempt
  at this run worded the multi-value rule (A1b) as a separate sentence after the
  verbatim surface-form rule. On the first ontologies the model resolved the
  contradiction by keeping enumerations verbatim as one value (`oboe, bass
  clarinet, piano and four percussionists`). The run was stopped after five
  ontologies, and the instruction was reworded so that splitting explicitly
  overrides verbatim copying, with a generic example not drawn from the benchmark
  (`"written for violin, cello and piano"` → `violin; cello; piano`, a phrase
  verified absent from every test sentence). The rewording was checked on 15 test
  sentences selected for having multi-valued `instrumentation` gold, and the full
  suite was then re-run from scratch; the numbers here come only from that re-run.
  It is a bug fix to an instruction written for this run, not a tuning step, but
  it was informed by test data and is disclosed as such.
- **B4 was also found by inspecting test output.** The zero-day date convention
  surfaced while examining this run's `publication_date` misses. It is a
  correction to the gold, applied identically to all systems, and §5.3 shows it
  moves only the property arm, by 0.01.
- **The adjusted protocol removes data.** B1–B5 score 3,564 of 4,062 sentences
  and 5,974 of 7,232 gold triples. The removals are all defects documented in
  `benchmark.md`, and the waterfall in §5.3 shows the effect of each. Still, it
  is a different test set from the one the baselines were published on.
- **The modelling change is WUKONG-specific.** A prompt-based baseline has no
  property representation, so there is nothing to adjust for it symmetrically.
  That asymmetry is the point of A1, since the vanilla format was the asymmetric
  part, but it means the adjusted modelling is a claim about WUKONG's native data
  model, not a like-for-like harness change.
- **Single run, single model.** No repetitions, so the ±0.03 differences between
  WUKONG arms on individual ontologies (§6.3) are within what variance could
  produce. The global differences (0.39 vs 0.36 vs 0.36) are larger but also
  unreplicated.
