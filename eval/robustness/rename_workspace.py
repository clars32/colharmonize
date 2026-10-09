"""Make a renamed copy of the tuning workspace for the robustness test.

    ./.venv/bin/python eval/robustness/rename_workspace.py SRC DEST

Copies the files candidates and annotate read (never the GEOmend project),
renames characteristic columns with `renames.json`, and rewrites `key_map.json`
so the scorer maps renamed columns back to gold keys. Values, titles, repaired
columns and everything else are unchanged.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
FILES = ["columns.parquet", "samples.parquet", "studies.parquet", "derived.parquet", "workspace.json", "key_map.json"]


def main(src: str, dest: str) -> None:
    src_p, dest_p = Path(src), Path(dest)
    if (dest_p / "candidates.parquet").exists() or (dest_p / "tasks").exists():
        sys.exit(f"{dest}: already has run outputs; refusing to overwrite")
    dest_p.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(src_p / f, dest_p / f)
    shutil.copytree(src_p / "geomend_evidence", dest_p / "geomend_evidence", dirs_exist_ok=True)

    renames = {tuple(k.split("::", 1)): v for k, v in json.loads((HERE / "renames.json").read_text()).items()}
    cols = pd.read_parquet(dest_p / "columns.parquet")
    missing = set(renames) - set(zip(cols.study_id, cols.column))
    if missing:
        sys.exit(f"renames for unknown columns: {sorted(missing)}")
    cols["column"] = [renames.get((s, c), c) for s, c in zip(cols.study_id, cols.column)]
    cols.to_parquet(dest_p / "columns.parquet", index=False)

    # key_map: "accession<TAB>gold key" -> the run's column name.
    km = json.loads((dest_p / "key_map.json").read_text())
    for (study, old), new in renames.items():
        hit = [k for k, v in km.items() if k.split("\t")[0] == study and v == old]
        for k in hit:
            km[k] = new
        if not hit:
            km[f"{study}\t{old}"] = new
    (dest_p / "key_map.json").write_text(json.dumps(km, indent=1, ensure_ascii=False) + "\n")
    print(f"renamed {len(renames)} columns into {dest}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
