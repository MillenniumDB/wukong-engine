# Results: suite `smoke`

3 documents, judged by `gpt-6.1-sol` at `low` effort. F1 is shown with its 95% bootstrap interval over chunks. Precision counts correct and field_error items as valid, and field accuracy is the share of valid items with correct field values.

| Setting | Entity P | Entity R | Entity F1 | Entity fields | Rel. P | Rel. R | Rel. F1 | Rel. fields | Extraction cost | Reasoning tokens | Failed jobs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `claude-haiku-5-5@low` | 91.4% | 76.2% | 83.1% [71.4%, 95.7%] | 96.9% | 100.0% | 26.1% | 41.4% [25.0%, 54.5%] | 100.0% | $0.009 | 8,142 | 0 |
| `claude-haiku-5-5@none` | 85.3% | 69.0% | 76.3% [74.1%, 81.8%] | 79.3% | 95.7% | 31.9% | 47.8% [35.3%, 57.1%] | 86.4% | $0.004 | 0 | 0 |
| `gpt-5.6-luna@low` | 87.5% | 83.3% | 85.4% [78.6%, 95.7%] | 85.7% | 96.3% | 37.7% | 54.2% [48.5%, 60.9%] | 84.6% | $0.009 | 2,833 | 0 |
| `gpt-5.6-luna@none` | 77.8% | 83.3% | 80.5% [70.6%, 87.0%] | 82.9% | 91.9% | 49.3% | 64.2% [55.0%, 76.2%] | 79.4% | $0.007 | 0 | 0 |
| `gpt-6-luna@low` | 92.3% | 85.7% | 88.9% [78.6%, 95.7%] | 94.4% | 100.0% | 33.3% | 50.0% [43.8%, 54.5%] | 100.0% | $0.004 | 2,513 | 0 |
| `gpt-6-luna@none` | 90.2% | 88.1% | 89.2% [82.8%, 100.0%] | 97.3% | 97.0% | 46.4% | 62.7% [55.0%, 76.9%] | 81.2% | $0.003 | 0 | 0 |

Judgments that failed or couldn't be parsed: 0 for entities, 0 for relationships (their chunks are left out of every setting's scores).
