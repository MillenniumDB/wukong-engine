# M1: structured questions on UDA-Bench NBA (Section 4.4 and Appendix C of the paper)

Does a graph built from an extraction schema answer UDA-Bench's structured NBA questions better than RAG systems
answering the way they are meant to? The graphs are those of the paper's NBA experiments: Wukong with the NBA schema
(`workspace-x6-s4`, three builds), the schema-based extractors built from the same schema (three builds each), and
the LightRAG and GraphRAG full builds (one each). Design and fairness rules: Section 4.4 of the paper.

## Results (macro F1 per question, UDA-Bench evaluator, deterministic mode)

| System | Select | Filter | Agg | Join | Mixed | All | Runs | Spend per run |
|---|---|---|---|---|---|---|---|---|
| LLM alone (floor) | 0.13 | 0.27 | 0.33 | 0.10 | 0.30 | **0.25** | 1 | $0.21 |
| LightRAG local | 0.14 | 0.08 | 0.33 | 0.05 | 0.20 | **0.13** | 1 | |
| LightRAG global | 0.10 | 0.15 | 0.39 | 0.02 | 0.16 | **0.16** | 1 | |
| LightRAG hybrid | 0.11 | 0.13 | 0.41 | 0.01 | 0.19 | **0.15** | 1 | |
| LightRAG mix | 0.13 | 0.14 | 0.42 | 0.06 | 0.23 | **0.18** | 1 | $2.69 (4 modes) |
| LightRAG, best mode per type | 0.14 | 0.15 | 0.42 | 0.06 | 0.23 | **0.18** | 1 | |
| GraphRAG local | 0.09 | 0.07 | 0.21 | 0.03 | 0.15 | **0.10** | 1 | ~$0.29 |
| Neo4j-GraphRAG + Cypher agent | 0.06 | 0.12 | 0.40 | 0.02 | 0.14 | **0.13** ±0.02 | 3 | $0.21 |
| LlamaIndex + Cypher agent | 0.06 | 0.07 | 0.41 | 0.02 | 0.08 | **0.10** ±0.01 | 3 | $0.21 |
| OntoGPT + Cypher agent | 0.65 | 0.33 | 0.37 | 0.21 | 0.32 | **0.34** ±0.00 | 3 | $0.17 |
| Wukong + Cypher agent | 0.51 | 0.42 | 0.80 | 0.29 | 0.41 | **0.44** ±0.01 | 3 | $0.12 |

Systems with three runs: the mean over the runs (one build each), with half the range of the overall score as ±.
Questions: 101 of the 132 (Select 8, Filter 49, Agg 10, Join 13, Mixed 21). Excluded: 10 whose gold SQL fails on the
benchmark's own gold tables (unscorable), 21 whose gold answer is empty (F1 undefined). The oracle (`oracle.py`:
the gold answer pushed through the same conversion) scores 1.000 on every included question. Every system is scored
against the same gold copy, Bench-U (BIT-DataLab/Bench-U) at `f2da981`.

Paired, per question (`paired.py --base wukong_s4`; for three-run systems each question's score is the mean over
the runs; bootstrap 95% CI, 5,000 resamples), Wukong minus: OntoGPT +0.10 [+0.04, +0.17], wins 65 / ties 8 /
losses 28; LLM alone +0.20 [+0.14, +0.26], 74/8/19; LightRAG mix +0.27 [+0.21, +0.32], 88/5/8; Neo4j-GraphRAG +0.31
[+0.27, +0.35], 93/5/3; GraphRAG local +0.35 [+0.29, +0.41], 93/3/5; LlamaIndex +0.35 [+0.30, +0.40], 94/3/4
(all in `results/paired.txt`).

Why: the RAG systems retrieve a few chunks, so they return a median of 2–7% of the rows a set question needs
(GraphRAG local answers 32 of 101 with no rows); Wukong returns at least half the gold rows on 83% of questions
(run 1). The LLM alone answers from memory (NBA is public knowledge), so it beats both RAG systems; on a private
corpus it would not. About a third of its 15–20 wins over Wukong (per run) are questions about team owners: the
schema's `Owns` has no current/former flag (unlike the player's `current_team`), so the agent also returns past
owners.

## Schema-based extractors + Cypher

The graphs that Neo4j's `neo4j-graphrag`, LlamaIndex's `SchemaLLMPathExtractor` and OntoGPT's SPIRES built from the
same extraction schema as Wukong (`../baselines/*_build.py --schema ../workspace-x6-s4/knowledge_model.json`, three
builds each, `runs/<tool>-s4-r{1,2,3}`), queried by Wukong's agent (`sys_typed.py`): same prompt, same schema text,
same 4 attempts, loaded into Kuzu the same way (one table per type, every value a string, missing or empty values
null). Only the link from entities to articles differs, as each tool records it: OntoGPT's root object per article is
its subject (`ExtractedFrom`, as Wukong's); neo4j-graphrag and LlamaIndex record only the chunk an entity came from
(`MentionedIn`, not necessarily the subject; OntoGPT gets it too). Properties a tool filled outside the schema are
kept and listed. Edges whose endpoint types do not match the relationship type are not loaded (LlamaIndex 40–62,
OntoGPT 5–9 per build).

What breaks them: values not in a queryable form (dates as "February 2, 1994", "808988 (2023)", "367.9square
miles", "Not drafted"), so the agent's casts fail: no rows on 18–31 questions per run, against 4–5 for Wukong; no
article subject in neo4j-graphrag and LlamaIndex, so set questions return every mentioned player; and duplicate
nodes. OntoGPT, with subjects and one object per article, is closest to Wukong and better on Select (0.65 vs 0.51).

Run with the harness environment (`$M1_ROOT/envs/harness`: kuzu 0.11.3, duckdb 1.3.2, Python 3.12). Every agent is told the
same date (`--today 2026-10-14`). The first neo4j-graphrag build lost four articles' calls to a sleep of the machine;
those articles were re-extracted before its agent ran (its other failed chunk is a malformed model reply, kept as the
tool's behaviour). Two agents were restarted after a sleep (Wukong run 2, neo4j-graphrag run 2) and resumed; the
interrupted questions' calls stay in their usage logs.

## Fairness

- One model and effort everywhere (`gpt-5.6-luna`, low), as in the builds.
- The SQL is never shown to a system: `translate.py` turns each query into a plain question with per-column meanings
  (no column names), once, shared by all. Every system gets the same question, the same answer instruction
  (`common.answer_instruction`: neutral keys `col1..`, `name_<entity>`), the same scope sentence (articles are about
  players, teams, cities, owners) and the same closed vocabulary (position: Frontcourt/Backcourt).
- RAG systems answer natively, at default parameters, with the instruction in their own slot for it (LightRAG
  `QueryParam.user_prompt`, GraphRAG `response_type`); every LightRAG mode is reported, and "best mode per type" is
  picked with the gold answers (an upper bound for LightRAG). No Cypher is run against the RAG graphs.
- GraphRAG global search is not reported: with dynamic community selection it made 8,790 calls ($3.60) for 3
  questions, about $120 for M1; at its static default it maps ~4,400 reports per question (~$75).
- Wukong: the NBA schema's three builds (`../runs/x6-s4-r{1,2,3}`), loaded into Kùzu with every value a string; an
  agent writes Cypher from the graph schema, up to 4 attempts (`sys_wukong.py --run ... --name wukong_s4_rN`).
  Wukong's schema was written for this domain; that is how an extraction schema is used, and the paper says so. The
  schema-based extractors receive the same schema, translated into their own formats.
- Scoring: rows → prediction CSV → UDA-Bench's `run_eval` (`--llm-provider none`), the same code for all. Entity
  names are mapped to document ids with one shared table (`common.NameIndex`: gold name and article title; exact,
  word-subset, or formal first name such as Timothy/Tim); an unmatched name is a wrong row. Nicknames that are not
  prefixes (Earvin/Magic Johnson) stay unmatched for every system. Answers with no rows (every query
  failed, or a reply that cannot be parsed) count as empty answers.

## Files

- `common.py` (shared rules), `translate.py`, `sys_floor.py`, `sys_wukong.py`, `sys_typed.py`, `sys_lightrag.py`,
  `sys_graphrag.py`, `score.py`, `table.py`, `paired.py`, `oracle.py`, `run_m1.sh` (the first run, with a budget
  watchdog).
- `results/`: `questions.{json,md}`, `queries.json` (uids, inclusion, oracle F1), `answers/<system>/`,
  `scores/<system>.json`, `usage/`, `m1_table.{md,tex}`, `paired.txt`, `<system>_system_prompt.txt`, `excluded/`
  (GraphRAG global pilot). Three-run systems are `<name>_s4_r{1,2,3}`. Answers larger than 5 MB (14
  neo4j-graphrag answers, up to millions of rows from a join over every mentioned player) keep their trace, their row
  count (`rows_total`) and their first 1,000 rows; their scores were computed on all the rows. The evaluator's per-question working folders are not included.
- Environments (`$M1_ROOT/envs/`): `harness` (Python 3.12, kuzu 0.11.3), `lightrag` and `graphrag` with
  the exact pins of `versions.txt`.
