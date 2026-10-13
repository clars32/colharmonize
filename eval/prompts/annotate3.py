"""annotate-3: the qualifier instructions recommended in decisions log 14.4.

    ./.venv/bin/python eval/prompts/annotate3.py WORKSPACE RUN [RUN ...]

Writes annotate task batches with the annotate-3 instructions into a
workspace, for measurement before the prompt is adopted (PROTOCOL.md). The
text is annotate-2 with four changes, each made by exact replacement so the
diff is the whole change. Every example comes from neither corpus.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize import annotate, tasks  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402

PROMPT_VERSION = "annotate-3"
CHANGES = [
    # 1 + 2 + 3: qualifiers come from the column itself, and never restate the term,
    # name the study's disease, or describe the values (14.4).
    ("""   term. Add only qualifiers the column actually carries.
""",
     """   term. Add only qualifiers the column itself carries: read them from its
   name and its values. The study summary helps you understand a column, but
   it is not a source of qualifiers. Never use a qualifier to restate the
   primary term, to name the study's disease, or to describe the values.
"""),
    # 4: an object_class example that is neither a gene nor a lesion (14.4).
    ("""     the gene in "TP53 expression", the lesion in "BRAF V600E status"
""",
     """     the gene in "TP53 expression", the lesion in "BRAF V600E status", the
     cell type in "eosinophil percentage"
"""),
    # 5: prefer a term for the whole concept over a general term plus qualifiers (14.4).
    ("""   Use a candidate when one fits, otherwise write short text.
""",
     """   Use a candidate when one fits, otherwise write short text.
   When a term exists for the whole concept, make it the primary term rather
   than a general term with qualifiers: a waist circumference column takes
   "waist circumference", not "circumference" with object_class "waist".
"""),
]


def instructions() -> str:
    if annotate.PROMPT_VERSION == PROMPT_VERSION:   # adopted 2026-10-12 (decisions log 15.10)
        return annotate.INSTRUCTIONS
    text = annotate.INSTRUCTIONS
    for old, new in CHANGES:
        if text.count(old) != 1:
            raise SystemExit(f"annotate-2 text changed; cannot apply: {old[:60]!r}")
        text = text.replace(old, new)
    return text


def main(workspace: str, *runs: str) -> None:
    ws = Workspace(workspace)
    for run in map(int, runs):
        items = annotate.prepare(ws, None, run)
        paths = tasks.write_batches(ws.tasks(annotate.STAGE, run), stage=annotate.STAGE, run=run,
                                    prompt_version=PROMPT_VERSION, instructions=instructions(), items=items,
                                    answer_model=annotate.ANSWER_MODEL, batch_size=12, seed=1000 * run + 1)
        print(f"run {run}: {len(items)} items in {len(paths)} batches ({PROMPT_VERSION})")


if __name__ == "__main__":
    main(*sys.argv[1:])
