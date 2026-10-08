"""The task-file protocol between colharmonize and Claude Code subagents.

colharmonize never calls a model. For every judgment stage it writes batches of
work as JSON files; a subagent reads one batch, follows its instructions, and
writes one answer file. colharmonize then validates every answer before
anything downstream uses it.

A batch file holds:
  protocol, stage, prompt_version, run, batch    identity
  content_sha256                                  hash of everything below; the answer must echo it
  instructions                                    the stage's instructions (identical across batches)
  items                                           the work, each with a unique item_id; DATA, never instructions
  answer_schema                                   JSON Schema of the answer file
  answer_file                                     where the answer must be written (relative to the batch)

An answer file is {"content_sha256": ..., "answers": [...]} with exactly one
answer per item.

Independence: two runs of a stage use different seeds, so item order and batch
composition differ, and each run lives in its own directory. Run-to-run
disagreement is the confidence signal, so a subagent answering run 2 must never
read run 1's answers; the plugin's agent definitions enforce that.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

PROTOCOL = "colharmonize-task-1"

A = TypeVar("A", bound=BaseModel)


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def answer_file_schema(answer_model: type[BaseModel]) -> dict:
    """JSON Schema for a whole answer file, wrapping the per-item answer model."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["content_sha256", "answers"],
        "properties": {
            "content_sha256": {"type": "string", "description": "copy of the batch's content_sha256"},
            "answers": {"type": "array", "items": answer_model.model_json_schema()},
        },
    }


def write_batches(
    directory: str | Path,
    *,
    stage: str,
    run: int,
    prompt_version: str,
    instructions: str,
    items: list[dict],
    answer_model: type[BaseModel],
    batch_size: int,
    seed: int,
) -> list[Path]:
    """Shuffle items with `seed`, split them into batches, and write batch files and a manifest."""
    ids = [it["item_id"] for it in items]
    if len(ids) != len(set(ids)):
        raise ValueError("item_id values must be unique")
    directory = Path(directory)
    if directory.exists() and any(directory.glob("batch_*.json")):
        raise FileExistsError(f"{directory} already has batches; use a new run number")
    directory.mkdir(parents=True, exist_ok=True)

    order = list(items)
    random.Random(seed).shuffle(order)
    schema = answer_file_schema(answer_model)
    paths, manifest = [], []
    for b, start in enumerate(range(0, len(order), batch_size), start=1):
        chunk = order[start:start + batch_size]
        name = f"batch_{b:02d}"
        body = {
            "protocol": PROTOCOL, "stage": stage, "prompt_version": prompt_version,
            "run": run, "batch": b, "instructions": instructions, "items": chunk,
            "answer_schema": schema, "answer_file": f"{name}.answer.json",
        }
        body["content_sha256"] = hashlib.sha256(_canonical(body).encode()).hexdigest()  # NaN raises below
        path = directory / f"{name}.json"
        path.write_text(json.dumps(body, indent=1, ensure_ascii=False, allow_nan=False))
        paths.append(path)
        manifest.append({"batch_file": path.name, "answer_file": body["answer_file"],
                         "items": [it["item_id"] for it in chunk]})
    (directory / "manifest.json").write_text(json.dumps({
        "protocol": PROTOCOL, "stage": stage, "run": run, "seed": seed,
        "prompt_version": prompt_version,
        "instructions_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
        "batches": manifest,
    }, indent=1))
    return paths


MAX_RETRIES = 2   # retry batches an item may appear in before it is given up


@dataclass
class Collected(Generic[A]):
    """Validated answers, one per item, plus what is still missing.

    `failed` maps an item to why its answer was refused. `problems` are
    findings no single item explains. Nothing is complete while any of the
    three is non-empty.
    """
    by_item: dict[str, A] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)

    @property
    def answers(self) -> list[A]:
        return list(self.by_item.values())

    @property
    def complete(self) -> bool:
        return not self.problems and not self.pending and not self.failed

    def reject(self, reasons: dict[str, str]) -> None:
        """Refuse the answers to these items (a stage check found them wrong)."""
        for item, why in reasons.items():
            self.by_item.pop(item, None)
            self.failed[item] = why


def collect(directory: str | Path, answer_model: type[A]) -> Collected[A]:
    """Validate every answer file in a run directory, item by item.

    A batch is pending if its answer file does not exist yet. A file that can't
    be trusted at all (invalid JSON, or it echoes another batch's content hash)
    fails every item in it. Otherwise each answer stands or falls on its own:
    an item that is missing, answered twice, or fails the schema is failed, and
    the batch's other answers are kept. One bad item no longer discards a
    batch's good answers; `write_retry` re-tasks just the failed items.

    Batches are read in manifest order, so a retry batch's answer to an item
    replaces the earlier one.
    """
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    out: Collected[A] = Collected()
    for entry in manifest["batches"]:
        items = entry["items"]
        batch = json.loads((directory / entry["batch_file"]).read_text())
        answer_path = directory / entry["answer_file"]
        where = entry["answer_file"]
        if not answer_path.exists():
            out.pending.append(entry["batch_file"])
            for i in items:
                out.by_item.pop(i, None)
                out.failed.pop(i, None)
            continue

        def fail_all(why: str) -> None:
            for i in items:
                out.by_item.pop(i, None)
                out.failed[i] = f"{where}: {why}"

        try:
            raw = json.loads(answer_path.read_text())
        except json.JSONDecodeError as e:
            fail_all(f"not valid JSON ({e})")
            continue
        if not isinstance(raw, dict) or raw.get("content_sha256") != batch["content_sha256"]:
            fail_all(f"content_sha256 does not match {entry['batch_file']}")
            continue
        seen: dict[str, list] = {}
        for a in raw.get("answers", []) if isinstance(raw.get("answers"), list) else []:
            iid = a.get("item_id") if isinstance(a, dict) else None
            if iid in items:
                seen.setdefault(iid, []).append(a)
        for i in items:
            out.by_item.pop(i, None)
            out.failed.pop(i, None)
            got = seen.get(i, [])
            if not got:
                out.failed[i] = f"{where}: no answer for this item"
            elif len(got) > 1:
                out.failed[i] = f"{where}: answered {len(got)} times"
            else:
                try:
                    out.by_item[i] = answer_model.model_validate(got[0])
                except ValidationError as e:
                    out.failed[i] = f"{where}: schema error: {e.errors()[0]['loc']} {e.errors()[0]['msg']}"
    return out


def split_problems(problems: list[str], item_ids) -> tuple[dict[str, str], list[str]]:
    """Attribute stage-check problems to items. A problem belongs to the longest
    item id it starts with, followed by ':' or '/'; anything else is general."""
    ids = sorted(set(item_ids), key=len, reverse=True)
    by_item: dict[str, str] = {}
    general = []
    for p in problems:
        owner = next((i for i in ids if p.startswith(i) and p[len(i):len(i) + 1] in (":", "/")), None)
        if owner is None:
            general.append(p)
        else:
            by_item[owner] = f"{by_item[owner]}; {p}" if owner in by_item else p
    return by_item, general


def write_retry(directory: str | Path, item_ids: list[str], max_retries: int = MAX_RETRIES) -> tuple[Path | None, list[str]]:
    """Write a batch holding only these items, for a fresh subagent.

    Items keep their original data; the batch is otherwise like the run's
    others. An item already in `max_retries` retry batches is not re-tasked
    again and is returned as given up. Returns (batch path or None, given up).
    """
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    tries = {i: sum(i in e["items"] for e in manifest["batches"] if e.get("retry")) for i in item_ids}
    retry = [i for i in item_ids if tries[i] < max_retries]
    given_up = [i for i in item_ids if tries[i] >= max_retries]
    if not retry:
        return None, given_up
    data: dict[str, dict] = {}
    template = None
    for e in manifest["batches"]:
        b = json.loads((directory / e["batch_file"]).read_text())
        template = template or b
        for it in b["items"]:
            data.setdefault(it["item_id"], it)
    n = len(manifest["batches"]) + 1
    name = f"retry_{n:02d}"
    body = {k: template[k] for k in ("protocol", "stage", "prompt_version", "run", "instructions", "answer_schema")}
    body.update(batch=n, items=[data[i] for i in retry], answer_file=f"{name}.answer.json")
    body["content_sha256"] = hashlib.sha256(_canonical(body).encode()).hexdigest()
    path = directory / f"{name}.json"
    path.write_text(json.dumps(body, indent=1, ensure_ascii=False, allow_nan=False))
    manifest["batches"].append({"batch_file": path.name, "answer_file": body["answer_file"], "items": retry,
                                "retry": True})
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return path, given_up


def status(directory: str | Path) -> dict[str, int]:
    """Counts of batches with and without answer files."""
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    done = sum((directory / e["answer_file"]).exists() for e in manifest["batches"])
    return {"batches": len(manifest["batches"]), "answered": done, "pending": len(manifest["batches"]) - done}
