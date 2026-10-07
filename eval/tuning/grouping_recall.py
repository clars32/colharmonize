"""How many gold-pooled pairs reach the same reconcile group (tuning workspace).

Reconciliation can only pool columns that candidate grouping put together, so
grouping recall bounds pooling recall. Usage:

    ./.venv/bin/python eval/tuning/grouping_recall.py WORKSPACE
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from colharmonize import profile, reconcile  # noqa: E402
from colharmonize.ontology import Ontology  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402


def main(workspace: str) -> None:
    ws = Workspace(workspace)
    ann = pd.read_parquet(ws.root / "annotations.parquet")
    cols = profile.annotation_columns(ws)
    values = {f"{s}::{c}": reconcile.distinctive(v for v, _ in json.loads(vals))
              for s, c, vals in zip(cols.study_id, cols.column, cols["values"])}
    links = reconcile.extra_links(ws) if hasattr(reconcile, "extra_links") else None
    kwargs = {"links": links} if links is not None else {}
    groups = reconcile.candidate_groups(ann, Ontology.from_dir(ws.ontology_dir()), values, **kwargs)
    group_of = {m: i for i, g in enumerate(groups) for m in g}
    gold = pd.read_csv(ROOT / "eval/gold/ds_tuning_columns.tsv", sep="\t", dtype=str, keep_default_na=False)
    gold = gold[gold.variable_id != "SPLIT"]
    km = {tuple(k.split("\t")): v for k, v in json.loads((ws.root / "key_map.json").read_text()).items()}
    member = {(a, k): f"{a}::{km.get((a, k), k)}" for a, k in zip(gold.accession, gold.raw_key)}
    var = dict(zip(zip(gold.accession, gold.raw_key), gold.variable_id))
    pairs = [(a, b) for a, b in itertools.combinations(var, 2) if var[a] == var[b]]
    hit = [(a, b) for a, b in pairs
           if member[a] in group_of and group_of.get(member[a]) == group_of.get(member[b])]
    print(f"groups: {len(groups)}, sizes {sorted((len(g) for g in groups), reverse=True)}")
    print(f"gold pairs in one group: {len(hit)}/{len(pairs)} = {len(hit) / len(pairs):.1%}")
    for a, b in sorted(set(pairs) - set(hit)):
        print(f"  apart: {var[a]}: {member[a]}  |  {member[b]}")


if __name__ == "__main__":
    main(sys.argv[1])
