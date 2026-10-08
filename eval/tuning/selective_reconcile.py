"""Offline test: reconcile only the groups annotation can't settle.

A candidate group is *settled* when every member already has the same
annotation identity (predicate, primary term, non-unit qualifiers) and no two
members conflict on shared samples. Annotation pools those columns anyway, so
reconciliation can only split them. This rebuilds each run's final variables
with settled groups taken from annotation and the rest from the run's existing
reconcile answers, then scores both against the gold. No new subagent runs.

    ./.venv/bin/python eval/tuning/selective_reconcile.py WORKSPACE RUN_A RUN_B {tuning|sealed}

On the sealed corpus this is a post-hoc analysis, never a headline number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from colharmonize import annotate, reconcile, tasks  # noqa: E402
from colharmonize.evaluate import load_gold, score  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402

GOLD = {"tuning": ("ds_tuning_columns.tsv", "ds_tuning_variables.tsv"),
        "sealed": ("generalization_columns.tsv", "generalization_variables.tsv")}


def settled_groups(ws: Workspace, run: int, ann: pd.DataFrame) -> set[str]:
    d = ws.tasks(reconcile.STAGE, run)
    members = json.loads((d / "members.json").read_text())
    cannot = {}
    for path in d.glob("batch_*.json"):
        if not path.name.endswith(".answer.json"):
            for it in json.loads(path.read_text())["items"]:
                cannot[it["item_id"]] = it.get("cannot_pool", [])
    ident = dict(zip(ann.study_id + "::" + ann.column, ann.variable_id))
    out = set()
    for gid, refs in members.items():
        cols = [c for c in refs.values() if not c.startswith("registry::")]
        if len({ident.get(c) for c in cols}) == 1 and not cannot.get(gid) and len(cols) == len(refs):
            out.add(gid)
    return out


def predictions(final: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"accession": final.study_id, "raw_key": final.column, "variable_id": final.variable_id,
                         "predicate": final.predicate, "primary_curie": final.primary_curie,
                         "qualifiers": final.qualifiers.map(lambda q: "; ".join(f"{a}={b}" for a, b in json.loads(q)))})


def main(workspace: str, run_a: str, run_b: str, corpus: str) -> None:
    ws = Workspace(workspace)
    resolver = annotate.make_resolver(ws)
    ann = pd.read_parquet(ws.root / "annotations.parquet")
    gold = load_gold(ROOT / "eval/gold" / GOLD[corpus][0], ROOT / "eval/gold" / GOLD[corpus][1])
    km = {tuple(k.split("\t")): v for k, v in json.loads((ws.root / "key_map.json").read_text()).items()}
    back = {(a, v): k for (a, k), v in km.items()}
    runs = {}
    for run in (int(run_a), int(run_b)):
        got = tasks.collect(ws.tasks(reconcile.STAGE, run), reconcile.ReconcileAnswer)
        runs[run] = reconcile.resolve_run(ws, got.answers, run, resolver)
    a, b = int(run_a), int(run_b)
    settled = settled_groups(ws, a, ann)
    n_groups = len(json.loads((ws.tasks(reconcile.STAGE, a) / "members.json").read_text()))
    rows = []
    for label, r1, r2 in [("reconcile every group", runs[a], runs[b]),
                          ("reconcile unsettled groups only",
                           runs[a][~runs[a].group.isin(settled)], runs[b][~runs[b].group.isin(settled_groups(ws, b, ann))])]:
        pred = predictions(reconcile.finalize(ann, r1, r2, resolver.ontology.label_map()))
        pred["raw_key"] = [back.get((x, k), k) for x, k in zip(pred.accession, pred.raw_key)]
        s = score(gold, pred)
        rows.append((label, s.pooling["precision"], s.pooling["recall"], s.pooling["f1"],
                     s.annotation["primary_accuracy"], s.annotation["annotation_accuracy"]))
    pred = predictions(ann.assign(qualifiers=ann.qualifiers))
    pred["raw_key"] = [back.get((x, k), k) for x, k in zip(pred.accession, pred.raw_key)]
    s = score(gold, pred)
    rows.append(("annotation only", s.pooling["precision"], s.pooling["recall"], s.pooling["f1"],
                 s.annotation["primary_accuracy"], s.annotation["annotation_accuracy"]))
    print(f"{corpus}, runs {a}/{b}: {len(settled)} of {n_groups} groups settled by annotation")
    print(f"{'':34s} {'P':>7s} {'R':>7s} {'F1':>7s} {'term':>7s} {'term+pred':>9s}")
    for label, p, r, f, t, tp in rows:
        print(f"{label:34s} {p:7.1%} {r:7.1%} {f:7.1%} {t:7.1%} {tp:9.1%}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
