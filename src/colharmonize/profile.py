"""Column profiles: what every downstream stage, and every prompt, sees about a column.

Built from the GEOmend project. Values are kept verbatim; profiling only counts.
"""
from __future__ import annotations

import json
from collections import Counter

import pandas as pd

from colharmonize import geomend_bridge as gb
from colharmonize.detect import shape_hint
from colharmonize.workspace import Workspace

MAX_VALUES = 40   # distinct values stored per column; counts are always complete


def value_counts(values: pd.Series) -> list[list]:
    """[[value, count], ...] most common first, ties broken by value for stable output."""
    counts = Counter(v for v in values if v is not None and str(v).strip() != "")
    return [[v, n] for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def build(ws: Workspace) -> dict[str, int]:
    """Write columns, samples and studies tables for a workspace whose GEOmend project exists."""
    values = gb.sample_values(ws.geomend, namespaces=("characteristic", "attribute"))
    chars = values[values.namespace == "characteristic"]
    attrs = values[values.namespace == "attribute"]
    fields = gb.field_table(ws.geomend)
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

    studies = gb.study_attributes(ws.geomend)
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
