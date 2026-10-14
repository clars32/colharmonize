"""Where a workspace stands, judged by the files that exist, and what to run next.

`colharmonize status` reads file names, task manifests and a few small tables.
It never validates answers and never writes anything, so it is safe to run at
any time, including while subagents are still answering. A stage is done when
its output exists. Answer files are counted, not checked: a stage's apply
command collects and validates them first.

Stages run in the /harmonize skill's order. One that never ran but is followed
by a stage that did (a workspace made before preprocess existed, say) counts as
skipped, so the next step is always after the furthest one reached.
"""
from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field

import pandas as pd

from colharmonize import tasks
from colharmonize.workspace import Workspace

DONE, PARTLY, WAITING, TODO, SKIPPED = "done", "in progress", "waiting for you", "not started", "skipped"

# Judgment stages as the skill runs them: runs, batch size (None: the default), subagent.
JUDGMENT = {
    "repair": ([1], None, "colharmonize:repairer"),
    "annotate": ([1, 2], 12, "colharmonize:annotator"),
    "reconcile": ([1, 2], 6, "colharmonize:reconciler"),
}


@dataclass
class Stage:
    name: str
    state: str = TODO
    detail: str = ""
    next: list[str] = field(default_factory=list)   # commands that move this stage forward
    note: str = ""                                   # what to know before running them
    then: str = ""                                   # what follows them


def _cmd(*parts: str) -> str:
    return " ".join(["colharmonize", *parts])


def _count(describe) -> str:
    try:
        return describe()
    except Exception as e:  # a table the report can't read is still a done stage
        return f"(could not read: {e})"


def _file_stage(name: str, done: bool, describe, command: str) -> Stage:
    if done:
        return Stage(name, DONE, _count(describe))
    return Stage(name, TODO, next=[command])


def _judgment(ws: Workspace, w: str, stage: str, output, describe, apply: str) -> Stage:
    runs, batch_size, agent = JUDGMENT[stage]
    progress, unwritten, pending = [], [], []
    for run in runs:
        d = ws.tasks(stage, run)
        if not (d / "manifest.json").exists():
            unwritten.append(run)
            continue
        c = tasks.status(d)
        progress.append(f"run {run}: {c['answered']}/{c['batches']} batches answered")
        if c["pending"]:
            pending.append(run)
    root = ws.root / "tasks" / stage
    others = sorted(int(p.name[3:]) for p in root.glob("run*")
                    if p.name[3:].isdigit() and int(p.name[3:]) not in runs and (p / "manifest.json").exists())
    if others:
        progress.append("also runs " + ", ".join(map(str, others)))
    if output.exists():
        return Stage(stage, DONE, "; ".join([_count(describe), *progress]))
    s = Stage(stage, TODO if len(unwritten) == len(runs) else PARTLY, "; ".join(progress))
    size = ["--batch-size", str(batch_size)] if batch_size else []
    s.next = [_cmd("tasks", "write", stage, "--workspace", w, "--run", str(r), *size) for r in unwritten]
    s.next += [_cmd("tasks", "status", stage, "--workspace", w, "--run", str(r)) for r in pending]
    if pending:
        s.note = (f"Tasks are written but not all answered, so don't run `tasks write` again for run "
                  f"{', '.join(map(str, pending))}. `tasks status` prints the path of each pending batch; "
                  f"give each path to its own {agent} subagent, never mixing runs.")
        s.then = f"When every batch has an answer: {apply}"
    elif s.state == TODO:
        s.then = (f"Then `colharmonize tasks status {stage}` prints each batch's path; give each path "
                  f"to its own {agent} subagent, never mixing runs.")
    else:
        s.next = [apply]
        s.note = "Every batch has an answer file."
        s.then = (f"Apply validates the answers first. If it reports failed items, re-task them with "
                  f"`colharmonize tasks retry {stage}`.")
    return s


def stages(ws: Workspace, w: str | None = None) -> list[Stage]:
    """Every stage's state, in pipeline order, with the commands that would move it forward.

    `w` is how the workspace is written in those commands (default: its path).
    """
    w = shlex.quote(w or str(ws.root))
    root = ws.root
    settings = ws.settings()
    read = pd.read_parquet

    def flags(*keys: str) -> list[str]:
        out = []
        if "geomend_store" in keys and not settings.get("geomend_store"):
            out += ["--store", "FILE"]
        if "ontology" in keys and not settings.get("ontology"):
            out += ["--ontology", "DIR"]
        return out

    ingest = _file_stage(
        "ingest", ws.columns.exists(),
        lambda: (lambda t: f"{len(t)} columns in {t.study_id.nunique()} studies")(read(ws.columns)),
        _cmd("ingest", "--workspace", w, "SOURCE..."))
    if ingest.state == TODO:
        ingest.then = "SOURCE: SOFT files, tables or GSE accessions."
    preprocess = _file_stage(
        "preprocess", (root / "geomend_evidence" / "units.parquet").exists(),
        lambda: "GEOmend evidence in geomend_evidence/",
        _cmd("preprocess", "--workspace", w, *flags("geomend_store", "ontology")))
    repair = _judgment(
        ws, w, "repair", ws.derived,
        lambda: f"{len(read(ws.derived, columns=['study_id', 'column']).drop_duplicates())} columns recovered",
        _cmd("repair", "apply", "--workspace", w, "--run", "1"))
    candidates = _file_stage(
        "candidates", ws.candidates.exists(),
        lambda: f"terms for {len(read(ws.candidates, columns=['study_id', 'column']).drop_duplicates())} columns",
        _cmd("candidates", "--workspace", w, *flags("ontology")))
    annotations = root / "annotations.parquet"
    annotate = _judgment(
        ws, w, "annotate", annotations,
        lambda: (lambda t: f"{len(t)} columns, {t.variable_id.nunique()} variables before reconciliation")(
            read(annotations, columns=["variable_id"])),
        _cmd("annotate", "apply", "--workspace", w, "--runs", "1", "2"))
    variables = root / "variables.parquet"
    reconcile = _judgment(
        ws, w, "reconcile", variables,
        lambda: (lambda t: f"{len(t)} columns in {t.variable_id.nunique()} variables")(
            read(variables, columns=["variable_id"])),
        _cmd("reconcile", "apply", "--workspace", w, "--runs", "1", "2"))
    scored = root / "scored.parquet"

    def tiers() -> str:
        t = read(scored, columns=["variable_id", "variable_tier"]).drop_duplicates("variable_id")
        counts = t.variable_tier.value_counts()
        return "variables by tier: " + ", ".join(f"{counts.get(k, 0)} {k}" for k in ("pre_accepted", "quick", "manual"))
    score = _file_stage("score", scored.exists(), tiers, _cmd("score", "--workspace", w))

    review = Stage("review")
    page, overlay = root / "review.html", root / "review.json"
    if overlay.exists():
        def decided() -> str:
            n = len(json.loads(overlay.read_text())["decisions"])
            of = f" of {read(scored, columns=['variable_id']).variable_id.nunique()}" if scored.exists() else ""
            return f"decisions for {n}{of} variables applied (review.json)"
        review.state, review.detail = DONE, _count(decided)
    elif page.exists():
        review.state, review.detail = WAITING, "review.html written; no decisions applied yet"
        review.note = (f"Open {page} in a browser, review it starting with the manual tier, and export "
                       f"the decisions. Then:")
        review.next = [_cmd("review", "apply", "--workspace", w, "EXPORT.json")]
    else:
        review.next = [_cmd("review", "page", "--workspace", w)]

    publish = _file_stage(
        "publish", (root / "published" / "variables.tsv").exists(),
        lambda: "published/: " + ", ".join(sorted(p.name for p in (root / "published").iterdir())),
        _cmd("publish", "--workspace", w))

    out = [ingest, preprocess, repair, candidates, annotate, reconcile, score, review, publish]
    last = max((i for i, s in enumerate(out) if s.state != TODO), default=0)
    for s in out[:last]:
        if s.state == TODO:
            s.state, s.next, s.note, s.then = SKIPPED, [], "", ""
    return out


def next_stage(report: list[Stage]) -> Stage | None:
    """The stage to work on: the furthest one reached if unfinished, else the one after it."""
    last = max((i for i, s in enumerate(report) if s.state != TODO), default=-1)
    if last >= 0 and report[last].state != DONE:
        return report[last]
    return report[last + 1] if last + 1 < len(report) else None


def render(ws: Workspace, w: str | None = None) -> str:
    report = stages(ws, w)
    settings = ws.settings()
    lines = [f"workspace   {ws.root}" + ("" if ws.root.exists() else "  (does not exist yet)"),
             f"ontology    {settings.get('ontology', 'not recorded')}",
             f"store       {settings.get('geomend_store', 'not recorded')}", ""]
    width = max(len(s.state) for s in report)
    lines += [f"{s.name:12s}{s.state:{width + 2}s}{s.detail}".rstrip() for s in report]
    nxt = next_stage(report)
    lines.append("")
    if nxt is None:
        lines.append("Every stage is done.")
        return "\n".join(lines)
    lines.append(f"Next: {nxt.name}." + (f" {nxt.note}" if nxt.note else ""))
    lines += [f"  {c}" for c in nxt.next]
    if nxt.then:
        lines.append(nxt.then)
    return "\n".join(lines)
