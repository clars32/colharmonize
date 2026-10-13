# Proposed GEOmend changes for the Claude matching stage

Draft for Preston, 2026-10-02. Written against GEOmend `main` at `989ec3d` (v0.0.2).

## Status at GEOmend 0.0.9 (released 2026-10-12)

The user now owns GEOmend (handed over by Preston on 2026-10-12). Each change
below was a separate branch with a test that fails without it. All were
merged and released as 0.0.9: 1,491 tests pass.

| Item | Status at 0.0.9 |
|---|---|
| Fix 1, concept IDs not validated | **Done.** An ID in a namespace the configured store covers must exist there. Provider proposals with unknown references are recorded invalid. IRIs are canonicalized first |
| Fix 2, `_KEY` regex | **Done:** `fix/characteristic-key-punctuation`. `PARSER_VERSION` bumped |
| Fix 3, `propose()` merges "unresolved characteristic" | **Done.** Kept per study |
| Fix 4, units lost | Partly obsolete. Header units already work. Scaled units (`1000/microliter`) would need a unit-model redesign; a new fix makes them stay unresolved instead of silently equaling `1/microliter` |
| Fix 5, store keeps CURIEs only | **Done.** `GraphNode.iri`; colharmonize's store builder fills it (decisions log 15.12) |
| Fix 6, neighbour cutoff | **Done.** Parents survive the limit |
| Changes 1–3 | Deferred to the user. They change the data contract and matter once colharmonize writes concept decisions into GEOmend |

## Status at GEOmend 0.0.8 (`main` at `f0a8fcc`, checked 2026-10-07)

None of the changes below has landed. Paths are the current ones.

| Item | Status at 0.0.8 | Where |
|---|---|---|
| Change 1, directed relations | Still applicable: the same six undirected relations | `cohort_models.py:226-229`; interchange maps only exact/related (`_cohort.py:1216-1222`) |
| Change 2, qualifier slots | Still applicable: `CohortConceptDecision` has no qualifiers, and `SemanticFacets` has no `method` | `cohort_models.py:254-262`, `models.py:93-117` |
| Change 3, pre-accepted state | Still applicable: every unreviewed mapping is a priority-4 `mapping_inspection` task | `project_navigation.py:338-356` |
| Fix 1, concept IDs not validated | Still applicable: any non-empty locator is accepted, and provider `ontology_references` are unchecked | `_cohort.py:1482-1510`, `cohort_models.py:121` |
| Fix 2, `_KEY` regex | **Fixed on branch `fix/characteristic-key-punctuation` (`e617f01`, pushed 2026-10-08), PR pending.** Root cause: the parser split at the first `:` or `=` and validated keys against `_KEY`; it now splits at a colon followed by whitespace when the key is valid. 537 of 151,653 attributes in 79 SOFT files change; GEOmend suite 1,481 passed | `geo_profile.py:41-48, 211-245` |
| Fix 3, `propose()` merges "unresolved characteristic" | Still applicable: moved, same label set | `cohort_mapping_core.py:34-36, 137` |
| Fix 4, units lost | Partly done: header suffixes now give units (`(hours)`, `(years)`), but `WBC, 1000/microliter` still has none, and the inventory field's `unit` is never set from the header | `cohort_units.py:49-116`, `cohort_profile.py:308-316` |
| Fix 5, store keeps CURIEs only | Still applicable: local candidates have no IRI, so interchange writes URNs | `ontology.py:19-22`, `_cohort.py:1226` |
| Fix 6, neighbour cutoff | Partly obsolete: the GEO term inspector was removed in `f0a8fcc`; the cutoff remains in `one_hop_context`, used by value groups | `ontology.py:175-206` |

Command names changed: the `geomend cohort` group is now `geomend project`.
Concept decisions are written with `project concepts` and transformations
with `project transformations` (provider proposals). In Python, the entry
point is `geomend.project.ProjectClient`.

## Why these changes

The next stage after GEOmend uses Claude to decide two things for each column.
First, which columns across studies can be pooled into one variable. Second, what
each column means in the ontology. That stage is called `colharmonize` for now
and runs downstream of GEOmend.

To write its decisions back through `cohort concepts`, GEOmend's concept model
needs to say two things it can't say today:

- **Direction.** "This column is narrower than the term" is a different claim
  from "this column is the term". With a direction, we can attach a term as an
  anchor *without* renaming the column.
- **Several terms per column.** For example, `age at draw (years)` is the age
  property, the blood-draw reference event, and the year unit.

An Ollama-free feasibility run on the 64-series Down syndrome corpus also
turned up a few small parser and validation issues. They are listed at the end
as separate small PRs.

## Change 1: directed concept relations

`ConceptRelation` (`cohort_models.py:194`) has `broader_or_narrower`, which has
no direction. The proposal adds two directed values plus an indicator relation, and keeps the old one
readable:

| relation | meaning (field relative to concept) | interchange predicate |
|---|---|---|
| `same_concept` | the field *is* the concept | `skos:exactMatch` (unchanged) |
| `narrower_than_concept` | the concept is broader; the field keeps its own name | `skos:broadMatch` |
| `broader_than_concept` | the concept is narrower than the field | `skos:narrowMatch` |
| `indicator_of_concept` | the field is a yes/no or 0/1 indicator of the concept (`shock: Yes/No` → septic shock) | `skos:relatedMatch` |
| `broader_or_narrower` | legacy, undirected | unchanged |

`indicator_of_concept` already exists as a workspace `MergeEdge.relation`
(`workspace_models.py:76`). Adding it to `ConceptRelation` lets cohort concept
decisions say the same thing. Eight of 68 variables in our new gold standard
need it.

Existing JSONL stays valid because the old literal remains. In
`concept_interchange` (`cohort.py:1091`), the two new relations get SKOS
predicates instead of `relations/<name>` IRIs. A new GEOmend version would
emit only the directed forms. Whether to deprecate `broader_or_narrower` is
your call.

## Change 2: qualifier slots on a concept decision

`CohortConceptDecision` (`cohort_models.py:222`) gains an optional
`qualifiers: list[ConceptQualifier] = []`. The slot names reuse
`SemanticFacets` (`models.py:93`), so field-side and target-side semantics use
one vocabulary:

```python
QualifierSlot = Literal["subject", "object_class", "event_time_anchor", "method", "unit"]

class ConceptQualifier(StrictModel):
    slot: QualifierSlot
    concept_id: str | None = None      # validated against the configured store
    text: str | None = None            # free text when no term exists (marked ungrounded)
    source_locator: str | None = Field(default=None, max_length=2048)

    # validator: exactly one of concept_id / text
```

Examples:

| field | relation, concept | qualifiers |
|---|---|---|
| `age in days at diagnosis` | `same_concept` efo:0004918 age at diagnosis | unit: uo:0000033 day |
| `age at draw` | `narrower_than_concept` efo:0000246 age | event_time_anchor: "blood draw" (text) · unit: uo:0000036 |
| `bcr-abl, t(9;22)` | `narrower_than_concept` efo:0007658 carrier status | object_class: "BCR-ABL1 fusion" (text) |

`method` is the one slot `SemanticFacets` lacks (qRT-PCR vs arrays, for
example). It is worth adding there too, so retrieval can compare it.

In interchange, qualifiers would export as extra rows that share the field's
subject and carry a GEOmend `qualifier/<slot>` predicate. That keeps the main
row a plain SSSOM triple.

## Change 3: pre-accepted state

You agreed that a pipeline decision can be "pre-accepted but still
reviewable". The suggested mechanism keeps "every mapping is a suggestion":

- `source: "algorithm"`, the existing value.
- `actor_id` set to the stage and version, e.g. `colharmonize-annotate@1`.
- A new optional `review_priority: Literal["pre_accepted", "confirm", "full_review"] | None`.

Review still owns the outcome. The field only orders the queue, and
`pre_accepted` items are spot-checked rather than skipped.

## Smaller fixes found by the feasibility run (separate PRs)

1. **Concept IDs aren't checked when a `source_locator` is given.** In the
   test project, `cohort concepts --concept-id efo:9999999 --source-locator …`
   was accepted, and so was a raw IRI string. Provider `ontology_references`
   aren't checked either. Proposal: resolve every concept ID against the
   configured ontology store, whether or not a locator is present.
2. **Two keys fail `_KEY` in `geo_profile.py:41`,** which puts 93 values into
   `unresolved characteristic`:
   - `%blast: 58.00` (GSE83449): the key must start with a letter.
   - `gestational age (weeks, days): 21 3/7` (GSE16176): `,` isn't allowed
     without a spaced colon.

   `_SPACED_KEY` already allows `,;%=+`. Proposal: align the two character
   classes, allow a leading `%`, and add both strings as fixtures.
3. **`propose()` merges every `unresolved characteristic` field across studies**
   (GSE16176, GSE1789, GSE4119, GSE83449) into one variable. Proposal: keep that
   label per study, i.e. add it to `AMBIGUOUS_CHARACTERISTIC_LABELS` or skip it
   in grouping.
4. **Some units are lost:**
   - `WBC, 1000/microliter` gets no unit.
   - A unit found in the profile doesn't always reach the inventory field.
     `Post mortem interval (hours)` and GSE151282 `age (years)` have hours/years
     in the profile but no unit on the field, so `propose()` treats them as text.
5. **The ontology store only stores CURIEs,** so candidates come back with
   `iri=None` and interchange writes `urn:geomend:concept:…` placeholders.
   Bioregistry's round trip also disagrees with EFO's own IRIs for about 6,900
   nodes in EFO 3.94 (mostly HGNC, plus AfPO, FMA and NCBIGene). Proposal: an
   optional `iri` column in the store's nodes table, filled from the source
   ontology.
6. **The neighbour lookup cuts off at a node limit** before reaching parents.
   At limit 20, `efo:0000324 cell type` loses its only parent because its 39
   children sort first. Proposal: list parents before children, or give each
   its own limit.

## What stays outside GEOmend

Decided 2026-10-05: GEOmend and colharmonize stay separate repositories, each
useful on its own. These stay in `colharmonize`, so GEOmend's loopback-only rule
for its own runtime is unaffected:
- the Claude Code task files and subagents
- cross-study reconciliation
- scoring
- the persistent variable registry
- SSSOM/TSV export

GEOmend sees only the results, written through `project concepts`,
`project transformations` provider proposals and the review packets. Nothing in GEOmend depends on
colharmonize. The test for where a change belongs: if it helps a GEOmend user
who never runs Claude, it is a GEOmend PR.

## Questions

1. ~~Same repo or separate?~~ Separate (decided 2026-10-05).
2. Is extending a v0.2 contract with optional fields acceptable without
   regenerating clients, or should changes 1 and 2 wait for a contract bump?
3. ~~Does the loopback rule cover downstream stages?~~ Moot now that the
   repositories are separate: it governs GEOmend's runtime, and colharmonize
   is a separate consumer of GEOmend's exports.
