# Sealed corpus: baseline geomend_propose

Gold columns: 137 · predicted: 118

## Pooling

| | precision | recall | F1 | pairs (true / predicted / gold) |
|---|---|---|---|---|
| all pairs | 98.8% | 29.9% | 45.8% | 80 / 81 / 268 |
| cross-dataset pairs | 98.8% | 30.4% | 46.5% | 79 / 80 / 260 |
| B-cubed | 99.3% | 61.4% | 75.9% | |

## Annotation

Not scored: predictions carry no predicate or primary term.

## Broadest predicted variables (distinct column names)

- `geomend:cohort-variable:e0666f0f73e5c279de0fbcec`: 2 names, 9 columns: gender, sex
- `geomend:cohort-variable:f5fce9a76cff2d8b8527658e`: 2 names, 2 columns: tumor size, tumor_size
- `geomend:cohort-variable:f0bc9cad22f2cae496082b81`: 2 names, 2 columns: age, age (yr)
- `geomend:cohort-variable:36f43c599c3a6bdf82e98b24`: 1 names, 9 columns: tissue
- `geomend:cohort-variable:f5840d41d643cbc06b70a2b1`: 1 names, 2 columns: her2

## False merges (1)

- `geomend:cohort-variable:3e41b1287152d1fdab42d486` merges gold cell_type (1), organism_part (1)

## Missed merges (20)

- `age` split 11 ways: GSE104674/age -> geomend:cohort-variable:2c8191a04239ad0c134bbe62; GSE137340/age -> geomend:cohort-variable:00567ade89de6ea3fb2e96de; GSE152111/donor age (yrs) -> geomend:cohort-variable:acb79f5ca0a4086d5324f232; GSE166925/patient_age -> geomend:cohort-variable:8c25c2a5add6f36e13ab978d; GSE189007/age (yr) -> geomend:cohort-variable:f0bc9cad22f2cae496082b81; GSE189007/age -> geomend:cohort-variable:f0bc9cad22f2cae496082b81; GSE192341/age -> geomend:cohort-variable:1c08069deaa0d05c5ef6315a; GSE231509/age -> geomend:cohort-variable:cb16a20c5caf21a84216cfef; GSE237290/age -> geomend:cohort-variable:7dad36aefe2773ee978cb107; GSE272769/age -> geomend:cohort-variable:86924362a4be35d2f96b3c33; GSE58984/age -> geomend:cohort-variable:3b7e5d33d56cc4f25bc9b5ca; GSE92415/age -> geomend:cohort-variable:e424cd0a7380069aec79edec
- `disease` split 8 ways: GSE104674/subject status -> geomend:cohort-variable:8f93060afd7eb2061aa1983c; GSE131411/clinical classification -> geomend:cohort-variable:e841e76e098cdbd890168fd9; GSE137340/diagnosis -> geomend:cohort-variable:81d71d51ce2a148f665320e8; GSE166925/disease -> geomend:cohort-variable:4d2af43c0222aaead2fe393a; GSE189007/disease group -> geomend:cohort-variable:5083e8d932f0bd0a38bc4407; GSE189007/sampling in t2d stage -> geomend:cohort-variable:c6e3cd66cdcddcc7c5c444c9; GSE189007/sampling t2d stage -> geomend:cohort-variable:bbabbb0b4f62410deb8f2355; GSE206171/uc or healthy control#diagnosis -> ('GSE206171', 'uc or healthy control#diagnosis'); GSE231509/diagnosis -> geomend:cohort-variable:81d71d51ce2a148f665320e8; GSE92415/disease -> geomend:cohort-variable:4d2af43c0222aaead2fe393a
- `subject_id` split 6 ways: GSE104674/subject id # -> ('GSE104674', 'subject id #'); GSE131411/patient -> geomend:cohort-variable:5b324eb18b7baba60dde176e; GSE166925/patient_id -> geomend:cohort-variable:39e9ba2b019284520bb45e63; GSE231509/individual -> geomend:cohort-variable:c10eae9350c8b34a93404673; GSE282580/title#subject -> ('GSE282580', 'title#subject'); GSE92415/subject -> geomend:cohort-variable:a6a4545f3efcafb3f23e7bb4
- `treatment` split 4 ways: GSE149322/arm -> geomend:cohort-variable:bffc5aa8cede611b641909df; GSE231509/treatment -> geomend:cohort-variable:cc36b67afb2782c9a9d37149; GSE58984/treatment -> geomend:cohort-variable:6d35450343d12ef3e1082593; GSE92415/treatment -> geomend:cohort-variable:0553c8f281edbacf40d130ad
- `disease_duration` split 4 ways: GSE166925/disease_duration (y) -> geomend:cohort-variable:dba6f8f275df561a54313ed9; GSE189007/duration (yr) -> geomend:cohort-variable:eaf51b02f00bd07b17f8f180; GSE189007/t2d duration -> geomend:cohort-variable:0f7f8f47a70dae6f8d2b8101; GSE206171/diagnose duration (years) -> geomend:cohort-variable:fefa93ebd3094c8f16e30477
- `hba1c` split 4 ways: GSE104674/hba1c (mmol/mol) -> geomend:cohort-variable:77f130e76049118b96374c96; GSE189007/blood glucose#hba1c -> ('GSE189007', 'blood glucose#hba1c'); GSE189007/hba1c (%) of the sample -> ('GSE189007', 'hba1c (%) of the sample'); GSE231509/hba1c, % -> ('GSE231509', 'hba1c, %')
- `organism_part` split 3 ways: GSE119217/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE131411/cell type -> geomend:cohort-variable:3e41b1287152d1fdab42d486; GSE131411/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE137340/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE166925/site_taken -> geomend:cohort-variable:da6ebd04d587decde199d8b7; GSE189007/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE206171/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE231509/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE282580/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE58984/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24; GSE92415/tissue -> geomend:cohort-variable:36f43c599c3a6bdf82e98b24
- `bmi` split 3 ways: GSE104674/bmi (kg/m2) -> geomend:cohort-variable:f96e646eec2ec0e215a1cb84; GSE152111/donor bmi (bmi kg/m2) -> geomend:cohort-variable:6d53200ca7fe7e1f8e15d4a6; GSE189007/bmi (kg/m2) -> geomend:cohort-variable:f96e646eec2ec0e215a1cb84; GSE189007/bmi -> geomend:cohort-variable:2a734a60eae633549bbdc3e5; GSE231509/bmi -> geomend:cohort-variable:2a734a60eae633549bbdc3e5
- `er_status` split 2 ways: GSE237290/er -> geomend:cohort-variable:5b78611b7f7e345df579abbf; GSE58984/er status -> geomend:cohort-variable:bcb38e18e5bc2caa355d0822
- `pr_status` split 2 ways: GSE237290/pr -> geomend:cohort-variable:95e8e25302bb846b8021694e; GSE58984/pgr status -> geomend:cohort-variable:96da3f87ea90051245767af7
- `stromal_til` split 2 ways: GSE237290/til -> geomend:cohort-variable:87ba42bf2aa24d1a578235b2; GSE58984/stromal lymphocytic infiltration -> geomend:cohort-variable:b51d3ecc1fc1f1b961dc6f11
- `recurrence_event` split 2 ways: GSE192341/recurrence -> geomend:cohort-variable:60579aedc897653144d03c25; GSE237290/event.rfi -> geomend:cohort-variable:b46b489674a1b07ce444e1f7
- `pcr` split 2 ways: GSE149322/pcr -> geomend:cohort-variable:c3db0dad17a9d8e2b50d641b; GSE192341/pathological complete response (pcr) -> geomend:cohort-variable:5f0b78f8e0d7f039c04bfc5d
- `sex` split 2 ways: GSE104674/gender -> geomend:cohort-variable:e0666f0f73e5c279de0fbcec; GSE119217/Sex -> geomend:cohort-variable:e0666f0f73e5c279de0fbcec; GSE131411/Sex -> geomend:cohort-variable:e0666f0f73e5c279de0fbcec; GSE137340/Sex -> geomend:cohort-variable:e0666f0f73e5c279de0fbcec; GSE152111/donor gender (m=male; f=female) -> ('GSE152111', 'donor gender (m=male; f=female)'); GSE166925/gender -> geomend:cohort-variable:e0666f0f73e5c279de0fbcec; GSE189007/gender -> geomend:cohort-variable:e0666f0f73e5c279de0fbcec; GSE206171/Sex -> geomend:cohort-variable:e0666f0f73e5c279de0fbcec; GSE231509/Sex -> geomend:cohort-variable:e0666f0f73e5c279de0fbcec; GSE272769/Sex -> geomend:cohort-variable:e0666f0f73e5c279de0fbcec
- `septic_shock_status` split 2 ways: GSE119217/shock_status -> geomend:cohort-variable:ec5312c77f64f0249d9f8154; GSE272769/shock -> geomend:cohort-variable:7234b10729d81bf417636a07
- `ethnic_group` split 2 ways: GSE119217/race_ethnicity -> geomend:cohort-variable:b914ba15b713cefbea542010; GSE189007/population -> geomend:cohort-variable:445a2248d1d7c1874877b59c
- `inflammation_status` split 2 ways: GSE166925/inflammation_status -> geomend:cohort-variable:f990963e9890ffab84e74c91; GSE282580/title#inflammation -> ('GSE282580', 'title#inflammation')
- `mayo_score` split 2 ways: GSE206171/mayoscore -> geomend:cohort-variable:ebab052f68dc3941e862b6de; GSE92415/mayo score -> geomend:cohort-variable:19ecadc25e2cdb37dc5af2eb
- `time_since_treatment_start` split 2 ways: GSE282580/title#week -> ('GSE282580', 'title#week'); GSE92415/visit -> geomend:cohort-variable:552ae77350a6f2c733f453c5
- `fasting_glucose` split 2 ways: GSE189007/blood glucose#glucose -> ('GSE189007', 'blood glucose#glucose'); GSE231509/fasting glucose,_mm -> ('GSE231509', 'fasting glucose,_mm')

Predicted on unsplit parent columns (their parts score as missing): GSE104674/timepoint, GSE189007/blood glucose, GSE189007/phenotype, GSE206171/uc or healthy control
