"""Copy a workspace's annotate inputs and existing annotate runs for the cross-model test.

    ./.venv/bin/python eval/models/setup.py SRC DEST RUN [RUN ...]

Copies what `tasks write annotate` and answer collection read (never the
GEOmend project), plus the named annotate run directories with their answers.
The source workspace is not modified.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

FILES = ["columns.parquet", "samples.parquet", "studies.parquet", "derived.parquet", "candidates.parquet",
         "workspace.json", "key_map.json"]


def main(src: str, dest: str, *runs: str) -> None:
    s, d = Path(src), Path(dest)
    if d.exists():
        sys.exit(f"{dest} exists; refusing to overwrite")
    d.mkdir(parents=True)
    for f in FILES:
        shutil.copy2(s / f, d / f)
    shutil.copytree(s / "geomend_evidence", d / "geomend_evidence")
    for run in runs:
        shutil.copytree(s / "tasks" / "annotate" / f"run{run}", d / "tasks" / "annotate" / f"run{run}")
    print(f"copied {src} -> {dest} with annotate runs {', '.join(runs)}")


if __name__ == "__main__":
    main(*sys.argv[1:])
