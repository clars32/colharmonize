"""Registry: variables established in earlier runs, so later runs give compatible columns the same label.

Interoperability within one run comes from reconciliation. Across runs it
needs memory: a column harmonized next month should join the `biological sex`
variable published today, under the same id, rather than found a new one. The
registry is that memory, and it is an emergent schema: it holds only variables
that came out of a run and passed review, never hand-authored ones.

A registry is a directory of two TSV files, so a lab can keep it under version
control and share it:

  variables.tsv   registry_id, name, predicate, primary_curie, qualifiers
                  (JSON), values (JSON [value, count], merged over members),
                  added, updated
  members.tsv     registry_id, workspace, study_id, column

`colharmonize registry add` registers a workspace's reviewed variables
(accepted or edited; pre-accepted too if asked). In a workspace that uses a
registry, reconciliation adds registered variables to candidate groups as
fixed members: the reconciler may put new columns in a registered variable's
part, which gives those columns the registry id and annotation, but it can't
change a registered annotation or merge two registered variables.

Limitation: registered variables carry value counts, not per-sample values, so
the co-occurrence rule can't be checked between a new column and a registered
member from the same study.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

REGISTRY_STUDY = "registry"
VARIABLE_COLUMNS = ["registry_id", "name", "predicate", "primary_curie", "qualifiers", "values", "added", "updated"]
MEMBER_COLUMNS = ["registry_id", "workspace", "study_id", "column"]
MAX_VALUES = 30


def load(path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = Path(path)
    v, m = path / "variables.tsv", path / "members.tsv"
    variables = pd.read_csv(v, sep="\t", dtype=str, keep_default_na=False) if v.exists() else pd.DataFrame(columns=VARIABLE_COLUMNS)
    members = pd.read_csv(m, sep="\t", dtype=str, keep_default_na=False) if m.exists() else pd.DataFrame(columns=MEMBER_COLUMNS)
    return variables, members


def save(path: str | Path, variables: pd.DataFrame, members: pd.DataFrame) -> None:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    variables[VARIABLE_COLUMNS].sort_values("registry_id").to_csv(path / "variables.tsv", sep="\t", index=False)
    members[MEMBER_COLUMNS].sort_values(["registry_id", "workspace", "study_id", "column"]).to_csv(
        path / "members.tsv", sep="\t", index=False)


def is_registry_id(vid: str) -> bool:
    return vid.startswith("R") and vid[1:].isdigit()


def member_key(registry_id: str) -> str:
    return f"{REGISTRY_STUDY}::{registry_id}"


def _merge_values(*lists: list) -> str:
    c = Counter()
    for vals in lists:
        for v, n in vals:
            c[str(v)] += int(n)
    return json.dumps([[v, n] for v, n in c.most_common(MAX_VALUES)], ensure_ascii=False)


def add(path: str | Path, workspace_name: str, rows: pd.DataFrame, values: dict[tuple[str, str], list],
        statuses: tuple[str, ...] = ("accepted", "edited")) -> dict:
    """Register the variables in `rows` (publish's current state) whose review status is in `statuses`.

    A variable whose id is already a registry id (its columns joined a
    registered variable during reconciliation) adds its columns to that entry;
    any other variable becomes a new entry. Re-registering the same columns
    changes nothing.
    """
    variables, members = load(path)
    today = date.today().isoformat()
    known = set(zip(members.registry_id, members.workspace, members.study_id, members.column))
    next_n = max((int(r[1:]) for r in variables.registry_id), default=0) + 1
    created = updated = 0
    new_vars, new_members = [], []
    by_id = variables.set_index("registry_id") if len(variables) else None
    for vid, g in rows[rows.review_status.isin(statuses)].groupby("variable_id", sort=True):
        r = g.iloc[0]
        cols = [(s, c) for s, c in zip(g.study_id, g.column)]
        vals = [values.get(k, []) for k in cols]
        if is_registry_id(vid) and by_id is not None and vid in by_id.index:
            rid = vid
            fresh = [(s, c) for s, c in cols if (rid, workspace_name, s, c) not in known]
            if not fresh:
                continue
            by_id.loc[rid, "values"] = _merge_values(json.loads(by_id.loc[rid, "values"]),
                                                     *[values.get(k, []) for k in fresh])
            by_id.loc[rid, "updated"] = today
            updated += 1
            cols = fresh
        else:
            rid = f"R{next_n:04d}"
            next_n += 1
            new_vars.append({"registry_id": rid, "name": r.variable_name, "predicate": r.predicate,
                             "primary_curie": r.primary_curie or "", "qualifiers": r.qualifiers,
                             "values": _merge_values(*vals), "added": today, "updated": today})
            created += 1
        new_members += [{"registry_id": rid, "workspace": workspace_name, "study_id": s, "column": c} for s, c in cols]
    base = by_id.reset_index() if by_id is not None else variables
    variables = pd.concat([base, pd.DataFrame(new_vars, columns=VARIABLE_COLUMNS)], ignore_index=True)
    members = pd.concat([members, pd.DataFrame(new_members, columns=MEMBER_COLUMNS)], ignore_index=True)
    save(path, variables, members)
    return {"created": created, "updated": updated, "registry_variables": len(variables), "registry_members": len(members)}


def as_annotations(variables: pd.DataFrame) -> pd.DataFrame:
    """Registered variables in the shape of annotation rows, as fixed members for reconciliation."""
    return pd.DataFrame({
        "study_id": REGISTRY_STUDY, "column": variables.registry_id, "variable_name": variables.name,
        "predicate": variables.predicate, "primary_curie": variables.primary_curie,
        "qualifiers": variables.qualifiers, "agree_primary": True,
    })
