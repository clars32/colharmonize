"""Repair rules applied to real MetaMend output from the fixture SOFT files."""
from pathlib import Path

import pandas as pd
import pytest

from colharmonize import metamend_bridge as gb, profile, repair
from colharmonize.workspace import Workspace

SOFT = Path(__file__).parent / "fixtures" / "soft"


@pytest.fixture(scope="module")
def ws(tmp_path_factory):
    ws = Workspace(tmp_path_factory.mktemp("ws"))
    gb.create_cohort(ws.metamend, sorted(SOFT.glob("*.soft.gz")), workers=2)
    profile.build(ws)
    return ws


@pytest.fixture(scope="module")
def values(ws):
    return gb.sample_values(ws.metamend)


def test_profiles_and_items(ws):
    cols = pd.read_parquet(ws.columns)
    assert {"age", "batch", "condition", "gender"} <= set(cols[cols.study_id == "GSE79842"].column)
    items = {it["item_id"]: it for it in repair.build_items(ws)}
    assert set(items) == {"GSE124252", "GSE128621", "GSE79842"}
    assert items["GSE79842"]["n_samples"] == 36
    assert any("replicate" in t for t in items["GSE79842"]["titles"])


def rule(**kw):
    base = dict(source="title", column=None, expected="all", rationale="test")
    return repair.Rule(**{**base, **kw})


def test_title_rule_recovers_a_hidden_variable(ws, values):
    # GSE79842 titles: "Disomic, Fibroblast, Female, 2 Day old, replicate 1"
    ans = repair.RepairAnswer(item_id="GSE79842", rules=[rule(name="replicate", pattern=r"replicate (?P<value>\d+)")])
    derived, report, problems = repair.apply(ws, [ans], values)
    assert problems == []
    assert report.iloc[0].matched == report.iloc[0].eligible == 36
    assert set(derived.column) == {"title#replicate"} and set(derived.value) <= {"1", "2", "3"}


def test_split_rules_on_a_characteristic(ws, values):
    ans = repair.RepairAnswer(item_id="GSE79842", split_columns=["age"], rules=[
        rule(name="number", source="characteristic", column="age", pattern=r"^(?P<value>\d+)"),
        rule(name="unit", source="characteristic", column="age", pattern=r"\d+ (?P<value>\w+)"),
    ])
    derived, report, problems = repair.apply(ws, [ans], values)
    assert problems == []
    assert set(derived.column) == {"age#number", "age#unit"}
    assert set(derived[derived.column == "age#unit"].value) == {"Year", "Day"}


def test_unusable_rules_are_reported_not_applied(ws, values):
    ans = repair.RepairAnswer(item_id="GSE79842", split_columns=["age"], rules=[
        rule(name="age", pattern=r"(?P<value>\d+ \w+ old)"),                 # already a characteristic
        rule(name="no group", pattern=r"replicate \d+"),                     # no named group
        rule(name="bad", pattern=r"(?P<value>"),                             # does not compile
        rule(name="lonely", source="characteristic", column="age", pattern=r"(?P<value>\d+)"),
    ])
    derived, report, problems = repair.apply(ws, [ans], values)
    text = " | ".join(problems)
    assert "already recorded" in text and "no named group" in text and "does not compile" in text
    assert "needs at least two rules" in text
    assert set(derived.column) <= {"age#lonely"}


def test_expected_all_reports_unmatched_samples(ws, values):
    ans = repair.RepairAnswer(item_id="GSE79842", rules=[rule(name="cell", pattern=r"(?P<value>Fibroblast)")])
    derived, report, problems = repair.apply(ws, [ans], values)
    assert report.iloc[0].matched == 24 and report.iloc[0].eligible == 36
    assert any("expected all samples, matched 24/36" in p for p in problems)
    assert "Lymphoblast, Female" in report.iloc[0].unmatched_examples


def test_rule_problems_surface_at_collection(ws):
    # GSE124252 in the pilot: a rule on a characteristic not declared as a split.
    ans = repair.RepairAnswer(item_id="GSE124252", rules=[
        rule(name="cell line", source="characteristic", column="tissue origin", pattern=r"^(?P<value>\w+)-derived")])
    problems = repair.validate_answers(ws, [ans])
    assert any("not in split_columns" in p for p in problems)
