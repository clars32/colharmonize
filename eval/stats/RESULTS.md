# Statistics: what holds up and what is noise

Handoff task 8, 2026-10-09. Every number is recomputed from the recorded
prediction files and `scored.parquet` by `stats.py`. Nothing was re-run, and
no sealed headline changes. The full tables are in `out/stats.md`.
`pred/tuning_reconcile_run{1..4}.tsv` are the four tuning reconcile runs,
rebuilt in memory by `eval/tuning/score_reconcile_runs.py`. Runs 1 and 2
match the recorded partitions exactly.

## Method

- **Pooling intervals** come from a bootstrap over studies, the unit a
  corpus samples, with 10,000 resamples. A bootstrap over columns is
  reported beside it. Pairs that share a column or study are not
  independent, so a bootstrap over pairs would be far too narrow.
- **Comparisons are paired:** both systems are scored on the same
  resamples.
- **Confidence signals** are scored per gold column:
  - AUC: the chance a right column scores higher than a wrong one.
  - Its 95% CI comes from a bootstrap over columns, and its p-value from
    permuting the labels.
  - Cohen's d is reported beside it.
- **Pooling correctness** for a column is split two ways:
  - no false mates: everything it was pooled with belongs with it
  - no missed mates: everything that belongs with it was pooled with it

## 1. Intervals are wide; the baselines are still clearly beaten

| pooling F1 (95% CI over studies) | tuning, 13 studies | sealed, 16 studies |
|---|---|---|
| colharmonize final | 82.6% (66.2–94.6) | 83.0% (75.3–91.6) |
| annotation alone | 78.2% (58.3–92.7) | 84.7% (75.2–92.6) |
| best baseline | 67.6% (45.6–80.7), iteration 2 | 53.8% (33.5–75.9), identical names |

| paired ΔF1, final minus … (95% CI over studies) | tuning | sealed |
|---|---|---|
| identical names | — | +29.2 (+12.3 to +46.0) |
| GEOmend `propose()` | +25.9 (+6.1 to +54.3) | +37.1 (+23.0 to +54.3) |
| iteration 2 | +14.9 (+2.6 to +31.9) | — |
| annotation alone | +4.3 (−11.9 to +18.5) | −1.8 (−5.7 to +3.9) |

- **Beating every baseline holds** on both corpora: every interval excludes
  zero.
- **"Generalization held" (82.6% tuning vs 83.0% sealed) is consistent with
  the data, but it isn't a measured equality.** The tuning interval spans 28
  points.
- **Reconciliation's effect is unresolved on both corpora.** The tuning gain
  (+4.3) and the sealed loss (−1.8) both have intervals spanning zero. RESULTS
  reading 4 ("reconciliation did not help here") is right. The tuning claim
  that it "added 4.4 points" should be read as not established.
- **Primary-term accuracy, 95% CI over studies:**
  - tuning 76.2% (69.6–83.1)
  - sealed 71.5% (63.5–81.4)

  The 4.7-point drop is inside both intervals.

## 2. Merge links (decisions log 12.3): no detectable effect

| tuning, mean of two runs | no links (runs 1, 2) | links (runs 3, 4) | Δ (95% CI over studies) |
|---|---|---|---|
| pooling F1 | 82.3% | 84.1% | +1.9 (−3.4 to +9.0) |
| precision | 81.7% | 87.2% | +5.5 (−2.8 to +15.0) |
| recall | 83.0% | 81.2% | −1.7 (−7.7 to +4.4) |

Run-to-run noise within one condition is −0.6 and +2.2 F1 points. That is
about the size of the gain. Exact McNemar tests on pair decisions find no
significant difference in any run pairing (p from 0.06 to 1.0), and those
p-values are optimistic because pairs aren't independent. Decision 12.3's
wording, "helps a little, does no harm", is too strong on "helps". Measured
honestly, the links make no detectable difference. Keeping them on is still
defensible, because they cost nothing.

## 3. Confidence signals work on tuning and fail on sealed

| AUC (95% CI) | tuning | sealed |
|---|---|---|
| annotation runs agree → annotation right | **0.67** (0.57–0.78) | 0.53 (0.48–0.59) |
| column tier → annotation right | **0.80** (0.71–0.88) | 0.54 (0.45–0.64) |
| variable tier → annotation right | **0.79** (0.69–0.87) | 0.51 (0.42–0.60) |
| qualifiers agree → annotation right | 0.51 (0.42–0.60) | 0.59 (0.49–0.69) |
| partition agreement → no false mates | **0.94** (0.87–0.99) | undefined: no false mates exist |
| partition agreement → no missed mates | **0.78** (0.64–0.92) | 0.49 (0.46–0.50) |

Bold: the permutation p is below 0.001.

- **For annotation, no signal discriminates on unseen data.**
  - On tuning, the tiers have AUC around 0.8, and pre-accepted columns were
    100% right.
  - On sealed, every annotation signal's interval includes 0.5. Agreement
    between runs is high on sealed (88.7%), and the runs agree on wrong
    answers nearly as often as on right ones.
  - The tier checks were chosen on tuning data (decision 8.1), so tuning's
    AUC is optimistic by construction. The sealed AUC is the honest number.
  - This makes RESULTS reading 5 quantitative and stronger: agreement is not
    just "not sufficient" for annotation; on unseen data it carries no
    measurable signal.
- **Partition agreement detects false merges, not missed ones.**
  - On tuning, every column whose runs agreed fully had no false mates (AUC
    0.94).
  - On sealed there were no false merges to detect. The 36 reconciled
    columns that were wrong all had missed mates, and both runs missed them
    alike, so agreement is blind to them (AUC 0.49).
  - The tiers therefore can't route missed merges to review. A different
    check would be needed, such as candidate groups whose members ended up
    in different variables.
- **Pair-level agreement is not perfect on tuning.** Both runs pooled 75
  pairs, and 70 were right. The 5 wrong ones are all in the disease-status /
  karyotype / Down syndrome status variable (`G001.2`): both runs made the
  same arguable call. The log's "53 of 53" (7.3) counts pairs of columns whose
  partitions agreed in full, which is a stricter condition. Both statements
  are true. On sealed, all 189 pairs both runs pooled were right.

## What this changes

- The headline claims that survive are pooling F1 well above every baseline,
  and pooling precision. Claims of improvement from reconciliation, merge
  links, or tuning-to-sealed stability are within noise.
- Before a new sealed corpus (task 9), size it for power. At about 15
  studies, the CI half-width on pooling F1 is 8–14 points, so no change
  smaller than about 10 points can be detected. Either pool several corpora,
  or pre-register the comparison and its expected effect.
- Task 12 (easy-first fast path) and task 15 (different models per run) are
  the places to look for an annotation signal that works on unseen data. The
  current one does not.
