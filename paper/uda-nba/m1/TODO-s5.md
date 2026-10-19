# To do: question answering (M1) with Wukong on schema s5, and one gold copy for every system

Written on 2026-10-19 for Juan (or his Claude). Delete this file when it is done.

## Why

- **Wrong schema.** M1 is the question-answering experiment of the paper's Section 4.4 ("Downstream tasks", label
  `sec:downstream`). Its Wukong row was run on the **s4** graph, E1 run 1 in `uda-nba-share.zip`
  (`wukong-e1-r1`). Every other NBA result in the paper now uses **s5** (commit `908d19c`).
  - **s4** is the full NBA schema, written before any result.
  - **s5** is s4 plus one field added after seeing s4's results: `Player.current_team`, read once from the player's
    own article.
- **The decision.** Sebastián and Juan decided on Oct 19 to re-run M1's Wukong row on s5.
- **Two gold copies.** The M1 table also mixes two copies of the UDA-Bench gold tables.
  - The rows scored on the iMac (LLM alone, LightRAG, GraphRAG, Wukong) used an older clone.
  - Juan's rows (Neo4j, LlamaIndex, OntoGPT) used Bench-U `f2da981`.
  - `f2da981` is the latest version. Its `Query/Player/city.csv` is identical to the zip's `data/ground_truth/city.csv`,
    which E1 and X6 use.
- **The fix.** Score every system against Bench-U `f2da981`.

## Steps

1. **Environment.** Use the M1 harness environment you used for the schema-based extractors (`envs/m1-harness`:
   Python 3.12, kuzu 0.11.3, duckdb 1.3.2). Set these variables:
   - `M1_ROOT` to your M1 folder (it holds `work/`; the committed `results/` has `questions.json`, `queries.json`
     and `titles.json`);
   - `UDA_BENCH` to a Bench-U checkout at `f2da981`;
   - `OPENAI_API_KEY`.
2. **Check the gold.** Run `python oracle.py`. Every included question should still score 1.000, and 101 questions
   should be included. If the count changes, note which questions and why.
3. **Point `sys_wukong.py` at an s5 run.** Today it is hard-wired to s4: `RUN = SHARE / 'wukong-e1-r1'` and
   `DB = WORK / 'kuzu' / 'wukong.kz'`.
   - Add `--run DIR` (default unchanged) and `--name NAME` (default `wukong`).
   - Use `NAME` for the Kuzu database (`WORK / 'kuzu' / f'{NAME}.kz'`), the answers folder (`WORK / 'answers' /
     NAME`), the usage log (pass `usage=NAME` to `answer()`) and the saved system prompt.
   - The schema shown to the agent already comes from `RUN / 'knowledge_model.json'`, so the s5 run gives it
     `current_team`.
   - **Use a name without a hyphen**, e.g. `wukong_s5`. `score.py` finds the usage log as
     `system.split("-")[0]`, so `wukong-s5` would read the s4 log.
4. **Run it.** For example:
   `python sys_wukong.py --run <your x6-s5-r1 workspace> --name wukong_s5 --reload`
   - The workspace needs `knowledge_model.json` and `exports/neo4j/`.
   - It costs about $0.15: the s4 run made 187 calls in total.
   - Optional: also r2 and r3 (`wukong_s5_r2`, `wukong_s5_r3`) for a mean, as in the NBA quality table.
5. **Re-score and rebuild the table.** Run `python score.py` (all systems), then `python table.py`. This writes
   `work/m1_table.{md,tex}`.
   Then run `python paired.py --base wukong_s5` for the per-question comparison: the mean difference with its
   95% confidence interval, and wins, ties and losses against each system. The README and the paper quote these.
6. **Commit to `paper-experiments`** (gitmoji `⚗️ feat(paper): ...`), in the same layout as the existing results in
   `results/`:
   - the new answers, scores and usage log;
   - the updated `m1_table.*`;
   - `README.md`, with the table now on s5 and on `f2da981`. Keep the s4 row as a labelled extra line, and update the
     caveat paragraph about the two gold copies.
7. **Paper (Overleaf), Section 4.4:**
   - fill in `[TABLE: ...]` and `[RESULTS: ...]`;
   - replace the ToDo asking which Wukong graph is used: say it is s5, and that s5 was revised after seeing s4's
     results, as the other NBA sections should also say.
8. **Plan (Overleaf):** in `experiments-plan.tex`, "What is missing", mark the M1 row done.

## Open question for Juan (do not change without agreeing)

Neo4j-GraphRAG, LlamaIndex and OntoGPT were built from `workspace-v1`, which is s4 (no `current_team` field). With
Wukong on s5, Wukong gets a field the other tools never received. This affects both the NBA quality table and M1.
Either give them s5 too, or say in the paper that they received the schema before the revision.
