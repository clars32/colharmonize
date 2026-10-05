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

## colharmonize and GEOmend are separate tools

[GEOmend](https://github.com/prestonraab/GEOmend) prepares the data;
colharmonize decides what the columns mean and which ones pool. Each must stay
useful on its own.

| | GEOmend | colharmonize |
|---|---|---|
| Purpose | Turn GEO series and local tables into profiled, reviewable, exportable cohort projects | Decide which columns pool across datasets and what they mean in the ontology |
| Owns | SOFT/table parsing, profiling (types, units, missingness, reference events), lexical retrieval, the concept-decision data model, review packets, cohort export and replay | Claude task files and the Claude Code plugin, property-space retrieval (embeddings, ZOOMA, OLS4), annotation, cross-dataset reconciliation, scoring, the persistent variable registry, SSSOM/TSV export, evaluation |
| Models | Local and loopback-only | Claude, via Claude Code subagents |
| Knows about the other | No | Reads GEOmend projects; writes back only through GEOmend's public commands (`cohort concepts`, `cohort provider`, review packets) |

**Where a change belongs.** Would it help a GEOmend user who never runs Claude?
Then it goes to GEOmend as a pull request: a parser fix, better unit detection,
ID validation, a richer concept-relation model. Does it need model judgment or
memory across projects? Then it belongs here. colharmonize never edits
GEOmend's files or databases directly, and nothing in GEOmend depends on
colharmonize.

## Layout

| Path | Contents |
|---|---|
| `src/colharmonize/` | The package. `ontology.py` holds the pinned release and validator, `geomend_bridge.py` the only GEOmend imports, `detect.py` value-shape hints, and `cli.py` the `colharmonize` command |
| `tests/` | pytest suite: regression cases from iteration 2 and contract tests for the GEOmend boundary |
| `docs/` | Design notes, including proposed GEOmend changes |
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

Iteration 3, in progress. The Down syndrome corpus (64 series) from iteration 2
(`../efo-column-mapping`) is the tuning set. A 16-series corpus in four other
disease areas is sealed for a single final measurement.
