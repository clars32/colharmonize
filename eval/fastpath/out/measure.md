# Easy-first fast path: what each rule would annotate

A fast-path column gets predicate exact and the matched term, with no qualifiers, and no subagent sees it. "Right" means primary term and predicate both match gold. "Pipeline" is the final output on the same gold columns.

| corpus | rule | columns taken (of all) | gold columns taken | fast path right | pipeline right on them |
|---|---|---|---|---|---|
| tuning | label + values agree | 12 of 105 | 6 | 6/6 (100%) | 6/6 (100%) |
| tuning | synonym + values agree | 13 of 105 | 7 | 6/7 (86%) | 7/7 (100%) |
| tuning | label only (no value guard) | 25 of 105 | 17 | 14/17 (82%) | 16/17 (94%) |
| sealed (post hoc) | label + values agree | 14 of 141 | 14 | 12/14 (86%) | 12/14 (86%) |
| sealed (post hoc) | synonym + values agree | 19 of 141 | 19 | 17/19 (89%) | 17/19 (89%) |
| sealed (post hoc) | label only (no value guard) | 29 of 141 | 27 | 20/27 (74%) | 24/27 (89%) |

## Where the chosen rule (label + values agree) disagrees with gold

| corpus | column | fast path | gold |
|---|---|---|---|
| sealed (post hoc) | GSE192341 sample_id | exact sample ID | none (none) |
| sealed (post hoc) | GSE192341 unresolved characteristic#n-stage | exact N stage | broad N stage |
