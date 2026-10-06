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
        body["content_sha256"] = hashlib.sha256(_canonical(body).encode()).hexdigest()
        path = directory / f"{name}.json"
        path.write_text(json.dumps(body, indent=1, ensure_ascii=False))
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


@dataclass
class Collected(Generic[A]):
    answers: list[A] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.problems and not self.pending


def collect(directory: str | Path, answer_model: type[A]) -> Collected[A]:
    """Validate every answer file in a run directory.

    A batch is pending if its answer file does not exist yet. An answer is
    rejected as a whole if it echoes the wrong content hash, fails the schema,
    or does not answer exactly the batch's items, because a partially wrong
    file is evidence the subagent misread the task.
    """
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    out: Collected[A] = Collected()
    for entry in manifest["batches"]:
        batch = json.loads((directory / entry["batch_file"]).read_text())
        answer_path = directory / entry["answer_file"]
        if not answer_path.exists():
            out.pending.append(entry["batch_file"])
            continue
        where = entry["answer_file"]
        try:
            raw = json.loads(answer_path.read_text())
        except json.JSONDecodeError as e:
            out.problems.append(f"{where}: not valid JSON ({e})")
            continue
        if not isinstance(raw, dict) or raw.get("content_sha256") != batch["content_sha256"]:
            out.problems.append(f"{where}: content_sha256 does not match {entry['batch_file']}")
            continue
        try:
            answers = [answer_model.model_validate(a) for a in raw.get("answers", [])]
        except ValidationError as e:
            out.problems.append(f"{where}: schema error: {e.errors()[0]['loc']} {e.errors()[0]['msg']}")
            continue
        got = [a.item_id for a in answers]
        expected = set(entry["items"])
        missing, extra = expected - set(got), set(got) - expected
        dupes = {i for i in got if got.count(i) > 1}
        if missing or extra or dupes:
            out.problems.append(f"{where}: missing {sorted(missing)}, unexpected {sorted(extra)}, duplicated {sorted(dupes)}")
            continue
        out.answers.extend(answers)
    return out


def status(directory: str | Path) -> dict[str, int]:
    """Counts of batches with and without answer files."""
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    done = sum((directory / e["answer_file"]).exists() for e in manifest["batches"])
    return {"batches": len(manifest["batches"]), "answered": done, "pending": len(manifest["batches"]) - done}
