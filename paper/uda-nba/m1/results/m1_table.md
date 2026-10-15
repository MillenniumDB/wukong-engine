| System | Select | Filter | Agg | Join | Mixed | All | n |
|---|---|---|---|---|---|---|---|
| LLM alone (floor) | 0.13 | 0.27 | 0.33 | 0.11 | 0.31 | **0.25** | 101 |
| LightRAG local | 0.14 | 0.08 | 0.33 | 0.05 | 0.20 | **0.13** | 101 |
| LightRAG global | 0.10 | 0.16 | 0.39 | 0.02 | 0.16 | **0.16** | 101 |
| LightRAG hybrid | 0.11 | 0.13 | 0.41 | 0.02 | 0.19 | **0.16** | 101 |
| LightRAG mix | 0.13 | 0.15 | 0.42 | 0.06 | 0.23 | **0.18** | 101 |
| LightRAG best mode per type (Select: local, Filter: global, Agg: mix, Join: mix, Mixed: mix) | 0.14 | 0.16 | 0.42 | 0.06 | 0.23 | **0.18** | 101 |
| GraphRAG local | 0.09 | 0.07 | 0.21 | 0.03 | 0.15 | **0.10** | 101 |
| Neo4j-GraphRAG + Cypher agent | 0.05 | 0.13 | 0.57 | 0.02 | 0.17 | **0.16** | 101 |
| LlamaIndex + Cypher agent | 0.04 | 0.06 | 0.36 | 0.01 | 0.04 | **0.08** | 101 |
| OntoGPT + Cypher agent | 0.64 | 0.29 | 0.49 | 0.19 | 0.32 | **0.33** | 101 |
| Wukong + Cypher agent | 0.49 | 0.42 | 0.90 | 0.28 | 0.36 | **0.44** | 101 |

Spend by log (USD): floor 0.21, graphrag 3.89, lightrag 2.69, llamaindex 0.21, neo4j 0.21, ontogpt 0.17, translate 0.02, wukong 0.14; total 7.55
