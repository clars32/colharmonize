# Alias dictionary: candidate recall

| corpus | retrieval | gold term in pool | gold term shown | gold terms | candidates (shown) | from aliases |
|---|---|---|---|---|---|---|
| tuning | pipeline | 88.6% | 84.8% | 79 | 15604 (5898) | 0 |
| tuning | pipeline + aliases | 88.6% | 82.3% | 79 | 21783 (5898) | 8363 |
| tuning | pipeline + exact aliases only (exploratory) | 88.6% | 84.8% | 79 | 15604 (5898) | 0 |
| sealed (post hoc) | pipeline | 70.6% | 66.4% | 119 | 20761 (7906) | 0 |
| sealed (post hoc) | pipeline + aliases | 73.9% | 68.1% | 119 | 29049 (7906) | 11385 |
| sealed (post hoc) | pipeline + exact aliases only (exploratory) | 70.6% | 66.4% | 119 | 20761 (7906) | 0 |

Gold columns that change (accession, gold column):

- tuning, pipeline + aliases: newly in pool none; lost from pool none
- tuning, pipeline + aliases: newly shown none; no longer shown [('GSE16176', 'condition'), ('GSE222365', 'study')]
- tuning, pipeline + exact aliases only (exploratory): newly in pool none; lost from pool none
- tuning, pipeline + exact aliases only (exploratory): newly shown none; no longer shown none
- sealed (post hoc), pipeline + aliases: newly in pool [('GSE131411', 'cell type'), ('GSE237290', 'er'), ('GSE237290', 'pr'), ('GSE237290', 'time.os')]; lost from pool none
- sealed (post hoc), pipeline + aliases: newly shown [('GSE237290', 'er'), ('GSE237290', 'pr'), ('GSE237290', 'time.os')]; no longer shown [('GSE137340', 'outcome')]
- sealed (post hoc), pipeline + exact aliases only (exploratory): newly in pool none; lost from pool none
- sealed (post hoc), pipeline + exact aliases only (exploratory): newly shown none; no longer shown none
