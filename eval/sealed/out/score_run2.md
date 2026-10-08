# Sealed corpus: reconcile run 2 alone

Gold columns: 137 · predicted: 119

## Pooling

| | precision | recall | F1 | pairs (true / predicted / gold) |
|---|---|---|---|---|
| all pairs | 100.0% | 70.5% | 82.7% | 189 / 189 / 268 |
| cross-dataset pairs | 100.0% | 70.8% | 82.9% | 184 / 184 / 260 |
| B-cubed | 100.0% | 80.2% | 89.0% | |

## Annotation

- primary term: 70.8%
- predicate: 73.0%
- term and predicate together: 67.9%
- NO_MATCH precision / recall: 62.5% / 55.6%
- qualifiers precision / recall: 24.0% / 41.4%

## Broadest predicted variables (distinct column names)

- `G002.1`: 4 names, 12 columns: age, age (yr), donor age (yrs), patient_age
- `G004.1`: 4 names, 5 columns: diagnosis, disease, disease group, subject status
- `G001.1`: 3 names, 11 columns: cell type, site_taken, tissue
- `G006.1`: 3 names, 5 columns: bmi, bmi (kg/m2), donor bmi (bmi kg/m2)
- `G003.1`: 2 names, 9 columns: gender, sex

## False merges (0)


## Missed merges (12)

- `subject_id` split 6 ways: GSE104674/subject id # -> ('GSE104674', 'subject id #'); GSE131411/patient -> G026.1; GSE166925/patient_id -> G029.1; GSE231509/individual -> G032.1; GSE282580/title#subject -> ('GSE282580', 'title#subject'); GSE92415/subject -> G036.1
- `disease` split 5 ways: GSE104674/subject status -> G004.1; GSE131411/clinical classification -> G004.2; GSE137340/diagnosis -> G004.1; GSE166925/disease -> G004.3; GSE189007/disease group -> G004.1; GSE189007/sampling in t2d stage -> G017.1; GSE189007/sampling t2d stage -> G017.1; GSE206171/uc or healthy control#diagnosis -> ('GSE206171', 'uc or healthy control#diagnosis'); GSE231509/diagnosis -> G004.1; GSE92415/disease -> G004.1
- `hba1c` split 4 ways: GSE104674/hba1c (mmol/mol) -> G005.2; GSE189007/blood glucose#hba1c -> ('GSE189007', 'blood glucose#hba1c'); GSE189007/hba1c (%) of the sample -> ('GSE189007', 'hba1c (%) of the sample'); GSE231509/hba1c, % -> ('GSE231509', 'hba1c, %')
- `treatment` split 3 ways: GSE149322/arm -> G009.2; GSE231509/treatment -> G009.3; GSE58984/treatment -> G009.1; GSE92415/treatment -> G009.1
- `stromal_til` split 2 ways: GSE237290/til -> S016; GSE58984/stromal lymphocytic infiltration -> G024.2
- `sex` split 2 ways: GSE104674/gender -> G003.1; GSE119217/Sex -> G003.1; GSE131411/Sex -> G003.1; GSE137340/Sex -> G003.1; GSE152111/donor gender (m=male; f=female) -> ('GSE152111', 'donor gender (m=male; f=female)'); GSE166925/gender -> G003.1; GSE189007/gender -> G003.1; GSE206171/Sex -> G003.1; GSE231509/Sex -> G003.1; GSE272769/Sex -> G003.1
- `ethnic_group` split 2 ways: GSE119217/race_ethnicity -> G013.2; GSE189007/population -> G013.1
- `inflammation_status` split 2 ways: GSE166925/inflammation_status -> G028.1; GSE282580/title#inflammation -> ('GSE282580', 'title#inflammation')
- `disease_duration` split 2 ways: GSE166925/disease_duration (y) -> G010.2; GSE189007/duration (yr) -> G010.1; GSE189007/t2d duration -> G010.1; GSE206171/diagnose duration (years) -> G010.2
- `mayo_score` split 2 ways: GSE206171/mayoscore -> G011.1; GSE92415/mayo score -> G035.1
- `time_since_treatment_start` split 2 ways: GSE282580/title#week -> ('GSE282580', 'title#week'); GSE92415/visit -> G007.2
- `fasting_glucose` split 2 ways: GSE189007/blood glucose#glucose -> ('GSE189007', 'blood glucose#glucose'); GSE231509/fasting glucose,_mm -> ('GSE231509', 'fasting glucose,_mm')

Predicted on unsplit parent columns (their parts score as missing): GSE104674/timepoint, GSE189007/blood glucose, GSE189007/phenotype, GSE206171/uc or healthy control
