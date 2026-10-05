"""Mechanical hints about a column's shape, computed before any model sees it.

These are evidence for the annotator, not decisions. Iteration 2 used the
assertion detector to force NO_MATCH (decision 8.1). In iteration 3 the same
shape suggests the `indicator` predicate: `BCR-ABL, t(9;22)` = Negative/Positive
is a yes/no indicator of a translocation. The annotator still decides, because
some assertion-shaped columns are statuses with their own exact terms
(`er status` 0/1 -> estrogen receptor status).
"""
from __future__ import annotations

from typing import Iterable

# Values that assert presence or absence rather than name a category.
ASSERTION_TOKENS = frozenset({
    "positive", "negative", "pos", "neg", "yes", "no", "present", "absent",
    "true", "false", "detected", "not detected", "unknown", "n/a", "na",
    "not available", "n.d", "nd", "normal, wild type", "wild type", "wt",
})
# Fraction of distinct values that must be assertion tokens.
ASSERTION_VALUE_FRACTION = 0.6
# A single-valued column is degenerate, not a contrast: GSE185192's
# `chip antibody` is "none" for every sample, yet it still names the antibody.
MIN_DISTINCT = 2
BINARY_CODES = frozenset({"0", "1"})


def _distinct(values: Iterable[str]) -> set[str]:
    # "Negative (206)"-style counts are stripped so value summaries also work.
    vals = {str(v).rsplit(" (", 1)[0].strip().casefold() for v in values}
    return {v for v in vals if v}


def is_assertion_column(values: Iterable[str]) -> bool:
    """True when most distinct values assert presence or absence."""
    vals = _distinct(values)
    if len(vals) < MIN_DISTINCT:
        return False
    return sum(v in ASSERTION_TOKENS for v in vals) / len(vals) >= ASSERTION_VALUE_FRACTION


def is_binary_code(values: Iterable[str]) -> bool:
    """True when the column is coded 0/1 (optionally with a missing marker such as -1)."""
    vals = _distinct(values) - {"-1", "na", "n/a", "", "."}
    return len(vals) == 2 and vals == BINARY_CODES


def shape_hint(values: Iterable[str]) -> str | None:
    """'assertion', 'binary_code', or None. Shown to the annotator as evidence."""
    values = list(values)
    if is_assertion_column(values):
        return "assertion"
    if is_binary_code(values):
        return "binary_code"
    return None
