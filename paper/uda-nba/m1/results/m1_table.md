| System | Select | Filter | Agg | Join | Mixed | All | n | runs |
|---|---|---|---|---|---|---|---|---|
| LLM alone (floor) | 0.13 | 0.27 | 0.33 | 0.10 | 0.30 | **0.25** | 101 | 1 |
| LightRAG local | 0.14 | 0.08 | 0.33 | 0.05 | 0.20 | **0.13** | 101 | 1 |
| LightRAG global | 0.10 | 0.15 | 0.39 | 0.02 | 0.16 | **0.16** | 101 | 1 |
| LightRAG hybrid | 0.11 | 0.13 | 0.41 | 0.01 | 0.19 | **0.15** | 101 | 1 |
| LightRAG mix | 0.13 | 0.14 | 0.42 | 0.06 | 0.23 | **0.18** | 101 | 1 |
| LightRAG best mode per type (Select: local, Filter: global, Agg: mix, Join: mix, Mixed: mix) | 0.14 | 0.15 | 0.42 | 0.06 | 0.23 | **0.18** | 101 | 1 |
| GraphRAG local | 0.09 | 0.07 | 0.21 | 0.03 | 0.15 | **0.10** | 101 | 1 |
| Neo4j-GraphRAG + Cypher agent | 0.06 | 0.12 | 0.40 | 0.02 | 0.14 | **0.13** ±0.02 | 101 | 3 |
| LlamaIndex + Cypher agent | 0.06 | 0.07 | 0.41 | 0.02 | 0.08 | **0.10** ±0.01 | 101 | 3 |
| OntoGPT + Cypher agent | 0.65 | 0.33 | 0.37 | 0.21 | 0.32 | **0.34** ±0.00 | 101 | 3 |
| Wukong + Cypher agent | 0.51 | 0.42 | 0.80 | 0.29 | 0.41 | **0.44** ±0.01 | 101 | 3 |

Spend by log (USD): floor 0.21, graphrag 3.89, lightrag 2.69, llamaindex_s4_r1 0.21, llamaindex_s4_r2 0.21, llamaindex_s4_r3 0.22, neo4j_s4_r1 0.21, neo4j_s4_r2 0.21, neo4j_s4_r3 0.21, ontogpt_s4_r1 0.17, ontogpt_s4_r2 0.17, ontogpt_s4_r3 0.17, translate 0.02, wukong_s4_r1 0.12, wukong_s4_r2 0.13, wukong_s4_r3 0.12; total 8.97
