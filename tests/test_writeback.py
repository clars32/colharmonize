from types import SimpleNamespace

from colharmonize.writeback import definition, value_mapping


def test_value_mapping_is_complete_or_absent():
    assert value_mapping("[]", ["a", "b"]) is None
    assert value_mapping(None, ["a"]) is None
    # MetaMend refuses a recode that leaves a reported value out: unrecoded values map to themselves.
    assert value_mapping('[["DS", "Down syndrome"]]', ["DS", "control"]) == {"DS": "Down syndrome",
                                                                          "control": "control"}


def test_definition_states_predicate_and_term():
    v = SimpleNamespace(predicate="broad", primary_curie="EFO:0000246", primary_label="age",
                        qualifiers="event_time_anchor=enrolment")
    assert definition(v).startswith("broad age [EFO:0000246]; qualifiers: event_time_anchor=enrolment")
    none = SimpleNamespace(predicate="none", primary_curie="", primary_label="", qualifiers="")
    assert definition(none).startswith("no ontology term (none)")
