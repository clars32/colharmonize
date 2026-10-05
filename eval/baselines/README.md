# Baselines

Prediction files scored with `colharmonize eval`, so iteration 3 is measured
like for like against what came before.

| File | Source | Scores |
|---|---|---|
| `iteration2_ds_tuning.tsv` | Iteration 2's published `mappings.tsv`. Variable = IRI; predicate `exact` or `none`; no qualifiers | pooling and annotation |
| `geomend_propose_ds_tuning.tsv` | GEOmend 0.0.2 default grouping (`propose()`, no model) over the 64 Down syndrome series | pooling only |

Regenerate with `python eval/baselines/iteration2.py` and
`python eval/baselines/geomend_propose.py`. The reports (`*.md`) come from:

```bash
colharmonize eval --gold-columns eval/gold/ds_tuning_columns.tsv \
  --gold-variables eval/gold/ds_tuning_variables.tsv \
  --predictions eval/baselines/iteration2_ds_tuning.tsv --report eval/baselines/iteration2_ds_tuning.md
```

Scored against the final tuning gold (owner review completed 2026-10-05).
The sealed generalization corpus
has no baselines yet: iteration 2 never ran on it, and GEOmend's grouping
needs the corpus ingested, which waits for the single final measurement.
