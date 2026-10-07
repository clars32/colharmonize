"""Measure what GEOmend preprocessing evidence adds to candidate retrieval (tuning workspace).

For each concept-score cutoff, regenerate candidates in memory (the workspace's
own candidates.parquet is left alone) and report gold primary-term recall in
the pool and among displayed candidates, and gold unit recall.

    ./.venv/bin/python eval/tuning/preprocess_effect.py WORKSPACE
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from colharmonize import candidates as cd, preprocess, profile, property_space  # noqa: E402
from colharmonize.evaluate import load_gold  # noqa: E402
from colharmonize.ontology import Ontology  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402


def unit_recall(c: pd.DataFrame, gold: pd.DataFrame, key_map: dict) -> tuple[int, int]:
    units = c[c.pool == "unit"].groupby(["study_id", "column"]).curie.agg(set).to_dict()
    hit = n = 0
    for r in gold.itertuples(index=False):
        u = str(r.unit).split(" ")[0]
        if not u.startswith("UO:"):
            continue
        n += 1
        hit += u in units.get(key_map.get((r.accession, r.raw_key), (r.accession, r.raw_key)), set())
    return hit, n


def main(workspace: str) -> None:
    ws = Workspace(workspace)
    onto = Ontology.from_dir(ws.ontology_dir())
    retriever = cd.Retriever(onto, property_space.build(onto), ROOT / "work/cache/embeddings",
                             cd.RemoteCache(ROOT / "work/cache/remote.json", enabled=False))
    cols = profile.annotation_columns(ws)
    gold = load_gold(ROOT / "eval/gold/ds_tuning_columns.tsv", ROOT / "eval/gold/ds_tuning_variables.tsv")
    km = {tuple(k.split("\t")): v for k, v in json.loads((ws.root / "key_map.json").read_text()).items()}
    key_map = {k: (k[0], v) for k, v in km.items()}
    print(f"{'GEOmend concepts':28s} {'pool':>7s} {'shown':>7s} {'units':>7s}")
    for label, cutoff in [("none (current)", None), ("exact only (score >= 4)", 4.0),
                          ("substring too (>= 2.4)", 2.4), ("all", 0.0)]:
        hints = {} if cutoff is None else preprocess.hints(ws, cutoff, concepts_on=True, units_on=False)
        if cutoff is None:   # units alone are measured separately below
            hints = {}
        c = cd.generate(retriever, cols, hints)
        rec = cd.evaluate_recall(c, gold, key_map)
        uh, un = unit_recall(c, gold, key_map)
        print(f"{label:28s} {rec['primary_pool_recall']:7.1%} {rec['primary_displayed_recall']:7.1%} {uh:>3d}/{un:<3d}")
    units_only = preprocess.hints(ws, concepts_on=False, units_on=True)
    c = cd.generate(retriever, cols, units_only)
    uh, un = unit_recall(c, gold, key_map)
    print(f"{'GEOmend units only':28s} {'':>7s} {'':>7s} {uh:>3d}/{un:<3d}")


if __name__ == "__main__":
    main(sys.argv[1])
