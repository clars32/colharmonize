"""Baseline pooling predictions on the sealed corpus (pre-registered).

- geomend_propose: GEOmend's own variable grouping (`propose()`, no model),
  read from the workspace's GEOmend project right after ingest, before
  `preprocess` reconfigures it. No ontology terms, so only pooling is scored.
- same_name: columns pool when their normalised names are identical.

Characteristic columns only; derived gold columns have no baseline prediction
and score as missing, as they did for the tuning baselines.

Usage: python eval/sealed/baselines.py WORKSPACE OUT_DIR
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize import geomend_bridge as gb  # noqa: E402
from colharmonize.normalise import normalise_key  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402


def main(workspace: str, out_dir: str) -> None:
    ws, out = Workspace(workspace), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fields = gb._fields(ws.geomend, lambda f: f["scope"] == "sample" and f["namespace"] == "characteristic",
                        with_values=False)
    propose = pd.DataFrame([{"accession": f["study_id"], "raw_key": f["name"],
                             "variable_id": (f.get("mapping") or {}).get("variable_id") or f"none:{f['field_id']}"}
                            for f in fields])
    propose.to_csv(out / "geomend_propose_sealed.tsv", sep="\t", index=False)
    same = propose.assign(variable_id=propose.raw_key.map(lambda k: "name:" + normalise_key(k)))
    same.to_csv(out / "same_name_sealed.tsv", sep="\t", index=False)
    print(f"{len(propose)} characteristic fields; GEOmend variables {propose.variable_id.nunique()}; "
          f"name groups {same.variable_id.nunique()}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
