"""Pure parts of candidate retrieval: query forms, unit strings, display order."""
from colharmonize import candidates as cd


def test_name_forms_strip_parentheticals_and_status_words():
    assert cd.name_forms("Age (years)")["plain"] == "age"
    f = cd.name_forms("down syndrome status")
    assert f["plain"] == "down syndrome status" and f["entity"] == "down syndrome"
    assert cd.name_forms("title#karyotype")["plain"] == "karyotype"
    assert "entity" not in cd.name_forms("tissue")


def test_unit_strings_from_name_and_profile():
    assert cd.unit_strings("donor bmi (bmi kg/m2)", None) == ["bmi kg/m2"]
    assert cd.unit_strings("fasting glucose,_mm", None) == ["mm"]
    assert cd.unit_strings("Post mortem interval (hours)", "hour") == ["hours", "hour"]


def test_rank_and_display_orders_by_agreement_then_rank():
    cands = [
        {"curie": "A:1", "pool": "space", "sources": {"mini_name": 1}},
        {"curie": "A:2", "pool": "space", "sources": {"mini_name": 3, "bge_name": 2, "exact_space": 1}},
        {"curie": "B:1", "pool": "entity", "sources": {"value_term": 1}},
    ]
    out = cd.rank_and_display(cands)
    space = [c["curie"] for c in out if c["pool"] == "space"]
    assert space == ["A:2", "A:1"]
    assert all(c["displayed"] for c in out)
    assert out[0]["n_sources"] == 3 and out[0]["best_rank"] == 1


def test_encoder_loads_from_the_local_cache_before_the_network(monkeypatch):
    import sys
    import types

    from colharmonize import candidates

    calls = []

    class FakeModel:
        def __init__(self, repo, **kwargs):
            calls.append((repo, kwargs))
            if kwargs.get("local_files_only") and repo == "not/cached":
                raise OSError("not in the local cache")

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeModel))
    candidates.load_encoder("cached/model")
    assert calls == [("cached/model", {"local_files_only": True})]
    calls.clear()
    candidates.load_encoder("not/cached")
    assert calls == [("not/cached", {"local_files_only": True}), ("not/cached", {})]
