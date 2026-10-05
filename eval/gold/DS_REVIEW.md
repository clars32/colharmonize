# Gold standard review: Down syndrome tuning set

Draft of 2026-10-05. This is iteration 2's 84 gold pairs (13 datasets) re-read
under the rules you confirmed. It now has **50 variables**, of which **11 pool
across datasets**. Full gold: `ds_tuning_columns.tsv` and
`ds_tuning_variables.tsv`. Builder: `build_ds_tuning_gold.py`.

This is **tuning** data. Iteration 2 already showed pipeline answers for these
datasets, so it can't serve as a held-out test. It shapes the pipeline, and the
sealed 16-series corpus measures it.

## Changed without a flag (they follow rules you already approved)

- **Assertion columns are now `indicator`s.** Iteration 2's decision 8.1 had
  withdrawn these to NO_MATCH: `BCR-ABL, t(9;22)`, `E2A-PBX, t(1;19)`, `MLL`,
  `TEL-AML,t(12;21)`, `trisomy 4 and 10` and `flt3-itd`. Each is now an
  indicator of a translocation, chromosomal aberration or duplication. The
  specific lesion is a qualifier, because EFO has no term for the fusions
  themselves. All six stay separate variables.
- **`down syndrome status` is an indicator of Down syndrome,** no longer
  `disease`. It records only that DS is present.
- **CRLF2/JAK2 columns gain qualifiers instead of NO_MATCH or bare
  `genotype`.** Expression by arrays and expression by qRT-PCR are different
  variables, because their methods and scales differ.

## Fifteen flagged calls in seven groups

**A. Ploidy columns join `karyotype`** (2 flags: GSE222365 `genotype`, GSE79842 `condition`)
```
GSE124252 karyotype   WT | Trisomy 21              GSE222365 genotype   trisomic | disomic
GSE128621 karyotype   T21 | D21                    GSE79842  condition  Disomic | Trisomic
GSE1397   karyotype   Euploid | TS21 | Trisomy 21 | TS13
```
All five describe the chromosome-21 complement, and pooling loses nothing.
Iteration 2's `ploidy` (PATO) means the number of whole chromosome *sets*
(diploid, triploid). A single-chromosome trisomy is aneuploidy, so `karyotype`
is the more accurate term as well as the one that pools.

**B. GSE16176 `condition` = euploid | Down syndrome stays in `disease`.**
It contrasts a karyotype (euploid) with a disease. `disease` keeps iteration 2's
call. The alternative is `karyotype`, since DS is defined by trisomy 21.

**C. Age** (2 flags)
```
GSE183701 age at draw              13 | 10 | 11 | 23 …     → pooled into age
GSE124252 age at dissection (day)  D59 | D105 | D134 …     → own variable
```
- `age at draw` is plain age: the draw *is* the sampling event. That reverses
  the plan's illustrative example, which treated it as qualified.
- `age at dissection` stays apart because its origin differs. The 10 fetal
  samples count days from conception and the 5 organoids count days in
  culture, so neither matches postnatal age.

**D. Batches get a term** (4 flags; all were NO_MATCH)
```
GSE222365 batch              org15 | org16 | org17 | org18 | none   ┐ pooled: EFO:0005067
GSE79842  batch              2F | 1F | 1L                            ┘ (defined as "a block or batch")
GSE11877  amplification set  3 | 1 | 2 | 8 …        → own variable, block + method "amplification"
GSE11877  hybridization set  11 | 9 | 5 | 7 …       → own variable, block + method "hybridization"
```
Iteration 2 never noticed that EFO's `block` is defined as "a block or batch".
The two GSE11877 columns co-occur, so they can't share a variable. They also
name a specific processing step, so they don't join the generic `batch`.

**E. A new pooled variable, `specimen source`** (3 flags)
```
GSE124252 tissue origin     fetal (10) | H9-derived retinal organoids (5)
GSE1397   source material   fetal cerebrum | fetal cerebellum | fetal astrocyte cell lines | fetal heart
GSE222365 cell type         iPSC-derived cerebral organoid
```
All three say what the specimen was derived from, and each value keeps that
meaning when pooled.
- GSE222365's `cell type` leaves `cell type` because an organoid isn't a cell
  type.
- GSE1397's `source material` can't stay in organism part, because it
  co-occurs with `tissue` (cerebrum, cerebellum, heart) under different values.

**F. GSE222365 `study` = expanded | pilot joins `cohort`,** alongside
`gene expression dataset` (AIEOP, ICH, BFM) and `registry` (Control, Type 1
Diabetes, DSRegistry). It was NO_MATCH. Alternative: keep it as its own
variable.

**G. Two former NO_MATCH columns get anchors** (2 flags)
- `CNS status` (No CNS disease | <5 CSF WBC/µl with blasts | >5 …) is
  anchored to `disease staging`, qualified by central nervous system. CNS
  involvement grade is a leukaemia staging element.
- `WBC, 1000/microliter` is anchored to `complete blood cell count`,
  qualified by leukocyte. `leukocyte count` is deprecated in this EFO release,
  but its parent plus a cell-type qualifier says the same thing without it.

## Owner decisions, 2026-10-05

- **A, C, D, E, F, G:** accepted as drafted.
- **B:** GSE16176 `condition` (euploid | Down syndrome) moves to **`karyotype`**.
  That describes the column as written and fits the other chromosome-21
  columns. Pooling recodes "Down syndrome" to "Trisomy 21". Nothing is lost,
  because every output keeps the raw value verbatim next to the harmonized one.
  This is the first gold call that needs a value recode, so the pipeline's
  reconciliation step has to be able to propose recodes, not only groupings.

**Tuning gold final as of 2026-10-05:** 84 column rows in 50 variables, 11 of
which pool across datasets. No open REVIEW flags.

## What happens next

Once you've ruled on these, the tuning gold is final. I'll then re-score
iteration 2's published `mappings.tsv` against it, which gives the baseline
for pooling precision and recall. Iteration 2 never ran on the sealed corpus,
so it has no baseline there.
