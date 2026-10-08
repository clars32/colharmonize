"""Grouping, partition checks and run agreement for the reconcile stage."""
import json

import pandas as pd

from colharmonize import reconcile as rc


def ann(rows):
    base = {"predicate": "exact", "qualifiers": "[]", "variable_name": ""}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_groups_link_same_term_parent_child_and_names(tiny):
    a = ann([
        {"study_id": "S1", "column": "treatment", "primary_curie": "EFO:0000727", "variable_name": "treatment"},
        {"study_id": "S2", "column": "drug", "primary_curie": "EFO:0000369", "variable_name": "compound treatment"},
        {"study_id": "S3", "column": "Sex", "primary_curie": "PATO:0000047", "variable_name": "biological sex"},
        {"study_id": "S4", "column": "gender", "primary_curie": "PATO:0000047", "variable_name": "biological sex"},
        {"study_id": "S5", "column": "batch", "primary_curie": "", "variable_name": "batch"},
        {"study_id": "S5", "column": "batch2", "primary_curie": "", "variable_name": "Batch"},
        {"study_id": "S6", "column": "notes", "primary_curie": "", "variable_name": "notes"},
    ])
    groups = rc.candidate_groups(a, tiny)
    as_sets = {frozenset(g) for g in groups}
    assert frozenset({"S1::treatment", "S2::drug"}) in as_sets          # is_a parent and child
    assert frozenset({"S3::Sex", "S4::gender"}) in as_sets             # same primary term
    assert frozenset({"S5::batch", "S5::batch2"}) in as_sets           # same study, same name
    assert not any("S6::notes" in g for g in groups)                   # nothing to pool with


def test_pair_agreement_between_runs():
    r1 = pd.DataFrame({"study_id": ["A", "B", "C"], "column": ["x", "y", "z"], "group": "G1",
                       "part": ["G1.1", "G1.1", "G1.2"]})
    r2 = r1.assign(part=["G1.1", "G1.2", "G1.2"])
    agree = rc.pair_agreement(r1, r2)
    # A: with B differs, with C same -> 0.5;  B: both differ -> 0;  C: with A same, with B differs -> 0.5
    assert agree[("A", "x")] == 0.5 and agree[("B", "y")] == 0.0 and agree[("C", "z")] == 0.5


def test_finalize_prefers_reconciled_parts():
    a = ann([{"study_id": "A", "column": "x", "primary_curie": "EFO:1", "variable_id": "exact|EFO:1|", "agree_primary": True},
             {"study_id": "B", "column": "y", "primary_curie": "EFO:2", "variable_id": "exact|EFO:2|", "agree_primary": True}])
    run = pd.DataFrame([{"study_id": "A", "column": "x", "run": 1, "group": "G1", "part": "G1.1",
                         "variable_name": "v", "predicate": "broad", "primary_curie": "EFO:9",
                         "qualifiers": "[]", "recodes": json.dumps([["a", "b"]]), "flags": "[]", "rationale": ""}])
    out = rc.finalize(a, run, None).set_index("column")
    assert out.loc["x", "variable_id"] == "G1.1" and out.loc["x", "reconciled"]
    assert out.loc["y", "variable_id"] == "S001" and not out.loc["y", "reconciled"]


def test_shared_distinctive_values_link_columns(tiny):
    a = ann([
        {"study_id": "S1", "column": "karyotype", "primary_curie": "EFO:0000727", "variable_name": "karyotype"},
        {"study_id": "S2", "column": "condition", "primary_curie": "PATO:0000047", "variable_name": "status"},
        {"study_id": "S3", "column": "group", "primary_curie": "", "variable_name": "arm"},
    ])
    values = {"S1::karyotype": rc.distinctive(["Euploid", "TS21"]),
              "S2::condition": rc.distinctive(["euploid", "Down syndrome"]),
              "S3::group": rc.distinctive(["control", "1", "Yes"])}
    assert values["S3::group"] == set()                                  # generic and numeric values do not link
    groups = rc.candidate_groups(a, tiny, values)
    assert any({"S1::karyotype", "S2::condition"} <= set(g) for g in groups)
    assert not any("S3::group" in g for g in groups)


def test_part_qualifiers_are_those_every_member_carries():
    label = {"EFO:1": "dissection"}.get
    a = [["object_class", "crlf2"], ["event_time_anchor", "EFO:1"], ["unit", "UO:0000033"]]
    b = [["object_class", "crlf2 gene"], ["event_time_anchor", "dissection"]]
    c = [["object_class", "crlf2"], ["method", "fish"]]
    assert rc.shared_qualifiers([a, b], lambda v: label(v) or "") == [("event_time_anchor", "EFO:1"), ("object_class", "crlf2")]
    assert rc.shared_qualifiers([a, b, c], lambda v: label(v) or "") == [("object_class", "crlf2")]
    assert rc.shared_qualifiers([c], lambda v: "") == [("method", "fish"), ("object_class", "crlf2")]
