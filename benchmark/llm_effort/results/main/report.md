# Results: suite `main`

100 documents, judged by `gpt-6.1-sol` at `low` effort. F1 is shown with its 95% bootstrap interval over chunks. Precision counts correct and field_error items as valid, and field accuracy is the share of valid items with correct field values.

| Setting | Entity P | Entity R | Entity F1 | Entity fields | Rel. P | Rel. R | Rel. F1 | Rel. fields | Extraction cost | Reasoning tokens | Failed jobs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `claude-haiku-5-5@low` | 98.3% | 60.3% | 74.8% [72.8%, 76.7%] | 93.6% | 98.7% | 16.4% | 28.1% [24.7%, 31.7%] | 94.8% | $0.256 | 271,934 | 0 |
| `claude-haiku-5-5@none` | 96.5% | 53.3% | 68.7% [66.1%, 71.1%] | 83.1% | 92.5% | 17.8% | 29.9% [25.9%, 33.9%] | 76.2% | $0.116 | 0 | 0 |
| `gpt-5.6-luna@low` | 95.6% | 71.1% | 81.6% [80.0%, 83.0%] | 87.1% | 96.1% | 28.9% | 44.4% [41.0%, 47.9%] | 95.5% | $0.327 | 101,396 | 0 |
| `gpt-5.6-luna@none` | 88.4% | 70.1% | 78.2% [76.6%, 79.7%] | 82.0% | 82.8% | 41.5% | 55.3% [52.0%, 58.6%] | 75.6% | $0.235 | 0 | 0 |
| `gpt-6-luna@low` | 96.3% | 71.3% | 82.0% [80.4%, 83.5%] | 91.4% | 96.5% | 26.4% | 41.5% [38.0%, 45.2%] | 92.8% | $0.132 | 87,528 | 0 |
| `gpt-6-luna@none` | 91.2% | 72.7% | 80.9% [79.1%, 82.5%] | 87.6% | 85.9% | 39.7% | 54.3% [51.5%, 57.1%] | 74.7% | $0.106 | 0 | 2 |

Judgments that failed or couldn't be parsed: 0 for entities, 0 for relationships (their chunks are left out of every setting's scores).
