# Sealed-corpus measurement: results

Run once, 2026-10-07 and 10-08, at tag `sealed-run` (`f1dfcb2`), following
`PROTOCOL.md`. Nothing in the pipeline changed after a sealed output was seen.
16 series in four disease areas (breast cancer, inflammatory bowel disease,
type 2 diabetes, sepsis), 1,623 samples. Gold:
137 scored columns in 66 variables; 4 split parents are scored through their
parts. Raw outputs are in `out/`.

## Pooling

| sealed corpus | precision | recall | F1 | cross-dataset F1 | B-cubed F1 |
|---|---|---|---|---|---|
| **colharmonize, final output (reconcile run 1)** | **100.0%** | **70.9%** | **83.0%** | 83.1% | 89.5% |
| reconcile run 2 alone | 100.0% | 70.5% | 82.7% | 82.9% | 89.0% |
| annotation alone (before reconciliation) | 100.0% | 73.5% | 84.7% | 85.5% | 89.2% |
| baseline: identical column names | 99.0% | 36.9% | 53.8% | 55.0% | 77.4% |
| baseline: GEOmend `propose()` | 98.8% | 29.9% | 45.8% | 46.5% | 75.9% |

No false merges: every pair colharmonize pooled belongs together.

Recall is limited by columns the pipeline never produced. 36 of the 268 gold
pairs involve one of the 18 gold columns it never produced, so recall can't
exceed 86.6%. Among pairs where both columns exist, 81.9% were pooled. The
missed merges that remain:
- identifiers (`patient`, `patient_id`, `individual`, `subject`), each kept
  apart
- `disease` split by study
- `treatment` vs `arm`
- `mayoscore` vs `mayo score`
- `til` vs `stromal lymphocytic infiltration`
- `disease_duration (y)` vs `duration (yr)`

## Annotation

| | sealed final | sealed annotation alone | tuning final |
|---|---|---|---|
| primary term | 71.5% | 70.1% | 76.2% |
| predicate | 73.7% | 70.8% | 78.6% |
| term and predicate | 69.3% | 66.4% | 69.0% |
| NO_MATCH precision / recall | 62.5% / 55.6% | 60.0% / 50.0% | 42.9% / 60.0% |
| qualifiers precision / recall | 28.9% / 37.9% | 34.3% / 41.4% | 61.5% / 64.0% |

## Confidence and review tiers

| sealed tier | columns | annotation correct | pooled pairs correct | tuning: annotation / pairs |
|---|---|---|---|---|
| pre-accepted | 23 | 87.0% | 21 / 21 | 100% / 9 of 9 |
| quick | 87 | 78.2% | 167 / 167 | 83.3% / 43 of 43 |
| manual | 9 | 77.8% | 2 / 2 | 44.1% / 19 of 32 |

The runs agreed far more than on tuning: on annotation for 88.7% of columns
(tuning 84.8%), and on the partition for 98.3% (tuning 92.5%; 2 columns
disagreed). Pooled pairs the runs agreed on: 189 of 189 correct.

## Process

| stage | batches | re-tasked | outcome |
|---|---|---|---|
| repair | 2 | 2 (same batch) | batch 1 still failed: its 8 studies got no repair rules |
| annotate | 24 | 1 (an answer omitted an item) | clean |
| reconcile | 12 | 0 | clean |

41 subagent runs in all. Ten annotators reported an account session-limit
error after writing their answers; no answer was lost.

**Why 18 gold columns are missing**
- **11 derived columns.** All the gold's title and split columns are in the
  repair batch that failed. Only one item, GSE189007, failed validation (a
  rule re-extracted the existing `disease group` characteristic), but re-tasking
  is per batch, so the protocol dropped all 8 studies' rules. Applying only the
  failing item's exclusion would have been more flattering, and choosing it
  after seeing which item failed is what pre-registration rules out.
- **7 characteristics.** GEOmend 0.0.8 mis-parses keys that contain commas,
  `#` or `%`. `fasting glucose,_mm`, `hba1c, %`, `subject id #` and
  `hba1c (%) of the sample` land in its catch-all "unresolved characteristic"
  field, and `donor gender (m=male; f=female)` is cut to `donor gender (m`.
  That is fix 2 in `docs/geomend-upstream-proposal.md`, still unfixed. Repair is meant to recover
  such columns, and all four affected studies were in the failed batch.

## Reading the results

1. **Generalization held for pooling.** Pooling F1 was 83.0% sealed against
   82.6% tuning, roughly 30 points above both baselines, with no false merges.
   The sealed corpus is easier on precision, though: the baselines also reach
   99%. It has few look-alike variables such as tuning's disease status vs
   karyotype.
2. **Primary-term accuracy fell by 4.7 points** (76.2% to 71.5%), well under
   the 12–24 point drops reported for LLM matchers on unseen targets
   (MetaHarmonizer, 2026). Term and predicate together held at 69.3%.
3. **Qualifiers did not generalize** (precision 28.9%, against 61.5% on
   tuning). This needs a look at whether the cause is the annotator or a
   difference in how the two gold standards write qualifiers. The sealed gold
   was curated separately.
4. **Reconciliation did not help here.** Annotation alone scored F1 84.7%
   against 83.0% after reconciliation. On tuning, reconciliation added 4.4
   points (78.2% to 82.6%). Its benefit there came from separating look-alike
   variables, and this corpus has few. Here it split a few variables
   annotation had pooled (`disease` by study). Its value is corpus-dependent and
   not established.
5. **Tiers discriminated less.** High agreement left only 9 columns in the
   manual tier, and pre-accepted columns were 87% correct rather than 100%.
   Agreement remains a perfect precision signal for pooling (189 of 189). It is
   not a sufficient one for annotation.
6. **One failure cost the most, and it is fixable.** Retrying validation per
   item instead of per batch, plus the GEOmend key-parsing fix, would have
   recovered up to all 18 missing columns and lifted the recall ceiling from
   86.6% toward 100%.

These numbers are final for this corpus. Fixes made in response to them must
be measured on new data, not re-run here as a headline.

## Post-hoc analysis (added after the measurement; no headline numbers change)

**Why annotation alone outscored reconciliation.** Reconciling only the
groups annotation can't settle (`eval/tuning/selective_reconcile.py`) changes
nothing. 20 of the 36 sealed groups were settled, and reconciliation had split
none of them. The recall difference comes from two mixed groups, where the
co-occurrence rule forced a choice:
- **GSE166925:** repair extracted `title#diagnosis` from sample titles. It
  conflicts on the same samples with the study's own `disease`
  characteristic, so only one can join the disease variable, and the
  reconciler kept the title-derived one.
- **GSE131411:** the same thing happened between `title#group` and
  `clinical classification`.

Annotation alone ignores the co-occurrence rule and pools both columns, which
the scorer rewards because the gold lists only the characteristic. So part of
annotation's apparent advantage comes from breaking a pooling rule. The cause
is redundant repair output, and the fix belongs in repair or in the
reconciler's tie-break, not in which groups are reconciled.
