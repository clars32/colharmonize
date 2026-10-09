# Handoff brief: colharmonize, iteration 3

Written 2026-10-08 for a fresh Claude instance, updated 2026-10-09. Read
this first, then the root `../BRIEFING.md` for the stable background (settled
decisions, environment, traps).

## What this is

**colharmonize** decides which sample-metadata columns pool across GEO
studies, and what each means. Every column gets:
- an EFO v3.94.0 term
- a predicate: exact, broad, indicator or none
- qualifiers: subject, object_class, event_time_anchor, method, unit

Pipeline:
1. ingest (through GEOmend)
2. preprocess
3. repair
4. candidates
5. annotate (two runs)
6. reconcile (two runs)
7. score (review tiers)
8. review page and overlay
9. publish (variables.tsv, columns.tsv, SSSOM)
10. registry

**GEOmend** (`../GEOmend`, Preston Raab's tool, v0.0.8) reads, profiles and
exports GEO metadata. colharmonize is a separate repository and reads
GEOmend only through `src/colharmonize/geomend_bridge.py`.

Read these, in order:
1. `README.md`
2. `docs/decisions_log.md`: every judgment call; sections 13–15 are the latest
3. `eval/sealed/PROTOCOL.md` and `eval/sealed/RESULTS.md`
4. `docs/geomend-upstream-proposal.md`
5. `plugin/skills/harmonize/SKILL.md`: how a run is driven

Plain-language overview for people: https://claude.ai/code/artifact/dd493462-a20a-4e51-9bcb-c7905db2caf7

## Where things stand

- **Sealed corpus**, 16 series, measured once at tag `sealed-run`:
  - pooling precision 100%, recall 70.9%, F1 83.0%
  - baselines: identical names 53.8%, GEOmend `propose()` 45.8%
  - primary term 71.5%
  - qualifiers 28.9% / 37.9%
- **Tuning set**, 13 series: pooling F1 82.6%, against 67.7% for iteration 2.
- **Built since the sealed run** (measured on tuning only):
  - per-item retry
  - qualifiers taken from what all member columns share (tuning qualifiers
    61.5/64.0 → 89.5/68.0)
  - a fix for the scorer's qualifier parser
- **Pushed but no PR yet:** a GEOmend fix for keys with punctuation, on branch
  `fix/characteristic-key-punctuation`.
- **Evaluation checks, 2026-10-09** (decisions log 15; `eval/memorization`,
  `eval/stats`, `eval/robustness`, `eval/curation`):
  - no model recalls these series' metadata
  - pooling beats every baseline with intervals that exclude zero; the
    gains from reconciliation and merge links are within noise
  - no confidence signal discriminates annotation correctness on sealed
    (tier AUC 0.54); partition agreement catches false merges, not missed ones
  - renamed columns cost about 2.4 points of primary term, within noise
  - a blind 44-column curation sheet is ready for a person
- **Tests:** `./.venv/bin/python -m pytest -q` passes 77.

## Constraints: do not break these

- **Claude Code only; no API key.** Judgments are made by subagents answering
  task files. Use one subagent per batch and never mix runs: independence is
  the confidence signal.
  - Models: Sonnet for repair and annotate, Opus for reconcile.
  - The plugin isn't installed, so launch general-purpose agents with the
    prompt template in `plugin/agents/*.md`. **Add: use only the Read and
    Write tools, and write nothing but the answer file.** The plugin's agents
    have only those tools; stand-ins that can run shell commands share the
    session scratchpad and collided there once (decisions log 15.3).
- **Never edit answer files by hand.** Re-task with
  `colharmonize tasks retry STAGE --run N`. Apply with `--drop-failed` only
  after two retries, and report what was dropped.
- **Session limits:** a subagent may report a session-limit error after
  writing its answer. Run `tasks status` before relaunching anything.
- **The sealed corpus is spent.** Never re-measure on it as a headline. Label
  anything new on it "post hoc".
- **Prompts:** examples must never come from the tuning or sealed corpora.
- **Testing changes:** measure on tuning, then on a new unseen corpus.
- **Ontology:** pin EFO v3.94.0, and validate every identifier and label
  against the pinned file, never a live API. Store full IRIs. NO_MATCH (no
  term found) is a valid answer.
- **Gold rules** (confirmed by the owner):
  - Pool only when no information is lost.
  - Columns with values on the same samples never pool unless the values are
    identical.
  - Assumed conventions are flagged, not hidden.
  - Recoding a value, such as "Down syndrome" → "Trisomy 21", is fine.
- **GEOmend:** everything colharmonize takes from it is preprocessing, never
  a final decision (agreed by the owners). Never push to GEOmend without the
  user's explicit go-ahead for that specific change. Work in branches and PRs
  for Preston to review.
- **Tuning workspace (`work/ds-tuning`):**
  - It holds the user's 21 review decisions (`review.json`).
  - Its runs of record are annotate 3/4 and reconcile 1/2. Reconcile 3/4
    were the merge-link experiment.
  - Regenerating its outputs would mark some review decisions stale (the
    shared-qualifier change). Ask the user first.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Environment

**colharmonize**
- Python: `./.venv` (Python 3.13). `uv` is at `./.venv/bin/uv`.
- Pinned ontology: `work/ontology/efo-v3.94.0`, plus the GEOmend store
  `work/ontology/efo-v3.94.0.sqlite`.

**GEOmend suite**
- Run in `../GEOmend`: `npm run contracts` (with `.venv/bin` on PATH), then
  `.venv/bin/python -m pytest -o addopts="" -q -p no:cacheprovider`.
- Baseline: 1,463 passed on `main`, 1,481 on the fix branch.

**Data**
- Tuning SOFT files: `../ds-metadata-harmonization/data/raw`, plus
  GSE61804 from `../efo-column-mapping/data/raw`.
- Sealed SOFT files: `work/sealed/raw`.

**Tools**
- `gh` isn't installed.
- The in-app browser isn't signed in to GitHub.
- poppler is installed, so PDFs can be read.

## What's left, in priority order

### A. Needs the user

1. **Open the GEOmend PR.** Compare page:
   https://github.com/prestonraab/GEOmend/compare/main...fix/characteristic-key-punctuation?expand=1
   The description is in `work/geomend_pr_key_punctuation.md`. After it
   merges and is released:
   - bump the `geomend==` pin
   - run `tests/test_geomend_bridge.py`
   - re-ingest, since the parser version changed
2. **Find a reviewer with clinical background** for the manual tier.
   Decisions log 9.4: a non-clinical reviewer accepted all 21 manual-tier
   variables, and only 2 matched gold.
3. **Choose a license for the SSSOM output.** Ask the PI.
4. **Decide whether to un-defer value→ontology mapping** (see task 19).
5. **Find a person to fill the curation sheet** (task 6):
   `eval/curation/curation_sheet.xlsx`. Send them only that file. Ideally
   they have clinical background and haven't seen the gold. Then run
   `eval/curation/agreement.py FILLED.xlsx`.

### B. Make the evaluation trustworthy

These ideas come from MetaHarmonizer, Li et al., bioRxiv 2026.06.13.732088.

5. ~~**Memorization probe.**~~ Done 2026-10-09 (`eval/memorization/`): no
   series recalled; Opus recognises GSE92415 by name only.
6. **Circular grading.** Sheet and scorer done 2026-10-09
   (`eval/curation/`, pre-registered in its PROTOCOL.md): 44 columns from 5
   sealed series. **Waiting for a person** (A5).
7. ~~**Robustness to renamed columns.**~~ Done 2026-10-09
   (`eval/robustness/`): primary term −2.4 points (CI −7.0 to +1.2), pooling
   unchanged. Not run through reconciliation.
8. ~~**Statistics.**~~ Done 2026-10-09 (`eval/stats/`; decisions log 15.2).
   It revised four claims: reconciliation's and the merge links' gains are
   within noise, and annotation signals fail on sealed.
9. **A new sealed corpus,** once the fixes below are in. Curate the gold before
   any run, preferably by a person, and pre-register it as
   `eval/sealed/PROTOCOL.md` did. Size it for power: at about 15 studies a
   pooling-F1 interval is 8–14 points wide on each side (decisions log 15.2).

### C. Pipeline improvements

Measure each on tuning first.

10. **Alias dictionary for candidate terms.** A one-time subagent task writes
    synonyms for the 2,057 property-space terms. Validate them, then add them
    as a retrieval index. Baseline candidate recall: 88.6% in the pool, 84.8%
    shown. MetaHarmonizer found a small model as good as a large one here, and
    that large models add off-target aliases.
11. **SapBERT** as a third embedding model in `candidates.py`. Measure recall.
12. ~~**Easy-first fast path.**~~ Measured 2026-10-09 (`eval/fastpath/`,
    decisions log 15.5): safe with a value guard, but it takes only about 10%
    of columns and saves about 5% of subagent calls. Not built; revisit for
    large corpora.
13. **Annotator instructions, as annotate-3** (decisions log 14.4):
    - Add a non-gene `object_class` example from neither corpus.
    - Don't restate the primary term or name the study's disease.
    - Qualifiers come only from the column name and values, not the study
      summary.
    - Prefer a whole-concept primary term (overall survival).

    Settle the gold-convention questions in 14.4 with the owner.
14. **Duplicate title variables** (decisions log 14.2, 15.7). The
    value-based repair check was tested and rejected: it would drop a tuning
    subject ID and lose sealed information. **Ask the owner** whether the
    authors' characteristic should win a conflict with a title variable. If
    yes, add it to reconcile-3 and measure it on a new corpus.
15. **Different models for run 1 and run 2,** so the runs' errors are less
    alike. GEOMeta uses consensus across models. Check whether the tiers
    discriminate better: on sealed, no current signal does (AUC 0.51–0.59), and
    partition agreement can't see missed merges (decisions log 15.2).
16. ~~**Cost.**~~ Done 2026-10-09 (`eval/cost/`, decisions log 15.6). The
    sealed run used 41 agents, 17.9M input tokens (76% cached) and 430k
    output tokens, with about 7 minutes of agent time on the critical path.
17. **Optional:** fill missing values within a study when all of that study's
    non-missing values agree (GEOMeta's QA1).

### D. Baselines, related work, product

18. **A deterministic baseline:** MetaHarmonizer's SchemaMapper
    (github.com/shbrief/MetaHarmonizer), with the EFO property-space labels as
    its target schema, against our annotate step on tuning. On sealed it would
    be a post-hoc baseline.
19. **Value mapping.** If un-deferred, reuse MetaHarmonizer's OntologyMapper
    (EFO, SapBERT, staged) rather than building one.
20. **Related work.** Position colharmonize against MetaHarmonizer (maps to a
    given schema; AI used sparingly), GEOMeta (bioRxiv 2026.08.19.745739; fills
    a fixed 27-field schema at about 595k samples, compressing detail) and
    Magneto. Our contribution: pooling across studies without a target schema
    and without losing information, directed annotations with qualifiers, and
    a pre-registered test on unseen data. GEOMeta's released labels could
    serve as an outside check of sex, age, tissue and disease on overlapping
    series.
21. ~~**Refresh the root docs.**~~ Done 2026-10-09. `../BRIEFING.md` is
    rewritten for iteration 3; `../briefing.html` is generated from it by
    `../build_briefing.py`. Iteration 2's versions are archived in
    `../efo-column-mapping/docs/`.
22. **Write results back to GEOmend** through the public provider seam,
    `transformations.propose_provider` (decisions log 1.5 and 1.6).
23. **The other planned GEOmend changes:** directed relations, qualifier
    slots, a pre-accepted review state, and fixes 1, 3, 4 and 5. One PR each,
    each only with the user's go-ahead.
24. **Package the plugin** for others: install instructions and the
    marketplace entry in `.claude-plugin/marketplace.json`.
