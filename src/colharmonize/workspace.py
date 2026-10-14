"""Where a colharmonize run keeps its files.

    <root>/
      geomend/              the GEOmend cohort project (created by `ingest`)
      columns.parquet       one row per (study, column): coverage, values, shape hint
      samples.parquet       per-sample title and source name
      studies.parquet       per-study title, summary, overall design
      tasks/<stage>/run<k>/ task batches for Claude Code subagents and their answers
      derived.parquet       columns recovered by the repair stage
      candidates.parquet    candidate terms per annotation column
      annotations.parquet   per-column annotation, run 1 of record, with run 2 agreement
      variables.parquet     final variable per column after reconciliation, with confidence signals
      scored.parquet        variables plus review tier and the reasons for it
      predictions_*.tsv     the same, in the scorer's (accession, raw_key) format
      workspace.json        settings recorded by earlier commands (pinned ontology directory, GEOmend store)
"""
from __future__ import annotations

import json
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

    @property
    def candidates(self) -> Path:
        return self.root / "candidates.parquet"

    def tasks(self, stage: str, run: int) -> Path:
        return self.root / "tasks" / stage / f"run{run}"

    @property
    def settings_file(self) -> Path:
        return self.root / "workspace.json"

    def settings(self) -> dict:
        return json.loads(self.settings_file.read_text()) if self.settings_file.exists() else {}

    def remember(self, **values) -> None:
        self.settings_file.write_text(json.dumps({**self.settings(), **values}, indent=1))

    def recorded(self, key: str, given: str | Path | None = None) -> Path:
        """A path setting: `given`, which is then recorded for later commands, or the one recorded earlier."""
        flag, what, how = _PATH_SETTINGS[key]
        if given:
            path = Path(given).expanduser().resolve()
            if not path.exists():
                raise SystemExit(f"{flag} {given}: no such file or directory")
            self.remember(**{key: str(path)})
            return path
        if not self.settings().get(key):
            raise SystemExit(f"{self.root}: no {what} recorded for this workspace; {how}")
        return Path(self.settings()[key])

    def ontology_dir(self) -> Path:
        return self.recorded("ontology")


# setting -> (the option that records it, what it is, how to record it)
_PATH_SETTINGS = {
    "ontology": ("--ontology", "pinned ontology directory",
                 "pass --ontology DIR to `colharmonize preprocess` or `candidates` "
                 "(`colharmonize ontology fetch` makes one)"),
    "geomend_store": ("--store", "GEOmend ontology store",
                      "pass --store FILE to `colharmonize preprocess` "
                      "(`colharmonize ontology fetch` builds one beside the pinned directory)"),
}
