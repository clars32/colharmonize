# annotate-3 vs annotate-2 on tuning (annotation alone)

| prompt | run | qualifier precision / recall | primary term | term and predicate | pooling F1 | runs agree |
|---|---|---|---|---|---|---|
| annotate-2 | 3 | 81.0% / 68.0% | 72.6% | 66.7% | 78.2% | 84.8% |
| annotate-2 | 4 | 63.3% / 76.0% | 78.6% | 75.0% | 81.9% | 84.8% |
| annotate-3 | 6 | 85.0% / 68.0% | 75.0% | 69.0% | 82.3% | 86.7% |
| annotate-3 | 7 | 90.5% / 76.0% | 77.4% | 73.8% | 81.4% | 86.7% |

annotate-3 minus annotate-2, mean of two runs each, paired bootstrap over studies:

| metric | annotate-2 | annotate-3 | Δ, points | 95% CI |
|---|---|---|---|---|
| qualifier precision | 72.1% | 87.7% | +15.6 | +6.3 to +48.9 |
| qualifier recall | 72.0% | 72.0% | +0.0 | -4.4 to +16.7 |
| term and predicate | 70.8% | 71.4% | +0.6 | -1.4 to +3.1 |
| pooling F1 | 80.0% | 81.8% | +1.8 | -6.6 to +9.3 |
