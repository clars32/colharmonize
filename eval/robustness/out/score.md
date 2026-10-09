# Renamed columns: annotation alone, tuning gold

84 gold columns, 72 of them renamed characteristics; the other 12 (repaired title and source-name columns) keep their names in both conditions.

| condition | run of record | pooling P | R | F1 | primary term | primary, renamed columns | primary, unrenamed | term and predicate | qualifiers P / R | runs agree |
|---|---|---|---|---|---|---|---|---|---|---|
| original | 3 | 76.9% | 79.5% | 78.2% | 72.6% | 72.2% | 75.0% | 66.7% | 81.0% / 68.0% | 84.8% |
| original | 4 | 84.3% | 79.5% | 81.9% | 78.6% | 79.2% | 75.0% | 75.0% | 60.0% / 72.0% | 84.8% |
| renamed | 3 | 80.0% | 77.3% | 78.6% | 76.2% | 76.4% | 75.0% | 67.9% | 56.5% / 52.0% | 79.0% |
| renamed | 4 | 87.2% | 77.3% | 81.9% | 70.2% | 69.4% | 75.0% | 65.5% | 59.3% / 64.0% | 79.0% |

Renamed minus original, mean of the two runs, paired bootstrap over 13 studies:

| metric | original | renamed | Δ, points | 95% CI |
|---|---|---|---|---|
| primary term, all columns | 75.6% | 73.2% | -2.4 | -7.0 to +1.2 |
| primary term, renamed columns | 75.7% | 72.9% | -2.8 | -8.3 to +1.4 |
| primary term, unrenamed columns | 75.0% | 75.0% | +0.0 | +0.0 to +0.0 |
| pooling F1 (annotation alone) | 80.0% | 80.3% | +0.2 | -4.9 to +5.2 |

Run-to-run noise, primary term (run 4 − run 3): original +6.0, renamed -6.0 points.

## Renamed columns whose primary term changed in both runs

| column | new name | gold | original (runs 3, 4) | renamed (runs 3, 4) |
|---|---|---|---|---|
| GSE11877 CNS status | Central nervous system state | broad disease staging | broad illness severity status / broad illness severity status | broad central nervous system cancer / broad central nervous system disorder |
| GSE11877 testicular involvement | Involvement of the testes | none (none) | indicator testicular cancer / indicator testicular cancer | indicator testicular disorder / indicator testicular disorder |
| GSE17459 crlf2 expression levels stratification | CRLF2 mRNA level strata | broad transcriptome measurement | broad cytokine receptor-like factor 2 measurement / broad cytokine receptor-like factor 2 measurement | broad transcriptome measurement / broad transcriptome measurement |
| GSE185192 cell line | Cell line name | exact cultured cell | exact cultured cell / exact cultured cell | none (none) / none (none) |
| GSE222365 sample type | Specimen category | broad material sample | indicator sample pooling / indicator sample pooling | broad specimen / broad specimen |
| GSE222365 study | Source study | exact cohort | exact experimental stage / exact experimental stage | broad experimental stage / none (none) |
| GSE5390 Post mortem interval (hours) | PMI (hrs) | broad duration | broad duration / broad duration | none (none) / none (none) |
