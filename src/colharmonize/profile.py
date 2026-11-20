"""Column profiles: what every downstream stage, and every prompt, sees about a column.

Built from the MetaMend project. Values are kept verbatim; profiling only counts.
"""
from __future__ import annotations

import json
from collections import Counter

import pandas as pd

from colharmonize import metamend_bridge as gb
from colharmonize.detect import shape_hint
from colharmonize.workspace import Workspace

MAX_VALUES = 40   # distinct values stored per column; counts are always complete


def value_counts(values: pd.Series) -> list[list]:
    """[[value, count], ...] most common first, ties broken by value for stable output."""
    counts = Counter(v for v in values if v is not None and str(v).strip() != "")
    return [[v, n] for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def build(ws: Workspace) -> dict[str, int]:
    """Write columns, samples and studies tables for a workspace whose MetaMend project exists."""
    values = gb.sample_values(ws.metamend, namespaces=("characteristic", "attribute"))
    chars = values[values.namespace == "characteristic"]
    attrs = values[values.namespace == "attribute"]
    fields = gb.field_table(ws.metamend)
    units = {(r.study_id, r.name): r.unit for r in fields.itertuples(index=False)
             if r.namespace == "characteristic" and r.scope == "sample"}
    n_study = values.groupby("study_id").sample_id.nunique().to_dict()

    rows = []
    for (study, name), grp in chars.groupby(["study_id", "name"], sort=True):
        vc = value_counts(grp.value)
        rows.append({
            "study_id": study, "column": name, "source": "characteristic",
            "n_samples": grp.sample_id.nunique(), "n_study_samples": n_study.get(study, 0),
            "n_distinct": len(vc), "values": json.dumps(vc[:MAX_VALUES], ensure_ascii=False),
            "shape_hint": shape_hint(v for v, _ in vc), "unit": units.get((study, name)),
        })
    columns = pd.DataFrame(rows)
    columns.to_parquet(ws.columns, index=False)

    def first(df: pd.DataFrame, name: str) -> pd.Series:
        sub = df[(df.name == name) & (df.ordinal == 0)]
        return sub.set_index(["study_id", "sample_id"]).value

    samples = pd.concat({"title": first(attrs, "title"), "source_name": first(attrs, "source_name")}, axis=1).reset_index()
    samples.to_parquet(ws.samples, index=False)

    studies = gb.study_attributes(ws.metamend)
    studies["n_samples"] = studies.study_id.map(n_study).fillna(0).astype(int)
    studies.to_parquet(ws.studies, index=False)
    return {"studies": len(studies), "samples": len(samples), "columns": len(columns)}


def annotation_columns(ws: Workspace) -> pd.DataFrame:
    """Every column that gets an annotation: characteristics, plus columns recovered
    by repair, minus characteristics that repair split (their parts replace them)."""
    cols = pd.read_parquet(ws.columns).assign(origin="characteristic")
    if not ws.derived.exists():
        return cols
    derived = pd.read_parquet(ws.derived)
    split_parents = set(zip(derived[derived.source == "characteristic"].study_id,
                            derived[derived.source == "characteristic"].source_column))
    cols = cols[[(s, c) not in split_parents for s, c in zip(cols.study_id, cols.column)]]
    n_study = pd.read_parquet(ws.studies).set_index("study_id").n_samples.to_dict()
    rows = []
    for (study, column), grp in derived.groupby(["study_id", "column"], sort=True):
        vc = value_counts(grp.value)
        rows.append({
            "study_id": study, "column": column, "source": grp.source.iloc[0],
            "n_samples": grp.sample_id.nunique(), "n_study_samples": n_study.get(study, 0),
            "n_distinct": len(vc), "values": json.dumps(vc[:MAX_VALUES], ensure_ascii=False),
            "shape_hint": shape_hint(v for v, _ in vc), "unit": None,
            "origin": "split" if grp.source.iloc[0] == "characteristic" else grp.source.iloc[0],
        })
    return pd.concat([cols, pd.DataFrame(rows)], ignore_index=True)


def sample_values(ws: Workspace, all_values: bool = False) -> pd.DataFrame:
    """Per-sample values of every annotation column: study_id, sample_id, column, value.

    Characteristics come from MetaMend; recovered columns from repair. Split
    parents are dropped, as in annotation_columns. A key repeated on one
    sample has several values; the judgment stages see the first, and
    `all_values` keeps every one (one row each, in order) for publishing.
    """
    from colharmonize import metamend_bridge as gb
    chars = gb.sample_values(ws.metamend)
    if not all_values:
        chars = chars[chars.ordinal == 0]
    chars = chars.rename(columns={"name": "column"})[["study_id", "sample_id", "column", "value"]]
    keep = set(zip(*annotation_columns(ws)[["study_id", "column"]].T.values))
    parts = [chars[[(s, c) in keep for s, c in zip(chars.study_id, chars.column)]]]
    if ws.derived.exists():
        parts.append(pd.read_parquet(ws.derived)[["study_id", "sample_id", "column", "value"]])
    return pd.concat(parts, ignore_index=True)


def cooccurrence(values: pd.DataFrame) -> dict[tuple[str, str, str], str]:
    """For each pair of columns in one study that share samples: 'identical' when
    their values agree on every shared sample, else 'conflicting'. Keys are
    (study, column_a, column_b) with a < b. Pairs on disjoint samples are absent."""
    out = {}
    for study, grp in values.groupby("study_id"):
        by_col = {c: dict(zip(g.sample_id, g.value)) for c, g in grp.groupby("column")}
        cols = sorted(by_col)
        for i, a in enumerate(cols):
            for b in cols[i + 1:]:
                shared = by_col[a].keys() & by_col[b].keys()
                if shared:
                    same = all(str(by_col[a][s]).strip().casefold() == str(by_col[b][s]).strip().casefold() for s in shared)
                    out[(study, a, b)] = "identical" if same else "conflicting"
    return out
