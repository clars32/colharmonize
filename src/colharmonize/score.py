"""Review tiers: which harmonized columns a reviewer can skim and which need a look.

Every column starts pre-accepted, and each failed check demotes it. A
pre-accepted column is not auto-accepted: the review page lists it, and a
reviewer can still change it (GEOmend's owner agreed to that state). The review
unit is a variable, so a variable's tier is its worst member's.

Checks fall into two tiers. A failed check sends the column to *manual* review
when it is evidence the answer is wrong:
  - the two runs annotated it differently
  - the two runs partitioned its group differently
  - the proposed term isn't in the pinned ontology
  - the primary term is outside the property space, which primaries are
    supposed to come from
It sends the column to *quick* review when the answer is probably right but
makes a claim that deserves a glance:
  - the qualifiers differ between runs
  - the term was picked among several with the same label
  - the annotator flagged it
  - the predicate is `indicator` or `none`, the two hardest to get right
  - values are recoded to pool
  - the variable pools many differently named columns (the bucket principle)

The precision of each tier on the tuning gold is in the decisions log (8.x).
It was measured on data these rules were chosen on, so the sealed corpus is
the honest test.
"""
from __future__ import annotations

import json

import pandas as pd

from colharmonize.normalise import normalise_key

PRE, QUICK, MANUAL = "pre_accepted", "quick", "manual"
RANK = {PRE: 0, QUICK: 1, MANUAL: 2}
# A variable that pools this many distinct column names gets a second look.
BROAD_BUCKET_NAMES = 4


def _checks(r) -> list[tuple[str, str]]:
    """(tier, reason) for every check this column fails."""
    out = []
    if not r.annotation_agree:
        out.append((MANUAL, "annotation runs disagree"))
    if r.reconciled and not r.partition_agreement == 1:
        out.append((MANUAL, "partition runs disagree"))
    if r.unresolved_proposal:
        out.append((MANUAL, f"proposed term not in the ontology: {r.unresolved_proposal}"))
    if r.outside_space:
        out.append((MANUAL, "primary term outside the property space"))
    if not r.qualifiers_agree:
        out.append((QUICK, "qualifier runs disagree"))
    if r.ambiguous:
        out.append((QUICK, "term picked among several with the same label"))
    flags = json.loads(r.flags)
    if flags:
        out.append((QUICK, "flagged: " + ", ".join(flags)))
    if r.predicate in ("indicator", "none"):
        out.append((QUICK, f"predicate {r.predicate}"))
    if json.loads(r.recodes):
        out.append((QUICK, "values recoded"))
    return out


def tiers(variables: pd.DataFrame) -> pd.DataFrame:
    """`variables` (from reconcile) plus tier, reasons, and the variable's tier."""
    v = variables.copy()
    checks = [_checks(r) for r in v.itertuples(index=False)]
    names = v.groupby("variable_id").column.agg(lambda c: len({normalise_key(x.split("#")[-1]) for x in c}))
    for i, vid in enumerate(v.variable_id):
        if names[vid] >= BROAD_BUCKET_NAMES:
            checks[i].append((QUICK, f"variable pools {names[vid]} column names"))
    v["tier"] = [max((t for t, _ in c), key=RANK.get, default=PRE) for c in checks]
    v["reasons"] = [json.dumps([why for _, why in c]) for c in checks]
    v["variable_tier"] = v.groupby("variable_id").tier.transform(lambda t: max(t, key=RANK.get))
    return v


def summary(scored: pd.DataFrame) -> str:
    cols = scored.tier.value_counts()
    var = scored.drop_duplicates("variable_id").variable_tier.value_counts()
    lines = [f"{'tier':14s} columns  variables"]
    for t in (PRE, QUICK, MANUAL):
        lines.append(f"{t:14s} {cols.get(t, 0):7d}  {var.get(t, 0):9d}")
    return "\n".join(lines)
