"""Publish: the harmonized variables, their columns, and SSSOM mappings.

Everything is recomputed from `scored.parquet` and the review overlay on every
run, so review work survives re-running any stage (see `review`). Output:

  variables.tsv       one row per variable: name, predicate, primary term
                      (full IRI and CURIE), qualifiers, member columns, review
                      status and tier
  columns.tsv         one row per column: its variable, unit, value recodes,
                      review status, tier and the reasons for it
  mappings.sssom.tsv  one SSSOM mapping per column, with a metadata header
  pooled_samples.tsv  the pooled table: one row per sample across all studies,
                      one column per variable, harmonized (recoded) values
  pooled_values.tsv   the same values in long form, each beside its raw value
                      and the study column it came from

Mapping predicates: exact -> skos:exactMatch, broad -> skos:broadMatch (the
column is narrower than the term), indicator -> skos:relatedMatch (a yes/no
indicator of the term), none -> object sssom:NoTermFound. Rejected variables
have no mapping. Qualifiers have no SSSOM slot, so they are spelled out in
`comment` and kept structured in variables.tsv.

Justification: a reviewer's edit is semapv:ManualMappingCuration, with the
reviewer as author. Everything else is semapv:CompositeMatching (retrieval,
model judgment and code checks), with the reviewer recorded when they
accepted it.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from colharmonize import __version__, review
from colharmonize.workspace import Workspace

UNSPECIFIED_LICENSE = "https://w3id.org/sssom/license/unspecified"
PREDICATE = {"exact": "skos:exactMatch", "broad": "skos:broadMatch", "indicator": "skos:relatedMatch",
             "none": "skos:exactMatch"}
BASE_PREFIXES = {
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "semapv": "https://w3id.org/semapv/vocab/",
    "sssom": "https://w3id.org/sssom/",
    "col": "urn:colharmonize:column:",
}


def _qualifier_text(qualifiers: str, ontology) -> str:
    """'slot=IRI [label]' for terms, 'slot="text" (ungrounded)' for free text."""
    out = []
    for slot, value in json.loads(qualifiers):
        v = ontology.validate(value) if ":" in value and " " not in value else None
        out.append(f"{slot}={v.iri} [{v.label}]" if v is not None and v.valid else f'{slot}="{value}" (ungrounded)')
    return "; ".join(out)


def _unit(qualifiers: str, detected: object) -> str:
    for slot, value in json.loads(qualifiers):
        if slot == "unit":
            return value
    return "" if detected is None or (isinstance(detected, float) and detected != detected) else str(detected)


def build(ws: Workspace, ontology) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """(variables, columns, stale decision ids) after applying the review overlay."""
    rows, stale = review.current(pd.read_parquet(ws.root / "scored.parquet"), review.load_overlay(ws))
    detected = pd.read_parquet(ws.columns).set_index(["study_id", "column"]).unit.to_dict() if ws.columns.exists() else {}
    overlay = review.load_overlay(ws)
    cols = pd.DataFrame({
        "study_id": rows.study_id, "column": rows.column, "variable_id": rows.variable_id,
        "unit": [_unit(q, detected.get((s, c))) for q, s, c in zip(rows.qualifiers, rows.study_id, rows.column)],
        "recodes": rows.recodes, "review_status": rows.review_status, "tier": rows.tier, "reasons": rows.reasons,
    }).sort_values(["variable_id", "study_id", "column"]).reset_index(drop=True)
    variables = []
    for vid, g in rows.groupby("variable_id", sort=True):
        r = g.iloc[0]
        v = ontology.validate(r.primary_curie) if r.primary_curie else None
        d = overlay.get(vid)
        variables.append({
            "variable_id": vid, "name": r.variable_name, "predicate": r.predicate,
            "primary_iri": v.iri if v else "", "primary_curie": r.primary_curie or "",
            "primary_label": v.label if v else "",
            "qualifiers": _qualifier_text(r.qualifiers, ontology),
            "n_columns": len(g), "n_studies": g.study_id.nunique(),
            "columns": "; ".join(f"{s}/{c}" for s, c in zip(g.study_id, g.column)),
            "review_status": r.review_status, "tier": r.variable_tier,
            "reviewer": d.reviewer if d and vid not in stale else "",
            "note": d.note if d and vid not in stale else "",
        })
    return pd.DataFrame(variables), cols, stale


def sssom(variables: pd.DataFrame, columns: pd.DataFrame, ontology, mapping_set_id: str,
          license: str = UNSPECIFIED_LICENSE) -> str:
    """SSSOM TSV text: a '#'-prefixed YAML metadata block, then one mapping per column."""
    var = variables.set_index("variable_id")
    rows, prefixes = [], dict(BASE_PREFIXES)
    for c in columns.itertuples(index=False):
        v = var.loc[c.variable_id]
        if v.review_status == "rejected":
            continue
        if v.primary_curie:
            obj, obj_label = v.primary_curie, v.primary_label
            prefix = obj.split(":", 1)[0]
            prefixes[prefix] = v.primary_iri[: -len(obj.split(":", 1)[1])]
        else:
            obj, obj_label = "sssom:NoTermFound", ""
        edited = v.review_status == "edited"
        comment = [f"variable {c.variable_id} '{v['name']}'", f"tier {c.tier}", f"review {v.review_status}"]
        if v.qualifiers:
            comment.insert(1, f"qualifiers: {v.qualifiers}")
        rows.append({
            "subject_id": f"col:{quote(c.study_id, safe='')}/{quote(c.column, safe='')}",
            "subject_label": c.column,
            "subject_source": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={c.study_id}",
            "predicate_id": PREDICATE[v.predicate],
            "object_id": obj, "object_label": obj_label,
            "mapping_justification": "semapv:ManualMappingCuration" if edited else "semapv:CompositeMatching",
            "author_label": v.reviewer if edited else "",
            "reviewer_label": v.reviewer if v.review_status == "accepted" else "",
            "comment": "; ".join(comment),
        })
    table = pd.DataFrame(rows)
    table = table.loc[:, [c for c in table.columns if table[c].astype(str).str.len().gt(0).any()]]
    header = {
        "mapping_set_id": mapping_set_id, "license": license,
        "mapping_tool": "colharmonize", "mapping_tool_version": __version__,
        "object_source_version": ontology.release_tag, "object_source": ontology.version_iri,
        "mapping_date": date.today().isoformat(),
    }
    lines = ["#curie_map:"] + [f"#  {k}: {v}" for k, v in sorted(prefixes.items())]
    lines += [f"#{k}: {v}" for k, v in header.items() if v]
    return "\n".join(lines) + "\n" + table.to_csv(sep="\t", index=False)


def _recoder(recodes: object):
    """A function raw value -> harmonized value from a column's [[from, to], ...] recodes."""
    pairs = json.loads(recodes) if isinstance(recodes, str) and recodes else (recodes or [])
    exact = {str(a): str(b) for a, b in pairs}
    loose = {str(a).strip().casefold(): str(b) for a, b in pairs}
    return lambda v: exact.get(v, loose.get(str(v).strip().casefold(), v))


def pool(values: pd.DataFrame, variables: pd.DataFrame, columns: pd.DataFrame,
         titles: dict[tuple[str, str], str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Stack every study's columns into the published variables, sample by sample.

    `values` is the per-sample table (study_id, sample_id, column, value) of
    `profile.sample_values`. Each value is recoded with its column's recodes;
    the raw value is kept beside it in the long table. Rejected variables are
    left out. Two columns of one variable may both hold a value for a sample
    only when the values agree (the co-occurrence rule); if they ever differ,
    both are kept, joined with " | ", and counted as conflicts.

    Returns (wide, long, report). Wide columns are named by variable, most
    widely pooled first; a name shared by two variables gets its id appended.
    """
    keep = variables[variables.review_status != "rejected"]
    var_of = {(c.study_id, c.column): c.variable_id for c in columns.itertuples(index=False)
              if c.variable_id in set(keep.variable_id)}
    recode = {(c.study_id, c.column): _recoder(c.recodes) for c in columns.itertuples(index=False)}
    unit = {(c.study_id, c.column): c.unit for c in columns.itertuples(index=False)}
    name = dict(zip(keep.variable_id, keep["name"]))
    long = []
    for r in values.itertuples(index=False):
        key = (r.study_id, r.column)
        if key not in var_of or r.value is None or str(r.value).strip() == "":
            continue
        long.append({"study_id": r.study_id, "sample_id": r.sample_id, "variable_id": var_of[key],
                     "variable": name[var_of[key]], "value": recode[key](str(r.value)), "raw_value": str(r.value),
                     "source_column": r.column, "unit": unit.get(key) or ""})
    long = pd.DataFrame(long, columns=["study_id", "sample_id", "variable_id", "variable", "value", "raw_value",
                                       "source_column", "unit"])
    order = (keep.sort_values(["n_studies", "n_columns", "name"], ascending=[False, False, True]).variable_id.tolist())
    counts = keep["name"].value_counts()
    header = {v: name[v] if counts[name[v]] == 1 else f"{name[v]} [{v}]" for v in order}
    conflicts = 0
    cells: dict[tuple[str, str], dict[str, str]] = {}
    for (study, sample, vid), g in long.groupby(["study_id", "sample_id", "variable_id"], sort=False):
        distinct = list(dict.fromkeys(g.value))
        conflicts += len(distinct) > 1
        cells.setdefault((study, sample), {})[header[vid]] = " | ".join(distinct)
    samples = sorted(set(zip(values.study_id, values.sample_id)))
    wide = pd.DataFrame([{"study_id": s, "sample_id": smp, "sample_title": (titles or {}).get((s, smp), ""),
                          **cells.get((s, smp), {})} for s, smp in samples],
                        columns=["study_id", "sample_id", "sample_title", *header.values()])
    report = {"samples": len(wide), "studies": wide.study_id.nunique(), "variables": len(header),
              "values": len(long), "conflicting_cells": conflicts}
    return wide, long, report


def publish(ws: Workspace, ontology, out: Path, mapping_set_id: str | None = None,
            license: str = UNSPECIFIED_LICENSE, pooled: bool = True) -> dict:
    variables, columns, stale = build(ws, ontology)
    bad = [c for c in variables.primary_curie if c and not ontology.validate(c).valid]
    if bad:
        raise SystemExit(f"refusing to publish: {len(bad)} primary terms fail validation, e.g. {bad[:3]}")
    out.mkdir(parents=True, exist_ok=True)
    variables.to_csv(out / "variables.tsv", sep="\t", index=False)
    columns.to_csv(out / "columns.tsv", sep="\t", index=False)
    (out / "mappings.sssom.tsv").write_text(sssom(variables, columns, ontology,
                                                  mapping_set_id or f"urn:colharmonize:{ws.root.name}", license))
    result = {"variables": len(variables), "columns": len(columns), "stale_decisions": stale,
              "status": variables.review_status.value_counts().to_dict()}
    if pooled:
        from colharmonize import profile
        samples = pd.read_parquet(ws.samples) if ws.samples.exists() else pd.DataFrame()
        titles = dict(zip(zip(samples.study_id, samples.sample_id), samples.title)) if len(samples) else {}
        wide, long, report = pool(profile.sample_values(ws), variables, columns, titles)
        wide.to_csv(out / "pooled_samples.tsv", sep="\t", index=False)
        long.to_csv(out / "pooled_values.tsv", sep="\t", index=False)
        result["pooled"] = report
    return result
