# Same-model vs cross-model annotation agreement

Outcome: the run of record (Sonnet) is right on primary term and predicate. "Agree": the partner run gives the same primary term and predicate. 95% CIs by paired bootstrap over studies (5,000 resamples).

## tuning: 82 gold columns

| partner | partner's own accuracy | runs agree on | right where they agree | wrong answers flagged | AUC |
|---|---|---|---|---|---|
| Sonnet run 4 (same model) | 76.8% | 87.8% | 77.8% | 38.5% (10 of 26) | 0.69 |
| Opus run 5 (cross model) | 58.5% | 80.5% | 69.7% | 23.1% (6 of 26) | 0.53 |
| both, as a count 0–2 (exploratory) | — | all three agree on 73.2% | 76.7% where all agree | 46.2% | 0.66 |

Run of record (Sonnet run 3) accuracy: 68.3%. AUC, cross minus same: -0.17 (95% CI -0.29 to -0.01). Exploratory, count minus same: -0.04 (95% CI -0.12 to +0.08).

## sealed (post hoc): 119 gold columns

| partner | partner's own accuracy | runs agree on | right where they agree | wrong answers flagged | AUC |
|---|---|---|---|---|---|
| Sonnet run 2 (same model) | 76.5% | 89.9% | 81.3% | 28.6% (8 of 28) | 0.62 |
| Opus run 3 (cross model) | 78.2% | 84.9% | 86.1% | 50.0% (14 of 28) | 0.73 |
| both, as a count 0–2 (exploratory) | — | all three agree on 83.2% | 85.9% where all agree | 50.0% | 0.72 |

Run of record (Sonnet run 1) accuracy: 76.5%. AUC, cross minus same: +0.11 (95% CI +0.04 to +0.18). Exploratory, count minus same: +0.10 (95% CI +0.04 to +0.17).

