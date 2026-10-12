# annotate-3 on tuning: protocol

Written 2026-10-12, before any annotate-3 answer existed. Handoff task 13.

## Change

`annotate3.py` applies the four instruction changes recommended in decisions
log 14.4 to annotate-2, by exact replacement:
1. Qualifiers come from the column's name and values. The study summary is
   not a source.
2. A qualifier never restates the primary term, names the study's disease,
   or describes the values.
3. An `object_class` example that is neither a gene nor a lesion: the cell
   type in "eosinophil percentage".
4. Prefer a term for the whole concept as primary: "waist circumference",
   not "circumference" plus object_class "waist".

Every example comes from neither corpus. The gold-convention questions in
14.4 are the owner's to settle, and this change doesn't depend on them.

## Runs

- Two annotate-3 runs (6 and 7) on the tuning set, in
  `work/ds-tuning-models`, with the same candidates as the annotate-2 runs of
  record (3 and 4).
- Sonnet, one batch per subagent, stand-ins limited to Read and Write.

## Measures

Annotation alone, against the tuning gold, by `eval/prompts/score.py`:
- qualifier precision and recall
- primary term, predicate, and the two together
- pooling F1
- agreement between the two runs

Each is the mean of the two runs per prompt, with paired bootstrap intervals
over studies.

## Decision rule

Fixed before the runs. annotate-3 replaces annotate-2 if both hold:
- **Qualifier precision rises**, the problem 14.3 and 14.4 found.
- **Nothing else falls past noise:** term-and-predicate accuracy and pooling
  F1 don't fall by more than run-to-run noise. On tuning that noise is about
  6 points of primary-term accuracy (decisions log 15.3).

Tuning favors the conventions of the current prompt (decisions log 15.8). So
a gain here counts only as a reason to carry annotate-3 to the next sealed
corpus, where it is measured again.
