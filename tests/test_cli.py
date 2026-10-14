"""The command line: one-command ontology setup."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from colharmonize import cli
from colharmonize import geomend_bridge as gb
from colharmonize.ontology import Ontology

TINY = Path(__file__).parent / "fixtures" / "tiny_obograph.json"


def test_ontology_fetch_pins_and_builds_the_store(tmp_path, capsys):
    out = tmp_path / "ontology" / "tiny-v1.0"
    assert cli.main(["ontology", "fetch", "--tag", "v1.0", "--out", str(out), "--url", TINY.as_uri()]) == 0
    onto = Ontology.from_dir(out)
    assert onto.release_tag == "v1.0"
    assert onto.version["sha256"] == hashlib.sha256(TINY.read_bytes()).hexdigest()
    assert onto.version["source_file"] == "efo.json"
    store = tmp_path / "ontology" / "tiny-v1.0.sqlite"
    assert gb.store_node_count(store, name="efo", version="1.0") == 7
    assert sorted(p.name for p in (tmp_path / "ontology").iterdir()) == ["tiny-v1.0", "tiny-v1.0.sqlite"]

    # Idempotent: a second fetch downloads nothing (this URL doesn't exist) and rewrites nothing.
    stamps = {p: p.stat().st_mtime_ns for p in [store, *out.iterdir()]}
    capsys.readouterr()
    missing = (tmp_path / "nowhere.json").as_uri()
    assert cli.main(["ontology", "fetch", "--tag", "v1.0", "--out", str(out), "--url", missing]) == 0
    assert "already pinned" in capsys.readouterr().out
    assert {p: p.stat().st_mtime_ns for p in stamps} == stamps


def test_ontology_fetch_builds_a_missing_store_without_downloading(tmp_path):
    out = tmp_path / "tiny-v1.0"
    cli.main(["ontology", "fetch", "--tag", "v1.0", "--out", str(out), "--url", TINY.as_uri()])
    (tmp_path / "tiny-v1.0.sqlite").unlink()
    missing = (tmp_path / "nowhere.json").as_uri()
    assert cli.main(["ontology", "fetch", "--tag", "v1.0", "--out", str(out), "--url", missing]) == 0
    assert gb.store_node_count(tmp_path / "tiny-v1.0.sqlite", name="efo", version="1.0") == 7


def test_ontology_fetch_refuses_a_known_tag_with_the_wrong_checksum(tmp_path):
    out = tmp_path / "efo-v3.94.0"
    with pytest.raises(SystemExit, match="SHA-256"):
        cli.main(["ontology", "fetch", "--tag", "v3.94.0", "--out", str(out), "--url", TINY.as_uri()])
    assert list(tmp_path.iterdir()) == []      # nothing pinned, no download left behind


def test_ontology_fetch_refuses_a_directory_pinned_to_another_release(tmp_path):
    out = tmp_path / "pinned"
    cli.main(["ontology", "fetch", "--tag", "v1.0", "--out", str(out), "--url", TINY.as_uri()])
    with pytest.raises(SystemExit, match="already pinned to v1.0"):
        cli.main(["ontology", "fetch", "--tag", "v2.0", "--out", str(out), "--url", TINY.as_uri()])
