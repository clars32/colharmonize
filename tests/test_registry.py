"""The cross-run registry, and how reconciliation treats registered variables."""
import json

import pandas as pd

from colharmonize import annotate as an, reconcile as rc, registry
from colharmonize.workspace import Workspace


def current_rows(rows):
    base = {"variable_name": "biological sex", "predicate": "exact", "primary_curie": "PATO:0000047",
            "qualifiers": "[]", "review_status": "accepted"}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_add_creates_updates_and_is_idempotent(tmp_path):
    values = {("A", "sex"): [["male", 3], ["female", 2]], ("B", "gender"): [["M", 4]], ("C", "Sex"): [["F", 1]]}
    rows = current_rows([{"study_id": "A", "column": "sex", "variable_id": "G1.1"},
                         {"study_id": "B", "column": "gender", "variable_id": "G1.1"},
                         {"study_id": "B", "column": "batch", "variable_id": "x", "review_status": "unreviewed"}])
    assert registry.add(tmp_path, "ws1", rows, values)["created"] == 1          # unreviewed is not registered
    assert registry.add(tmp_path, "ws1", current_rows([]).reindex(columns=rows.columns), values)["created"] == 0
    # A later workspace's column joined R0001 during reconciliation.
    later = current_rows([{"study_id": "C", "column": "Sex", "variable_id": "R0001"}])
    assert registry.add(tmp_path, "ws2", later, values) == {"created": 0, "updated": 1, "registry_variables": 1,
                                                            "registry_members": 3}
    assert registry.add(tmp_path, "ws2", later, values)["updated"] == 0          # same columns again: no change
    v, m = registry.load(tmp_path)
    assert v.registry_id.tolist() == ["R0001"] and dict(json.loads(v.loc[0, "values"]))["male"] == 3
    assert sorted(m.study_id) == ["A", "B", "C"]


def test_registered_variables_join_candidate_groups(tiny):
    reg = pd.DataFrame([{"registry_id": "R0001", "name": "biological sex", "predicate": "exact",
                         "primary_curie": "PATO:0000047", "qualifiers": "[]", "values": "[]"}])
    ann = pd.DataFrame([{"study_id": "S9", "column": "gender", "variable_name": "sex", "predicate": "exact",
                         "primary_curie": "PATO:0000047", "qualifiers": "[]"}])
    groups = rc.candidate_groups(pd.concat([ann, registry.as_annotations(reg)], ignore_index=True), tiny)
    assert groups == [["S9::gender", "registry::R0001"]]


def reconcile_ws(tmp_path):
    ws = Workspace(tmp_path)
    d = ws.tasks(rc.STAGE, 1)
    d.mkdir(parents=True)
    (d / "members.json").write_text(json.dumps({"G001": {"M1": "S9::gender", "M2": "registry::R0001", "M3": "S9::sex2",
                                                         "M4": "registry::R0002"}}))
    (d / "refs.json").write_text(json.dumps({"G001": {"T1": "PATO:0000047", "T2": "EFO:0000727"}}))
    (d / "registered.json").write_text(json.dumps({
        "registry::R0001": {"predicate": "exact", "primary_curie": "PATO:0000047", "name": "biological sex",
                            "qualifiers": "[]", "values": []},
        "registry::R0002": {"predicate": "exact", "primary_curie": "EFO:0000727", "name": "treatment",
                            "qualifiers": "[]", "values": []}}))
    return ws


def part(members, ref, name="x"):
    return rc.Part(members=members, variable_name=name, predicate="exact", primary=an.Term(ref=ref), rationale="")


def test_registered_parts_keep_their_annotation_and_id(tmp_path, tiny):
    ws = reconcile_ws(tmp_path)
    res = an.Resolver(tiny, pd.DataFrame({"curie": ["PATO:0000047", "EFO:0000727"]}))
    bad = rc.ReconcileAnswer(item_id="G001", parts=[part(["M1", "M2", "M4"], "T1"), part(["M3"], "T1")])
    assert any("share a part" in p for p in rc.validate_answers(ws, [bad], run=1, resolver=res))
    wrong_term = rc.ReconcileAnswer(item_id="G001", parts=[part(["M1", "M2"], "T2"), part(["M3"], "T1"), part(["M4"], "T2")])
    assert any("must keep" in p for p in rc.validate_answers(ws, [wrong_term], run=1, resolver=res))
    good = rc.ReconcileAnswer(item_id="G001", parts=[part(["M1", "M2"], "T1", name="sex"), part(["M3"], "T1"), part(["M4"], "T2")])
    assert rc.validate_answers(ws, [good], run=1, resolver=res) == []
    out = rc.resolve_run(ws, [good], 1, res).set_index("column")
    assert out.loc["gender", "part"] == "R0001" and out.loc["gender", "variable_name"] == "biological sex"
    assert out.loc["sex2", "part"] == "G001.2" and "R0002" not in out.part.values   # nothing joined R0002
