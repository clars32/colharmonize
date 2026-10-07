"""Review tiers from run agreement and checks."""
import json

import pandas as pd

from colharmonize import score


def col(**kw):
    base = {"study_id": "S", "column": "c", "variable_id": "v", "predicate": "exact", "primary_curie": "EFO:1",
            "qualifiers": "[]", "recodes": "[]", "reconciled": False, "partition_agreement": float("nan"),
            "annotation_agree": True, "qualifiers_agree": True, "outside_space": False, "ambiguous": False,
            "unresolved_proposal": "", "flags": "[]"}
    return {**base, **kw}


def test_clean_column_is_pre_accepted_and_each_check_demotes():
    v = pd.DataFrame([
        col(column="clean", variable_id="v1"),
        col(column="disagree", variable_id="v2", annotation_agree=False),
        col(column="outside", variable_id="v3", outside_space=True),
        col(column="flagged", variable_id="v4", flags=json.dumps(["CONVENTION_ASSUMED"])),
        col(column="none", variable_id="v5", predicate="none", primary_curie=""),
        col(column="recoded", variable_id="v6", recodes=json.dumps([["DS", "Down syndrome"]])),
        col(column="split", variable_id="v7", reconciled=True, partition_agreement=0.5),
        col(column="one run", variable_id="v8", reconciled=True),            # partition agreement not measured
    ])
    t = score.tiers(v).set_index("column").tier.to_dict()
    assert t == {"clean": "pre_accepted", "disagree": "manual", "outside": "manual", "flagged": "quick",
                 "none": "quick", "recoded": "quick", "split": "manual", "one run": "manual"}


def test_variable_tier_is_its_worst_member_and_broad_buckets_get_a_look():
    v = pd.DataFrame([col(study_id="A", column="sex"), col(study_id="B", column="gender", flags='["X"]')]
                     + [col(study_id=s, column=n, variable_id="wide") for s, n in zip("CDEF", ["ds", "class", "strain", "group"])])
    out = score.tiers(v).set_index("column")
    assert out.loc["sex", "tier"] == "pre_accepted" and out.loc["sex", "variable_tier"] == "quick"
    assert (out.loc[["ds", "class", "strain", "group"], "tier"] == "quick").all()
    assert "variable pools 4 column names" in out.loc["ds", "reasons"]
