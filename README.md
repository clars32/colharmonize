# colharmonize

Harmonizes metadata columns across datasets so they can be pooled. For every
(dataset, column), colharmonize decides two things:

- **which harmonized variable the column belongs to.** Columns that can be
  stacked into one column of a pooled table without losing meaning share a
  variable.
- **what the variable means in the ontology.** That is a primary term with a
  match type (exact, broad, indicator or none), plus qualifiers: subject,
  object, reference event, method and unit.

The judgment steps run through Claude Code subagents. The package itself never
calls a model. It writes task files, validates the answers, and records every
decision with its provenance.

## How a run goes

In Claude Code with the plugin installed, `/harmonize <workspace> <sources...>`
runs every stage. The only human step is review.

| Stage | Command | Who judges |
|---|---|---|
| Ingest | `colharmonize ingest` | GEOmend parses and profiles (offline by default) |
| Repair | `tasks write repair`, then `repair apply` | One subagent run: variables hidden in titles, columns that encode two things |
| Candidates | `colharmonize candidates` | Code: exact match, two embedding models, values-to-category, ZOOMA/OLS4 cache |
| Annotate | `tasks write annotate` (runs 1 and 2), then `annotate apply` | Two independent subagent runs, one answer per column |
| Reconcile | `tasks write reconcile` (runs 1 and 2), then `reconcile apply` | Two independent subagent runs: related columns side by side, partitioned into variables |
| Score | `colharmonize score` | Code: run agreement and checks set each column's review tier |
| Review | `review page`, then `review apply EXPORT` | A person, on a local HTML page |
| Publish | `colharmonize publish` | Code: `variables.tsv`, `columns.tsv`, `mappings.sssom.tsv`, review overlay applied last |
| Registry | `registry use` before reconcile, `registry add` after review | Code: carries reviewed variables to later runs |

Every identifier is validated against the pinned ontology file, never a live
service. Answers are checked against a content hash of the batch they answer,
so stale or misfiled answers are refused.

## colharmonize and GEOmend are separate tools

[GEOmend](https://github.com/prestonraab/GEOmend) prepares the data;
colharmonize decides what the columns mean and which ones pool. Each must stay
useful on its own.

| | GEOmend | colharmonize |
|---|---|---|
| Purpose | Turn GEO series and local tables into profiled, reviewable, exportable cohort projects | Decide which columns pool across datasets and what they mean in the ontology |
| Owns | SOFT/table parsing, profiling (types, units, missingness, reference events), unit normalization, lexical retrieval, the concept-decision data model, review packets, project export and replay | Claude task files and the Claude Code plugin, property-space retrieval (embeddings, ZOOMA, OLS4), annotation, cross-dataset reconciliation, scoring, the persistent variable registry, SSSOM/TSV export, evaluation |
| Models | Optional, local and loopback-only (Ollama), off unless a model is configured. colharmonize ingests with it off | Claude, via Claude Code subagents |
| Knows about the other | No | Reads GEOmend projects through `geomend.project.ProjectClient`; writes back only through GEOmend's public operations (`project concepts`, `project transformations` provider proposals, review packets) |

**Overlap since GEOmend 0.0.7.** With a local model configured, GEOmend's
categorical inference proposes cross-study variables with value recodes. That
is the decision colharmonize's reconcile stage makes with Claude. They differ:
- GEOmend's is opt-in, runs once, and handles unitless fields with at most 32
  categories.
- GEOmend treats co-occurring fields as evidence; colharmonize refuses to pool
  them.

Which tool should own cross-study pooling is an open question for the two
maintainers (decisions log 1.5).

**Where a change belongs.** Would it help a GEOmend user who never runs Claude?
Then it goes to GEOmend as a pull request: a parser fix, better unit detection,
ID validation, a richer concept-relation model. Does it need Claude, agreement
between independent runs, or memory across projects? Then it belongs here. colharmonize never edits
GEOmend's files or databases directly, and nothing in GEOmend depends on
colharmonize.

## Layout

| Path | Contents |
|---|---|
| `src/colharmonize/` | The package. `ontology.py` holds the pinned release and validator, `geomend_bridge.py` the only GEOmend imports, `detect.py` value-shape hints, and `cli.py` the `colharmonize` command |
| `tests/` | pytest suite: regression cases from iteration 2 and contract tests for the GEOmend boundary |
| `plugin/` | The Claude Code plugin: the `/harmonize` skill and the repairer, annotator and reconciler agents |
| `docs/` | The decisions log and proposed GEOmend changes |
| `eval/` | Sealed evaluation corpora, gold standards and how they were selected. Self-contained so it can move to `geomend-research`. |
| `work/` | Run workspaces and scratch projects (git-ignored; a GEOmend project is ~1.5 GB) |

## Setup

```bash
/opt/anaconda3/bin/conda create -p ./.venv --override-channels -c conda-forge python=3.13
./.venv/bin/python -m pip install -e ".[dev]"
./.venv/bin/python -m pytest
./.venv/bin/colharmonize ontology pin --json efo.json --tag v3.94.0 --out work/ontology/efo-v3.94.0
./.venv/bin/colharmonize ontology store --ontology work/ontology/efo-v3.94.0 --out work/ontology/efo-v3.94.0.sqlite
```

GEOmend requires Python 3.13. The pinned ontology directory and the store are
regenerable and kept under `work/`.

## Status

Iteration 3, in progress. The Down syndrome corpus from iteration 2
(`../efo-column-mapping`) is the tuning set. A 16-series corpus in four other
disease areas is sealed for a single final measurement.

On the tuning gold (13 series, 84 columns), pooling F1 is 82.6%, against 67.7%
for iteration 2 and 56.7% for GEOmend's `propose()`. Every pre-accepted column
was correct. These numbers come from the data the pipeline was tuned on; see
`docs/decisions_log.md` sections 7 and 8.
