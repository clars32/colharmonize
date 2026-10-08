# Sealed corpus: baseline same_name

Gold columns: 137 · predicted: 118

## Pooling

| | precision | recall | F1 | pairs (true / predicted / gold) |
|---|---|---|---|---|
| all pairs | 99.0% | 36.9% | 53.8% | 99 / 100 / 268 |
| cross-dataset pairs | 99.0% | 38.1% | 55.0% | 99 / 100 / 260 |
| B-cubed | 99.3% | 63.4% | 77.4% | |

## Annotation

Not scored: predictions carry no predicate or primary term.

## Broadest predicted variables (distinct column names)

- `name:age`: 1 names, 9 columns: age
- `name:tissue`: 1 names, 9 columns: tissue
- `name:sex`: 1 names, 6 columns: sex
- `name:treatment`: 1 names, 3 columns: treatment
- `name:gender`: 1 names, 3 columns: gender

## False merges (1)

- `name:cell type` merges gold cell_type (1), organism_part (1)

## Missed merges (21)

- `disease` split 8 ways: GSE104674/subject status -> name:subject status; GSE131411/clinical classification -> name:clinical classification; GSE137340/diagnosis -> name:diagnosis; GSE166925/disease -> name:disease; GSE189007/disease group -> name:disease group; GSE189007/sampling in t2d stage -> name:sampling in t2d stage; GSE189007/sampling t2d stage -> name:sampling t2d stage; GSE206171/uc or healthy control#diagnosis -> ('GSE206171', 'uc or healthy control#diagnosis'); GSE231509/diagnosis -> name:diagnosis; GSE92415/disease -> name:disease
- `subject_id` split 6 ways: GSE104674/subject id # -> ('GSE104674', 'subject id #'); GSE131411/patient -> name:patient; GSE166925/patient_id -> name:patient_id; GSE231509/individual -> name:individual; GSE282580/title#subject -> ('GSE282580', 'title#subject'); GSE92415/subject -> name:subject
- `age` split 4 ways: GSE104674/age -> name:age; GSE137340/age -> name:age; GSE152111/donor age (yrs) -> name:donor age (yrs); GSE166925/patient_age -> name:patient_age; GSE189007/age (yr) -> name:age (yr); GSE189007/age -> name:age; GSE192341/age -> name:age; GSE231509/age -> name:age; GSE237290/age -> name:age; GSE272769/age -> name:age; GSE58984/age -> name:age; GSE92415/age -> name:age
- `disease_duration` split 4 ways: GSE166925/disease_duration (y) -> name:disease_duration (y); GSE189007/duration (yr) -> name:duration (yr); GSE189007/t2d duration -> name:t2d duration; GSE206171/diagnose duration (years) -> name:diagnose duration (years)
- `hba1c` split 4 ways: GSE104674/hba1c (mmol/mol) -> name:hba1c (mmol/mol); GSE189007/blood glucose#hba1c -> ('GSE189007', 'blood glucose#hba1c'); GSE189007/hba1c (%) of the sample -> ('GSE189007', 'hba1c (%) of the sample'); GSE231509/hba1c, % -> ('GSE231509', 'hba1c, %')
- `organism_part` split 3 ways: GSE119217/tissue -> name:tissue; GSE131411/cell type -> name:cell type; GSE131411/tissue -> name:tissue; GSE137340/tissue -> name:tissue; GSE166925/site_taken -> name:site_taken; GSE189007/tissue -> name:tissue; GSE206171/tissue -> name:tissue; GSE231509/tissue -> name:tissue; GSE282580/tissue -> name:tissue; GSE58984/tissue -> name:tissue; GSE92415/tissue -> name:tissue
- `sex` split 3 ways: GSE104674/gender -> name:gender; GSE119217/Sex -> name:sex; GSE131411/Sex -> name:sex; GSE137340/Sex -> name:sex; GSE152111/donor gender (m=male; f=female) -> ('GSE152111', 'donor gender (m=male; f=female)'); GSE166925/gender -> name:gender; GSE189007/gender -> name:gender; GSE206171/Sex -> name:sex; GSE231509/Sex -> name:sex; GSE272769/Sex -> name:sex
- `bmi` split 3 ways: GSE104674/bmi (kg/m2) -> name:bmi (kg/m2); GSE152111/donor bmi (bmi kg/m2) -> name:donor bmi (bmi kg/m2); GSE189007/bmi (kg/m2) -> name:bmi (kg/m2); GSE189007/bmi -> name:bmi; GSE231509/bmi -> name:bmi
- `tumor_size` split 2 ways: GSE237290/tumor_size -> name:tumor_size; GSE58984/tumor size -> name:tumor size
- `er_status` split 2 ways: GSE237290/er -> name:er; GSE58984/er status -> name:er status
- `pr_status` split 2 ways: GSE237290/pr -> name:pr; GSE58984/pgr status -> name:pgr status
- `stromal_til` split 2 ways: GSE237290/til -> name:til; GSE58984/stromal lymphocytic infiltration -> name:stromal lymphocytic infiltration
- `recurrence_event` split 2 ways: GSE192341/recurrence -> name:recurrence; GSE237290/event.rfi -> name:event.rfi
- `treatment` split 2 ways: GSE149322/arm -> name:arm; GSE231509/treatment -> name:treatment; GSE58984/treatment -> name:treatment; GSE92415/treatment -> name:treatment
- `pcr` split 2 ways: GSE149322/pcr -> name:pcr; GSE192341/pathological complete response (pcr) -> name:pathological complete response (pcr)
- `septic_shock_status` split 2 ways: GSE119217/shock_status -> name:shock_status; GSE272769/shock -> name:shock
- `ethnic_group` split 2 ways: GSE119217/race_ethnicity -> name:race_ethnicity; GSE189007/population -> name:population
- `inflammation_status` split 2 ways: GSE166925/inflammation_status -> name:inflammation_status; GSE282580/title#inflammation -> ('GSE282580', 'title#inflammation')
- `mayo_score` split 2 ways: GSE206171/mayoscore -> name:mayoscore; GSE92415/mayo score -> name:mayo score
- `time_since_treatment_start` split 2 ways: GSE282580/title#week -> ('GSE282580', 'title#week'); GSE92415/visit -> name:visit
- `fasting_glucose` split 2 ways: GSE189007/blood glucose#glucose -> ('GSE189007', 'blood glucose#glucose'); GSE231509/fasting glucose,_mm -> ('GSE231509', 'fasting glucose,_mm')

Predicted on unsplit parent columns (their parts score as missing): GSE104674/timepoint, GSE189007/blood glucose, GSE189007/phenotype, GSE206171/uc or healthy control
