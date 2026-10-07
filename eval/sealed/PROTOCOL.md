# Sealed-corpus measurement protocol

Written 2026-10-07, before any sealed series was downloaded or run. The
measurement happens once. Nothing in the pipeline changes after a sealed
output has been viewed. A bug found during or after the run is reported as
found, fixed afterwards, and any rerun is reported separately, never as the
headline.

## Corpus and gold

The 16 series in `eval/generalization_corpus.tsv`, in four disease areas
unrelated to the tuning corpus. The gold standard is in
`eval/gold/generalization_{columns,variables}.tsv`: 141 columns in 66
variables, curated 2026-10-02 from the series' characteristics and titles,
before any pipeline output existed, and owner-reviewed. The SOFT family files
are downloaded from NCBI GEO into `work/sealed/raw/` (git-ignored).

## The pipeline, frozen

Git tag `sealed-run`. Prompt versions: repair-3, annotate-2, reconcile-2. The
models are the plugin agents' models: repair Sonnet, annotate Sonnet,
reconcile Opus. Each subagent answers one batch; runs are never mixed. Batch
sizes follow the skill: repair 8, annotate 12, reconcile 6. GEOmend
preprocessing: merge suggestions on, concept candidates and units off
(`preprocess.USE_*`). No registry.

Steps, in workspace `work/sealed`:

1. `colharmonize ingest --workspace work/sealed work/sealed/raw/*_family.soft.gz` (offline)
2. Baselines, before anything reconfigures the GEOmend project:
   `python eval/sealed/baselines.py work/sealed eval/sealed/out`
3. `colharmonize preprocess --workspace work/sealed --store work/ontology/efo-v3.94.0.sqlite`
4. Repair: one run, then `repair apply`
5. `colharmonize candidates --workspace work/sealed --ontology work/ontology/efo-v3.94.0`
   (remote services off; the shared cache is used as is)
6. Annotate: runs 1 and 2, then `annotate apply --runs 1 2`
7. Reconcile: runs 1 and 2, then `reconcile apply --runs 1 2`
8. `colharmonize score`
9. `python eval/sealed/align.py work/sealed`, then score every prediction file
   with `eval/sealed/score.py`

Re-tasking follows the skill. A batch that fails validation has its answer
deleted and is re-tasked, at most twice. If it still fails, its items get no
prediction and are scored as missing. No answer is edited by hand, and there
is no human review.

## Matching gold columns to pipeline columns

`eval/sealed/align.py`, fixed before the run:
- A gold characteristic the run annotated under the same name maps to itself.
- Any other gold column matches the run's repaired column from the same source
  in the same study whose name shares the most words with it. A gold
  characteristic with no shared word can match on snapshot value agreement of
  0.7 or more instead.
- Matching is greedy, one-to-one. Unmatched gold columns score as missing.

Tested on the tuning workspace before the sealed run: 81 of 84 tuning gold
columns matched; the 3 misses were named differently by repair.

## What is reported

All of it, whatever it shows:

- **Pooling:** pairwise precision, recall and F1, all pairs and cross-dataset
  pairs, and B-cubed. For the final output (reconcile run 1), reconcile run 2
  on its own, annotate-only (before reconciliation), and both baselines.
- **Annotation:**
  - primary term
  - predicate
  - term and predicate together
  - NO_MATCH precision and recall
  - qualifier precision and recall
- **Review tiers:** columns, annotation accuracy and pooled-pair precision per
  tier, and the precision of pairs both runs agreed on.
- **Run agreement:** annotation and partition agreement.
- **Process:** batches per stage, re-tasked batches, items left unanswered,
  and gold columns unmatched by alignment.
- **Comparison with tuning:** the same metrics on the tuning set, next to the
  sealed numbers.

Baselines:
- GEOmend's `propose()` grouping, with no model
- pooling by identical normalised column name

Iteration 2 can't run on this corpus (its pipeline was corpus-specific), so it
has no sealed baseline.
