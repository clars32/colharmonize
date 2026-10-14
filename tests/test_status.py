"""`colharmonize status`: stage states from the files that exist, and the next command."""
from __future__ import annotations

import json

import pandas as pd

from colharmonize import cli, status
from colharmonize.workspace import Workspace


def _table(path, **columns) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns).to_parquet(path, index=False)


def _run(ws: Workspace, stage: str, run: int, batches: int, answered: int) -> None:
    d = ws.tasks(stage, run)
    d.mkdir(parents=True)
    entries = [{"batch_file": f"batch_{b:02d}.json", "answer_file": f"batch_{b:02d}.answer.json", "items": [f"i{b}"]}
               for b in range(1, batches + 1)]
    (d / "manifest.json").write_text(json.dumps({"batches": entries}))
    for e in entries[:answered]:
        (d / e["answer_file"]).write_text("{}")


def _through_candidates(tmp_path) -> Workspace:
    ws = Workspace(tmp_path / "ws")
    cols = {"study_id": ["GSE1", "GSE2"], "column": ["sex", "gender"]}
    _table(ws.columns, **cols)
    _table(ws.root / "geomend_evidence" / "units.parquet", **cols)
    _run(ws, "repair", 1, batches=1, answered=1)
    _table(ws.derived, **cols)
    _table(ws.candidates, **cols)
    ws.remember(ontology="/pinned/efo", geomend_store="/pinned/efo.sqlite")
    return ws


def _states(ws) -> dict[str, str]:
    return {s.name: s.state for s in status.stages(ws)}


def test_a_new_workspace_starts_with_ingest(tmp_path, capsys):
    assert cli.main(["status", "--workspace", str(tmp_path / "new")]) == 0
    out = capsys.readouterr().out
    assert "does not exist yet" in out
    assert f"Next: ingest.\n  colharmonize ingest --workspace {tmp_path / 'new'} SOURCE..." in out
    assert not (tmp_path / "new").exists()


def test_unanswered_tasks_say_tasks_status_not_tasks_write(tmp_path):
    ws = _through_candidates(tmp_path)
    _run(ws, "annotate", 1, batches=3, answered=1)
    _run(ws, "annotate", 2, batches=3, answered=3)
    report = status.stages(ws, "ws")
    assert {s.name: s.state for s in report} == {
        "ingest": "done", "preprocess": "done", "repair": "done", "candidates": "done", "annotate": "in progress",
        "reconcile": "not started", "score": "not started", "review": "not started", "publish": "not started"}
    nxt = status.next_stage(report)
    assert nxt.name == "annotate"
    assert nxt.next == ["colharmonize tasks status annotate --workspace ws --run 1"]
    assert "don't run `tasks write` again for run 1" in nxt.note
    assert "colharmonize annotate apply --workspace ws --runs 1 2" in nxt.then


def test_unwritten_runs_are_written_and_answered_runs_applied(tmp_path):
    ws = _through_candidates(tmp_path)
    nxt = status.next_stage(status.stages(ws, "ws"))
    assert nxt.name == "annotate" and nxt.state == "not started"
    assert nxt.next == [f"colharmonize tasks write annotate --workspace ws --run {r} --batch-size 12" for r in (1, 2)]
    _run(ws, "annotate", 1, batches=2, answered=2)
    _run(ws, "annotate", 2, batches=2, answered=2)
    nxt = status.next_stage(status.stages(ws, "ws"))
    assert nxt.next == ["colharmonize annotate apply --workspace ws --runs 1 2"]
    _table(ws.root / "annotations.parquet", variable_id=["v1", "v1"])
    nxt = status.next_stage(status.stages(ws, "ws"))
    assert nxt.name == "reconcile" and nxt.next[0].endswith("--run 1 --batch-size 6")


def test_a_stage_never_run_before_a_later_one_is_skipped(tmp_path):
    ws = _through_candidates(tmp_path)
    (ws.root / "geomend_evidence" / "units.parquet").unlink()
    assert _states(ws)["preprocess"] == "skipped"
    ws.settings_file.unlink()
    ws.candidates.unlink()
    nxt = status.next_stage(status.stages(ws, "ws"))
    assert nxt.name == "candidates"
    assert nxt.next == ["colharmonize candidates --workspace ws --ontology DIR"]   # nothing recorded to fall back on


def test_review_waits_for_a_person_then_publish(tmp_path):
    ws = _through_candidates(tmp_path)
    for name in ("annotations", "variables"):
        _table(ws.root / f"{name}.parquet", variable_id=["v1", "v2"])
    _table(ws.root / "scored.parquet", variable_id=["v1", "v2"], variable_tier=["manual", "quick"])
    (ws.root / "review.html").write_text("<html></html>")
    nxt = status.next_stage(status.stages(ws, "ws"))
    assert (nxt.name, nxt.state) == ("review", "waiting for you")
    assert nxt.next == ["colharmonize review apply --workspace ws EXPORT.json"]
    (ws.root / "review.json").write_text(json.dumps({"decisions": {"v1": {}}}))
    report = status.stages(ws, "ws")
    assert report[-2].detail == "decisions for 1 of 2 variables applied (review.json)"
    assert status.next_stage(report).next == ["colharmonize publish --workspace ws"]


def test_status_writes_nothing(tmp_path, capsys):
    ws = _through_candidates(tmp_path)
    _run(ws, "annotate", 1, batches=2, answered=1)
    before = {p: p.stat().st_mtime_ns for p in ws.root.rglob("*")}
    cli.main(["status", "--workspace", str(ws.root)])
    assert {p: p.stat().st_mtime_ns for p in ws.root.rglob("*")} == before
    assert "Next: annotate." in capsys.readouterr().out
