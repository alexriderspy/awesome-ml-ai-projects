Test split: 96 tickets, 12 per category.

| System | Accuracy | Macro-F1 | Invalid | p50 latency | p95 latency | Cost / 1k tickets |
|---|---|---|---|---|---|---|
| TF-IDF + logistic regression | 0.875 | 0.878 | 0 | 1 ms | 2 ms | $0.0000 |
| deepseek-flash zero-shot | 0.906 | 0.907 | 0 | 963 ms | 3136 ms | $0.1833 |
