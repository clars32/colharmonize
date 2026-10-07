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


# Words that don't change what a short qualifier phrase refers to.
_FILLER = {"gene", "genes", "locus", "the", "of", "a", "an", "in", "fusion", "status", "level", "levels"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.casefold()) if w not in _FILLER}


def same_meaning(a: str, b: str) -> bool:
    """Whether two short phrases written by different hands name the same thing.

    "crlf2" and "crlf2 gene", "fish" and "fluorescence in situ hybridization
    (fish)" do: after dropping filler words, one word set contains the other or
    they share at least half their words. Used both to score qualifiers against
    gold and to decide whether two runs' qualifiers agree, so the confidence
    signal and the measurement apply one rule.
    """
    if a == b:
        return True
    x, y = _words(a), _words(b)
    if not x or not y:
        return False
    return x <= y or y <= x or len(x & y) / len(x | y) >= 0.5
