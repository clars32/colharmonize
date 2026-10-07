"""Map sealed-gold column keys to the columns a pipeline run produced (pre-registered).

1. A gold characteristic the run annotated under the same name maps to itself.
2. Every other gold column is matched among the run's repaired columns in the
   same study, from the same source: titles or source names for `title#X` /
   `source_name#X`, the parent for a split part `parent#X`, and any
   characteristic (including GEOmend's "unresolved characteristic") for a gold
   characteristic GEOmend did not parse under its name. Candidates score by
   Jaccard similarity of their names after `#` over normalised words. For a gold
   characteristic with no shared word, the score is instead the share of its
   samples whose snapshot values agree with the candidate's value counts, and it
   counts only at 0.7 or more.
3. Matching is greedy, best score first; each run column matches at most one
   gold column. Anything unmatched is scored as missing.

The sealed gold has no per-sample values for derived columns, so unlike the
tuning alignment this matches mainly by source and name. The rule was fixed before the
pipeline ran on the sealed corpus (eval/sealed/PROTOCOL.md).

Usage: python eval/sealed/align.py WORKSPACE   -> WORKSPACE/key_map.json
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize import profile  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402

import os  # noqa: E402
GOLD = Path(os.environ.get("SEALED_ALIGN_GOLD", ROOT / "eval/gold/generalization_columns.tsv"))
SNAPSHOT = Path(os.environ.get("SEALED_ALIGN_SNAPSHOT", ROOT / "eval/snapshots/generalization_characteristics.json"))
MIN_VALUE_AGREEMENT = 0.7


def words(name: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", name.casefold().replace("_", " ")))


def jaccard(a: str, b: str) -> float:
    x, y = words(a), words(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def norm(v: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(v).casefold()).strip()


def value_agreement(gold_counts: dict[str, int], run_counts: list) -> float:
    """Share of the gold column's samples whose value appears among the run column's values."""
    total = sum(gold_counts.values())
    run = {norm(v): n for v, n in run_counts}
    return sum(min(n, run.get(norm(v), 0)) for v, n in gold_counts.items()) / total if total else 0.0


def main(workspace: str) -> None:
    ws = Workspace(workspace)
    gold = pd.read_csv(GOLD, sep="\t", dtype=str, keep_default_na=False)
    cols = profile.annotation_columns(ws)
    annotated = set(zip(cols.study_id, cols.column))
    derived = pd.read_parquet(ws.derived) if ws.derived.exists() else pd.DataFrame(
        columns=["study_id", "column", "source", "source_column"])
    origin = derived.drop_duplicates(["study_id", "column"])[["study_id", "column", "source", "source_column"]]
    run_values = {(s, c): json.loads(v) for s, c, v in zip(cols.study_id, cols.column, cols["values"])}
    snap = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}
    key_map, report = {}, []
    scored = []
    identity = {(r.accession, r.raw_key) for r in gold.itertuples(index=False)
                if r.source == "characteristic" and (r.accession, r.raw_key) in annotated}
    for r in gold.itertuples(index=False):
        if (r.accession, r.raw_key) in identity:
            report.append((r.accession, r.raw_key, r.raw_key, ""))
            continue
        here = origin[origin.study_id == r.accession]
        if r.source == "characteristic":
            pool, part = here[here.source == "characteristic"], r.raw_key
        elif r.source == "title":
            prefix, part = r.raw_key.split("#", 1)
            pool = here[here.source == prefix]
        else:
            part = r.raw_key.split("#", 1)[1]
            pool = here[(here.source == "characteristic") & (here.source_column == r.source.removeprefix("split:"))]
        counts = {}
        if r.source == "characteristic" and r.accession in snap:
            chars = snap[r.accession]["characteristics"]
            chars = ast.literal_eval(chars) if isinstance(chars, str) else chars   # stored as a repr in places
            counts = chars.get(r.raw_key, {})
        for c in pool.column:
            if (r.accession, c) not in annotated or (r.accession, c) in identity:
                continue
            sim = jaccard(part, c.split("#", 1)[-1])
            if sim == 0 and counts:
                agree = value_agreement(counts, run_values.get((r.accession, c), []))
                sim = agree if agree >= MIN_VALUE_AGREEMENT else 0
            scored.append((sim, r.accession, r.raw_key, c))
    taken_gold, taken_run = set(), set()
    for sim, study, raw_key, col in sorted(scored, key=lambda t: (-t[0], t[1], t[2], t[3])):
        if sim <= 0 or (study, raw_key) in taken_gold or (study, col) in taken_run:
            continue
        taken_gold.add((study, raw_key))
        taken_run.add((study, col))
        key_map[f"{study}\t{raw_key}"] = col
        report.append((study, raw_key, col, f"{sim:.2f}"))
    for r in gold.itertuples(index=False):
        if (r.accession, r.raw_key) not in identity and (r.accession, r.raw_key) not in taken_gold:
            report.append((r.accession, r.raw_key, None, ""))
    (ws.root / "key_map.json").write_text(json.dumps(key_map, indent=1))
    missing = [x for x in report if x[2] is None]
    for row in report:
        if row[3] or row[2] is None:
            print("{:10} {:42} -> {} {}".format(*row))
    print(f"{len(gold) - len(missing)}/{len(gold)} gold columns matched; {len(missing)} missing")


if __name__ == "__main__":
    main(sys.argv[1])
