"""GEOmend's default variable grouping (`propose()`, no model) as pooling predictions.

GEOmend groups fields by normalised label with a few aliases (gender -> sex),
keeps generic labels (condition, treatment, ...) per study, and assigns no
ontology terms, so only pooling is scored. Columns GEOmend could not parse
(GSE16176 'gestational age (weeks, days)') and columns iteration 2 recovered
from titles have no GEOmend field and score as missing.

Input is the field-to-variable dump from the Phase 0 GEOmend run over all 64
series (`work/spike/out/field_to_variable_characteristics.tsv`). The output TSV is
committed because the 1.5 GB project it came from is not.

Run: python eval/baselines/geomend_propose.py
"""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DUMP = ROOT / "work/spike/out/field_to_variable_characteristics.tsv"
SNAPSHOT = ROOT / "eval/snapshots/ds_tuning_characteristics.json"

snap = json.loads(SNAPSHOT.read_text())
f = pd.read_csv(DUMP, sep="\t", dtype=str, keep_default_na=False)
f = f[f.study_id.isin(snap) & (f.scope == "sample") & (f.namespace == "characteristic")]
rows = [{"accession": r.study_id, "raw_key": r.field_name, "variable_id": r.variable_id}
        for r in f.itertuples(index=False) if r.field_name in snap[r.study_id]["characteristics"]]
out = HERE / "geomend_propose_ds_tuning.tsv"
pd.DataFrame(rows).to_csv(out, sep="\t", index=False)
print(f"{out.name}: {len(rows)} predictions ({len(f) - len(rows)} GEOmend fields with no gold column)")
