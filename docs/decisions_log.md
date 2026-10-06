# Decisions log, iteration 3

Every judgment call that could have gone the other way, with the reasoning.
Append-only. Iteration 2's log is `../efo-column-mapping/docs/decisions_log.md`.

---

## Scope and structure (2026-10-02 to 10-05, owner decisions)

### 1.1: Interoperability is the objective
Columns that should pool must share one harmonized variable; this matters more
than per-column term accuracy. Measured by pooling precision (no information
loss) and pooling recall (interoperability), not top-1 alone.

### 1.2: GEOmend and colharmonize stay separate
GEOmend is the deterministic precursor: parsing, profiling, review and export.
It keeps a loopback-only rule for model inference. colharmonize is the Claude
matching stage. Test for where a change belongs: if it helps a GEOmend user who
never runs Claude, it is a GEOmend PR. colharmonize writes back only through
GEOmend's public commands.

### 1.3: Claude Code only
No API key. The package writes task files, Claude Code subagents answer them,
and the package validates the answers. The plugin lives in `plugin/`.

### 1.4: Values scope is light cleanup
Units, splitting combined columns, and variables hidden in titles. Mapping
values to ontology terms is deferred.

## Gold standards

### 2.1: Bucket principle, operational form (owner-confirmed)
Pool differently named columns only if every value keeps its meaning in the
pooled column. Recodes, unit conversion and splits are allowed to achieve that.
Raw values are always kept verbatim beside harmonized ones.

### 2.2: Four predicates
`exact`, `broad`, `indicator` and `none`. `indicator` was added during gold
curation for yes/no or 0/1 columns (`shock: Yes/No`, `pcr: 0/1`), which are
neither equivalent to a term nor narrower than one. It replaces iteration 2's
decision 8.1 (assertion columns withdrawn to NO_MATCH).

### 2.3: Co-occurrence rule
Columns with values on the same samples never pool, unless their values are
identical on every shared sample (duplicate encoding). Columns covering
disjoint samples of one dataset may pool: GSE189007 records `age (yr)` for one
sub-cohort and `age` for another.

### 2.4: Assumed conventions are flagged
When the metadata is silent (a unit, a TIL compartment), assume the usual
convention and flag the row `assumed_convention`.

### 2.5: Two gold standards, two roles
- The 64-series Down syndrome corpus is **tuning**: 84 columns in 50 variables,
  converted from iteration 2.
- A 16-series corpus in four other disease areas is **sealed**: 141 columns in
  66 variables, curated before any pipeline output existed. It is measured
  once.

## Baselines (tuning gold, final)

| | pooling precision | pooling recall | primary term |
|---|---|---|---|
| iteration 2 | 59.5% | 78.4% | 69.0% |
| GEOmend propose() | 92.3% | 40.9% | — |

Iteration 2 over-merges; GEOmend under-merges. Iteration 3 has to beat both on
precision and recall at once.

## Engineering

### 3.1: Collapsing the index on CURIE lost 90 terms
The first `Ontology` indexed terms by CURIE. EFO imports 91 non-deprecated
classes with non-OBO IRIs (dbpedia, NCBI) that have no CURIE, and they
collapsed into one. ID validation was unaffected, because none of those terms
is allowlisted, but the GEOmend store silently lost 90 nodes. Terms are now
unique by IRI, and the store matches the Phase 0 feasibility run (84,375 nodes).

### 3.2: Plugin format, checked against the official docs
A subagent's summary of the plugin format was wrong on several points, so the
plugin follows `code.claude.com/docs/en/plugins-reference` instead:
- `skills/` and `agents/` sit at the plugin root.
- `name` is the only required manifest field.
- Components are namespaced (`colharmonize:repairer`).
- `permissionMode` is ignored for plugin agents.

Tools can't be restricted to particular paths, so "do not read other runs'
answers" is an instruction. Content hashes prove which batch an answer
answers, but not what the subagent read.

### 3.3: GEOmend dev baseline
On untouched `main`, GEOmend's own suite had 35 failures, all environmental:
29 needed the R packages `duckdb` and `DBI`, 5 needed the generated
TypeScript clients, and 1 inference test (flaky). After installing both, with
owner approval, the suite has 1,240 passed, 4 skipped and 0 failed. Any PR is
compared against that.

## Repair stage

### 4.1: Rules, not values
The subagent proposes regular expressions whose named group `value` captures
text verbatim. Code applies them, measures coverage and lists unmatched
samples. This replaces iteration 2's hand-written per-series regexes (`s01b`)
with reviewable, replayable data.

### 4.2: repair-1 to repair-2, tuned on GSE1397 and GSE4119
Six tuning series were used, two of which hide their variables in titles.
Recovery of iteration 2's 11 title variables went from 7/11 to 11/11.

repair-1 missed four:
- GSE4119 patient IDs
- GSE1397's TS13 comparison group
- the astrocyte cell type, folded into tissue
- "fetal", silently dropped by a tissue regex

Two causes were fixed:
- The prompt showed only 60 of GSE4119's 80 titles. It now shows up to 200.
- The instructions never said that identifiers are variables, or that no
  informative part of a title may be dropped.

Two examples first written for repair-2 came straight from the tuning data
("Down-Syndrome"/"DS-", "fetal cerebrum"). They were replaced with neutral ones
before the run, so the prompt isn't flattered on the series it was tuned on.

### 4.3: Rule checks run at collection time
A rule that reads a characteristic without declaring it a split, or that
doesn't compile, now fails `tasks collect`, so the skill re-tasks the batch.
Previously it was dropped silently at apply time. Found in the pilot: GSE124252
`tissue origin` ("H9-derived retinal organoids") holds a cell line and a
specimen type, and the agent extracted one without declaring the split.
