# Alias dictionary for candidate retrieval: protocol

Written 2026-10-12, before any alias existed. Handoff task 10.

## Idea

MetaHarmonizer (Li et al., bioRxiv 2026.06.13.732088) adds an LLM-written
alias dictionary to its target schema. The aliases are written once, offline,
and used only for lexical and embedding retrieval, so the model is never
asked at match time. Six top-tier models' dictionaries performed alike; the
failure mode of larger models was correct but off-task aliases that pull
embedding retrieval toward wrong targets (`docs/related-work.md`).

## Aliases

- **Terms:** the 1,998 property-space terms that annotate chooses its
  primary term from (`property_space.build`). Entity and unit terms are out
  of scope.
- **Writer:** one subagent per batch of 100 terms, Claude Haiku, with only
  the Read and Write tools, writing nothing but its answer file. Haiku because
  MetaHarmonizer found it on the cost-accuracy frontier. Each subagent sees a
  term's label, definition (first 300 characters) and existing exact synonyms,
  and nothing from either corpus.
- **Prompt:** `make_tasks.py`. Its examples (systolic blood pressure,
  intraocular pressure, visual acuity) appear in neither gold standard.
- **Validation, in code (`validate.py`), before any measurement:**
  - at most 5 aliases per term, each 2–60 characters
  - drop an alias equal, after `loose()` normalization, to the term's own
    label or exact synonyms (no new information)
  - drop an alias equal to another property-space term's label or exact
    synonym, or proposed for more than one term (ambiguous)
  - answers are never edited by hand; a failed batch is re-tasked

## Use in retrieval (`measure.py`)

The pipeline code is unchanged; the script extends the space index in memory.
- `alias_exact`: a column name form that equals an alias retrieves its term,
  like `exact_space`.
- `<model>_alias`: each embedding model also ranks alias strings against the
  column name; a term's rank is its best alias's rank among unique terms
  (top 50).

Both are new sources, so they also raise a term's source count, which orders
the display.

## Measures

Candidate recall, as `candidates.evaluate_recall`:
- gold primary term in the pool, and among the terms shown to the annotator
- on tuning, against the pipeline (mini + bge, the recorded 88.6% / 84.8%;
  the control run must reproduce it)
- on sealed, post hoc only

Also: candidates per column, aliases kept and dropped by each rule, and the
gold terms each configuration newly finds or loses.

## Decision rule

Fixed before any alias exists. Aliases are adopted into `candidates.py` if,
on tuning:
- **shown recall rises,** since display is what the annotator sees, and
- **pool recall doesn't fall.**

Because tuning has about 80 gold primary terms, a gain of one or two terms is
within noise. A gain is reported as such and, if adopted, measured again on
the next sealed corpus. Sealed numbers are reported but never decide.
