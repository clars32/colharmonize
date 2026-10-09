# Memorization probe: protocol

Written 2026-10-08, before any probe answer existed. Handoff task 5, after
MetaHarmonizer (Li et al., bioRxiv 2026.06.13.732088), which found that LLMs
had memorized a public benchmark and lost 12–24 points when its targets were
renamed.

## Question

Do the models colharmonize uses remember the sample characteristics of the
tuning and sealed series? If a model can list a series' characteristic keys
and values from its accession alone, its annotations of that series may draw
on memory of the series or of published curations of it, and the sealed
numbers may be inflated.

## Design

- **Series:** all 29: 13 tuning and 16 sealed. GSE1397 and GSE4119 have no
  characteristics (their variables are in titles), so they are probed but
  score only on title.
- **Models:** Sonnet (repair, annotate) and Opus (reconcile), the pipeline's
  two, through Claude Code subagents.
- **Input:** the accession only. No title, summary, data or file access.
- **Batches:** the 29 accessions shuffled with a fixed seed and dealt into 4
  batches (`batches.json`), mixing corpora so a batch reveals no theme. One
  subagent per batch per model: 8 runs. The same batches go to both models.
- **Tools:** the prompt (`prompt.md`) forbids every tool. A run that used any
  tool is discarded and reported, not rerun silently.
- **Answers:** saved verbatim from each subagent's reply to
  `answers/<model>_batch<n>.json`.

## Scoring (`score.py`)

Truth is the characteristic snapshot taken at corpus selection
(`eval/snapshots/*_characteristics.json`).

- **Key recall, strict:** share of a series' true keys that some predicted key
  equals after `normalise_key` (case, whitespace, dashes, trailing
  punctuation).
- **Key recall, loose:** the same, matched by `text.same_meaning` on the
  `loose` forms (one word set contains the other, or Jaccard >= 0.5). Generous
  on purpose: `age` matches `age at diagnosis`.
- **Key precision**, strict and loose: share of predicted keys that match a
  true key.
- **Value recall:** for true keys with at most 30 distinct non-numeric values,
  the share of those values listed (casefolded, trimmed) under the matched
  predicted key. Micro-averaged over values.
- **Title similarity:** word Jaccard between the predicted and true titles.

**Control.** A model that guesses generic keys (`age`, `sex`, `tissue`) scores
some recall on any series. Each series' answer is also scored against every
other series in the same corpus, and the mean of those is its control. Same
corpus is the conservative choice: those series share a disease area and its
vocabulary. **Memorization is the excess over control**, not the raw recall.

## What would count as a signal

Decided before the run:
- A series is **recalled** when strict key recall is at least 50% and exceeds
  its control by at least 30 points.
- The corpus-level result is the mean excess over control, per model, with
  strict key recall as the headline and value recall beside it.
- If any sealed series is recalled, the sealed annotation numbers for that
  series are reported separately in `RESULTS.md` as possibly inflated.
