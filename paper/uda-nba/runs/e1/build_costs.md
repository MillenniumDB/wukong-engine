# Cost of building each graph over the 216 NBA documents (Table 7 of the paper)

| System | LLM calls | Input tokens | Output tokens | Wall time |
|---|---:|---:|---:|---:|
| Wukong | 4,447 | 6.4M | 1.1M | 18 min |
| LightRAG | 6,341 | 17.3M | 7.8M | 92 min |
| GraphRAG | 24,965 | 35.3M | 15.1M | 101 min |
| KGGen | 26,025 | 13.8M | 1.7M | 228 min |

- Wukong: mean of its three runs with the NBA schema of the paper (`../x6/summary.csv`, column `full`); the wall
  time leaves out the run during which the machine slept.
- KGGen: `report.json`, key `KGGen`, field `usage`. Its calls are 440 extraction calls (14 min) and 25,585
  deduplication calls (214 min), plus 0.1M embedding tokens; it ran alone.
- LightRAG and GraphRAG: from their build logs, which are not in the repository. GraphRAG's calls are 3,362 graph
  extractions, 16,511 description summaries and 5,092 community reports; it also used 8.2M embedding tokens.

Runs shared the machine with other runs, so wall times are indicative.
