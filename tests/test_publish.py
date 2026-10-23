"""The pooled sample table: recodes, raw values, rejected variables, name clashes, conflicts,
repeated keys."""
import json

import pandas as pd

from colharmonize.publish import pool


def _fixture():
    variables = pd.DataFrame([
        {"variable_id": "G1", "name": "karyotype", "review_status": "accepted", "n_studies": 2, "n_columns": 2},
        {"variable_id": "G2", "name": "age", "review_status": "unreviewed", "n_studies": 1, "n_columns": 1},
        {"variable_id": "G3", "name": "age", "review_status": "unreviewed", "n_studies": 1, "n_columns": 1},
        {"variable_id": "G4", "name": "batch", "review_status": "rejected", "n_studies": 1, "n_columns": 1},
    ])
    columns = pd.DataFrame([
        {"study_id": "A", "column": "karyotype", "variable_id": "G1", "unit": "",
         "recodes": json.dumps([["T21", "Trisomy 21"], ["D21", "Euploid"]])},
        {"study_id": "B", "column": "condition", "variable_id": "G1", "unit": "", "recodes": "[]"},
        {"study_id": "A", "column": "age", "variable_id": "G2", "unit": "year", "recodes": "[]"},
        {"study_id": "B", "column": "age at draw", "variable_id": "G3", "unit": "", "recodes": "[]"},
        {"study_id": "B", "column": "batch", "variable_id": "G4", "unit": "", "recodes": "[]"},
    ])
    values = pd.DataFrame([
        ("A", "s1", "karyotype", "T21"), ("A", "s2", "karyotype", "d21 "), ("A", "s1", "age", "12"),
        ("B", "s3", "condition", "Trisomy 21"), ("B", "s3", "age at draw", "40"), ("B", "s3", "batch", "2"),
        ("B", "s4", "condition", ""),
    ], columns=["study_id", "sample_id", "column", "value"])
    return values, variables, columns


def test_pool_recodes_keeps_raw_and_drops_rejected():
    wide, long, report = pool(*_fixture(), titles={("A", "s1"): "first"})
    assert list(wide.columns[:3]) == ["study_id", "sample_id", "sample_title"]
    assert "batch" not in wide.columns and "G4" not in set(long.variable_id)        # rejected
    kar = long[long.variable_id == "G1"].set_index("sample_id")
    assert kar.loc["s1", "value"] == "Trisomy 21" and kar.loc["s1", "raw_value"] == "T21"
    assert kar.loc["s2", "value"] == "Euploid" and kar.loc["s2", "raw_value"] == "d21 "  # loose match
    assert set(wide.karyotype.dropna()) == {"Trisomy 21", "Euploid"}
    assert {"age [G2]", "age [G3]"} <= set(wide.columns)                              # names clash
    assert wide.set_index("sample_id").loc["s1", "sample_title"] == "first"
    assert report == {"samples": 4, "studies": 2, "variables": 3, "values": 5, "conflicting_cells": 0,
                      "multi_valued_cells": 0}


def test_pool_keeps_and_counts_conflicting_values():
    values, variables, columns = _fixture()
    columns = pd.concat([columns, pd.DataFrame([{"study_id": "A", "column": "kar2", "variable_id": "G1",
                                                 "unit": "", "recodes": "[]"}])], ignore_index=True)
    values = pd.concat([values, pd.DataFrame([("A", "s1", "kar2", "Euploid")], columns=values.columns)])
    wide, _, report = pool(values, variables, columns)
    assert report["conflicting_cells"] == 1
    assert wide.set_index("sample_id").loc["s1", "karyotype"] == "Trisomy 21 | Euploid"


def test_pool_keeps_every_value_of_a_repeated_key():
    # GSE77298 repeats `disease state`: the disease, then the tissue. Both are kept, not counted as a conflict.
    values, variables, columns = _fixture()
    values = pd.concat([values, pd.DataFrame([("A", "s1", "karyotype", "mosaic")], columns=values.columns)])
    wide, long, report = pool(values, variables, columns)
    assert wide.set_index("sample_id").loc["s1", "karyotype"] == "Trisomy 21 | mosaic"
    assert sorted(long[(long.sample_id == "s1") & (long.variable_id == "G1")].raw_value) == ["T21", "mosaic"]
    assert (report["conflicting_cells"], report["multi_valued_cells"]) == (0, 1)


def test_sample_values_gives_every_value_only_when_asked(tmp_path, monkeypatch):
    from colharmonize import geomend_bridge as gb
    from colharmonize import profile
    from colharmonize.workspace import Workspace
    ws = Workspace(tmp_path / "ws")
    ws.root.mkdir()
    pd.DataFrame([{"study_id": "A", "column": "disease state"}]).to_parquet(ws.columns)
    monkeypatch.setattr(gb, "sample_values", lambda project: pd.DataFrame(
        [("A", "s1", "f1", "characteristic", "disease state", 0, "RA"),
         ("A", "s1", "f1", "characteristic", "disease state", 1, "synovium")],
        columns=["study_id", "sample_id", "field_id", "namespace", "name", "ordinal", "value"]))
    assert profile.sample_values(ws).value.tolist() == ["RA"]                  # judgment stages: first value
    assert profile.sample_values(ws, all_values=True).value.tolist() == ["RA", "synovium"]
