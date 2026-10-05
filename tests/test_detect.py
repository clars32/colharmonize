from colharmonize.detect import is_assertion_column, is_binary_code, shape_hint


def test_cytogenetic_assertion_columns():
    # GSE11877 `BCR-ABL, t(9;22)` and GSE61804 `flt3-itd`.
    assert is_assertion_column(["Negative", "Unknown"])
    assert is_assertion_column(["negative", "positive", "not available"])
    assert is_assertion_column(["Negative (206)", "Unknown (1)"])


def test_single_valued_column_is_not_an_assertion():
    # GSE185192 `chip antibody` is "none" everywhere yet names the antibody.
    assert not is_assertion_column(["none"])
    assert not is_assertion_column(["Negative"])


def test_binary_codes():
    assert is_binary_code(["0", "1"])           # GSE237290 er
    assert is_binary_code(["0", "1", "-1"])     # GSE149322 pcr, -1 missing
    assert not is_binary_code(["0", "1", "2"])  # a count


def test_shape_hint():
    assert shape_hint(["Yes", "No"]) == "assertion"
    assert shape_hint(["1", "0"]) == "binary_code"
    assert shape_hint(["bone marrow", "peripheral blood"]) is None
