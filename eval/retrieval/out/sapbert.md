# SapBERT as a third embedding model: candidate recall

| corpus | models | gold term in pool | gold term shown | qualifiers in pool / shown | candidates (shown) |
|---|---|---|---|---|---|
| tuning | mini + bge (pipeline) | 88.6% | 84.8% | 81.8% / 81.8% | 15604 (5898) |
| tuning | mini + bge + SapBERT | 91.1% | 81.0% | 90.9% / 90.9% | 22140 (5898) |
| sealed (post hoc) | mini + bge (pipeline) | 70.6% | 66.4% | 14.3% / 14.3% | 20761 (7906) |
| sealed (post hoc) | mini + bge + SapBERT | 78.2% | 73.9% | 14.3% / 14.3% | 29586 (7906) |

Gold term shown if the property-space display cap were larger (entity cap 16):

| corpus | models | cap 40 | cap 50 | cap 60 |
|---|---|---|---|---|
| tuning | mini + bge (pipeline) | 84.8% | 84.8% | 84.8% |
| tuning | mini + bge + SapBERT | 81.0% | 86.1% | 87.3% |
| sealed (post hoc) | mini + bge (pipeline) | 66.4% | 66.4% | 68.1% |
| sealed (post hoc) | mini + bge + SapBERT | 73.9% | 73.9% | 74.8% |

Gold primary terms not retrieved (study/gold column):

- tuning, mini + bge (pipeline): GSE11877/E2A-PBX, t(1;19); GSE11877/MLL; GSE11877/amplification set; GSE11877/hybridization set; GSE1397/title#replicate; GSE1397/source_name#source material; GSE17459/gene expression dataset; GSE222365/cell type; GSE61804/flt3-itd
- tuning, mini + bge + SapBERT: GSE11877/E2A-PBX, t(1;19); GSE11877/amplification set; GSE11877/hybridization set; GSE1397/title#replicate; GSE1397/source_name#source material; GSE17459/gene expression dataset; GSE222365/cell type
- sealed (post hoc), mini + bge (pipeline): GSE237290/pam50; GSE237290/er; GSE237290/pr; GSE237290/til; GSE237290/time.os; GSE237290/time.rfi; GSE237290/event.rfi; GSE237290/event.dss; GSE58984/time to ddfs; GSE192341/subtype; GSE192341/rfs (years); GSE149322/pcr; GSE149322/arm; GSE131411/cell type; GSE166925/nancy_score; GSE206171/uc or healthy control#diagnosis; GSE206171/uc or healthy control#activity; GSE206171/mayoscore; GSE92415/visit; GSE92415/wk6response; GSE282580/title#week; GSE152111/donor gender (m=male; f=female); GSE104674/timepoint#day; GSE104674/timepoint#zeitgeber_time; GSE231509/fasting glucose,_mm; GSE231509/fasting insulin,_miu/l; GSE231509/fasting c-peptid,_ng/ml; GSE231509/hba1c, %; GSE189007/phenotype#notes; GSE189007/phenotype#uacr; GSE189007/blood glucose#glucose; GSE189007/blood glucose#hba1c; GSE189007/hba1c (%) of the sample; GSE189007/sampling in t2d stage; GSE189007/sampling t2d stage
- sealed (post hoc), mini + bge + SapBERT: GSE237290/pam50; GSE237290/time.rfi; GSE237290/event.rfi; GSE237290/event.dss; GSE192341/subtype; GSE149322/arm; GSE131411/cell type; GSE166925/nancy_score; GSE206171/uc or healthy control#diagnosis; GSE206171/uc or healthy control#activity; GSE92415/wk6response; GSE282580/title#week; GSE152111/donor gender (m=male; f=female); GSE104674/timepoint#day; GSE104674/timepoint#zeitgeber_time; GSE231509/fasting glucose,_mm; GSE231509/fasting insulin,_miu/l; GSE231509/fasting c-peptid,_ng/ml; GSE231509/hba1c, %; GSE189007/phenotype#notes; GSE189007/phenotype#uacr; GSE189007/blood glucose#glucose; GSE189007/blood glucose#hba1c; GSE189007/hba1c (%) of the sample; GSE189007/sampling in t2d stage; GSE189007/sampling t2d stage
