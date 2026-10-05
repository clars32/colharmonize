# Gold standard review: generalization corpus

Draft of 2026-10-02, for the project owner. It covers 16 series, 139 column rows
(130 characteristic columns, 3 variables from titles, 6 split parts) and 68 gold
variables, 22 of which pool columns from more than one dataset.

The full gold is in `generalization_columns.tsv` (which variable each column
belongs to) and `generalization_variables.tsv` (each variable's annotation).
`build_generalization_gold.py` regenerates both and validates them: every term
against pinned EFO v3.94.0, every column covered exactly once, and no
co-occurring columns pooled. A gold change is an edit to that script.

Only three decisions shape most of the gold. They come first, followed by 13
smaller calls.

## 1. How the bucket principle is applied

Your principle is that disparate column names should not share one bucket,
because it loses information. To decide cases mechanically, I turned "loses
information" into a test: **pool two columns only if every value still means
the same thing once it sits in the pooled column.**

`disease` passes the test, so it pools 7 differently named columns:

```
GSE137340 diagnosis                 Severe Sepsis | Septic Shock | Healthy
GSE166925 disease                   Control | CD | UC | IBDu
GSE92415  disease                   Ulcerative Colitis (UC) | Healthy
GSE231509 diagnosis                 T2D, Obesity | Obesity | Metabolically healthy
GSE104674 subject status            Type 2 diabetes | Healthy
GSE131411 clinical classification   SS | CS
GSE206171 uc or healthy control     (diagnosis part, after the split)
```

Every value is still a diagnosis when stacked. Iteration 2's failures were a
different kind of column: `ds` = `DS`/`non-DS`, where "non-DS" is not a disease,
or a column that combined two concepts. Those fail the test and stay separate.

Related columns that fail the test become **separate variables that share an
anchor term**. Three columns are anchored to `disease` but kept apart because
each uses a different classification system: `pam50`, `subtype` (TN/LUM) and
`histology`. Likewise `mayo score` and `nancy_score` are both anchored to
`illness severity status` but stay separate because they are different
instruments.

**Please confirm or correct this reading.** It determines the whole partition.

## 2. A fourth match type: `indicator`

Gold curation surfaced a kind of column the plan's model couldn't express
cleanly. Examples: `shock: Yes/No`, `pcr: 0/1`, `chemo: 0/1`, `event.os: 0/1`,
`distant metastasis: 0/1`.

- The column is not *equivalent* to the term: "Yes" is not a septic shock.
- It is not *narrower* than the term either.
- It is a yes/no indicator *of* the term.

So the gold uses four predicates: `exact`, `broad`, `indicator` and `none`.
Eight variables use `indicator`. This also covers iteration 2's assertion
columns more simply than "broad anchor + about": `bcr-abl, t(9;22)` becomes an
indicator of the fusion. GEOmend's workspace already has `indicator_of_concept`
as a merge relation, so I'll add it to the upstream proposal.

## 3. The co-occurrence rule, made precise

"Never merge two columns from the same dataset" turned out to be wrong in both
directions:

- **GSE189007 has two sub-cohorts with different conventions.** `age (yr)`
  covers 40 samples and `age` the other 90; `sampling in t2d stage` and
  `sampling t2d stage` are a typo split 45/45. They should pool, and they do,
  because they never describe the same samples.
- **GSE131411 records `cell type: Whole Blood` on 10 samples** that also carry
  `tissue: Whole Blood`, identical on all 10. That is a duplicate encoding, so
  pooling it loses nothing.

The rule is now: **columns that have values on the same samples never pool,
unless their values are identical on every shared sample.** The plan is
updated to match.

## 4. Judgment calls flagged `REVIEW` (13 flags; the two tumour-size flags share a row)

| Column | My call | Alternative |
|---|---|---|
| GSE237290 `tumor_size`, GSE58984 `tumor size` | One variable. Units are unstated; values imply cm and mm. | Keep apart until units are known |
| GSE237290 `til` | Separate from GSE58984's stromal and intratumoral scores, because the compartment isn't stated | Pool with stromal TILs (the usual convention) |
| GSE237290 `gc` | Its own variable, meaning unknown | Ask the depositors / leave out of scoring |
| GSE58984 `tissue` = "HER2 breast cancer tumor" | Organism part | Treat as a specimen type |
| GSE149322 `arm` | Treatment arm (group assignment), separate from treatment | Pool with `treatment` |
| GSE137340 `outcome` | Follow-up status, not pooled with `mort30` (30-day window vs unstated window) | Pool both as "death" |
| GSE131411 `cell type` | Pooled into organism part (duplicate of `tissue`) | Own variable |
| GSE166925 `sample_age(y)` | Own variable, meaning unclear (storage time?) | — |
| GSE152111 `cell type` = "Primary islet cells" | Cell type (values name cells) | Organism part (islet of Langerhans) |
| GSE231509 `time point` | Separate: the reference is a meal test, not therapy start | Pool into one "time since intervention" |
| GSE189007 `disease group` | A T2D-complication variable shared with `sampling (in) t2d stage` | Pool into `disease` |
| GSE189007 `population` = "Taiwanese" | Ethnic group, pooled with `race_ethnicity` | Own variable (nationality) |

## Owner decisions, 2026-10-05

- **§1 bucket principle:** confirmed. Columns may pool as long as no
  information from the original dataset is lost, even if that requires
  carefully restructuring values.
- **§2 `indicator`:** adopted.
- **§3 co-occurrence rule:** adopted as written.
- **§4 accepted as drafted:** rows 1 (tumour size), 3 (`gc`), 4 (GSE58984
  `tissue`), 7 (GSE131411 `cell type`), 8 (`sample_age(y)`), 9 (GSE152111
  `cell type`) and 12 (`population`).
- **§4 row 2 (`til`):** alternative taken. Pooled with stromal TILs under the
  usual convention. More generally, assume the usual convention when the
  metadata is silent, but flag it. The gold now carries an `assumed_convention`
  flag on such rows (17 rows, including every inferred unit).
- **§4 rows 5, 6, 10, 11:** pending; the owner asked to see the values first.

## What happens next

Once you've reviewed this, the gold is final for the generalization corpus,
and it is measured once after the pipeline is frozen. Changes made later, after
any pipeline output for these series exists, have to be recorded as
corrections with reasons, as iteration 2 did in decisions 4.7–4.8.
