"""Validate alias answers and build the dictionary (handoff task 10; PROTOCOL.md).

    ./.venv/bin/python eval/aliases/validate.py

A batch fails as a whole if its hash differs or its answers don't cover its
items exactly once; failed batches are listed for re-tasking and contribute
nothing. Answers are never edited. Aliases in passing batches then go through
the protocol's rules, in order. Writes eval/aliases/aliases.json (curie ->
aliases) and eval/aliases/out/validation.md.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize.text import loose  # noqa: E402

TASKS = ROOT / "eval/aliases/tasks"
MAX_ALIASES, MIN_LEN, MAX_LEN = 5, 2, 60


def check_batch(path: Path) -> tuple[list[dict], dict | None, str | None]:
    """(items, answers by id, failure reason)."""
    batch = json.loads(path.read_text())
    answer_path = path.parent / batch["answer_file"]
    if not answer_path.exists():
        return batch["items"], None, "no answer file"
    try:
        answer = json.loads(answer_path.read_text())
    except json.JSONDecodeError as error:
        return batch["items"], None, f"invalid JSON: {error}"
    if answer.get("content_sha256") != batch["content_sha256"]:
        return batch["items"], None, "content_sha256 differs"
    ids = [a.get("item_id") for a in answer.get("answers", [])]
    expected = {item["item_id"] for item in batch["items"]}
    counts = Counter(ids)
    missing, extra = expected - set(ids), set(ids) - expected
    duplicated = [i for i, n in counts.items() if n > 1]
    if missing or extra or duplicated:
        return batch["items"], None, (f"{len(missing)} items unanswered, {len(extra)} unknown ids, "
                                      f"{len(duplicated)} answered twice")
    bad = [a["item_id"] for a in answer["answers"]
           if not isinstance(a.get("aliases"), list) or not all(isinstance(s, str) for s in a["aliases"])]
    if bad:
        return batch["items"], None, f"{len(bad)} answers without a list of strings"
    return batch["items"], {a["item_id"]: a["aliases"] for a in answer["answers"]}, None


def main() -> None:
    batches = sorted(TASKS.glob("batch_??.json"))
    failures: dict[str, str] = {}
    items: dict[str, dict] = {}
    proposed: dict[str, list[str]] = {}
    for path in batches:
        batch_items, answers, reason = check_batch(path)
        for item in batch_items:
            items[item["item_id"]] = item
        if reason:
            failures[path.name] = reason
        else:
            proposed.update(answers)

    # Every label and exact synonym in the space, for the collision rule.
    owners: dict[str, set[str]] = defaultdict(set)
    for curie, item in items.items():
        for s in [item["label"], *item["synonyms"]]:
            owners[loose(s)].add(curie)
    dropped = Counter()
    candidates: dict[str, list[str]] = {}
    for curie, aliases in proposed.items():
        kept = []
        for alias in aliases:
            text = alias.strip()
            if len(kept) >= MAX_ALIASES:
                dropped["over the 5-alias limit"] += 1
            elif not MIN_LEN <= len(text) <= MAX_LEN:
                dropped["length outside 2-60"] += 1
            elif curie in owners.get(loose(text), set()):
                dropped["same as the term's label or synonym"] += 1
            elif owners.get(loose(text)):
                dropped["another term's label or synonym"] += 1
            elif loose(text) in {loose(k) for k in kept}:
                dropped["repeated within the term"] += 1
            else:
                kept.append(text)
        candidates[curie] = kept
    claimed: dict[str, set[str]] = defaultdict(set)
    for curie, aliases in candidates.items():
        for alias in aliases:
            claimed[loose(alias)].add(curie)
    final: dict[str, list[str]] = {}
    for curie, aliases in candidates.items():
        keep = [a for a in aliases if len(claimed[loose(a)]) == 1]
        dropped["proposed for more than one term"] += len(aliases) - len(keep)
        if keep:
            final[curie] = keep

    n_proposed = sum(len(v) for v in proposed.values())
    n_kept = sum(len(v) for v in final.values())
    (ROOT / "eval/aliases/aliases.json").write_text(json.dumps(dict(sorted(final.items())), indent=1) + "\n")
    lines = ["# Alias dictionary: validation", "",
             f"- batches: {len(batches)}, passing {len(batches) - len(failures)}",
             f"- terms answered: {len(proposed)} of {len(items)}",
             f"- aliases proposed: {n_proposed}; kept: {n_kept}, for {len(final)} terms", "",
             "Dropped, by the first rule each alias failed:", ""]
    lines += [f"- {rule}: {n}" for rule, n in dropped.most_common()] or ["- none"]
    if failures:
        lines += ["", "Failed batches (re-task; their answers are not used):", ""]
        lines += [f"- {name}: {reason}" for name, reason in failures.items()]
    out = ROOT / "eval/aliases/out"
    out.mkdir(exist_ok=True)
    (out / "validation.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
