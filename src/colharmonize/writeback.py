"""Write harmonized variables back to the workspace's MetaMend project.

colharmonize decides which columns pool and what they mean. MetaMend users
who never run Claude can still use those decisions: each characteristic
column in a published variable becomes a MetaMend provider proposal. The
proposal names a target variable, carries the variable's ontology term and a
complete value recode, and keeps colharmonize's provenance. MetaMend validates
it against the field's actual values and keeps it pending its own review. A
proposal is never a reviewer vote, and nothing is selected unless asked
(decisions log 1.2, 1.6).

Not written back:
- rejected variables
- columns repair recovered from titles, source names or split values, which
  are not MetaMend fields
"""
from __future__ import annotations

import json

import pandas as pd

from colharmonize import __version__, metamend_bridge as gb, publish
from colharmonize.workspace import Workspace

PROVIDER_VARIABLE_PREFIX = "colharmonize:"


def value_mapping(recodes: object, distinct: list[str]) -> dict[str, str] | None:
    """A complete recode for MetaMend, or None to copy values unchanged.

    MetaMend refuses an explicit recode that leaves any reported value out, so
    values colharmonize didn't recode map to themselves.
    """
    pairs = json.loads(recodes) if isinstance(recodes, str) and recodes else (recodes or [])
    if not pairs:
        return None
    rec = {str(a): str(b) for a, b in pairs}
    return {v: rec.get(v, v) for v in distinct} | {a: b for a, b in rec.items() if a not in distinct}


def definition(v) -> str:
    """The variable's meaning as text: predicate, primary term and qualifiers."""
    if v.predicate == "none" or not v.primary_curie:
        head = "no ontology term (none)"
    else:
        head = f"{v.predicate} {v.primary_label} [{v.primary_curie}]"
    quals = f"; qualifiers: {v.qualifiers}" if isinstance(v.qualifiers, str) and v.qualifiers else ""
    return f"{head}{quals}. Harmonized by colharmonize."


def proposals(ws: Workspace, ontology) -> tuple[list[dict], pd.DataFrame]:
    """(proposals to send, every published column with what happens to it)."""
    variables, columns, _ = publish.build(ws, ontology)
    vby = {r.variable_id: r for r in variables.itertuples(index=False)}
    fields = gb.characteristic_fields(ws.metamend)
    out, rows = [], []
    for c in columns.itertuples(index=False):
        v = vby[c.variable_id]
        row = {"study_id": c.study_id, "column": c.column, "variable_id": c.variable_id,
               "review_status": v.review_status, "field_id": "", "action": "", "reason": ""}
        if v.review_status == "rejected":
            row.update(action="skipped", reason="variable rejected in review")
        elif (c.study_id, c.column) not in fields:
            row.update(action="skipped", reason="not a MetaMend characteristic field (recovered by repair)")
        else:
            field_id, distinct = fields[(c.study_id, c.column)]
            row.update(field_id=field_id, action="propose")
            out.append({
                "field_id": field_id,
                "variable_id": PROVIDER_VARIABLE_PREFIX + c.variable_id,
                "label": v.name,
                "definition": definition(v),
                "ontology_references": [v.primary_iri] if v.predicate != "none" and v.primary_iri else [],
                "mappings": value_mapping(c.recodes, distinct),
                "locator": f"colharmonize:{ws.root.name}/published/variables.tsv#{c.variable_id}",
                "rationale": (f"colharmonize {__version__}: {v.review_status}, review tier {v.tier}; pools "
                              f"{v.n_columns} column(s) from {v.n_studies} stud{'y' if v.n_studies == 1 else 'ies'}"),
            })
        rows.append(row)
    return out, pd.DataFrame(rows)


def run(ws: Workspace, ontology, *, select: bool = False, dry_run: bool = False) -> pd.DataFrame:
    """Send the proposals and return the per-column report (also written to published/)."""
    props, report = proposals(ws, ontology)
    if not dry_run and props:
        results = {r["field_id"]: r for r in gb.propose_mappings(ws.metamend, props, select=select,
                                                                provider_version=__version__)}
        for i, r in report.iterrows():
            res = results.get(r.field_id)
            if res is None:
                continue
            report.loc[i, "action"] = ("selected" if res["selected"] else "proposed") if res["valid"] else "refused"
            report.loc[i, "proposal_id"] = res["proposal_id"]
            if not res["valid"]:
                report.loc[i, "reason"] = "; ".join(res["failures"])[:500]
    out = ws.root / "published"
    out.mkdir(exist_ok=True)
    report.to_csv(out / "geomend_proposals.tsv", sep="\t", index=False)
    return report
