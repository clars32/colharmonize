# Subagent cost per stage

From Claude Code transcripts (`collect.py`). Input counts every prompt token, cached or not; cached reads are shown separately because they are much cheaper. Agents run in parallel, so a stage's wall time is about its slowest agent, not the sum.

| workspace | stage | model | agents | items | input tokens (cached reads) | output tokens | input per item | agent-minutes | slowest agent |
|---|---|---|---|---|---|---|---|---|---|
| ds-tuning | repair | sonnet-5-5 | 4 | 26 | 0.87M (0.58M) | 76k | 33k | 9 | 3.0 min |
| ds-tuning | annotate | sonnet-5-5 | 36 | 420 | 20.07M (15.30M) | 332k | 48k | 58 | 2.2 min |
| ds-tuning | reconcile | opus-5-5 | 11 | 52 | 2.36M (1.29M) | 233k | 45k | 35 | 7.8 min |
| ds-tuning-renamed | annotate | sonnet-5-5 | 18 | 210 | 13.76M (11.72M) | not recorded | 66k | 25 | 2.2 min |
| e2e | repair | sonnet-5-5 | 1 | 3 | 0.16M (0.09M) | 9k | 52k | 1 | 1.1 min |
| e2e | annotate | sonnet-5-5 | 5 | 45 | 2.63M (2.19M) | 33k | 58k | 4 | 1.3 min |
| e2e | reconcile | opus-5-5 | 2 | 12 | 0.31M (0.19M) | 13k | 26k | 2 | 1.1 min |
| repair-pilot | repair | sonnet-5-5 | 2 | 12 | 0.36M (0.25M) | 26k | 30k | 3 | 2.0 min |
| sealed | repair | sonnet-5-5 | 4 | 32 | 1.22M (0.95M) | 86k | 38k | 10 | 3.1 min |
| sealed | annotate | sonnet-5-5 | 25 | 294 | 14.63M (11.34M) | 233k | 50k | 31 | 1.7 min |
| sealed | reconcile | opus-5-5 | 12 | 72 | 2.02M (1.22M) | 111k | 28k | 17 | 2.4 min |
