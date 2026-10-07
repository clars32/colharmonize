"""Score a pair of reconcile runs without touching the workspace's outputs.

`colharmonize reconcile apply` overwrites variables.parquet, which review
decisions are fingerprinted against. To compare an experimental pair of runs
with the pair of record, this builds the final variables in memory and writes
predictions only to OUT.

    ./.venv/bin/python eval/tuning/score_reconcile_runs.py WORKSPACE RUN_A RUN_B OUT.tsv
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from colharmonize import annotate, reconcile, tasks  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402


def main(workspace: str, run_a: str, run_b: str, out: str) -> None:
    ws = Workspace(workspace)
    resolver = annotate.make_resolver(ws)
    runs = []
    for run in (int(run_a), int(run_b)):
        got = tasks.collect(ws.tasks(reconcile.STAGE, run), reconcile.ReconcileAnswer)
        got.problems += reconcile.validate_answers(ws, got.answers, run=run, resolver=resolver)
        if not got.complete:
            sys.exit(json.dumps({"run": run, "pending": got.pending, "problems": got.problems}, indent=1))
        runs.append(reconcile.resolve_run(ws, got.answers, run, resolver))
    ann = pd.read_parquet(ws.root / "annotations.parquet")
    final = reconcile.finalize(ann, runs[0], runs[1], resolver.ontology.label_map())
    pred = pd.DataFrame({"accession": final.study_id, "raw_key": final.column, "variable_id": final.variable_id,
                         "predicate": final.predicate, "primary_curie": final.primary_curie,
                         "qualifiers": final.qualifiers.map(lambda q: "; ".join(f"{a}={b}" for a, b in json.loads(q)))})
    pred.to_csv(out, sep="\t", index=False)
    grouped = final[final.reconciled]
    print(f"{len(final)} columns -> {final.variable_id.nunique()} variables; "
          f"partition agreement {grouped.partition_agreement.mean():.1%}; wrote {out}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
