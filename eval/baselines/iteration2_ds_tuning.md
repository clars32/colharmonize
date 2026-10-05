# iteration2 vs tuning gold

Gold columns: 84 · predicted: 84

## Pooling

| | precision | recall | F1 | pairs (true / predicted / gold) |
|---|---|---|---|---|
| all pairs | 59.5% | 78.4% | 67.6% | 69 / 116 / 88 |
| cross-dataset pairs | 62.7% | 78.4% | 69.7% | 69 / 110 / 88 |
| B-cubed | 81.3% | 88.5% | 84.7% | |

## Annotation

- primary term: 69.0%
- predicate: 60.7%
- term and predicate together: 54.8%
- NO_MATCH precision / recall: 26.3% / 100.0%
- qualifiers precision / recall: — / 0.0%

## Broadest predicted variables (distinct column names)

- `MONDO:0000001`: 7 names, 9 columns: condition, congenital abnormality, diagnosis, disease_status, down syndrome status, registry, strain
- `EFO:0000246`: 4 names, 5 columns: age, age (years), age at dissection (day), age at draw
- `EFO:0000635`: 3 names, 8 columns: source material, tissue, tissue type
- `EFO:0009865`: 3 names, 3 columns: crlf2 expression levels (gene expression arrays - log2), crlf2 expression levels (qrt-pcr - relative to si-ds-all-12), crlf2 expression levels stratification
- `PATO:0000047`: 2 names, 7 columns: gender, sex

## False merges (8)

- `MONDO:0000001` merges gold down_syndrome_status (1), karyotype (1), cohort (1), disease (5), congenital_abnormality (1)
- `EFO:0000635` merges gold organism_part (7), specimen_source (1)
- `EFO:0000246` merges gold age (4), age_at_dissection (1)
- `EFO:0000324` merges gold cell_type (4), specimen_source (1)
- `EFO:0009865` merges gold crlf2_expression_array (1), crlf2_expression_strata (1), crlf2_expression_qpcr (1)
- `EFO:0000433` merges gold post_mortem_interval (1), days_in_vitro (1)
- `OBI:0100051` merges gold sample_pooling (1), specimen_source (1)
- `EFO:0000336` merges gold crlf2_fish (1), genetic_aberration (1)

## Missed merges (5)

- `karyotype` split 3 ways: GSE124252/karyotype -> EFO:0004426; GSE128621/karyotype -> EFO:0004426; GSE1397/title#karyotype -> EFO:0004426; GSE16176/condition -> MONDO:0000001; GSE222365/genotype -> PATO:0001374; GSE79842/condition -> PATO:0001374
- `specimen_source` split 3 ways: GSE124252/tissue origin -> OBI:0100051; GSE1397/source_name#source material -> EFO:0000635; GSE222365/cell type -> EFO:0000324
- `cohort` split 3 ways: GSE17459/gene expression dataset -> EFO:0004445; GSE183701/registry -> MONDO:0000001; GSE222365/study -> nomatch:GSE222365:study
- `cell_line` split 2 ways: GSE185192/cell line -> nomatch:GSE185192:cell line; GSE222365/cell line -> nomatch:GSE222365:cell line
- `batch` split 2 ways: GSE222365/batch -> nomatch:GSE222365:batch; GSE79842/batch -> EFO:0005067
