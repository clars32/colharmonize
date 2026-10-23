"""The command line: one-command ontology setup, settings the workspace remembers, task runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from colharmonize import candidates, cli, preprocess, property_space
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


def test_preprocess_records_the_store_and_later_commands_reuse_it(tmp_path, tiny_dir, monkeypatch):
    ws, store = tmp_path / "ws", tmp_path / "efo.sqlite"
    ws.mkdir()
    store.touch()
    calls = []
    monkeypatch.setattr(preprocess, "run", lambda w, s, onto: calls.append((Path(s), onto.release_tag)) or {})
    cli.main(["preprocess", "--workspace", str(ws), "--store", str(store), "--ontology", str(tiny_dir)])
    settings = json.loads((ws / "workspace.json").read_text())
    assert settings == {"ontology": str(tiny_dir.resolve()), "geomend_store": str(store.resolve())}
    cli.main(["preprocess", "--workspace", str(ws)])
    assert calls == [(store.resolve(), "v1.0")] * 2


class _Loaded(Exception):
    pass


def test_candidates_uses_the_recorded_ontology(tmp_path, tiny_dir, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "workspace.json").write_text(json.dumps({"ontology": str(tiny_dir)}))

    def loaded(path, **kw):
        raise _Loaded(Path(path))
    monkeypatch.setattr(Ontology, "from_dir", loaded)   # stop before retrieval
    with pytest.raises(_Loaded) as got:
        cli.main(["candidates", "--workspace", str(ws)])
    assert got.value.args[0] == tiny_dir


def test_unknown_settings_are_a_clear_error(tmp_path, tiny_dir):
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(SystemExit, match="no pinned ontology directory recorded.*--ontology DIR"):
        cli.main(["candidates", "--workspace", str(ws)])
    with pytest.raises(SystemExit, match="no GEOmend ontology store recorded.*--store FILE"):
        cli.main(["preprocess", "--workspace", str(ws), "--ontology", str(tiny_dir)])
    with pytest.raises(SystemExit, match="no such file"):
        cli.main(["preprocess", "--workspace", str(ws), "--store", str(tmp_path / "typo.sqlite")])


@pytest.mark.parametrize("given, env, expected", [
    (None, None, "home/.cache/colharmonize"),
    (None, "shared", "shared"),
    ("mine", "shared", "mine"),
])
def test_candidates_cache_is_per_user_not_per_directory(tmp_path, tiny_dir, monkeypatch, given, env, expected):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    if env:
        monkeypatch.setenv("COLHARMONIZE_CACHE", str(tmp_path / env))
    else:
        monkeypatch.delenv("COLHARMONIZE_CACHE", raising=False)

    def retriever(onto, space, cache_dir, remote):
        raise _Loaded(cache_dir, remote.path)
    monkeypatch.setattr(property_space, "build", lambda onto: None)
    monkeypatch.setattr(candidates, "Retriever", retriever)   # stop before embedding anything
    argv = ["candidates", "--workspace", str(ws), "--ontology", str(tiny_dir)]
    with pytest.raises(_Loaded) as got:
        cli.main(argv + (["--cache", str(tmp_path / given)] if given else []))
    assert got.value.args == (tmp_path / expected / "embeddings", tmp_path / expected / "remote.json")


@pytest.mark.parametrize("action", ["status", "collect", "retry"])
def test_tasks_on_a_run_with_no_tasks_is_a_clear_error(tmp_path, action):
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(SystemExit) as got:
        cli.main(["tasks", action, "annotate", "--workspace", str(ws), "--run", "3"])
    assert "annotate run 3 has no tasks yet" in str(got.value.code)   # a message, so the exit status is 1


SOFT = Path(__file__).parent / "fixtures" / "soft"


@pytest.mark.parametrize("sources", [["GSE1"], [str(SOFT / "GSE128621_family.soft.gz"), "GSE1"]],
                         ids=["only-uncached", "one-of-two-uncached"])
def test_ingest_that_cannot_read_a_source_fails_and_leaves_nothing(tmp_path, capsys, sources):
    from colharmonize import status
    from colharmonize.workspace import Workspace
    ws = Workspace(tmp_path / "ws")
    with pytest.raises(SystemExit) as got:
        cli.main(["ingest", "--workspace", str(ws.root), *sources])
    assert f"ingest failed for 1 of {len(sources)} sources" in str(got.value.code)
    assert "need --online" in str(got.value.code)
    assert "GSE1: " in capsys.readouterr().err                   # each failure says why
    assert not ws.geomend.exists()                                # so a retry with --online isn't refused
    assert {s.name: s.state for s in status.stages(ws)}["ingest"] == "not started"
