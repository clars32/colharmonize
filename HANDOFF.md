# Handoff brief: colharmonize, iteration 3

Written 2026-10-08 for a fresh Claude instance, updated 2026-10-22. Read
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
9. publish (the pooled sample table, variables.tsv, columns.tsv, SSSOM)
10. registry

**GEOmend** (`../GEOmend`, v0.0.9) reads, profiles and exports GEO
metadata. Preston Raab wrote it, and since 2026-10-12 the user owns it. colharmonize is a separate repository and reads
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
- **GEOmend 0.0.9** (released 2026-10-12): six fixes, including the
  key-punctuation parser fix. colharmonize pins it, and its ontology store
  now gives GEOmend real IRIs (decisions log 15.12).
- **Evaluation checks, 2026-10-09** (decisions log 15; `eval/memorization`,
  `eval/stats`, `eval/robustness`, `eval/curation`):
  - no model recalls these series' metadata
  - pooling beats every baseline with intervals that exclude zero; the
    gains from reconciliation and merge links are within noise
  - no confidence signal discriminates annotation correctness on sealed
    (tier AUC 0.54); partition agreement catches false merges, not missed ones
  - renamed columns cost about 2.4 points of primary term, within noise
  - a blind 44-column curation sheet is ready for a person
- **Pooled sample table** (2026-10-12, decisions log 15.13): `publish` also
  writes `pooled_samples.tsv`, one row per sample and one column per
  variable, and its long form `pooled_values.tsv` with raw values beside
  harmonized ones. For most users this is the product.
- **Genetic-syndromes demo** (decisions log 15.14), run through scoring on
  2026-10-13 in `work/demo-genetic`. It has 8 series in 5 syndromes, none
  in the Down syndrome corpus, and 49 columns, 17 of them recovered by
  repair.
  - The result is 27 variables, 11 of them pooling two or more studies.
    `karyotype`, `karytype` and `chromosomes` pool into one karyotype
    variable across 4 studies.
  - The annotate runs agree on primary term and predicate for 87.8% of
    columns, and the reconcile partitions agree 100%.
  - Tiers: 4 variables pre-accepted, 19 quick, 4 manual.
  - Reviewed and published 2026-10-14: the user accepted the 4 manual
    variables. The pooled table is 387 samples × 27 variables, 2,254 values
    and no conflicting cells. The 19 quick-tier variables are still
    unreviewed (A11).
  - It has no gold, so it measures nothing. It can't become the next sealed
    corpus either, since the pipeline has already run on it.
- **Setup and resume** (2026-10-14, decisions log 15.15; merged to
  `master` as `62eb62a`):
  - `colharmonize ontology fetch --tag v3.94.0 --out DIR` downloads
    `efo.json`, pins it and builds the store as `DIR.sqlite` in one
    command. For v3.94.0 it refuses a file with any other checksum. The
    real download has been checked for size only, never run end to end.
  - The workspace records the store and ontology, so `--store` and
    `--ontology` are needed only once.
  - `colharmonize status --workspace W` reports which stages are done and
    prints the next command. It only reads files. The skill's step 0 runs
    it, so an interrupted run resumes from the stage it names.
  - The `candidates` cache now defaults to `$COLHARMONIZE_CACHE`, else
    `~/.cache/colharmonize`. To reproduce the recorded workspaces' candidates
    (tuning, sealed, demo), pass `--cache work/cache`: its `remote.json`
    supplies the ZOOMA and OLS4 answers.
- **Tests:** `./.venv/bin/python -m pytest -q` passes 131.

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
  a final decision (agreed by the owners). The user owns GEOmend (handed over
  by Preston on 2026-10-12):
  - GEOmend branches may be pushed.
  - Confirm with the user before merging to `main` or cutting a release.
  - Each change gets its own branch, with a test that fails without it.
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
- Pinned ontology: `work/ontology/efo-v3.94.0`, plus two GEOmend stores
  built from the same EFO file:
  - `efo-v3.94.0-iri.sqlite`: projection-2, whose nodes carry IRIs (15.12).
    Use it for new workspaces; `work/demo-genetic` does.
  - `efo-v3.94.0.sqlite`: projection-1, CURIEs only. `work/ds-tuning` and
    `work/sealed` were run with it.

**GEOmend suite**
- Run in `../GEOmend`: `npm run contracts` (with `.venv/bin` on PATH), then
  `.venv/bin/python -m pytest -o addopts="" -q -p no:cacheprovider`.
- Baseline: 1,491 passed, 4 skipped on `main` at 0.0.9.

**Data**
- Tuning SOFT files: `../ds-metadata-harmonization/data/raw`, plus
  GSE61804 from `../efo-column-mapping/data/raw`.
- Sealed SOFT files: `work/sealed/raw`.
- Demo corpus: `examples/genetic-syndromes/corpus.tsv`; its SOFT files are
  cached in `work/demo-genetic/geomend/.geomend/cache/geo`.

**Tools**
- `gh` isn't installed.
- The in-app browser isn't signed in to GitHub.
- poppler is installed, so PDFs can be read.

## What's left, in priority order

### A. Needs the user

1. ~~**Open the GEOmend PR.**~~ Merged and released as GEOmend 0.0.9 on
   2026-10-12. The pin is bumped and the bridge tests pass. A re-ingest into
   new workspaces is in decisions log 15.12. **Still the user's call:**
   regenerating `work/ds-tuning` itself, which would mark review decisions
   stale.
2. **Find a reviewer with clinical background** for the manual tier.
   Decisions log 9.4: a non-clinical reviewer accepted all 21 manual-tier
   variables, and only 2 matched gold.
3. **Choose a license for the SSSOM output.** Ask the PI.
4. **Decide whether to un-defer value→ontology mapping** (see task 19).
5. **Find a person to fill the curation sheet** (task 6):
   `eval/curation/curation_sheet.xlsx`. Send them only that file. Ideally
   they have clinical background and haven't seen the gold. Then run
   `eval/curation/agreement.py FILLED.xlsx`.
6. **Owner questions:**
   - the gold conventions in decisions log 14.4
   - whether the authors' characteristic wins over a title variable that
     conflicts with it (task 14, decisions log 15.7)
7. **Approve installing and running MetaHarmonizer** (task 18). It is
   third-party code.
8. **Find a person to curate the next sealed corpus's gold** before any run
   (task 9).
9. **GEOmend decisions:** whether to build changes 1–3 (task 23) and a
   feature for derived fields (task 22).
10. **Host the plugin repository** and run `claude plugin validate`
    (task 24).
11. **Finish reviewing the genetic-syndromes demo.** The 4 manual variables
    were accepted and published on 2026-10-14. Still open, if the user
    wants a fully reviewed demo: the 19 quick-tier variables in
    `work/demo-genetic/review.html`. Two are worth a look first:
    - Williams syndrome lands in two variables: `disease status` in
      GSE89594 and `genotype` (`WBS`) in GSE63055.
    - The `karytype` column of GSE103905 holds non-karyotype values, such
      as "Known patient with Klinefelter syndrome" and "Two copies of SHOX".
      They pass through unrecoded.

    Re-run `review apply` and `publish` after any new export.
12. **Run the pipeline the real way, outside this folder.** Every run so
    far used general-purpose stand-in agents in this checkout. On a machine
    with the `claude` command: install from `docs/INSTALL.md`, run
    `claude plugin validate ./plugin --strict`, then `/colharmonize:harmonize`
    on 3–4 new series through publish, and write down what breaks. This is
    also the first real test of `ontology fetch`'s 169 MB download.

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
   Pre-register the three-run agreement count (decisions log 15.8) as a
   candidate confidence signal next to the current tiers.

### C. Pipeline improvements

Measure each on tuning first.

10. ~~**Alias dictionary.**~~ Measured 2026-10-12 (`eval/aliases/`,
    decisions log 15.11). There are 1,333 aliases for 1,094 of the 1,998
    property-space terms; 1,998 is the current count, not 2,057. Not
    adopted: shown recall fell on tuning.
11. ~~**SapBERT.**~~ Measured 2026-10-12 (`eval/retrieval/`, decisions log
    15.11). Pool recall rose and shown recall fell at the current 40-term
    cap; with a cap of 50 it helps on both corpora. Next: pre-register
    "SapBERT plus a cap of 50" and measure it by annotation accuracy.
12. ~~**Easy-first fast path.**~~ Measured 2026-10-09 (`eval/fastpath/`,
    decisions log 15.5): safe with a value guard, but it takes only about 10%
    of columns and saves about 5% of subagent calls. Not built; revisit for
    large corpora.
13. ~~**Annotator instructions, as annotate-3.**~~ Adopted 2026-10-12
    (`eval/prompts/`, decisions log 15.10). On tuning, qualifier precision
    rose from 72.1% to 87.7%, and nothing else fell. Still open for the owner:
    the gold-convention questions in 14.4. Confirm on the next sealed corpus.
14. **Duplicate title variables** (decisions log 14.2, 15.7). The
    value-based repair check was tested and rejected: it would drop a tuning
    subject ID and lose sealed information. **Ask the owner** whether the
    authors' characteristic should win a conflict with a title variable. If
    yes, add it to reconcile-3 and measure it on a new corpus.
15. ~~**Different models for run 1 and run 2.**~~ Tested 2026-10-12
    (`eval/models/`, decisions log 15.8). Under the pre-registered rule, run 2
    stays Sonnet: Sonnet–Opus agreement was a better error signal on sealed
    (+0.11 AUC) and a worse one on tuning (−0.17), where the prompt was tuned
    with Sonnet. A three-run count (two Sonnet runs plus one Opus) holds on
    both corpora. Pre-register it for task 9.
16. ~~**Cost.**~~ Done 2026-10-09 (`eval/cost/`, decisions log 15.6). The
    sealed run used 41 agents, 17.9M input tokens (76% cached) and 430k
    output tokens, with about 7 minutes of agent time on the critical path.
17. ~~**Fill missing values (GEOMeta's QA1).**~~ Closed as not applicable
    (`docs/related-work.md`). colharmonize publishes column-level decisions,
    not per-sample values. If anywhere, it belongs in GEOmend's export, as a
    reviewable suggestion.

### D. Baselines, related work, product

18. **A deterministic baseline:** MetaHarmonizer's SchemaMapper
    (github.com/shbrief/MetaHarmonizer), with the EFO property-space labels as
    its target schema, against our annotate step on tuning. On sealed it would
    be a post-hoc baseline.
19. **Value mapping.** If un-deferred, reuse MetaHarmonizer's OntologyMapper
    (EFO, SapBERT, staged) rather than building one.
20. ~~**Related work.**~~ Done 2026-10-12 (`docs/related-work.md`) and
    checked against the full texts. Resolved:
    - GEOMeta: a 27-field schema, mapped to HPA, CTD MEDIC and PubChem, not
      EFO. Model consensus is used only in its prospective release. Labels
      are on Hugging Face (`binchenlab/GEOMeta`).
    - MetaHarmonizer's GDC benchmark is Magneto's.
    - 13 of our 29 series could overlap GEOMeta; membership is unchecked.

    Extended 2026-10-13 with nine papers: Sun et al.'s dataset-screening
    paper (*Scientific Data*, 2026) and eight it led to.
    - EMBERS (Higashi et al., bioRxiv 2024) pools keys across studies
      without a schema but never scores the grouping. Contribution 1 now
      claims *measured* schema-free pooling.
    - Brown et al. (Piccolo lab, BYU) curated 30 Down syndrome series: 20
      are in our 64-series corpus, none are sealed, and 10 are in no
      corpus of ours. They're listed in `docs/related-work.md`.
    - Possible baselines, not run: EMBERS's tree cut for pooling; our top
      retrieved candidate with no judge, for annotation.
21. ~~**Refresh the root docs.**~~ Done 2026-10-09. `../BRIEFING.md` is
    rewritten for iteration 3; `../briefing.html` is generated from it by
    `../build_briefing.py`. Iteration 2's versions are archived in
    `../efo-column-mapping/docs/`.
22. ~~**Write results back to GEOmend.**~~ Done 2026-10-12:
    `colharmonize geomend propose` (decisions log 15.9). Proposals are
    previewed, unselected and idempotent. Columns recovered by repair can't
    be sent, because they aren't GEOmend fields. A GEOmend feature for
    derived fields would close that gap; it is the user's call now.
23. **The other planned GEOmend changes.** Mostly done in 0.0.9:
    - fixes 1, 3, 5 and 6, plus a new scaled-unit bug
      (`1000/microliter` had read as `1/microliter`)
    - fix 4 is partly obsolete: header units already work, and scaled units
      would need a unit-model redesign

    Changes 1–3 (directed relations, qualifier slots, a pre-accepted review
    state) are deferred to the user. They change GEOmend's data contract and
    matter only once colharmonize writes concept decisions there.
24. **Package the plugin.** Done 2026-10-12 locally: `docs/INSTALL.md`,
    with the plugin layout and commands checked against the Claude Code
    docs. The missing runtime dependencies (sentence-transformers and
    others) are now declared. Still open, for the user: host the repository
    on GitHub so others can run `claude plugin marketplace add
    OWNER/colharmonize`, and run `claude plugin validate ./plugin --strict`
    on a machine with the `claude` command (not available here).

### E. Housekeeping

25. ~~**`tasks status` on a run that doesn't exist.**~~ Fixed 2026-10-14
    (`27f54ec`): `tasks status`, `collect` and `retry` now say the run has
    no tasks yet and exit 1, instead of a traceback.
26. **Stale files and branches**, each the user's call:
    - `../parallel-session-briefing.md`: everything in it is merged and
      written up (15.11, 15.12).
    - GEOmend's six merged `fix/*` branches, still local and on origin.
      Deleting the remote ones is outward-facing.
    - colharmonize's merged `usability/setup-and-resume` branch.
