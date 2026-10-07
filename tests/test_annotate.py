"""Name resolution, pre-reconciliation identity, and run agreement for the annotate stage."""
import json

import pandas as pd

from colharmonize import annotate as an


def resolver(tiny):
    return an.Resolver(tiny, pd.DataFrame({"curie": ["EFO:0000727"]}))


def test_resolves_refs_labels_and_synonyms(tiny):
    r = resolver(tiny)
    refs = {"T1": "PATO:0000047"}
    assert r.resolve(an.Term(ref="T1"), refs).curie == "PATO:0000047"
    assert r.resolve(an.Term(name="Treatment"), refs).curie == "EFO:0000727"
    syn = r.resolve(an.Term(name="drug treatment"), refs)
    assert (syn.curie, syn.how) == ("EFO:0000369", "synonym")


def test_never_invents_or_accepts_bad_terms(tiny):
    r = resolver(tiny)
    assert r.resolve(an.Term(name="a completely made up term"), {}).curie == ""
    assert r.resolve(an.Term(name="EFO:0000727"), {}).curie == ""            # identifiers are not names
    assert r.resolve(an.Term(ref="T9"), {"T1": "EFO:0000727"}).reason.startswith("unknown ref")
    # A deprecated term is not usable, so its label does not resolve.
    assert r.resolve(an.Term(name="obsolete_leukocyte count"), {}).curie == ""


def row(**kw):
    base = {"study_id": "S", "column": "c", "predicate": "exact", "primary_curie": "EFO:0000246", "qualifiers": "[]"}
    return {**base, **kw}


def test_identity_ignores_unit_but_not_other_qualifiers():
    years = an.identity(row(qualifiers=json.dumps([["unit", "UO:0000036"]])))
    days = an.identity(row(qualifiers=json.dumps([["unit", "UO:0000033"]])))
    at_dx = an.identity(row(predicate="broad", qualifiers=json.dumps([["event_time_anchor", "diagnosis"]])))
    assert years == days != at_dx
    assert an.identity(row(predicate="none", primary_curie="")) == "none:S::c"


def test_combine_measures_agreement():
    r1 = pd.DataFrame([row(column="a"), row(column="b", qualifiers=json.dumps([["method", "fish"]]))])
    r2 = pd.DataFrame([row(column="a"), row(column="b", qualifiers=json.dumps([["method", "pcr"]]))])
    m = an.combine(r1, r2)
    assert m.agree_primary.tolist() == [True, True]
    assert m.agree_qualifiers.tolist() == [True, False]
    assert m.variable_id.nunique() == 2


def test_qualifiers_agree_by_meaning():
    q = lambda *pairs: json.dumps([list(p) for p in pairs])
    assert an.qualifiers_agree(q(("object_class", "crlf2")), q(("object_class", "crlf2 gene")))
    assert an.qualifiers_agree(q(("unit", "UO:0000036")), q())                       # units don't count
    assert an.qualifiers_agree(q(("event_time_anchor", "EFO:1")), q(("event_time_anchor", "dissection")),
                               {"EFO:1": "dissection"})
    assert not an.qualifiers_agree(q(("subject", "fetus")), q(("subject", "fetus"), ("event_time_anchor", "birth")))
    assert not an.qualifiers_agree(q(("method", "fish")), q(("object_class", "fish")))  # slot differs
    assert not an.qualifiers_agree(q(), None)                                          # no second run


def test_single_run_never_agrees():
    m = an.combine(pd.DataFrame([row(column="a")]), None)
    assert not m.agree_primary.iloc[0] and not m.agree_qualifiers.iloc[0]
