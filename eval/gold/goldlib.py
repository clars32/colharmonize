"""Validation and output shared by every gold-standard builder.

A gold standard is two lists written as Python data in a builder script:

V: (variable_id, name, predicate, primary_curie, qualifiers, value_type, rationale)
   qualifiers is a list of (slot, value); a value matching CURIE is validated
   against the pinned ontology, anything else is recorded as ungrounded text.
C: (accession, raw_key, source, variable_id, unit, flags, note)
   source is "characteristic", "title", or "split:<parent raw_key>".
   variable_id "SPLIT" marks a column whose parts are listed as separate rows.

Predicates:
  exact      the variable means the term; values are instances or measurements of it
  broad      the term is broader; the variable keeps its own name, the term anchors it
  indicator  the variable is a yes/no or 0/1 indicator of the term
  none       no adequate term in the pinned pool; the variable still pools

Partition rules (owner-confirmed 2026-10-05):
  1. Pool columns only when no information from the original dataset is lost:
     every value keeps its meaning in the pooled column. Recoding, unit
     conversion and splitting are allowed to achieve that.
  2. Columns with values on the same samples never pool, unless their values
     are identical on every shared sample (flag duplicate_encoding).
  3. Columns of one dataset covering disjoint samples may pool.
  4. Different classification systems or instruments are different variables,
     even when they share an anchor term.

The snapshot is the metadata the gold was curated against. It must contain, per
accession, "characteristics" (raw_key -> value counts), optionally "derived"
(gold raw_key -> value counts for columns recovered from titles or source
names), "coverage" (raw_key -> number of samples) and "disjoint_pairs"
("a || b" for keys with no sample in common).
"""
from __future__ import annotations

import csv
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT.parent / "efo-column-mapping/data/ontology/efo_index_v3.94.0.parquet"
ALLOWED = {"EFO", "UBERON", "CL", "MONDO", "PATO", "NCIT", "OBI", "CHEBI", "UO"}
PREDICATES = {"exact", "broad", "indicator", "none"}
SLOTS = {"subject", "object_class", "event_time_anchor", "method", "unit"}
FLAGS = {"REVIEW", "assumed_convention", "duplicate_encoding"}
CURIE = re.compile(r"^[A-Za-z]+:\d+$")


def build(V: list, C: list, snapshot: Path, out_dir: Path, prefix: str) -> int:
    """Validate V and C against the snapshot and pinned ontology, then write
    `<prefix>_variables.tsv` and `<prefix>_columns.tsv`. Returns a process exit code."""
    errors: list[str] = []
    snap = json.loads(Path(snapshot).read_text())
    ix = pd.read_parquet(INDEX).set_index("curie")

    def check_curie(c: str, where: str) -> str:
        if c not in ix.index:
            errors.append(f"{where}: {c} not in pinned file"); return ""
        row = ix.loc[c]
        if bool(row.deprecated): errors.append(f"{where}: {c} is deprecated")
        if c.split(":")[0] not in ALLOWED: errors.append(f"{where}: {c} prefix not allowlisted")
        return str(row.label)

    var = {}
    for vid, name, pred, prim, quals, vtype, why in V:
        if vid in var: errors.append(f"duplicate variable {vid}")
        if pred not in PREDICATES: errors.append(f"{vid}: bad predicate {pred}")
        if (pred == "none") != (prim == ""): errors.append(f"{vid}: predicate/term mismatch")
        label = check_curie(prim, vid) if prim else ""
        qs = []
        for slot, val in quals:
            if slot not in SLOTS: errors.append(f"{vid}: bad slot {slot}")
            if CURIE.match(val):
                qs.append(f"{slot}={val} [{check_curie(val, vid)}]")
            else:
                qs.append(f'{slot}="{val}" (ungrounded)')
        var[vid] = dict(variable_id=vid, name=name, predicate=pred, primary_curie=prim,
                        primary_label=label, qualifiers="; ".join(qs), value_type=vtype, rationale=why)

    rows = []
    for a, k, src, vid, unit, flags, note in C:
        fl = [f for f in flags.split(",") if f]
        if "inferred" in unit and "assumed_convention" not in fl:
            fl.append("assumed_convention")
        for f in fl:
            if f not in FLAGS: errors.append(f"{a}/{k}: unknown flag {f}")
        rows.append((a, k, src, vid, unit, ",".join(fl), note))

    seen = Counter((a, k) for a, k, src, *_ in C if not src.startswith("split:"))
    for (a, k), n in seen.items():
        if n > 1: errors.append(f"{a}/{k} listed {n} times")
    for acc, x in snap.items():
        for k in list(x["characteristics"]) + list(x.get("derived", {})):
            if (acc, k) not in seen: errors.append(f"{acc}/{k} has no gold row")
    for a, k, src, vid, *_ in C:
        if a not in snap: errors.append(f"{a} not in snapshot"); continue
        if src == "characteristic" and k not in snap[a]["characteristics"]:
            errors.append(f"{a}/{k} not in snapshot")
        if vid != "SPLIT" and vid not in var: errors.append(f"{a}/{k}: unknown variable {vid}")
        if src.startswith("split:") and (a, src[6:]) not in seen: errors.append(f"{a}/{k}: split parent missing")

    # Rule 2: members of one variable from the same dataset must cover disjoint
    # samples, unless flagged as a duplicate encoding. Only keys whose coverage
    # the snapshot records can be checked; split parts of one column never share.
    members = defaultdict(list)
    for a, k, src, vid, unit, flags, note in C:
        if vid != "SPLIT": members[vid].append((a, k, src, flags))
    for vid, ms in members.items():
        for (a1, k1, s1, f1), (a2, k2, s2, f2) in itertools.combinations(ms, 2):
            if a1 != a2: continue
            if s1.startswith("split:") and s1 == s2:
                errors.append(f"{vid}: two parts of one split column in one variable"); continue
            cov = snap[a1]["coverage"]
            if k1 in cov and k2 in cov:
                pairs = snap[a1]["disjoint_pairs"]
                disjoint = f"{k1} || {k2}" in pairs or f"{k2} || {k1}" in pairs
                if not disjoint and "duplicate_encoding" not in f1 + f2:
                    errors.append(f"{vid}: {a1} '{k1}' and '{k2}' co-occur")
    for vid in var:
        if vid not in members: errors.append(f"variable {vid} has no members")

    if errors:
        print("\n".join(errors)); return 1

    for vid, v in var.items():
        ms = members[vid]
        v["n_members"] = len(ms)
        v["n_datasets"] = len({a for a, *_ in ms})
    cols = ["variable_id", "name", "predicate", "primary_curie", "primary_label", "qualifiers",
            "value_type", "n_members", "n_datasets", "rationale"]
    out_dir = Path(out_dir)
    with open(out_dir / f"{prefix}_variables.tsv", "w", newline="") as f:
        w = csv.DictWriter(f, cols, delimiter="\t", lineterminator="\n"); w.writeheader()
        w.writerows(var.values())
    with open(out_dir / f"{prefix}_columns.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["accession", "raw_key", "source", "variable_id", "unit", "flags", "note"])
        w.writerows(rows)

    pooled = [v for v in var.values() if v["n_datasets"] > 1]
    print(f"OK: {len(C)} column rows, {len(var)} variables, {len(pooled)} span >1 dataset")
    print(f"predicates: {dict(Counter(v['predicate'] for v in var.values()))}")
    print(f"flags: {dict(Counter(f for r in rows for f in r[5].split(',') if f))}")
    return 0
