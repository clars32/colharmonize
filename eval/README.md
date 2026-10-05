# Evaluation data

Self-contained so it can move to `geomend-research` once access is arranged.

## Generalization corpus (sealed 2026-10-02)

`generalization_corpus.tsv`: 16 human GEO series in four disease areas unrelated to
the Down syndrome tuning corpus (breast cancer, sepsis, inflammatory bowel disease,
type 2 diabetes), 9 array and 7 RNA-seq. Within each area, related series share
concepts under different names, encodings and units, so pooling is testable. Across
areas, sex, age, tissue, time point and identifiers recur.

Selected from NCBI E-utilities search results (`corpus_selection/search.py`) and sample
characteristics only (`corpus_selection/profile.py`; full values via `corpus_selection/values.py`, snapshotted in `snapshots/`). No candidate list, annotation or
matching output had been produced for any of these series when they were chosen.

Rules:
- The gold standard for this corpus is curated **before** any candidate generation
  runs on it.
- It is measured **once**, after the pipeline is frozen. Nothing is tuned in response.
- The Down syndrome corpus (64 series) remains the tuning set.
