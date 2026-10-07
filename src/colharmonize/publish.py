"""Publish: the harmonized variables, their columns, and SSSOM mappings.

Everything is recomputed from `scored.parquet` and the review overlay on every
run, so review work survives re-running any stage (see `review`). Output:

  variables.tsv       one row per variable: name, predicate, primary term
                      (full IRI and CURIE), qualifiers, member columns, review
                      status and tier
  columns.tsv         one row per column: its variable, unit, value recodes,
                      review status, tier and the reasons for it
  mappings.sssom.tsv  one SSSOM mapping per column, with a metadata header

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


def publish(ws: Workspace, ontology, out: Path, mapping_set_id: str | None = None,
            license: str = UNSPECIFIED_LICENSE) -> dict:
    variables, columns, stale = build(ws, ontology)
    bad = [c for c in variables.primary_curie if c and not ontology.validate(c).valid]
    if bad:
        raise SystemExit(f"refusing to publish: {len(bad)} primary terms fail validation, e.g. {bad[:3]}")
    out.mkdir(parents=True, exist_ok=True)
    variables.to_csv(out / "variables.tsv", sep="\t", index=False)
    columns.to_csv(out / "columns.tsv", sep="\t", index=False)
    (out / "mappings.sssom.tsv").write_text(sssom(variables, columns, ontology,
                                                  mapping_set_id or f"urn:colharmonize:{ws.root.name}", license))
    return {"variables": len(variables), "columns": len(columns), "stale_decisions": stale,
            "status": variables.review_status.value_counts().to_dict()}
