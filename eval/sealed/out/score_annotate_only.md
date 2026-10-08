# Sealed corpus: annotate only (before reconciliation)

Gold columns: 137 · predicted: 119

## Pooling

| | precision | recall | F1 | pairs (true / predicted / gold) |
|---|---|---|---|---|
| all pairs | 100.0% | 73.5% | 84.7% | 197 / 197 / 268 |
| cross-dataset pairs | 100.0% | 74.6% | 85.5% | 194 / 194 / 260 |
| B-cubed | 100.0% | 80.6% | 89.2% | |

## Annotation

- primary term: 70.1%
- predicate: 70.8%
- term and predicate together: 66.4%
- NO_MATCH precision / recall: 60.0% / 50.0%
- qualifiers precision / recall: 34.3% / 41.4%

## Broadest predicted variables (distinct column names)

- `exact|MONDO:0000001|`: 5 names, 7 columns: clinical classification, diagnosis, disease, disease group, subject status
- `exact|EFO:0000246|`: 4 names, 12 columns: age, age (yr), donor age (yrs), patient_age
- `exact|EFO:0000635|`: 3 names, 11 columns: cell type, site_taken, tissue
- `exact|EFO:0004340|`: 3 names, 5 columns: bmi, bmi (kg/m2), donor bmi (bmi kg/m2)
- `exact|PATO:0000047|`: 2 names, 9 columns: gender, sex

## False merges (0)


## Missed merges (13)

- `subject_id` split 6 ways: GSE104674/subject id # -> ('GSE104674', 'subject id #'); GSE131411/patient -> none:GSE131411::patient; GSE166925/patient_id -> none:GSE166925::patient_id; GSE231509/individual -> none:GSE231509::individual; GSE282580/title#subject -> ('GSE282580', 'title#subject'); GSE92415/subject -> none:GSE92415::subject
- `disease` split 4 ways: GSE104674/subject status -> exact|MONDO:0000001|; GSE131411/clinical classification -> exact|MONDO:0000001|; GSE137340/diagnosis -> exact|MONDO:0000001|; GSE166925/disease -> exact|MONDO:0000001|; GSE189007/disease group -> exact|MONDO:0000001|; GSE189007/sampling in t2d stage -> broad|EFO:0000410|object_class=type 2 diabetes; GSE189007/sampling t2d stage -> broad|EFO:0000410|object_class=type 2 diabetes mellitus; GSE206171/uc or healthy control#diagnosis -> ('GSE206171', 'uc or healthy control#diagnosis'); GSE231509/diagnosis -> exact|MONDO:0000001|; GSE92415/disease -> exact|MONDO:0000001|
- `hba1c` split 4 ways: GSE104674/hba1c (mmol/mol) -> exact|EFO:0004541|; GSE189007/blood glucose#hba1c -> ('GSE189007', 'blood glucose#hba1c'); GSE189007/hba1c (%) of the sample -> ('GSE189007', 'hba1c (%) of the sample'); GSE231509/hba1c, % -> ('GSE231509', 'hba1c, %')
- `treatment` split 3 ways: GSE149322/arm -> broad|EFO:0000727|; GSE231509/treatment -> exact|EFO:0000727|object_class=mixed meal tolerance test (mmtt); GSE58984/treatment -> exact|EFO:0000727|; GSE92415/treatment -> exact|EFO:0000727|
- `disease_duration` split 3 ways: GSE166925/disease_duration (y) -> broad|EFO:0000433|event_time_anchor=diagnosis; GSE189007/duration (yr) -> exact|EFO:0000433|event_time_anchor=diagnosis of type 2 diabetes; GSE189007/t2d duration -> broad|EFO:0000433|event_time_anchor=diagnosis of type 2 diabetes; GSE206171/diagnose duration (years) -> broad|EFO:0000433|event_time_anchor=diagnosis
- `stromal_til` split 2 ways: GSE237290/til -> none:GSE237290::til; GSE58984/stromal lymphocytic infiltration -> broad|EFO:0009832|object_class=stromal lymphocytes
- `recurrence_event` split 2 ways: GSE192341/recurrence -> indicator|EFO:0004952|object_class=breast cancer; GSE237290/event.rfi -> indicator|EFO:0004952|
- `pcr` split 2 ways: GSE149322/pcr -> exact|EFO:0002943|; GSE192341/pathological complete response (pcr) -> indicator|EFO:0009697|
- `sex` split 2 ways: GSE104674/gender -> exact|PATO:0000047|; GSE119217/Sex -> exact|PATO:0000047|; GSE131411/Sex -> exact|PATO:0000047|; GSE137340/Sex -> exact|PATO:0000047|; GSE152111/donor gender (m=male; f=female) -> ('GSE152111', 'donor gender (m=male; f=female)'); GSE166925/gender -> exact|PATO:0000047|; GSE189007/gender -> exact|PATO:0000047|; GSE206171/Sex -> exact|PATO:0000047|; GSE231509/Sex -> exact|PATO:0000047|; GSE272769/Sex -> exact|PATO:0000047|
- `inflammation_status` split 2 ways: GSE166925/inflammation_status -> indicator|MONDO:0021166|; GSE282580/title#inflammation -> ('GSE282580', 'title#inflammation')
- `mayo_score` split 2 ways: GSE206171/mayoscore -> broad|EFO:0007863|method=mayo score;object_class=ulcerative colitis; GSE92415/mayo score -> none:GSE92415::mayo score
- `time_since_treatment_start` split 2 ways: GSE282580/title#week -> ('GSE282580', 'title#week'); GSE92415/visit -> broad|EFO:0000724|event_time_anchor=start of treatment (baseline)
- `fasting_glucose` split 2 ways: GSE189007/blood glucose#glucose -> ('GSE189007', 'blood glucose#glucose'); GSE231509/fasting glucose,_mm -> ('GSE231509', 'fasting glucose,_mm')

Predicted on unsplit parent columns (their parts score as missing): GSE104674/timepoint, GSE189007/blood glucose, GSE189007/phenotype, GSE206171/uc or healthy control
