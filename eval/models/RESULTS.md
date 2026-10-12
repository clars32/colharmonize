# Cross-model agreement: results

Handoff task 15, run 2026-10-12 under `PROTOCOL.md`, which was committed
before any Opus answer existed. Full tables: `out/score.md`.

## Process

- **Runs:** 21 Opus subagents, one batch each.
- **First attempt:** it failed outright. One agent hit the account session
  limit after writing its answer, and the other 20 couldn't reach the API. The
  20 batches without answers were relaunched, after `tasks status` was
  checked as the handoff requires.
- **Retry:** one tuning item failed validation (a unit qualifier gave more
  than one of ref, name and text). It was re-tasked once and passed.
- **Audit:** every transcript shows Read on the agent's own batch, Write on
  its own answer, and nothing else.

## Results

Outcome: whether the Sonnet run of record is right on primary term and
predicate, on gold columns. AUC measures how well agreement with a partner
run separates right answers from wrong ones.

| | tuning (82 columns) | sealed, post hoc (119 columns) |
|---|---|---|
| Sonnet run-of-record accuracy | 68.3% | 76.5% |
| Opus accuracy, same prompt | **58.5%** | 78.2% |
| same-model agreement, AUC | 0.69 | 0.62 |
| cross-model agreement, AUC | 0.53 | 0.73 |
| **cross minus same** (95% CI over studies) | **−0.17 (−0.29 to −0.01)** | **+0.11 (+0.04 to +0.18)** |
| wrong answers flagged: same / cross | 10 / 6 of 26 | 8 / 14 of 28 |
| exploratory: three-run count (0–2 partners agree), minus same | −0.04 (−0.12 to +0.08) | +0.10 (+0.04 to +0.17) |

**Under the pre-registered rule, cross-model agreement is not adopted.**
It helped on sealed, but it was significantly worse on tuning.

## Why the corpora disagree

On tuning, Opus is 10–18 points less accurate than Sonnet. On sealed it is
as accurate. The ten tuning columns that Sonnet gets right and Opus gets
wrong are mostly convention calls:
- exact vs broad on the CRLF2 columns
- a more specific term: "somatic genotype" for genotype, "compound based
  treatment" for treatment
- "chromosomal aberration" where gold says "translocation"

The annotate prompt was tuned on this corpus with Sonnet (decisions log 6.3),
so the tuning gold and the prompt share Sonnet's conventions. A second model
disagrees with those conventions there, and that disagreement says nothing
about errors. On sealed, which no prompt was tuned on, Opus disagrees where
Sonnet is wrong: it flags half of Sonnet's errors, against 29% for a second
Sonnet run.

## What to do with it

- **Run 2 stays Sonnet for now**, as the rule says.
- **Pre-register the three-run count for the next sealed corpus** (task 9):
  two Sonnet runs plus one Opus run. Its signal is the number of partners
  that agree with the run of record. It is the only signal so far that
  doesn't lose on tuning and gains on unseen data. That evidence is
  exploratory, and the new corpus would make it confirmatory.
  - Cost: a third annotate run adds about 40% to a run's input tokens
    (annotation is 82% of them; `eval/cost/`), more because it is Opus.
- **A side finding for prompt work:** the tuning corpus favors whichever
  model the prompt was tuned with. Model comparisons on tuning are biased
  toward Sonnet. Prompt changes measured there (annotate-3, task 13) should be
  checked on unseen data before being trusted.
