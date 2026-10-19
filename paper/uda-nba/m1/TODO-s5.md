# To do: everything on schema s5, and one gold copy for question answering

Written on 2026-10-19 for Juan (or his Claude). Delete this file when it is done.

## Decided (Sebastián and Juan, Oct 19)

1. **Every NBA result uses s5.** s4 is the full NBA schema, written before any result. s5 is s4 plus one field added
   after seeing s4's results: `Player.current_team`, read once from the player's own article. The paper says so.
2. **The three schema-based tools are rebuilt from s5 too** (Neo4j-GraphRAG, LlamaIndex, OntoGPT), so they get the same
   schema as Wukong. Today they are built from `workspace-v1`, which is s4.
3. **Question answering (M1) is scored against Bench-U `f2da981` for every system.**
   - It is the latest version, and its gold tables are the ones in `uda-nba-share.zip`, which E1 and X6 use.
   - The rows scored on the iMac used an older copy, whose city answers differ.

## Cost: about $7–8 in total

| What | Runs | Cost |
|---|---|---|
| Rebuild Neo4j-GraphRAG, LlamaIndex and OntoGPT with s5 | one build each | ~$2–3, ~$2–3, ~$1–1.5 |
| Their question-answering runs | one each, 101 questions | ~$0.20 each |
| Wukong's question-answering run on s5 | one | ~$0.15 |
| LLM alone, LightRAG (4 modes), GraphRAG | not re-run, only re-scored | $0 |

The build costs are estimated from the output tokens in the report; input tokens were not recorded. No system needs
three runs. Wukong's s5 graphs already exist (`x6-s5-r1..r3`); extra Wukong question-answering runs (r2, r3) are
optional, at ~$0.15 each.

## Steps (from `paper/uda-nba/`)

### A. Rebuild the three graphs with s5

1. `baselines/neo4j_graphrag_build.py` and `baselines/llamaindex_build.py` read the schema from a hard-coded
   `KM_PATH = HERE / 'workspace-v1' / 'knowledge_model.json'`. Add a `--schema PATH` option (default unchanged), as
   `baselines/ontogpt_build.py` already has.
2. Build into **new** folders, so that the s4 graphs stay as they are:

   ```
   envs/neo4j-graphrag/bin/python baselines/neo4j_graphrag_build.py --data data/docs \
       --schema workspace-x6-s5/knowledge_model.json --out runs/neo4j-graphrag-s5-full
   envs/llamaindex/bin/python baselines/llamaindex_build.py --data data/docs \
       --schema workspace-x6-s5/knowledge_model.json --out runs/llamaindex-s5-full
   envs/ontogpt/bin/python baselines/ontogpt_build.py --data data/docs \
       --schema workspace-x6-s5/knowledge_model.json --out runs/ontogpt-s5-full
   ```

3. Check each tool's `mapping.md` to see where `current_team` landed. It should become a Player property.
   - Neo4j-GraphRAG and LlamaIndex have no slot for "read at document level", so for them it is extracted like any
     other field (from chunks).
   - In OntoGPT it is a slot of the Player root class, which reads the whole article.

### B. NBA quality table (paper Section 4.3)

4. In `nba_quality.py`, point `TYPED` to the `-s5-full` folders and run it again.
5. Update `report/nba_quality_table.tex` and the quality table in the paper.

### C. Question answering (M1, paper Section 4.4), in `m1/`

6. **Environment:** use the M1 harness environment (`envs/m1-harness`: Python 3.12, kuzu 0.11.3, duckdb 1.3.2). Set
   `M1_ROOT` to the M1 folder, `UDA_BENCH` to a Bench-U checkout at `f2da981`, and `OPENAI_API_KEY`.
7. **Check the gold:** run `python oracle.py`. 101 questions should be included, and each should score 1.000. If the
   count changes, note which questions and why.
8. **Wukong.** `sys_wukong.py` is hard-wired to s4: `RUN = SHARE / 'wukong-e1-r1'`, `DB = WORK / 'kuzu' /
   'wukong.kz'`.
   - Add `--run DIR` and `--name NAME` (defaults unchanged), and use `NAME` for the Kuzu database, the answers folder,
     the usage log (`answer(..., usage=NAME)`) and the saved system prompt.
   - The agent's schema already comes from `RUN / 'knowledge_model.json'`.
   - Run: `python sys_wukong.py --run <runs/x6-s5-r1> --name wukong_s5 --reload`.
9. **The three tools.** In `sys_typed.py`, both the agent's schema (`KM = ... 'workspace-v1' ...`) and the graph
   folders (`GRAPHS`) point to s4.
   - Add s5 entries that read `workspace-x6-s5/knowledge_model.json` and the `-s5-full` folders, named `neo4j_s5`,
     `llamaindex_s5` and `ontogpt_s5`.
   - Then run each with `--reload`.
10. **Names without hyphens:** `score.py` finds a system's usage log as `system.split("-")[0]`, so a name like
    `wukong-s5` would read the s4 log.
11. **Re-score and compare:**
    - run `python score.py` (all systems, against `f2da981`), then `python table.py`;
    - then `python paired.py --base wukong_s5`, for the per-question comparison: mean difference with its 95%
      confidence interval, and wins, ties and losses against each system.
12. **Commit to `paper-experiments`** (gitmoji `⚗️ feat(paper): ...`), in the layout of `results/`:
    - the new answers, scores and usage logs;
    - `m1_table.*`;
    - `README.md`, with the table on s5 and `f2da981`. Keep the s4 rows as labelled extra lines, and update the
      caveat about the two gold copies.

### D. Paper (Overleaf) and plan

13. **Setup (Section 4.1):** say that every NBA system receives s5, and that s5 added the current team after seeing
    s4's results.
14. **Section 4.3:** use the regenerated quality table.
15. **Section 4.4:** fill in `[TABLE: ...]` and `[RESULTS: ...]`, and replace the ToDo about which Wukong graph is
    used.
16. **Plan:** in `experiments-plan.tex`, "What is missing", mark the M1 and X6 rows done.
