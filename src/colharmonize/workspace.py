"""Where a colharmonize run keeps its files.

    <root>/
      geomend/              the GEOmend cohort project (created by `ingest`)
      columns.parquet       one row per (study, column): coverage, values, shape hint
      samples.parquet       per-sample title and source name
      studies.parquet       per-study title, summary, overall design
      tasks/<stage>/run<k>/ task batches for Claude Code subagents and their answers
      derived.parquet       columns recovered by the repair stage
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workspace:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def geomend(self) -> Path:
        return self.root / "geomend"

    @property
    def columns(self) -> Path:
        return self.root / "columns.parquet"

    @property
    def samples(self) -> Path:
        return self.root / "samples.parquet"

    @property
    def studies(self) -> Path:
        return self.root / "studies.parquet"

    @property
    def derived(self) -> Path:
        return self.root / "derived.parquet"

    def tasks(self, stage: str, run: int) -> Path:
        return self.root / "tasks" / stage / f"run{run}"
