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
