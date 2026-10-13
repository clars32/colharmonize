# annotate-3 on tuning: results

Handoff task 13, run 2026-10-12 under `PROTOCOL.md`, which was committed
before any answer existed. Full tables: `out/score.md`.

## Process

- **Runs:** 18 Sonnet subagents, one batch each, for two annotate-3 runs (6
  and 7) on the tuning workspace copy.
- **First launch:** it hit the account session limit before any answer was
  written. All 18 were relaunched after the reset.
- **Validation:** every answer passed on the first try.
- **Audit:** every transcript shows Read on the agent's own batch and Write on
  its own answer. One agent also ran a single `grep` on its own batch file,
  against the Read and Write instruction. Harmless; noted.

## Results

Annotation alone, mean of two runs per prompt, with paired bootstrap intervals
over studies:

| tuning | annotate-2 (runs 3, 4) | annotate-3 (runs 6, 7) | Δ, points (95% CI) |
|---|---|---|---|
| qualifier precision | 72.1% | 87.7% | **+15.6 (+6.3 to +48.9)** |
| qualifier recall | 72.0% | 72.0% | 0.0 (−4.4 to +16.7) |
| term and predicate | 70.8% | 71.4% | +0.6 (−1.4 to +3.1) |
| pooling F1 | 80.0% | 81.8% | +1.8 (−6.6 to +9.3) |
| runs agree on primary and predicate | 84.8% | 86.7% | — |

**The rule is met, so annotate-3 is adopted** as the pipeline's annotate
prompt (`PROMPT_VERSION = "annotate-3"`):
- Qualifier precision rose.
- Recall, term-and-predicate accuracy and pooling did not fall.

Most qualifiers that annotate-2 added and gold lacks are gone; recall is
unchanged.

## Caveats

- **Tuning has few gold qualifiers,** so the interval is wide.
- **Tuning favors the current prompt's conventions** (decisions log 15.8).
- **This doesn't confirm the sealed problem is fixed.** The sealed qualifier
  drop (13.1, 14.3) was driven by survival endpoints and study-summary
  context, which tuning lacks. The next sealed corpus (task 9) is the real
  test.
- **The tuning workspace's own runs of record stay annotate-2.**
  Regenerating them would mark review decisions stale. A new workspace uses
  annotate-3.
