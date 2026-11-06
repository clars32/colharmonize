"""Review: a local page for checking each harmonized variable, and the overlay that keeps the decisions.

The review unit is a variable: its member columns side by side with their
values, the annotation they share, any value recodes, and why the variable is
in its tier. The page is one self-contained HTML file (data embedded, opens from
disk, no server). Decisions persist in the browser and export as JSON.

`colharmonize review apply` validates an export and merges it into the
workspace overlay, `review.json`. Publish recomputes its output from
`scored.parquet` and the overlay every time. Re-running a stage therefore never
discards review work: iteration 2 lost its decisions because s09 edited a
file that s08 later rebuilt.

Each decision records a fingerprint of the pipeline output it judged. If a
later run changes that variable, the decision is stale: the page shows the
variable again and publish doesn't apply the decision.

A decision can:
  - accept the variable as it is
  - edit its name, predicate, primary term or qualifiers
  - move member columns out, either to a variable of their own or into
    another variable (which then gives them its annotation)
  - reject it, meaning it is wrong and the reviewer has no fix
A column split out to its own variable gets the id `<parent>+<study>::<column>`,
and can be reviewed in turn once the page is rebuilt.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from colharmonize.workspace import Workspace

FORMAT = "colharmonize-review-1"
ANNOTATION = ["variable_name", "predicate", "primary_curie", "qualifiers"]
SLOTS = ("subject", "object_class", "event_time_anchor", "method", "unit")
NEW = "new"


class Edit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    predicate: Literal["exact", "broad", "indicator", "none"] | None = None
    primary: str | None = None                      # CURIE, or "" for no term
    qualifiers: list[tuple[str, str]] | None = None  # [slot, CURIE or text]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["accept", "edit", "reject"]
    fp: str
    at: str = ""
    reviewer: str = ""
    edit: Edit | None = None
    moves: dict[str, str] = Field(default_factory=dict)   # "study::column" -> "new" or a variable id
    note: str = ""


def _key(study: str, column: str) -> str:
    return f"{study}::{column}"


def _fp(rows: pd.DataFrame) -> str:
    """What a reviewer judged: members, annotation and recodes. Not the name or tier."""
    payload = sorted((r.study_id, r.column, r.predicate, r.primary_curie or "", r.qualifiers, r.recodes)
                     for r in rows.itertuples(index=False))
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:16]


def fingerprints(scored: pd.DataFrame) -> dict[str, str]:
    return {vid: _fp(g) for vid, g in scored.groupby("variable_id", sort=False)}


def derived_id(parent: str, member: str) -> str:
    return f"{parent}+{member}"


def _derived_fp(parent_fp: str, member: str) -> str:
    return hashlib.sha256(f"{parent_fp}+{member}".encode()).hexdigest()[:16]


def rekey(decisions: dict, fps: dict[str, str]) -> tuple[dict, dict[str, str]]:
    """Move decisions whose variable id no longer exists to the variable they judged.

    Ids can change between runs while the content does not (singleton
    numbering, group order). A decision follows its content when its
    fingerprint matches exactly one current variable; columns split out of a
    renamed variable (`<old>+<member>`) follow their parent. Returns the
    re-keyed decisions and the renames applied.
    """
    def fp_of(d) -> str:
        return d.fp if isinstance(d, Decision) else d.get("fp", "")
    owner: dict[str, list[str]] = {}
    for vid, fp in fps.items():
        owner.setdefault(fp, []).append(vid)
    renames = {}
    for vid, d in decisions.items():
        if vid not in fps and len(owner.get(fp_of(d), [])) == 1 and owner[fp_of(d)][0] not in decisions:
            renames[vid] = owner[fp_of(d)][0]
    out = {}
    for vid, d in decisions.items():
        new = renames.get(vid)
        if new is None:
            parent = next((old for old in renames if vid.startswith(old + "+")), None)
            new = renames[parent] + vid[len(parent):] if parent else vid
            if parent:
                renames[vid] = new
        out[new] = d
    return out, renames


def load_overlay(ws: Workspace) -> dict[str, Decision]:
    path = ws.root / "review.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {vid: Decision.model_validate(d) for vid, d in data["decisions"].items()}


def save_overlay(ws: Workspace, overlay: dict[str, Decision]) -> None:
    data = {"format": FORMAT, "decisions": {vid: d.model_dump(exclude_none=True) for vid, d in sorted(overlay.items())}}
    (ws.root / "review.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))


def current(scored: pd.DataFrame, overlay: dict[str, Decision]) -> tuple[pd.DataFrame, list[str]]:
    """The pipeline output with every still-valid decision applied, and the stale decision ids.

    Order: decide which decisions are valid, apply moves, then give every
    variable its annotation (the pipeline's, with any edit on top). A moved
    column takes its new variable's annotation and loses its recodes, which
    were written for the old variable's vocabulary.
    """
    rows = scored.copy()
    rows["key"] = [_key(s, c) for s, c in zip(rows.study_id, rows.column)]
    rows["moved"] = False
    fps = fingerprints(scored)
    overlay, _ = rekey(overlay, fps)
    base = {vid: g.iloc[0][ANNOTATION].to_dict() for vid, g in scored.groupby("variable_id", sort=False)}
    valid = {vid: d for vid, d in overlay.items() if fps.get(vid) == d.fp}
    for vid, d in list(valid.items()):
        for member, target in d.moves.items():
            m = (rows.variable_id == vid) & (rows.key == member)
            if target == NEW:
                new = derived_id(vid, member)
                rows.loc[m, "variable_id"] = new
                base[new] = {**base[vid], "variable_name": member.split("::", 1)[1]}
                fps[new] = _derived_fp(fps[vid], member)
            elif target in base:
                rows.loc[m, ["variable_id", "recodes", "moved"]] = [target, "[]", True]
    valid.update({vid: d for vid, d in overlay.items() if vid not in valid and fps.get(vid) == d.fp})
    stale = sorted(set(overlay) - set(valid))

    status, fp_col = {}, {}
    for vid in rows.variable_id.unique():
        ann, d = dict(base[vid]), valid.get(vid)
        if d and d.edit:
            e = d.edit
            if e.name is not None:
                ann["variable_name"] = e.name
            if e.primary is not None:
                ann["primary_curie"] = e.primary
            if e.predicate is not None:
                ann["predicate"] = e.predicate
            if e.qualifiers is not None:
                ann["qualifiers"] = json.dumps(sorted([list(q) for q in e.qualifiers]))
            if ann["predicate"] == "none":
                ann["primary_curie"] = ""
        m = rows.variable_id == vid
        for k, v in ann.items():
            rows.loc[m, k] = v
        tiers = rows.loc[m, "tier"]
        rows.loc[m, "variable_tier"] = max(tiers, key=["pre_accepted", "quick", "manual"].index)
        if d is not None:
            status[vid] = {"accept": "accepted", "edit": "edited", "reject": "rejected"}[d.action]
        else:
            status[vid] = "pre_accepted" if rows.loc[m, "variable_tier"].iloc[0] == "pre_accepted" else "unreviewed"
        fp_col[vid] = fps[vid]
    rows["review_status"] = rows.variable_id.map(status)
    rows["fp"] = rows.variable_id.map(fp_col)
    return rows, stale


def validate_export(ws: Workspace, export: dict, scored: pd.DataFrame, ontology,
                    conflicts: dict[tuple[str, str, str], str] | None = None) -> tuple[dict[str, Decision], list[str], list[str]]:
    """Decisions from a page export that can be applied, the stale ones, and problems.

    A reviewer can mistype an identifier as easily as a model can invent one,
    so every CURIE is checked against the pinned file. A move may not put two
    columns with conflicting values on the same samples into one variable (the
    co-occurrence rule binds reviewers too).
    """
    if export.get("format") != FORMAT:
        return {}, [], [f"not a {FORMAT} export"]
    fps = fingerprints(scored)
    members = {vid: set(_key(s, c) for s, c in zip(g.study_id, g.column)) for vid, g in scored.groupby("variable_id")}
    ok, stale, problems = {}, [], []
    decisions, renamed = rekey(export.get("decisions", {}), fps)
    parents_new = {derived_id(vid, m): vid for vid, d in decisions.items() for m, t in d.get("moves", {}).items() if t == NEW}
    for vid, raw in decisions.items():
        try:
            d = Decision.model_validate({**raw, "reviewer": raw.get("reviewer") or export.get("reviewer", "")})
        except Exception as e:  # noqa: BLE001 - report every malformed decision, keep going
            problems.append(f"{vid}: {e}")
            continue
        if vid in parents_new:
            parent = parents_new[vid]
            expected = _derived_fp(fps.get(parent, ""), vid[len(parent) + 1:])
        else:
            expected = fps.get(vid)
        if expected != d.fp:
            stale.append(vid)
            continue
        bad = []
        if d.edit:
            e = d.edit
            if e.primary:
                v = ontology.validate(e.primary)
                if not v.valid:
                    bad.append(f"primary {e.primary}: {v.reason}")
            if (e.predicate == "none") and e.primary:
                bad.append("predicate none with a primary term")
            if e.predicate in ("exact", "broad", "indicator") and e.primary == "":
                bad.append(f"predicate {e.predicate} without a primary term")
            for slot, value in e.qualifiers or []:
                if slot not in SLOTS:
                    bad.append(f"unknown qualifier slot {slot!r}")
                elif ":" in value and " " not in value and not ontology.validate(value).valid:
                    bad.append(f"qualifier {slot}={value}: {ontology.validate(value).reason}")
        for member, target in d.moves.items():
            if member not in members.get(vid, set()):
                bad.append(f"move: {member} is not in {vid}")
            elif target != NEW and target not in members:
                bad.append(f"move: no variable {target}")
            elif target != NEW and conflicts:
                study, col = member.split("::", 1)
                for other in members[target]:
                    s2, c2 = other.split("::", 1)
                    if s2 == study and conflicts.get((study, *sorted([col, c2]))) == "conflicting":
                        bad.append(f"move: {member} conflicts with {other} on shared samples")
        if bad:
            problems += [f"{vid}: {b}" for b in bad]
        else:
            ok[vid] = d
    return ok, sorted(stale), problems


def apply_export(ws: Workspace, export_path: Path, ontology, conflicts=None) -> dict:
    """Merge a page export into the workspace overlay. Later decisions replace earlier ones."""
    scored = pd.read_parquet(ws.root / "scored.parquet")
    export = json.loads(Path(export_path).read_text())
    ok, stale, problems = validate_export(ws, export, scored, ontology, conflicts)
    fps = fingerprints(scored)
    _, renamed = rekey(export.get("decisions", {}), fps)
    overlay, _ = rekey(load_overlay(ws), fps)
    overlay.update(ok)
    if not problems:
        save_overlay(ws, overlay)
    return {"applied": len(ok), "renamed": renamed, "stale": stale, "problems": problems, "saved": not problems,
            "overlay_decisions": len(overlay)}


# ---------------------------------------------------------------------------
# The page

def payload(ws: Workspace, ontology) -> dict:
    scored = pd.read_parquet(ws.root / "scored.parquet")
    overlay = load_overlay(ws)
    rows, stale = current(scored, overlay)
    from colharmonize import profile
    cols = profile.annotation_columns(ws).set_index(["study_id", "column"])
    studies = pd.read_parquet(ws.studies).set_index("study_id")
    cands = pd.read_parquet(ws.candidates)
    cands = cands[cands.displayed & (cands.pool == "space")]
    in_space = set(cands.curie)

    def term(curie: str) -> dict:
        if not curie:
            return {}
        return {"curie": curie, "label": ontology.label(curie), "def": (ontology.definition(curie) or "")[:240]}

    def quals(q: str) -> list:
        return [[s, v, ontology.label(v) if ":" in v and " " not in v else ""] for s, v in json.loads(q)]

    variables = []
    for vid, g in rows.groupby("variable_id", sort=False):
        first = g.iloc[0]
        members = []
        for r in g.itertuples(index=False):
            c = cols.loc[(r.study_id, r.column)] if (r.study_id, r.column) in cols.index else None
            alt = {}
            if r.alt_predicate and (r.alt_predicate, r.alt_primary_curie) != (r.predicate, r.primary_curie):
                alt = {"predicate": r.alt_predicate, **term(r.alt_primary_curie)}
            members.append({
                "key": r.key, "study": r.study_id, "column": r.column,
                "values": json.loads(c["values"])[:8] if c is not None else [],
                "n_samples": int(c["n_samples"]) if c is not None else 0,
                "n_study_samples": int(c["n_study_samples"]) if c is not None else 0,
                "recodes": json.loads(r.recodes), "tier": r.tier, "reasons": json.loads(r.reasons),
                "alt": alt, "alt_mates": json.loads(r.alt_mates or "[]"), "moved": bool(r.moved),
            })
        mine = cands[[(s, c) in set(zip(g.study_id, g.column)) for s, c in zip(cands.study_id, cands.column)]]
        top = (mine.sort_values(["n_sources", "best_rank"], ascending=[False, True])
               .drop_duplicates("curie").head(12))
        reasons = sorted({x for m in members for x in m["reasons"]})
        variables.append({
            "id": vid, "fp": first.fp, "name": first.variable_name, "predicate": first.predicate,
            "primary": term(first.primary_curie), "in_space": first.primary_curie in in_space or not first.primary_curie,
            "qualifiers": quals(first.qualifiers), "tier": first.variable_tier, "status": first.review_status,
            "reasons": reasons, "members": members,
            "candidates": [{**term(c.curie), "in_space": True} for c in top.itertuples(index=False)],
        })
    rank = {"manual": 0, "quick": 1, "pre_accepted": 2}
    variables.sort(key=lambda v: (rank.get(v["tier"], 9), -len(v["members"]), v["name"]))
    return {
        "workspace": ws.root.name, "ontology": ontology.release_tag,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "variables": variables, "stale": stale,
        "decisions": {vid: d.model_dump(exclude_none=True) for vid, d in overlay.items() if vid not in stale},
        "studies": {s: str(studies.loc[s, "title"])[:200] for s in rows.study_id.unique() if s in studies.index},
        "format": FORMAT,
    }


def write_page(ws: Workspace, ontology, out: Path | None = None) -> Path:
    data = payload(ws, ontology)
    out = Path(out) if out else ws.root / "review.html"
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = (Path(__file__).parent / "data" / "review.html").read_text()
    out.write_text(page.replace("__PAYLOAD__", blob))
    return out
