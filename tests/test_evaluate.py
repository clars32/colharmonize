"""The scorer, checked against a small example computed by hand."""
import math

import pandas as pd
import pytest

from colharmonize.evaluate import parse_qualifiers, report, score

# Gold: v1 pools A/x, B/x and B/z (two of them in dataset B, disjoint samples).
GOLD = pd.DataFrame([
    ("A", "x", "characteristic", "v1", "UO:0000036", "exact", "EFO:0000246", ""),
    ("A", "y", "characteristic", "v2", "", "indicator", "EFO:0006834", ""),
    ("B", "x", "characteristic", "v1", "UO:0000036 (inferred)", "exact", "EFO:0000246", ""),
    ("B", "z", "characteristic", "v1", "", "exact", "EFO:0000246", ""),
    ("C", "w", "characteristic", "v3", "", "none", "", 'object_class="BCR-ABL1 t(9;22)" (ungrounded)'),
], columns=["accession", "raw_key", "source", "variable_id", "unit", "predicate", "primary_curie", "qualifiers"])

# Prediction: p1 wrongly absorbs A/y, B/z is left apart, C/w is missing.
PRED = pd.DataFrame([
    ("A", "x", "p1", "exact", "EFO:0000246", "year"),
    ("A", "y", "p1", "exact", "EFO:0000246", ""),
    ("B", "x", "p1", "exact", "EFO:0000246", "UO:0000036"),
    ("B", "z", "p2", "broad", "EFO:0000246", ""),
], columns=["accession", "raw_key", "variable_id", "predicate", "primary_curie", "unit"])


def test_pairwise_pooling_by_hand():
    s = score(GOLD, PRED)
    # gold pairs: (Ax,Bx) (Ax,Bz) (Bx,Bz); predicted: (Ax,Ay) (Ax,Bx) (Ay,Bx); shared: (Ax,Bx)
    assert s.pooling["true_pairs"] == 1 and s.pooling["predicted_pairs"] == 3 and s.pooling["gold_pairs"] == 3
    assert s.pooling["precision"] == pytest.approx(1 / 3) and s.pooling["recall"] == pytest.approx(1 / 3)
    # cross-dataset only: gold (Ax,Bx) (Ax,Bz); predicted (Ax,Bx) (Ay,Bx)
    assert s.pooling_cross_dataset["precision"] == pytest.approx(1 / 2)
    assert s.pooling_cross_dataset["recall"] == pytest.approx(1 / 2)


def test_missing_prediction_is_an_unpooled_singleton():
    s = score(GOLD, PRED)
    assert s.n_gold_columns == 5 and s.n_predicted == 4
    assert all("C/w" not in " ".join(r["columns"]) for r in s.false_merges)


def test_bcubed_by_hand():
    s = score(GOLD, PRED)
    # precision per item: Ax 2/3, Ay 1/3, Bx 2/3, Bz 1, Cw 1   -> 11/15
    # recall per item:    Ax 2/3, Ay 1,   Bx 2/3, Bz 1/3, Cw 1 -> 11/15
    assert s.bcubed["precision"] == pytest.approx(11 / 15)
    assert s.bcubed["recall"] == pytest.approx(11 / 15)


def test_annotation_scores():
    a = score(GOLD, PRED).annotation
    assert a["primary_accuracy"] == pytest.approx(3 / 5)     # Ax, Bx, Bz right; Ay wrong; Cw missing
    assert a["predicate_accuracy"] == pytest.approx(2 / 5)   # Ax, Bx
    assert a["annotation_accuracy"] == pytest.approx(2 / 5)
    assert a["no_match_recall"] == 0 and math.isnan(a["no_match_precision"])
    assert a["qualifier_recall"] == 0
    # units: Ax 'year' != UO:0000036; Bx matches once '(inferred)' is ignored
    assert a["unit_scored"] == 2 and a["unit_accuracy"] == pytest.approx(1 / 2)


def test_error_lists_and_breadth():
    s = score(GOLD, PRED)
    assert [r["predicted"] for r in s.false_merges] == ["p1"]
    assert {r["gold"] for r in s.missed_merges} == {"v1"}
    assert s.breadth[0] == {"variable": "p1", "columns": 3, "distinct_names": 2, "names": ["x", "y"]}
    assert "False merges (1)" in report(s)


def test_parse_qualifiers_reads_gold_and_prediction_formats():
    gold = 'event_time_anchor="Start of treatment" (ungrounded); unit=UO:0000034 [week]'
    assert parse_qualifiers(gold) == {("event_time_anchor", "start of treatment"), ("unit", "UO:0000034")}
    assert parse_qualifiers("object_class=CL:0000542; method=FISH") == {("object_class", "CL:0000542"), ("method", "fish")}
    assert parse_qualifiers("") == frozenset()


def test_unsplit_parent_is_reported():
    gold = pd.DataFrame([
        ("D", "t#day", "split:t", "s1", "", "exact", "EFO:0000724", ""),
        ("D", "t#zt", "split:t", "s2", "", "exact", "EFO:0000724", ""),
    ], columns=GOLD.columns)
    pred = pd.DataFrame([("D", "t", "q")], columns=["accession", "raw_key", "variable_id"])
    s = score(gold, pred)
    assert s.unsplit_parents == ["D/t"] and s.n_predicted == 0
    assert not s.annotation["scored"]


def test_qualifiers_match_by_meaning_not_spelling():
    from colharmonize.evaluate import qualifier_match
    labels = {"EFO:0003856": "dissection"}
    assert qualifier_match(("object_class", "crlf2"), ("object_class", "crlf2 gene"))
    assert qualifier_match(("method", "fish"), ("method", "fluorescence in situ hybridization (fish)"))
    assert qualifier_match(("event_time_anchor", "dissection"), ("event_time_anchor", "EFO:0003856"), labels)
    assert not qualifier_match(("method", "fish"), ("object_class", "fish"))          # slot differs
    assert not qualifier_match(("object_class", "crlf2"), ("object_class", "jak2 r683"))
