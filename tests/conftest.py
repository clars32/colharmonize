from __future__ import annotations

from pathlib import Path

import pytest

from colharmonize.ontology import Ontology, pin_obograph

FIXTURES = Path(__file__).parent / "fixtures"
# The pinned EFO v3.94.0 index built in iteration 2. Tests that need the real
# release skip when it is absent rather than download 169 MB.
PINNED_EFO = Path(__file__).resolve().parents[2] / "efo-column-mapping" / "data" / "ontology"


@pytest.fixture(autouse=True)
def _no_user_defaults(tmp_path_factory, monkeypatch):
    """Keep tests away from this machine's default ontology, ~/Downloads, Claude Code settings and browser."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("COLHARMONIZE_HOME", str(home / "colharmonize"))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)              # never a real Claude Code config
    monkeypatch.setattr("webbrowser.open", lambda *a, **k: True)        # never open a real browser


@pytest.fixture(scope="session")
def efo() -> Ontology:
    if not any(PINNED_EFO.glob("*index*.parquet")):
        pytest.skip(f"pinned EFO index not found under {PINNED_EFO}")
    return Ontology.from_dir(PINNED_EFO)


@pytest.fixture(scope="session")
def tiny_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("tiny_ontology")
    pin_obograph(FIXTURES / "tiny_obograph.json", out, "v1.0")
    return out


@pytest.fixture(scope="session")
def tiny(tiny_dir) -> Ontology:
    return Ontology.from_dir(tiny_dir)
