# M1: structured questions on UDA-Bench NBA (midpoint for E2)

Does a graph built from an extraction schema answer UDA-Bench's structured NBA questions better than RAG systems
answering the way they are meant to? Run on 2026-10-14 on Juan's graphs (`uda-nba-share`: Wukong E1 run 1 = schema
s4, LightRAG and GraphRAG full builds); nothing was rebuilt. Design and fairness rules: `overleaf/outline-v2.tex`,
box "M1".

## Results (macro F1 per question, UDA-Bench evaluator, deterministic mode)

| System | Select | Filter | Agg | Join | Mixed | All | Spend |
|---|---|---|---|---|---|---|---|
| LLM alone (floor) | 0.13 | 0.27 | 0.33 | 0.11 | 0.31 | **0.25** | $0.21 |
| LightRAG local | 0.14 | 0.08 | 0.33 | 0.05 | 0.20 | **0.13** | |
| LightRAG global | 0.10 | 0.16 | 0.39 | 0.02 | 0.16 | **0.16** | |
| LightRAG hybrid | 0.11 | 0.13 | 0.41 | 0.02 | 0.19 | **0.16** | |
| LightRAG mix | 0.13 | 0.15 | 0.42 | 0.06 | 0.23 | **0.18** | $2.69 (4 modes) |
| LightRAG, best mode per type | 0.14 | 0.16 | 0.42 | 0.06 | 0.23 | **0.18** | |
| GraphRAG local | 0.09 | 0.07 | 0.21 | 0.03 | 0.15 | **0.10** | ~$0.29 |
| Wukong + Cypher agent | 0.49 | 0.42 | 0.90 | 0.28 | 0.36 | **0.44** | $0.14 |

Questions: 101 of the 132 (Select 8, Filter 49, Agg 10, Join 13, Mixed 21). Excluded: 10 whose gold SQL fails on the
benchmark's own gold tables (unscorable), 21 whose gold answer is empty (F1 undefined). The oracle (`oracle.py`:
the gold answer pushed through the same conversion) scores 1.000 on every included question.

Paired, per question (bootstrap 95% CI, 5,000 resamples): Wukong − LightRAG mix +0.26 [+0.21, +0.32], wins 86 /
ties 8 / losses 7; Wukong − GraphRAG local +0.35 [+0.29, +0.41], 89/7/5; Wukong − LLM alone +0.19 [+0.12, +0.25],
76/8/17.

Why: the RAG systems retrieve a few chunks, so they return a median of 2–7% of the rows a set question needs
(GraphRAG local answers 32 of 101 with no rows); Wukong returns a full-size answer on 83% of questions. The LLM alone
answers from memory (NBA is public knowledge), so it beats both RAG systems; on a private corpus it would not. Its
17 wins over Wukong are mostly team questions about "the owner": the s4 schema's `Owns` has no current/former flag
(unlike `PlaysFor.tenure`), so the agent joins every past owner (127 rows for 25). Wukong's two Mixed answers with
1,000+ rows come from the agent dropping the article-subject restriction.

Calls and tokens (all of M1, pilots included): Wukong 187 calls, 0.19M input; LightRAG 804 calls, 12.1M input (4
modes); GraphRAG 9,015 calls, 13.5M input, of which 8,790 calls and $3.60 were the global-search pilot (3 questions).
Total M1 spend $6.95 (cap $15).

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
- Wukong: E1's s4 graph (written before any result; s5 was revised after seeing s4), loaded into Kùzu with every
  value a string; an agent writes Cypher from the graph schema, up to 4 attempts. Wukong's schema was written for this
  domain; that is how an extraction schema is used, and the paper says so.
- Scoring: rows → prediction CSV → UDA-Bench's `run_eval` (`--llm-provider none`), the same code for all. Entity
  names are mapped to document ids with one shared table (`common.NameIndex`: gold name and article title; exact,
  word-subset, or formal first name such as Timothy/Tim); an unmatched name is a wrong row. Nicknames that are not
  prefixes (Earvin/Magic Johnson) stay unmatched for every system. Parse failures count as empty answers (Wukong 2,
  others 0).

## Files

- `common.py` (shared rules), `translate.py`, `sys_floor.py`, `sys_wukong.py`, `sys_lightrag.py`, `sys_graphrag.py`,
  `score.py`, `table.py`, `oracle.py`, `run_m1.sh` (the run, with a budget watchdog).
- `results/`: `questions.{json,md}`, `queries.json` (uids, inclusion, oracle F1), `answers/<system>/`,
  `scores/<system>.json`, `usage/`, `m1_table.{md,tex}`, `wukong_system_prompt.txt`, `excluded/` (GraphRAG global
  pilot). The evaluator's per-question folders are archived in `WWW-Wukong/m1-input/m1-evaluator-dirs.tar.gz`.
- Environments (iMac, `~/wukong-runs/m1/envs/`): `harness` (Python 3.12, kuzu 0.11.3), `lightrag` and `graphrag` with
  the exact pins of the share's `versions.txt`.
