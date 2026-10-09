# Cost: tokens and time per stage

Handoff task 16, 2026-10-09. `collect.py` reads the Claude Code subagent
transcripts kept under `~/.claude/projects/`. They cover every pipeline run
of iteration 3. Per-agent numbers are in `agents.tsv` and per-stage totals in
`summary.md`. No transcript text is copied.

## The sealed run (16 series, 1,623 samples, 141 columns)

| stage | model | agents | items | input tokens (of which cached reads) | output tokens | slowest agent |
|---|---|---|---|---|---|---|
| repair | Sonnet | 4 (2 batches, re-tasked twice) | 32 | 1.22M (0.95M) | 86k | 3.1 min |
| annotate | Sonnet | 25 (2 runs × 12, plus 1 retry) | 294 | 14.63M (11.34M) | 233k | 1.7 min |
| reconcile | Opus | 12 (2 runs × 6) | 72 | 2.02M (1.22M) | 111k | 2.4 min |
| **total** | | **41** | | **17.9M (13.5M, 76%)** | **430k** | about 7 min of agent time on the critical path |

- **Per gold column:** about 130k input tokens, most of them cached reads,
  and 3k output tokens.
- **Agent-minutes in all:** 58. Agents run in parallel within a stage, so a
  stage takes about as long as its slowest agent. Orchestration,
  validation, and the command-line steps add a few minutes, and the
  embedding-based candidate step about 1 minute.
- **Billing:** the pipeline runs under Claude Code, with no API key. Usage
  counts against the Claude plan rather than being billed per token, so
  this reports tokens, not dollars.

## Patterns

- **Annotation is the cost:** 82% of input tokens. Each item costs about
  50k input tokens, because an agent re-reads its batch over several tool
  turns. Most of that is cached.
- **Stand-ins that run scripts cost more.** The renamed-columns annotators
  used 66k input tokens per item, against 48–50k. They wrote and ran helper
  scripts, which meant more turns. Limiting stand-ins to Read and Write
  (decisions log 15.3) should also cut cost.
- **Reconciliation uses the larger model on few items.** Opus, 72 items, 11%
  of input tokens. On tuning it was the slowest stage (7.8 minutes for the
  biggest group).
- **Cutting cost:** the fast path would save about 5% (`eval/fastpath/`).
  Bigger annotate batches would mean fewer re-reads of shared context.
  Neither is needed at this scale.

## Caveat

The Claude Code version used on 2026-10-09 records only each call's
start-of-stream output count in the transcript. That session's output
tokens (the renamed-columns run) are therefore marked "not recorded".
Input tokens and times are unaffected.
