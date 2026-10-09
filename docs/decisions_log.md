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

### 1.5: GEOmend 0.0.7 overlaps the reconcile stage (open, 2026-10-07)
Decision 1.2 called GEOmend the deterministic precursor. That was already
inexact at 0.0.2, where an optional Ollama model could reassign fields to
variables. At 0.0.8 it is wrong. With `llm_model` set, `cohort_categorical_inference.py`
does the following:
- shows a local model a categorical field and up to seven peers from other
  studies
- gets back a shared trait, its states, and a state for every source value
- compiles that into one variable with per-source recodes

Best-guess export uses the top group unreviewed. That is cross-study pooling
with recodes: reconcile's job.

| | GEOmend categorical inference | colharmonize reconcile |
|---|---|---|
| Model | Local Ollama, opt-in | Claude subagents |
| Runs | One | Two; disagreement routes to review |
| Fields | Unitless, at most 32 distinct values | Any |
| Co-occurring fields | Pooled; evidence intersected | Never pooled unless identical (2.3) |
| Annotation | Trait label and predicates | Primary term, directed predicate, qualifiers |

colharmonize is unaffected today: it ingests with `llm_model` unset and
concept enrichment off, so it reads raw fields, not GEOmend's groups. But the
boundary needs an owners' decision. Options: GEOmend keeps it as the
local-model path and colharmonize stays the Claude path; or one tool owns
cross-study pooling. Decision 1.2 stands until then.

### 1.6: Settled: colharmonize stays separate; GEOmend output is preprocessing (owners, 2026-10-07)
Resolves 1.5. colharmonize stays a separate tool and takes whatever help
GEOmend offers. GEOmend goes less deep, so everything colharmonize takes from
it is preprocessing: evidence that feeds colharmonize's own stages, never a
decision colharmonize adopts unchecked. That covers parsed fields, units,
lexical concept candidates and merge suggestions. When GEOmend runs with a
local model, it covers its categorical groups too. Cross-study pooling and
annotation stay colharmonize's decisions, made by its own runs and
reconciliation rules (the co-occurrence rule included).

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

### 3.4: GEOmend 0.0.2 to 0.0.8 (2026-10-07)
GEOmend moved from 0.0.2 to 0.0.8 (14 commits, 227 files). The cohort module
became private (`_cohort._CohortEngine`), and the public entry point is now
`geomend.project.ProjectClient`, with operation groups (`inputs`, `mappings`,
`concepts`, `review`, `exports`). The bridge now uses only that public API:
- `ProjectClient.create` builds a project.
- `mappings.fields` lists fields, and `mappings.field` pages their per-sample
  values, 200 entities at a time. It refuses any truncated value list rather
  than drop values.

`CohortConfig`, `OntologyStore.replace_all`, `resolve_local_ontology`, the
graph models and the `text` helpers are unchanged.

Verified against both workspaces before anything downstream was trusted:
- **Tuning set (13 series):** re-ingesting under 0.0.8 gives the same columns,
  samples and study tables (1,050 samples, 74 columns) and identical per-sample
  values (42,578).
- **End-to-end set (3 series):** also identical.
- **Old projects:** 0.0.8 reads projects written by 0.0.2 without migration.

Every result recorded above therefore stands. The field table now reports
GEOmend's `reported_count` rather than counting values itself, because its only
consumer reads units.

GEOmend's own suite at `f0a8fcc` is the new baseline for any PR: 1,463 passed,
4 skipped, 0 failed. Six tests fail until `npm run contracts` generates the
client assets, which a fresh pull doesn't include. That environmental class
also caused failures at 0.0.2 (3.3).

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

### 4.4: repair-3 stops over-splitting and reads unparsed characteristics
On the 13 tuning series, repair-2 split GSE61804 and GSE17459 `condition`
("AML with t(8;21)", "Down's syndrome with ALL") into a diagnosis and a
karyotype. The owner-approved gold treats those as single diagnoses. repair-3
adds a test: split only when the parts vary independently across samples, and
a named category that mentions several features is one variable (the example,
"EGFR-mutant adenocarcinoma", is from neither corpus). It also tells the agent
that GEOmend's "unresolved characteristic" holds raw `key: value` text to
recover. GSE16176's gestational age, which GEOmend's parser could not split,
is now recovered for 14/14 samples.

One regression: repair-3 captured GSE1397's replicate as "Euploid sample 1"
(karyotype and number together), where repair-2 captured "1". Repair runs once
per workspace, so this run-to-run variation is uncorrected. A second repair
run with agreement checking would catch it; noted, not built.

## Candidates

### 5.1: Values propose their own category
Each column's most common values are matched to ontology terms, and the
property-space ancestors those terms share become candidates
(`value_category`). Values are instances of the column's category, so
"Control / Down syndrome" proposes `disease` for a column named `strain`.
That was iteration 2's trap (its 6a.4), where every name-based source agreed on
the wrong `strain`. The same mechanism proposes organism part for tissue
values, biological sex for male/female, and cultured cell for K562/NALM6.

### 5.2: Entity subtrees are enforced; `disposition` added as a category root
The property space's design rule is that entity roots' subtrees never enter
it, but iteration 2's builder relied on roots not overlapping. Enforcing the
rule removes 129 terms iteration 2 had admitted through side routes: specific
developmental stages such as "Theiler stage 12", and specific diseases. With
the rule enforced, a `disposition` root (BFO) admits 70 terms:
- staging and grading categories (`disease staging`, `tumor stage`,
  `T/N/M stage`, `Clark level`)
- `remission`, `risk factor`, `toxicity`
- about 30 injury and fracture terms, accepted as the smaller cost

Prompted by tuning misses (`Braak stage`, `CNS status` -> disease staging),
not by the sealed corpus.

### 5.3: Retrieval recall on the tuning gold
| | pool | displayed |
|---|---|---|
| primary term, before 5.2 | 84.8% | 78.5% |
| primary term, after 5.2 | 88.6% | 79.7% |
| primary term, display 40 category + 16 entity (was 30 + 12) | 88.6% | 84.8% |
| grounded qualifiers | 81.8% | 81.8% |

Of the 9 remaining primary misses:
- 2 have no column to retrieve for (GSE1397 replicate and source material, see 4.4).
- 6 need domain knowledge no retrieval provides: `E2A-PBX`/`MLL` -> translocation,
  `flt3-itd` -> duplication, `amplification set`/`hybridization set` -> block,
  `gene expression dataset` -> cohort. The annotator can still propose these by name.
- 1 is GSE222365 `cell type` = "iPSC-derived cerebral organoid" -> specimen.

Iteration 2 reached 76% displayed recall on its own gold.

### 5.4: Annotation prompt examples come from neither corpus
The obvious examples for the new predicates (`shock: Yes/No`, the Mayo score,
PAM50, HbA1c) are all in the sealed corpus, and `strain` and CRLF2 are in the
tuning gold. annotate-1 uses outside examples (NYHA class, hypertension yes/no,
TP53 expression), so neither measurement is flattered by its own prompt.

## Annotate stage

### 6.1: Qualifiers are scored by meaning, not text
The annotator writes qualifiers as terms or free text, and the gold writes them
as curated phrases. Exact-text matching scored annotate-1's qualifiers at 10.5%
while most were right ("blood draw" vs "blood sample collection"). The scorer
now matches qualifiers in the same slot when one word set contains the other or
their Jaccard similarity is at least 0.5, after dropping filler words, and
compares terms by label. annotate-1 rescored at 68.4% precision / 52.0% recall.

### 6.2: An unresolvable proposed name is a review hint, not a failure
annotate-1 proposed names with no term in the pinned file (`cell line`,
`leukocyte count`, which is deprecated). Failing the batch made the subagent
guess a nearby term. Now an unknown ref is still a problem, but an unresolvable
name resolves to predicate `none` with the name kept as a hint for review.

### 6.3: annotate-1 to annotate-2
Changes, each prompted by a tuning miss and illustrated with outside examples:
- a lesion indicator targets the lesion class, with the specific lesion as
  `object_class`
- age at sampling, collection or biopsy is plain age; other events are anchors
- processing batches are `block`
- identifiers get predicate `none`
- term definitions are shown, and the agent reads them before proposing a name

| tuning gold | annotate-1 | annotate-2 |
|---|---|---|
| pooling precision / recall | 81.5% / 75.0% | 76.9% / 79.5% |
| pooling F1 | 78.1% | 78.2% |
| primary term | 66.7% | 72.6% |
| predicate | 76.2% | 77.4% |
| primary and predicate together | — | 66.7% |
| NO_MATCH precision / recall | — | 37.5% / 60.0% |
| qualifiers precision / recall | 68.4% / 52.0% | 81.0% / 68.0% |
| runs agree on primary and predicate | — | 84.8% |

annotate-2 beats iteration 2's primary-term accuracy (69.0%), the phase 3
gate. Pooling recall rose and precision fell: annotation alone pools any two
columns with the same annotation, so `age at dissection` joins `age` and a
hybridization set joins a generic batch. Reconciliation, which sees the
columns side by side, is the stage meant to separate them.

## Reconcile stage

### 7.1: Candidate groups link on shared distinctive values
Groups start from the same term, the same normalised name, and a primary
within two hops of another column's primary. That missed karyotype columns
annotated as `disease` or `trisomy`, whose names share nothing. Columns that
share a distinctive value (not yes/no, control, male/female or a number) are
now linked too, including within one study. The 13 tuning series give 16
groups of 2 to 15 columns.

### 7.2: Run 1's partition is the answer; run 2 measures confidence
As in annotation, the second run doesn't vote. Each column records the share
of its group-mates whose same-variable status matches in both runs.

### 7.3: reconcile-1 on the tuning gold
| tuning gold | annotate-2 | reconcile run 1 | reconcile run 2 |
|---|---|---|---|
| pooling precision | 76.9% | 84.5% | 78.9% |
| pooling recall | 79.5% | 80.7% | 85.2% |
| pooling F1 | 78.2% | 82.6% | 82.0% |
| B-cubed F1 | — | 92.1% | 92.9% |
| primary term | 72.6% | 76.2% | 75.0% |
| predicate | 77.4% | 78.6% | 79.8% |

Reconciliation beats iteration 2 (59.5% / 78.4%) on precision and recall at
once. It beats GEOmend's `propose()` (92.3% / 40.9%) on recall and F1 but not
on precision, because `propose()` barely pools.

**The disagreement between runs locates every error.** 53 predicted pairs
join two columns whose partition agreed across runs, and all 53 are correct.
All 13 false pairs involve one of the 18 columns where the runs disagree.
They fall in two groups:
- **Disease, karyotype and Down syndrome status** (15 columns). Run 1 split it
  much as the gold does but kept GSE16176 `condition` ("euploid / Down
  syndrome") with disease status, and recoded `registry`'s "DSRegistry" as a
  diagnosis. Run 2 recoded "Control" to "euploid" and folded two disease-status
  columns into karyotype. That infers a karyotype from a diagnosis: arguable,
  and not what the owner decided.
- **GSE222365 `cell type`** ("iPSC-derived cerebral organoid"), which gold
  treats as a specimen source; its agreement is 0.

The prompt was not tuned on this group: it is one cluster of genuinely close
calls, and the agreement signal already routes it to review. Both runs also
kept leukemia diagnoses apart from Down syndrome / control columns, which the
gold pools as `disease`. That is a conservative split and costs only recall.

## Score stage

### 8.1: Pre-accepted means every check passed, not a confidence threshold
Iteration 2 accepted on a score. Here a column starts pre-accepted and each
failed check demotes it, so a reviewer always sees why a column needs a look.
Checks that suggest the answer is wrong send it to manual review:
- the runs disagree on the annotation
- the runs disagree on the partition
- the proposed term isn't in the pinned file
- the primary is outside the property space

Checks for claims that deserve a glance send it to quick review:
- qualifiers differ between runs
- the term was picked among same-label terms
- the annotator flagged it
- the predicate is `indicator` or `none`
- values were recoded
- the variable pools 4 or more column names

A variable's tier is its worst member's. With one run, nothing counts as
agreed.

The primary-outside-space check comes from the data: all 5 such columns among
those both runs agreed on were wrong. The others have reasons that don't
depend on the tuning data. All were chosen on the tuning corpus, so its
numbers are optimistic.

### 8.2: Qualifier agreement uses the scorer's meaning rule
Runs word free-text qualifiers differently ("kmt2a (mll) gene rearrangement"
vs "mll (kmt2a) gene rearrangement"). Exact comparison counted that as
disagreement and held back 18 columns. Agreement now uses `text.same_meaning`,
the rule the scorer uses against gold, so the confidence signal and the
measurement agree on what "the same qualifier" means. A qualifier only one run
gave still counts as disagreement.

### 8.3: Tier calibration on the tuning gold
| tier | columns (all 105) | gold columns | annotation correct | pooled pairs correct |
|---|---|---|---|---|
| pre_accepted | 26 | 18 | 100% | 9 / 9 |
| quick | 43 | 30 | 83.3% | 43 / 43 |
| manual | 36 | 34 | 44.1% | 19 / 32 |

All 13 false pooled pairs are in the manual tier.

## Review and publish

### 9.1: Decisions are an overlay, applied last, with fingerprints
Iteration 2's reviewer decisions never reached its harmonized output: s09
edited `mappings.tsv`, then s08 rebuilt it. Here the page export is validated
into `review.json`, and publish recomputes everything from `scored.parquet`
plus that overlay on every run. Each decision records a fingerprint of the
variable it judged: its members, annotation and recodes, but not its name or
tier. A re-run that changes the variable makes the decision stale; publish
skips it and the page shows the variable again.

### 9.2: The review unit is a variable, and reviewers can move columns
A decision accepts, edits (name, predicate, primary, qualifiers), rejects, or
moves member columns. A column can move to a variable of its own
(`<parent>+<study>::<column>`, reviewable in turn) or into another variable,
where it takes that variable's annotation and loses recodes written for the
old one. A move that would pool columns with conflicting values on shared
samples is refused, because the co-occurrence rule binds reviewers too. Every
identifier a reviewer types is validated against the pinned file, and an
export with any problem saves nothing.

### 9.3: SSSOM choices
- **Subjects** are columns, as `col:<study>/<column>` under
  `urn:colharmonize:column:`, because GEO columns have no IRIs.
  `subject_source` is the series' GEO page.
- **Predicates:** `indicator` maps to `skos:relatedMatch`, and no-term to
  object `sssom:NoTermFound`.
- **Qualifiers** have no SSSOM slot. They go in `comment`, and stay structured
  in `variables.tsv`.
- **Justification:** an edit is `semapv:ManualMappingCuration`, with the
  reviewer as author; anything else is `semapv:CompositeMatching`.
- **License:** defaults to SSSOM's "unspecified" URL. The owner has not chosen
  a license, and the tool doesn't choose one for them.

### 9.4: A non-clinical reviewer can't settle the manual tier (owner, 2026-10-07)
The owner reviewed the tuning set's 21 manual-tier variables and accepted all
of them. 2 match the tuning gold in full. The others differ, mostly in
exact-vs-broad choices, and in two pooling calls the gold rules out (disease
status vs karyotype vs cohort; an organoid "cell type"). Asked about it, the
owner said these calls "could go either way" without a clinical background.
The acceptances stand as the review of record, and the gold stays as curated.

Implication: the manual tier is where run disagreement concentrates real
errors, and it needs domain judgment. Review is a safeguard only as strong as
the reviewer's domain knowledge, and measurements of the pipeline should not
assume review fixes the manual tier.

## Registry

### 10.1: A registry carries interoperability across runs
Reconciliation pools columns within one run. For a column harmonized later to
get the same label, later runs must see earlier variables. A registry is a
directory with `variables.tsv` and `members.tsv`, plain text so a lab can
version and share it. Only reviewed variables (accepted or edited) are
registered by default, so the registry is an emergent schema of vetted
variables, never a hand-written one.

### 10.2: Registered variables are fixed members of candidate groups
In a workspace that uses a registry, registered variables join candidate
grouping through the same links as columns: term, name, distinctive values.
The reconciler can put new columns in a registered variable's part, and those
columns take the registry's id, name and qualifiers. It can't change the
registered predicate or primary term, or put two registered variables in one
part; validation sends such answers back. The registry is snapshotted when
tasks are written (`registered.json`), so answers are checked against what the
reconciler saw.

The instructions gained one paragraph about registered members, so the prompt
is now reconcile-2. Without a registry, no item has a registered member and
the paragraph is inert; the tuning results in 7.3 are reconcile-1's.

Known gap: a registered variable keeps value counts but not per-sample values,
so co-occurrence between a new column and a registered column from the same
study can't be checked.

## End-to-end run

### 11.1: From an empty workspace, following the skill (2026-10-06)
GSE1397, GSE4119 and GSE128621 ran through ingest, repair, candidates,
annotate (two runs), reconcile (two runs), score, the review page and publish.
Subagents answered every judgment batch, using the plugin's agent instructions
and models; the plugin wasn't installed in the session, so they ran as
general-purpose agents. Everything else was the `colharmonize` command.

- 3 studies, 122 samples; repair recovered 13 columns from titles and source
  names, and every rule covered the samples it claimed.
- 19 columns became 15 variables. The annotate runs agreed on 84.2% of
  columns, and the reconcile runs on every partition.
- Tiers: 8 columns pre-accepted, 8 quick, 3 manual.

One answer was misfiled. An annotator wrote the item id
`GSE4119::title#unresolved characteristic` for `GSE4119::unresolved
characteristic`. Collection refused it, the batch was re-tasked once as the
skill says, and the second answer was clean. This is why answers are checked
against the batch's items, not trusted.

Columns no candidate group reached now get plain singleton ids (`S001`)
instead of their internal annotation key.

### 7.4: An unresolvable term name in reconciliation is a review hint
Reconciliation used to reject an answer whose part named a term not in the
pinned file. On run 3 (12.3) the reconciler named "cell line" twice in a row.
That is the pattern decision 6.2 describes: re-tasking repeats the same
missing name. Reconciliation now follows annotation's rule:
- An unknown candidate ref is still an error.
- An unresolvable name gives the part predicate `none` and keeps the name as
  `unresolved_proposal`. Score then sends the column to manual review.

Runs 1 and 2 never hit this case, so their results are unchanged.

## GEOmend preprocessing (decisions log 1.6)

### 12.1: What is collected
`colharmonize preprocess` runs after ingest, offline and with no model. It
turns on GEOmend's concept retrieval against the pinned store only; hosted
OLS4 needs `offline=False`, and the subagent that mapped the API confirmed no
network calls. It saves three files in `geomend_evidence/`:
- **concepts:** lexical candidates per characteristic, with evidence scores
- **merges:** suggested joins between characteristics
- **units:** units found on fields, variables and mapping specifications

On the 13 tuning series: 3,100 candidates (all mapping to pinned terms), 86
merge pairs, and units for 5 fields. It takes 50 s. Per-sample values are
unchanged afterwards (42,578).

Each kind was measured on the tuning set and used only if it helped.

### 12.2: Concept candidates and units are collected but not used
GEOmend's evidence scores are 5 for an exact field-name match, 4 for a value
match, 2.4 for a substring and 1 or less for a definition-only hit. Its own
`rank` is not meaningful: definition-only hits can outrank exact matches, and
for `Sex` it never offered "biological sex".

| GEOmend concept candidates used | gold term in pool | gold term shown |
|---|---|---|
| none (current) | 88.6% | 84.8% |
| exact only (score >= 4) | 88.6% | 84.8% |
| substring too (>= 2.4) | 88.6% | 83.5% |
| all | 88.6% | 83.5% |

They add no gold term, and substring matches push correct terms out of the
display.

Units: GEOmend reported units for 5 fields, which colharmonize's own unit
spotting already finds. Gold-unit recall stays 8 of 12. Across 13 series,
GEOmend puts every `age` into one text variable, so it never normalizes the
per-value units ("1 Year old") it finds in smaller projects.

### 12.3: Merge suggestions are used, as extra links for reconciliation groups
GEOmend's suggestions link variables by shared header words, plus value
agreement within one study. As extra grouping links they raise the gold pairs
reaching one group from 82 to 84 of 88. They also merge 16 groups into 7, two
at the 30-column cap; "stage" links `developmental stage` with `Braak stage`.
Reconcile ran twice more with the links (runs 3 and 4, prompt reconcile-2)
and was compared with runs 1 and 2 (reconcile-1, no links):

| | run 1 | run 2 | run 3 (links) | run 4 (links) |
|---|---|---|---|---|
| pooling precision | 84.5% | 78.9% | 85.5% | 88.9% |
| pooling recall | 80.7% | 85.2% | 80.7% | 81.8% |
| pooling F1 | 82.6% | 82.0% | 83.0% | 85.2% |
| partition agreement | 92.5% | 92.5% | 98.9% | 98.9% |
| pairs where both runs agree: correct | 53/53 | 53/53 | 61/61 | 61/61 |
| primary term | 76.2% | 75.0% | 70.2% | 79.8% |

With the links, precision is up, recall is unchanged, and eight more pooled
pairs are ones both runs agree on, all correct. Every false pair still
involves a column the runs disagree on. The four gold variables split before
are still split: the two extra pairs grouped were not pooled.

With two runs per side, the F1 difference is about the size of run-to-run
variation, so this is "helps a little, does no harm", not a firm gain. The
links stay on (`preprocess.USE_MERGES`). The tuning workspace's runs of record
are still 1 and 2, because the review decisions are fingerprinted against them.

## Sealed measurement (eval/sealed/RESULTS.md)

### 13.1: Measured once at tag `sealed-run`, 2026-10-08
- **Pooling:** precision 100.0%, recall 70.9%, F1 83.0%, against baselines
  of 53.8% (identical names) and 45.8% (GEOmend `propose()`). Tuning F1 was
  82.6%.
- **Primary term:** 71.5% (tuning 76.2%).
- **Qualifiers:** precision 28.9%, recall 37.9% (tuning 61.5% / 64.0%).
- **Reconciliation:** annotation alone scored F1 84.7%, so reconciliation
  did not help on this corpus.
- **Tiers:** discriminated less. Pre-accepted columns were 87% correct, and
  agreement left only 9 columns in the manual tier.

18 of 137 gold columns were never produced, which caps recall at 86.6%:
- 11 because one repair batch failed validation three times, and re-tasking
  drops whole batches
- 7 because of GEOmend's key-parsing bug (upstream fix 2)

### 13.2: Follow-ups, to be measured on new data, never on the sealed corpus
- Validate and re-task repair per item, not per batch: one item cost seven
  studies' valid rules.
- Send GEOmend fix 2 (keys with commas, `#`, `%`, `=`) upstream. Needs the
  owner's go-ahead to push.
- Find out why qualifiers fell: the annotator, or a gap in how the two gold
  standards write qualifiers.
- Reconciliation helps where look-alike variables exist (tuning) and slightly
  hurts where they don't (sealed). Consider running it only on groups whose
  annotations disagree.
- Agreement is a reliable precision signal for pooling, but not enough for
  annotation. A per-column annotation check is needed to keep the
  pre-accepted tier honest.

## After the sealed measurement

### 14.1: Answers are validated and retried per item, not per batch
On the sealed corpus, one repair item (GSE189007) failed validation three
times, and re-tasking per batch dropped all 8 studies' rules, every derived
gold column among them (13.1). The protocol now works item by item:
- **Collection:** an answer that is missing, duplicated or off-schema fails
  only its item, and the batch's other answers stand. A file that can't be
  trusted at all (invalid JSON, wrong content hash) fails each of its items.
- **Stage checks:** problems are attributed to the item ids they start with.
- **Retries:** `tasks retry` writes a batch holding only the failed items,
  each with its original data. A retry's answer replaces the earlier one.
  Each item gets at most two retries.
- **Apply:** refuses while items are failing, unless given `--drop-failed`,
  which applies the rest and lists what was dropped. No answer is ever edited
  by hand.

Read against the sealed repair answers, per-item collection keeps 15 of 16
studies' rules; only GSE189007 would have been retried. This is a
consequence, not a new measurement.

### 14.2: Reconciling only unsettled groups was tested and not adopted
Proposed after 13.1: send to reconciliation only groups whose members'
annotations differ or that contain conflicting columns, and let annotation
pool the rest. Tested offline with existing answers, no new runs:

| | groups settled by annotation | pooling F1, all groups | pooling F1, unsettled only |
|---|---|---|---|
| tuning, runs 1/2 | 4 of 16 | 82.6% | 82.6% |
| tuning, runs 3/4 | 2 of 7 | 83.0% | 83.0% |
| sealed, runs 1/2 (post hoc) | 20 of 36 | 83.0% | 83.0% |

Reconciliation never split a settled group, so the rule changes nothing. The
sealed gap with annotation alone comes from co-occurrence conflicts. Repair
had extracted title variables (GSE166925 `title#diagnosis`, GSE131411
`title#group`) that conflict with the study's own characteristic, and the
reconciler kept the derived column.

Candidate fixes, to be measured on a new corpus:
- repair skips a title variable whose values duplicate an existing
  characteristic's meaning (the current check catches only same-name
  duplicates)
- or, between conflicting same-study columns, the reconciler prefers the one
  the authors recorded as a characteristic

### 14.3: A part's qualifiers are the ones its members share, computed in code
A read-only analysis of the sealed qualifier drop (13.1) found:
- **The drop starts before reconciliation:** annotation alone already scores
  34.3% precision on sealed.
- **Precision is mostly the models.** Of 27 unmatched predicted qualifiers,
  21 were added, put in the wrong slot, or wrong. Survival endpoints account
  for 10, and the three breast cancer studies for most.
- **Recall is mostly coverage and gold conventions:** 7 of the 18 misses are
  columns never produced.
- **The reconciler adds qualifiers.** It was asked for "qualifiers shared by
  every member" and wrote new ones instead, including on tuning, where it
  added "specimen collection" anchors to plain age (against the annotation
  rule in 6.3).

A part's qualifiers are now the non-unit qualifiers all its members' own
annotations carry, matched by slot and meaning (`reconcile.shared_qualifiers`).
What the reconciler wrote is kept as `proposed_qualifiers`. Its partition
decisions are untouched, and so is the prompt (reconcile-2).

| qualifiers, precision / recall | before | after |
|---|---|---|
| tuning, runs 1/2 | 61.5% / 64.0% | 89.5% / 68.0% |
| sealed (post hoc, not a headline) | 28.9% / 37.9% | 35.3% / 41.4% |

Pooling and primary-term scores are unchanged.

The scorer's qualifier parser no longer cuts free text at ";" (`t(9;22)`). No
score changes.

### 14.4: Recommended for the next corpus, not done here
- **Annotator instructions:**
  - The `object_class` examples are only genes and lesions. Add a cell
    population example that doesn't come from either corpus.
  - Say not to restate the primary term, name the study's disease, or describe
    the values.
  - Say that a qualifier must come from the column's name or values; the study
    summary explains a column but is not a source. Several sealed false
    positives (disease context, an ICU-admission anchor) came from the summary.
  - Prefer a term for the whole concept (overall survival) as the primary over
    restating it as a qualifier.
- **Gold conventions to settle:**
  - whether `event_time_anchor` covers states, windows and assessment weeks
  - whether survival times get anchors
  - whether severity scores name their disease (the sealed gold does both)
  - whether assumed conventions extend beyond units
  - that variables with predicate `none` carry no qualifiers (both golds
    already do this, but it isn't written down)

These need new annotation runs and a new corpus to measure honestly, so they
wait.

## Making the evaluation trustworthy (handoff tasks 5–8, 2026-10-09)

### 15.1: The models don't remember these series (`eval/memorization/`)
Sonnet and Opus were given each tuning and sealed accession, with no data
and no tools, and asked to list the series' characteristic keys and values.
- They declined 53 of 58 series-model pairs.
- No series met the pre-registered recall rule: at least 50% of keys, and at
  least 30 points above a same-corpus control.
- The one real recognition is GSE92415 (golimumab, PURSUIT). Opus named 3 of
  its 8 keys, all generic. The pipeline scored no better on that series
  (75.0%) than on the rest of the sealed corpus (69.0%).

The gold itself was never public. The sealed numbers show no sign of
memorization.

### 15.2: Intervals and paired tests revise four earlier claims (`eval/stats/`)
Study-level bootstrap intervals, paired comparisons, and AUCs for each
confidence signal:
- **Stands:** pooling F1 beats every baseline on both corpora, and every
  paired interval excludes zero. For example, sealed final minus identical
  names is +29.2 points (+12.3 to +46.0).
- **Not established:**
  - reconciliation's gain on tuning (7.3): +4.3 points (−11.9 to +18.5)
  - merge links (12.3), which have no detectable effect: +1.9 F1 points
    (−3.4 to +9.0), against run-to-run noise of 0.6 and 2.2 points
  - "generalization held": tuning F1 has a 95% interval of 66–95%
- **Confidence signals fail on unseen data for annotation.**
  - On tuning, tier AUC is 0.80, but the tier checks were chosen on tuning
    (8.1).
  - On sealed, tier AUC is 0.54, and annotation agreement 0.53, so neither
    is distinguishable from chance.
- **Partition agreement detects false merges (AUC 0.94 on tuning) and is
  blind to missed ones.** Both runs miss the same merges. Every sealed
  pooling error is a missed merge, so the tiers can't route them to review.
- At about 15 studies, a pooling-F1 interval has a half-width of 8–14
  points. A new sealed corpus (task 9) should be sized, and its comparisons
  pre-registered, with that in mind.

### 15.3: Renamed columns cost little; stand-in subagents get Read and Write only (`eval/robustness/`)
All 72 tuning characteristic names were paraphrased, values were kept, and
the columns were re-annotated (annotate-2, two runs). Against the original
runs:
- primary term: −2.4 points (−7.0 to +1.2), smaller than run-to-run noise of
  6 points
- pooling F1: +0.2
- run agreement: −5.8 points
- qualifiers: fell the most, because they are read from the name

The pipeline relies on values and context more than on names.

Process change. The plugin's agents have only Read and Write. The
general-purpose agents launched in their place can also run shell commands
and share the session scratchpad. In this run, three of them overwrote one
another's helper script, and one printed another batch's input items. No
answer crossed runs (transcripts audited). From now on, a stand-in prompt
says: use only the Read and Write tools, and write nothing but the answer
file.

### 15.4: An independent curation sheet is ready, waiting for a person (`eval/curation/`)
- 44 columns from 5 sealed series, chosen by a fixed rule. Values are taken
  from raw SOFT. No gold or pipeline output is in it.
- `agreement.py` scores three comparisons: person vs gold, pipeline vs gold,
  and pipeline vs person.
- Pre-registered: if the pipeline scores at least 10 points higher against
  the gold than against the person, the sealed numbers partly measure
  agreement with Claude's conventions.

### 15.5: The easy-first fast path is safe but not worth building yet (`eval/fastpath/`)
Handoff task 12, measured from existing outputs. Code annotates a column as
exact when two conditions hold:
- its name equals exactly one property-space label
- its values agree with that term: it is their top proposed category, or
  the values are numeric and propose none

It takes about 10% of columns: 12 of 105 on tuning, 14 of 141 on sealed (post
hoc). On those columns it matches the pipeline exactly (6/6 and 12/14 right).
The value guard is what makes it safe. Without it, accuracy falls to 82% and
74%.

It saves about one annotate batch per run, roughly 5% of subagent calls, on
columns the subagents already get right. That doesn't pay for a second
annotation path and its review mechanics. Revisit for large corpora.
