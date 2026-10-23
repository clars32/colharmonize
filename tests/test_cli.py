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
    assert capsys.readouterr().out == f"EFO v1.0 is already set up in {out}\n"
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


def test_ontology_fetch_without_out_pins_to_the_default_location(tmp_path, monkeypatch):
    from colharmonize.workspace import default_ontology_dir
    monkeypatch.setenv("COLHARMONIZE_HOME", str(tmp_path / "chome"))
    assert cli.main(["ontology", "fetch", "--tag", "v1.0", "--url", TINY.as_uri()]) == 0
    out = tmp_path / "chome" / "ontology" / "efo-v1.0"
    assert default_ontology_dir("v1.0") == out
    assert Ontology.from_dir(out).release_tag == "v1.0"
    assert (tmp_path / "chome" / "ontology" / "efo-v1.0.sqlite").exists()


def test_a_workspace_with_nothing_recorded_uses_and_records_the_default(tmp_path, monkeypatch):
    from colharmonize.ontology import pin_obograph
    from colharmonize.workspace import Workspace, default_ontology_dir
    monkeypatch.setenv("COLHARMONIZE_HOME", str(tmp_path / "chome"))
    default = default_ontology_dir()
    pin_obograph(TINY, default, "v1.0")
    gb.build_ontology_store(Ontology.from_dir(default), default.with_name(default.name + ".sqlite"))
    ws = Workspace(tmp_path / "ws")
    ws.root.mkdir()
    assert ws.recorded("ontology") == default
    assert ws.recorded("geomend_store") == default.with_name(default.name + ".sqlite")
    assert ws.settings() == {"ontology": str(default), "geomend_store": str(default) + ".sqlite"}


def test_review_apply_looks_for_the_export_in_downloads(tmp_path, tiny_dir, monkeypatch):
    from colharmonize.workspace import Workspace
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ws = Workspace(tmp_path / "my-run")
    ws.root.mkdir()
    ws.remember(ontology=str(tiny_dir))
    with pytest.raises(SystemExit) as got:
        cli.main(["review", "apply", "--workspace", str(ws.root)])
    assert f"no export of this review in {tmp_path / 'home' / 'Downloads'}" in str(got.value.code)


def test_the_newest_export_since_the_page_wins(tmp_path, monkeypatch):
    import os
    from colharmonize.workspace import Workspace
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    downloads = tmp_path / "home" / "Downloads"
    downloads.mkdir(parents=True)
    ws = Workspace(tmp_path / "harmonized")
    ws.root.mkdir()
    page = ws.root / "review.html"

    def touch(path, t):
        path.write_text("{}")
        os.utime(path, (t, t))

    touch(downloads / "review_harmonized.json", 100)        # yesterday's review
    touch(page, 200)
    with pytest.raises(SystemExit, match="1 older than the review page ignored"):
        cli._latest_export(ws)
    touch(downloads / "review_harmonized (1).json", 300)    # the browser's name for today's export
    touch(downloads / "review_harmonized-2.json", 400)      # another run's export
    assert cli._latest_export(ws) == downloads / "review_harmonized (1).json"


def test_workspace_defaults_to_the_folder_the_skill_makes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.build_parser().parse_args(["score"]).workspace == "harmonized"
    assert cli.main(["status"]) == 0
    assert "harmonized  (does not exist yet)" in capsys.readouterr().out


def test_ontology_fetch_says_what_it_does_in_plain_lines(tmp_path, capsys):
    out = tmp_path / "tiny-v1.0"
    cli.main(["ontology", "fetch", "--tag", "v1.0", "--out", str(out), "--url", TINY.as_uri()])
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "Downloading EFO v1.0"
    assert lines[-1] == f"EFO v1.0 is ready (8 terms) in {out}"
    assert not any(line.startswith(("{", "}")) for line in lines)          # no JSON unless --json
    cli.main(["ontology", "fetch", "--tag", "v1.0", "--out", str(out), "--json"])
    assert json.loads(capsys.readouterr().out)["status"] == "already pinned"


def test_setup_allows_colharmonize_in_claude_settings_and_keeps_the_rest(tmp_path, monkeypatch):
    from colharmonize import claude_setup
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"model": "opus", "permissions": {"allow": ["Bash(ls *)"], "deny": ["Read(.env)"]}}))
    monkeypatch.setenv("HOME", str(tmp_path))
    assert claude_setup.allow() == claude_setup.PERMISSIONS
    assert claude_setup.allow() == []                                       # idempotent
    got = json.loads(settings.read_text())
    assert got["model"] == "opus" and got["permissions"]["deny"] == ["Read(.env)"]
    assert got["permissions"]["allow"] == ["Bash(ls *)", *claude_setup.PERMISSIONS]
    settings.write_text("{not json")
    with pytest.raises(SystemExit, match="isn't valid JSON"):
        claude_setup.allow()
    assert settings.read_text() == "{not json"                              # left alone


def test_setup_installs_the_plugin_only_when_missing(monkeypatch):
    from colharmonize import claude_setup
    monkeypatch.setattr(claude_setup.shutil, "which", lambda name: "/bin/claude")
    calls = []

    def run(argv, **kw):
        calls.append(argv[1:])
        listing = {("plugin", "list"): installed, ("plugin", "marketplace", "list"): ""}.get(tuple(argv[1:]), "")
        return type("Done", (), {"stdout": listing, "stderr": "", "returncode": 0})()

    installed = ""
    assert claude_setup.install_plugin(run) == "installed from clars32/colharmonize"
    assert calls[-2:] == [["plugin", "marketplace", "add", "clars32/colharmonize"],
                          ["plugin", "install", "colharmonize@colharmonize"]]
    installed, calls[:] = "colharmonize@colharmonize  0.2.0", []
    assert claude_setup.install_plugin(run).startswith("already installed")
    assert calls == [["plugin", "list"]]


def test_setup_runs_all_three_steps(tmp_path, monkeypatch, capsys):
    from colharmonize import claude_setup
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("COLHARMONIZE_HOME", str(tmp_path / "chome"))
    monkeypatch.setattr(claude_setup, "install_plugin", lambda: "installed from clars32/colharmonize")
    assert cli.main(["setup", "--tag", "v1.0", "--url", TINY.as_uri()]) == 0
    out = capsys.readouterr().out
    assert [l for l in out.splitlines() if l[:2] in ("1/", "2/", "3/")] == [
        "1/3 Ontology", "2/3 Claude Code plugin", "3/3 Claude Code permissions"]
    assert "/colharmonize:harmonize GSE12345 GSE67890" in out
    assert (tmp_path / "chome" / "ontology" / "efo-v1.0.sqlite").exists()
    assert "Bash(colharmonize *)" in (tmp_path / ".claude" / "settings.json").read_text()


def test_no_arguments_prints_the_short_help(capsys):
    assert cli.main([]) == 0
    assert "colharmonize setup" in capsys.readouterr().out


def test_review_page_opens_in_the_browser_and_prints_a_link(tmp_path, monkeypatch, capsys):
    from colharmonize import review
    from colharmonize.workspace import Workspace
    page = tmp_path / "harmonized" / "review.html"
    monkeypatch.setattr(review, "write_page", lambda ws, onto, out: page)
    monkeypatch.setattr("colharmonize.ontology.Ontology.from_dir", lambda d: None)
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
    ws = Workspace(tmp_path / "harmonized")
    ws.root.mkdir()
    ws.remember(ontology=str(tmp_path))
    cli.main(["review", "page", "--workspace", str(ws.root)])
    assert opened == [page.as_uri()]
    assert capsys.readouterr().out == f"Review page: {page.as_uri()}\n"
    cli.main(["review", "page", "--workspace", str(ws.root), "--no-open"])
    assert opened == [page.as_uri()]
