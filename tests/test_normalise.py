import doctest

import colharmonize.normalise as normalise_module
from colharmonize.normalise import normalise_key


def test_doctests():
    assert doctest.testmod(normalise_module).failed == 0


def test_case_whitespace_and_trailing_punctuation():
    assert normalise_key("  Gender ") == "gender"
    assert normalise_key("Age (years):") == "age (years)"
    assert normalise_key("disease   state") == "disease state"


def test_semantic_variants_stay_distinct():
    # String rules must not merge concepts; that is annotation's job.
    assert normalise_key("gender") != normalise_key("sex")
    assert normalise_key("disease_status") != normalise_key("disease status")
