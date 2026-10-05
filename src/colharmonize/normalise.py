"""The one normalisation for column names.

Iteration 2 had five slightly different copies of this function. Every place
that compares column names now calls this one. It is deliberately minimal:
case, whitespace, unicode dashes and trailing punctuation. Anything beyond that
(`gender` vs `sex`, `disease state` vs `disease status`) is a semantic
equivalence, decided by annotation and reconciliation, never by string rules.
"""
from __future__ import annotations

import re

_DASHES = re.compile(r"[‐-―−]")
_SPACE = re.compile(r"\s+")


def normalise_key(key: str) -> str:
    """Return the comparison form of a column name.

    >>> normalise_key("  Disease_status: ")
    'disease_status'
    >>> normalise_key("Age – (years)")
    'age - (years)'
    """
    k = _DASHES.sub("-", str(key).strip().casefold())
    return _SPACE.sub(" ", k).strip(" :.-_")
