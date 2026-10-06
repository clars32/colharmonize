"""Loose text forms for matching names against ontology labels.

`normalise.normalise_key` is the strict form used to compare column names.
`loose` additionally splits camelCase and treats _ - / as spaces, which is
right for looking a name up among labels ("organismPart" -> "organism part")
and wrong for deciding whether two column names are the same column.
"""
from __future__ import annotations

import re

_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")
_SEP = re.compile(r"[_\-/]+")
_SPACE = re.compile(r"\s+")
_PAREN = re.compile(r"\s*[\(\[][^)\]]*[\)\]]")


def loose(s: str) -> str:
    s = _CAMEL.sub(" ", str(s))
    s = _SEP.sub(" ", s)
    return _SPACE.sub(" ", s).strip().casefold()


def strip_parenthetical(s: str) -> str:
    """'age (years)' -> 'age'; 'donor bmi (bmi kg/m2)' -> 'donor bmi'."""
    return _PAREN.sub("", str(s)).strip()


def parenthetical(s: str) -> list[str]:
    """Contents of parentheses or brackets: 'age (years)' -> ['years']."""
    return [m.strip() for m in re.findall(r"[\(\[]([^)\]]*)[\)\]]", str(s)) if m.strip()]
