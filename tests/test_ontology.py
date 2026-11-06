"""Regression tests for the validator, carried over from iteration 2's findings."""
import pandas as pd

from colharmonize import ontology as o


def test_phantom_zooma_identifier_is_rejected(efo):
    # ZOOMA returns UBERON_0000361 for "bone marrow"; it is not in pinned
    # EFO v3.94.0 (iteration 2 decisions 0b.1 and 3.1). The real term passes.
    assert efo.validate("UBERON_0000361").reason == o.NOT_IN_PINNED_FILE
    ok = efo.validate("http://purl.obolibrary.org/obo/UBERON_0002371")
    assert ok.valid and ok.label == "bone marrow" and ok.curie == "UBERON:0002371"


def test_deprecated_term_is_diagnosed_not_missed(efo):
    # leukocyte count exists but is deprecated (iteration 2 decision 6a.5).
    v = efo.validate("EFO:0004308")
    assert v.reason == o.DEPRECATED and not v.valid and v.label.startswith("obsolete")


def test_rejected_and_off_allowlist_prefixes(efo):
    assert efo.validate("BTO:0000141").reason == o.REJECTED_PREFIX
    hp = efo.terms[efo.terms.prefix == "HP"].curie.iloc[0]
    assert efo.validate(hp).reason == o.OFF_ALLOWLIST


def test_label_must_match_pinned_label(efo):
    assert efo.validate("PATO:0000047", "Biological Sex").valid
    assert efo.validate("PATO:0000047", "sex").reason == o.LABEL_MISMATCH
    assert efo.validate("EFO:9999999", "biological sex").reason == o.NOT_IN_PINNED_FILE


def test_curieless_terms_are_not_collapsed(efo):
    # EFO imports 91 non-deprecated classes with non-OBO IRIs (dbpedia, NCBI).
    # They have no CURIE; collapsing on CURIE once merged them into one term.
    classes = efo.terms[(efo.terms.node_type == "CLASS") & ~efo.terms.deprecated]
    assert len(classes) == 84375
    assert (classes.curie == "").sum() == 91


def test_unparseable_inputs(efo):
    for junk in ["", "a completely made up term", "EFO:", "_0000047"]:
        assert efo.validate(junk).reason == o.UNPARSEABLE, junk


def test_units_are_allowlisted(efo):
    v = efo.validate("UO:0000036")
    assert v.valid and v.label == "year"


def test_iri_construction_keeps_efo_namespace(efo):
    assert efo.iri("EFO:0000727") == "http://www.ebi.ac.uk/efo/EFO_0000727"
    assert efo.iri("PATO:0000047") == "http://purl.obolibrary.org/obo/PATO_0000047"


def test_is_a_adjacency_for_reconciliation(efo):
    # Iteration 2 split `treatment` across these two terms; reconciliation
    # groups them because one is_a the other.
    assert "EFO:0000727" in efo.parents("EFO:0000369")
    assert "EFO:0000369" in efo.children("EFO:0000727")


def test_allowlist_is_evaluated_at_call_time(tiny_dir):
    narrow = o.Ontology.from_dir(tiny_dir, allowed={"EFO"})
    assert narrow.validate("PATO:0000047").reason == o.OFF_ALLOWLIST
    assert set(narrow.usable_terms().prefix) == {"EFO"}


def test_pin_obograph_round_trip(tiny_dir, tiny):
    assert tiny.release_tag == "v1.0"
    assert tiny.version_iri.endswith("/1.0/tiny.owl")
    assert len(tiny.terms) == 8                  # unique by IRI, CURIE-less terms kept
    assert (tiny.terms.curie == "").sum() == 2
    row = tiny.terms.set_index("iri").loc[tiny.iri("EFO:0000369")]
    assert list(row.exact_synonyms) == ["drug treatment"]
    assert tiny.validate("EFO:0004308").reason == o.DEPRECATED
    assert tiny.parents("EFO:0000369") == ["EFO:0000727"]
    assert set(tiny.usable_terms().curie) == {"EFO:0000727", "EFO:0000369", "PATO:0000047"}


def test_a_repeated_curie_resolves_to_one_term(tiny):
    # EFO v3.94.0 gives definition:citation two IRIs. Lookups return the first
    # row's values, not a pandas Series rendered as text.
    terms = tiny.terms
    row = terms[terms.curie == "EFO:0000369"].iloc[0]
    twin = row.copy()
    twin["iri"] = row["iri"] + "-twin"
    twin["label"] = "a second label"
    onto = o.Ontology(pd.concat([terms, twin.to_frame().T], ignore_index=True), tiny.edge_table, tiny.version)
    assert onto.label("EFO:0000369") == row["label"]
    assert onto.iri("EFO:0000369") == row["iri"]
    verdict = onto.validate("EFO:0000369", row["label"])
    assert (verdict.iri, verdict.label, verdict.reason) == (row["iri"], row["label"], o.OK)
