# Cross-model agreement: protocol

Written 2026-10-09, before any Opus annotate answer existed. Handoff task 15.

## Question

Agreement between two Sonnet annotate runs doesn't flag wrong annotations on
the sealed corpus: AUC 0.53 (decisions log 15.2). Two runs of one model tend
to make the same mistakes. Does agreement between Sonnet and a different
model, Opus, separate right annotations from wrong ones better?

## Runs

- **New:** one Opus annotate run per corpus:
  - prompt annotate-2, with the same candidates and the batch size (12) of
    the existing runs
  - one batch per subagent
  - stand-ins limited to the Read and Write tools (decisions log 15.3)
- **Isolation:** the runs go into copies of the workspaces
  (`work/ds-tuning-models`, `work/sealed-models`, made by `setup.py`), so
  neither original workspace changes.
- **Sealed is post hoc.** The sealed corpus is spent. Results on it are
  labeled post hoc, and the decision below is confirmed on the next sealed
  corpus.

## Comparison

On gold columns, the outcome is whether the run of record's annotation is
right, meaning both the primary term and the predicate match gold. The run of
record is Sonnet: tuning run 3, sealed run 1.

| signal | tuning partner | sealed partner |
|---|---|---|
| same-model agreement (now) | Sonnet run 4 | Sonnet run 2 |
| cross-model agreement | Opus run 5 | Opus run 3 |

"Agree" means primary term and predicate both match, as in `annotate.combine`.

Reported per corpus:
- AUC of agreement for correctness
- share of wrong annotations flagged (the runs disagree)
- accuracy where the runs agree
- share of columns the runs agree on

The cross minus same AUC difference gets a paired bootstrap over studies.
Opus's own accuracy is reported too, as a side result.

## Decision rule

Fixed before the runs. Cross-model agreement replaces same-model agreement
(Opus as annotate run 2) if both hold:
- its sealed AUC is higher, with the paired interval excluding zero
- its tuning AUC is not lower by more than the tuning interval allows

Otherwise run 2 stays Sonnet. If Opus is clearly more accurate than Sonnet as
an annotator, that is reported separately. Choosing the run-of-record model is
a different decision.
