"""The review overlay: fingerprints, moves, edits, staleness, validation; and the published SSSOM."""
import json

import pandas as pd

from colharmonize import publish, review


def scored():
    def col(study, column, vid, **kw):
        base = {"study_id": study, "column": column, "variable_id": vid, "variable_name": vid.lower(),
                "predicate": "exact", "primary_curie": "PATO:0000047", "qualifiers": "[]", "recodes": "[]",
                "tier": "quick", "reasons": "[]", "variable_tier": "quick"}
        return {**base, **kw}
    return pd.DataFrame([
        col("A", "sex", "SEX"), col("B", "gender", "SEX"), col("C", "Sex", "SEX"),
        col("A", "treatment", "TRT", primary_curie="EFO:0000727", recodes=json.dumps([["none", "untreated"]])),
        col("B", "drug", "DRUG", primary_curie="EFO:0000369", tier="pre_accepted", variable_tier="pre_accepted"),
    ])


def decision(s, vid, **kw):
    return review.Decision(fp=review.fingerprints(s)[vid], **{"action": "accept", **kw})


def test_moves_and_edits_apply_and_moved_columns_take_the_new_annotation():
    s = scored()
    overlay = {
        "SEX": decision(s, "SEX", action="edit", moves={"C::Sex": "new"}),
        "DRUG": decision(s, "DRUG", action="edit", moves={"B::drug": "TRT"}),
        "TRT": decision(s, "TRT", action="edit", edit=review.Edit(predicate="broad", name="treatment")),
    }
    rows, stale = review.current(s, overlay)
    by = rows.set_index("key")
    assert not stale
    assert by.loc["C::Sex", "variable_id"] == "SEX+C::Sex" and by.loc["C::Sex", "review_status"] == "unreviewed"
    assert by.loc["B::drug", "variable_id"] == "TRT" and by.loc["B::drug", "predicate"] == "broad"
    assert by.loc["B::drug", "primary_curie"] == "EFO:0000727" and by.loc["B::drug", "recodes"] == "[]"
    assert by.loc["A::treatment", "recodes"] != "[]"                       # the target's own recodes stay
    assert by.loc["A::sex", "review_status"] == "edited"


def test_a_decision_on_changed_pipeline_output_is_stale_and_not_applied():
    s = scored()
    overlay = {"SEX": decision(s, "SEX", action="reject")}
    s.loc[s.column == "gender", "primary_curie"] = "PATO:0000384"           # a re-run changed the variable
    rows, stale = review.current(s, overlay)
    assert stale == ["SEX"] and set(rows[rows.variable_id == "SEX"].review_status) == {"unreviewed"}


def test_split_out_column_can_be_reviewed_in_turn():
    s = scored()
    parent = decision(s, "SEX", action="edit", moves={"C::Sex": "new"})
    child_fp = review._derived_fp(parent.fp, "C::Sex")
    overlay = {"SEX": parent, "SEX+C::Sex": review.Decision(action="edit", fp=child_fp,
                                                           edit=review.Edit(predicate="none", primary=""))}
    rows, stale = review.current(s, overlay)
    r = rows.set_index("key").loc["C::Sex"]
    assert not stale and r.predicate == "none" and r.primary_curie == "" and r.review_status == "edited"


class FakeOntology:
    def validate(self, curie):
        ok = curie in {"PATO:0000047", "EFO:0000727", "EFO:0000369", "PATO:0000384"}
        return type("V", (), {"valid": ok, "reason": "" if ok else "NOT_IN_PINNED_FILE", "curie": curie,
                              "iri": "http://purl.obolibrary.org/obo/" + curie.replace(":", "_"), "label": curie.lower()})()


def test_export_validation_checks_terms_moves_and_cooccurrence():
    s = scored()
    fps = review.fingerprints(s)
    export = {"format": review.FORMAT, "reviewer": "pat", "decisions": {
        "SEX": {"action": "edit", "fp": fps["SEX"], "edit": {"primary": "EFO:9999999"}},
        "TRT": {"action": "edit", "fp": fps["TRT"], "moves": {"A::treatment": "SEX"}},
        "DRUG": {"action": "accept", "fp": "not-the-fingerprint"},
    }}
    conflicts = {("A", "sex", "treatment"): "conflicting"}
    ok, stale, problems = review.validate_export(None, export, s, FakeOntology(), conflicts)
    assert stale == ["DRUG"] and not ok
    assert any("EFO:9999999" in p for p in problems)
    assert any("conflicts with A::sex" in p for p in problems)


def test_sssom_maps_predicates_and_skips_rejected():
    variables = pd.DataFrame([
        {"variable_id": "SEX", "name": "sex", "predicate": "exact", "primary_curie": "PATO:0000047",
         "primary_iri": "http://purl.obolibrary.org/obo/PATO_0000047", "primary_label": "biological sex",
         "qualifiers": "", "review_status": "edited", "reviewer": "pat"},
        {"variable_id": "BAT", "name": "batch", "predicate": "none", "primary_curie": "", "primary_iri": "",
         "primary_label": "", "qualifiers": "", "review_status": "unreviewed", "reviewer": ""},
        {"variable_id": "BAD", "name": "x", "predicate": "broad", "primary_curie": "PATO:0000384",
         "primary_iri": "http://purl.obolibrary.org/obo/PATO_0000384", "primary_label": "male",
         "qualifiers": "", "review_status": "rejected", "reviewer": "pat"},
    ])
    columns = pd.DataFrame([{"study_id": "GSE1", "column": "gender", "variable_id": "SEX", "tier": "quick"},
                            {"study_id": "GSE1", "column": "batch #", "variable_id": "BAT", "tier": "quick"},
                            {"study_id": "GSE2", "column": "x", "variable_id": "BAD", "tier": "manual"}])
    onto = type("O", (), {"release_tag": "v3.94.0", "version_iri": "http://www.ebi.ac.uk/efo/releases/v3.94.0/efo.owl"})()
    text = publish.sssom(variables, columns, onto, "urn:test")
    body = [l.split("\t") for l in text.splitlines() if not l.startswith("#")]
    rows = [dict(zip(body[0], r)) for r in body[1:]]
    assert "#  PATO: http://purl.obolibrary.org/obo/PATO_" in text and "#license: " in text
    assert [r["subject_id"] for r in rows] == ["col:GSE1/gender", "col:GSE1/batch%20%23"]
    assert rows[0]["predicate_id"] == "skos:exactMatch" and rows[0]["mapping_justification"] == "semapv:ManualMappingCuration"
    assert rows[1]["object_id"] == "sssom:NoTermFound"


def test_decisions_follow_a_renamed_variable_by_fingerprint():
    s = scored()
    old = {"OLD-SEX": review.Decision(action="edit", fp=review.fingerprints(s)["SEX"], moves={"C::Sex": "new"}),
           "OLD-SEX+C::Sex": review.Decision(action="reject", fp="x"),
           "GONE": review.Decision(action="accept", fp="no-such-content")}
    moved, renames = review.rekey(old, review.fingerprints(s))
    assert renames == {"OLD-SEX": "SEX", "OLD-SEX+C::Sex": "SEX+C::Sex"}
    assert set(moved) == {"SEX", "SEX+C::Sex", "GONE"}
    rows, stale = review.current(s, old)
    assert rows.set_index("key").loc["C::Sex", "variable_id"] == "SEX+C::Sex"
    assert "GONE" in stale and "SEX" not in stale
