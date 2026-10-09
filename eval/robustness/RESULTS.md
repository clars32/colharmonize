# Robustness to renamed columns: results

Handoff task 7, run 2026-10-09 on the tuning corpus. Annotation alone, with
no reconciliation. Full tables: `out/score.md`.

## Design

- **Renaming:** one Opus subagent paraphrased all 72 characteristic column
  names (`paraphrase_prompt.md`). It saw names only, never values. The rules:
  - keep the meaning and every unit and code
  - change the wording
  - don't make a name more or less specific
  - give repeated names a different paraphrase in each study

  It read only its input file. The paraphrases are kept verbatim in
  `renames.json`. Reviewed for meaning, none was changed. Four land on or near
  an ontology label ("Organism part", "Biological sex", "organism_sex",
  "disease state"), which can only make retrieval easier.
- **Unchanged:** values, study text and the 33 repaired columns.
  `rename_workspace.py` builds `work/ds-tuning-renamed` from the tuning
  workspace without touching it.
- **Control:** the tuning workspace's annotate runs 3 and 4 (prompt
  annotate-2). Regenerating candidates for the original names reproduces
  their candidate table exactly (15,604 rows, the same displayed set), so
  those runs are a valid control.
- **Renamed condition:** the same code and prompt, with new candidates and
  two new annotate runs, also numbered 3 and 4 so candidate shuffling uses
  the same seeds. 18 Sonnet subagents, one batch each. Every answer
  validated on the first try.
- **Remote lookups:** for the original names, ZOOMA and OLS4 results came
  from the cache, and they supply 266 of the displayed candidates. So the
  renamed names were queried live (`--remote`), into a separate cache
  (`work/cache-robustness`). That gave them the same chance. The 31 empty
  OLS4 results were checked by hand; they are genuine, not errors.

## Results

| tuning, annotation alone | original | renamed | Δ, points (95% CI over studies) |
|---|---|---|---|
| gold term retrieved / shown | 88.6% / 84.8% | 86.1% / 82.3% | −2.5 / −2.5 |
| primary term, mean of 2 runs | 75.6% | 73.2% | −2.4 (−7.0 to +1.2) |
| primary term, the 72 renamed columns | 75.7% | 72.9% | −2.8 (−8.3 to +1.4) |
| pooling F1, mean of 2 runs | 80.0% | 80.3% | +0.2 (−4.9 to +5.2) |
| qualifier precision / recall, run of record | 81.0% / 68.0% | 56.5% / 52.0% | — |
| runs agree on primary and predicate | 84.8% | 79.0% | −5.8 |

Run-to-run noise in primary-term accuracy is larger than the effect: run 4
minus run 3 is +6.0 points for the original names and −6.0 for the renamed.

**Renaming costs about 2–3 points of primary-term accuracy, within noise, and
nothing in pooling.** Values and study context carry most of the decision.
That is consistent with the memorization probe (`eval/memorization/`): the
pipeline isn't leaning on remembered names. MetaHarmonizer's 12–24-point drop
came from renaming the targets of a memorized benchmark. That is a different
experiment, so the two numbers are not compared.

Where renaming does hurt:
- **Agreement between runs fell 5.8 points**, so more columns go to review.
- **Qualifiers fell the most,** because they are read from the name
  (decision 14.4 already recommends reading them only from name and values):
  - unit and anchor wording got lost
  - qualifier retrieval recall fell from 81.8% to 63.6%, 2 of 11 qualifiers
- **Seven renamed columns changed primary term in both runs.** Two got worse
  from a lost cue: "PMI (hrs)" and "Cell line name" both went to `none`. One
  got better: "CRLF2 mRNA level strata" now matches gold. Four moved between
  wrong answers.

## Process incident, no effect on the result

Subagents launched as general-purpose agents can run shell commands, and
several wrote helper scripts into the session's shared scratchpad. Three
wrote `show.py` at the same moment and overwrote one another, so run 3
batch 5 printed run 3 batch 7's input items before noticing and switching.

An audit of all 18 transcripts found the following:
- No agent read another run's files.
- No agent read any answer file, gold file or tuning workspace file.
- Run 4 batches 7 and 8 each printed only their own items.

Inputs are not answers, so run independence holds.

The installed plugin agents can't do this: their tools are Read and Write
only. The fix is for the stand-in prompt to say so (decisions log 15.3).
