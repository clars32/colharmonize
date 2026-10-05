"""Iteration 2's published mappings as predictions against the tuning gold.

Iteration 2 gave each column one IRI and treated columns with the same IRI as
the same concept, so its implied variable is the IRI. NO_MATCH columns pooled
with nothing. Its predicate is `exact` for every match (the IRI replaced the
column) and `none` for NO_MATCH, and it had no qualifiers.

Run: python eval/baselines/iteration2.py
"""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MAPPINGS = ROOT.parent / "efo-column-mapping/data/outputs/mappings.tsv"
SNAPSHOT = ROOT / "eval/snapshots/ds_tuning_characteristics.json"

snap = json.loads(SNAPSHOT.read_text())
m = pd.read_csv(MAPPINGS, sep="\t", dtype=str, keep_default_na=False)
rows = []
for r in m[m.gse.isin(snap)].itertuples(index=False):
    known = set(snap[r.gse]["characteristics"]) | set(snap[r.gse]["derived"])
    # raw_column joins every spelling seen corpus-wide ("Gender; gender").
    candidates = [v for raw in r.raw_column.split("; ") for v in (raw, f"title#{raw}", f"source_name#{raw}")]
    key = next((k for k in candidates if k in known), None)
    if key is None:
        raise SystemExit(f"cannot place {r.gse}/{r.raw_column}")
    match = r.decision == "MATCH"
    rows.append({"accession": r.gse, "raw_key": key,
                 "variable_id": r.curie if match else f"nomatch:{r.gse}:{key}",
                 "predicate": "exact" if match else "none",
                 "primary_curie": r.curie if match else "", "qualifiers": ""})
out = HERE / "iteration2_ds_tuning.tsv"
pd.DataFrame(rows).to_csv(out, sep="\t", index=False)
print(f"{out.name}: {len(rows)} predictions")
