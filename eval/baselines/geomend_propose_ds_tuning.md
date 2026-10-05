# geomend_propose vs tuning gold

Gold columns: 84 · predicted: 72

## Pooling

| | precision | recall | F1 | pairs (true / predicted / gold) |
|---|---|---|---|---|
| all pairs | 92.3% | 40.9% | 56.7% | 36 / 39 / 88 |
| cross-dataset pairs | 92.3% | 40.9% | 56.7% | 36 / 39 / 88 |
| B-cubed | 98.2% | 75.1% | 85.1% | |

## Annotation

Not scored: predictions carry no predicate or primary term.

## Broadest predicted variables (distinct column names)

- `geomend:cohort-variable:e0666f0f73e5c279de0fbcec`: 2 names, 7 columns: gender, sex
- `geomend:cohort-variable:f0bc9cad22f2cae496082b81`: 2 names, 3 columns: age, age (years)
- `geomend:cohort-variable:36f43c599c3a6bdf82e98b24`: 1 names, 4 columns: tissue
- `geomend:cohort-variable:3e41b1287152d1fdab42d486`: 1 names, 4 columns: cell type
- `geomend:cohort-variable:4b4a72e2ba3302dc0ca4c2ba`: 1 names, 2 columns: karyotype

## False merges (1)

- `geomend:cohort-variable:3e41b1287152d1fdab42d486` merges gold cell_type (3), specimen_source (1)

## Missed merges (8)

- `karyotype` split 5 ways: GSE124252/karyotype -> geomend:cohort-variable:4b4a72e2ba3302dc0ca4c2ba; GSE128621/karyotype -> geomend:cohort-variable:4b4a72e2ba3302dc0ca4c2ba; GSE1397/title#karyotype -> ('GSE1397', 'title#karyotype'); GSE16176/condition -> geomend:cohort-variable:8b14c23ad2f649bb049623ec; GSE222365/genotype -> geomend:cohort-variable:acb7e10f3eb7a8a72fb49ecd; GSE79842/condition -> geomend:cohort-variable:98594bf58c7f7132b1091ccc
- `disease` split 5 ways: GSE17459/condition -> geomend:cohort-variable:3cc9a3095508210834960d73; GSE185192/strain -> geomend:cohort-variable:4e5a05ea9d145762bfaa09a1; GSE4119/title#diagnosis -> ('GSE4119', 'title#diagnosis'); GSE5390/Disease_status -> geomend:cohort-variable:9cdb5f3a827c9e1fbe447caa; GSE61804/condition -> geomend:cohort-variable:62cc1f32a56409d7f181771a
- `organism_part` split 4 ways: GSE11877/tissue type -> geomend:cohort-variable:68c973d9efb5ca01955f6a90; GSE124252/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE1397/title#tissue -> ('GSE1397', 'title#tissue'); GSE16176/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE183701/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE4119/source_name#tissue -> ('GSE4119', 'source_name#tissue'); GSE61804/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24
- `specimen_source` split 3 ways: GSE124252/tissue origin -> geomend:cohort-variable:8553caa24bd00799dc1ec4da; GSE1397/source_name#source material -> ('GSE1397', 'source_name#source material'); GSE222365/cell type -> geomend:cohort-variable:3e41b1287152d1fdab42d486
- `cohort` split 3 ways: GSE17459/gene expression dataset -> geomend:cohort-variable:6dcf72881f0f9485bc12b81c; GSE183701/registry -> geomend:cohort-variable:5592023d8d80c7caa9ac9d18; GSE222365/study -> geomend:cohort-variable:7c19d47f764672647cda7d2d
- `age` split 2 ways: GSE128621/age -> geomend:cohort-variable:f0bc9cad22f2cae496082b81; GSE183701/age at draw -> geomend:cohort-variable:cfcace735067ad2eb53520b7; GSE5390/Age (years) -> geomend:cohort-variable:f0bc9cad22f2cae496082b81; GSE79842/age -> geomend:cohort-variable:f0bc9cad22f2cae496082b81
- `cell_type` split 2 ways: GSE128621/cell type -> geomend:cohort-variable:3e41b1287152d1fdab42d486; GSE1397/title#cell type -> ('GSE1397', 'title#cell type'); GSE17459/cell type -> geomend:cohort-variable:3e41b1287152d1fdab42d486; GSE185192/cell type -> geomend:cohort-variable:3e41b1287152d1fdab42d486
- `gestational_age` split 2 ways: GSE1397/source_name#gestational age -> ('GSE1397', 'source_name#gestational age'); GSE16176/gestational age (weeks, days) -> ('GSE16176', 'gestational age (weeks, days)')
