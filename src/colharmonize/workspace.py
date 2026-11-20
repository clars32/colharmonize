"""Where a colharmonize run keeps its files.

    <root>/
      geomend/              the MetaMend cohort project (folder keeps its pre-rename name) (created by `ingest`)
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
      workspace.json        settings recorded by earlier commands (pinned ontology directory, MetaMend store)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TAG = "v3.94.0"


def default_ontology_dir(tag: str = DEFAULT_TAG) -> Path:
    """Where `ontology fetch` pins a release when no --out is given, and where a
    workspace with nothing recorded looks: $COLHARMONIZE_HOME, else
    ~/.local/share/colharmonize, then ontology/efo-<tag>."""
    home = os.environ.get("COLHARMONIZE_HOME") or Path.home() / ".local" / "share" / "colharmonize"
    return Path(home).expanduser() / "ontology" / f"efo-{tag}"


@dataclass(frozen=True)
class Workspace:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def metamend(self) -> Path:
        # The folder keeps the name it had before GEOmend became MetaMend, so
        # existing workspaces still open.
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
        """A path setting: `given`, which is then recorded for later commands, or the
        one recorded earlier, or else the default location if something is there."""
        flag, what, how = _PATH_SETTINGS[key]
        if given:
            path = Path(given).expanduser().resolve()
            if not path.exists():
                raise SystemExit(f"{flag} {given}: no such file or directory")
            self.remember(**{key: str(path)})
            return path
        if self.settings().get(key):
            return Path(self.settings()[key])
        default = default_ontology_dir()
        if key == "geomend_store":
            default = default.with_name(default.name + ".sqlite")
        if default.exists():
            self.remember(**{key: str(default)})
            return default
        raise SystemExit(f"{self.root}: no {what} recorded for this workspace, and none at {default}; {how}")

    def ontology_dir(self) -> Path:
        return self.recorded("ontology")


# setting -> (the option that records it, what it is, how to record it)
_PATH_SETTINGS = {
    "ontology": ("--ontology", "pinned ontology directory",
                 "pass --ontology DIR to `colharmonize preprocess` or `candidates` "
                 "(`colharmonize ontology fetch` makes one)"),
    "geomend_store": ("--store", "MetaMend ontology store",
                      "pass --store FILE to `colharmonize preprocess` "
                      "(`colharmonize ontology fetch` builds one beside the pinned directory)"),
}
