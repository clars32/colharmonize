"""Write the alias-dictionary task batches (handoff task 10; see PROTOCOL.md).

    ./.venv/bin/python eval/aliases/make_tasks.py

One batch per 100 property-space terms, in eval/aliases/tasks/. Each is
answered by one subagent that reads only its batch and writes only its answer
file. Nothing from either corpus goes into a batch.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize import property_space  # noqa: E402
from colharmonize.ontology import Ontology  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402

BATCH = 100
OUT = ROOT / "eval/aliases/tasks"

INSTRUCTIONS = """\
Each item is an ontology term that a column of sample metadata in a gene
expression study can mean. Write up to 5 aliases for each term: other ways a
researcher would write that same variable as a column header in sample
metadata.

Good aliases:
- common abbreviations and acronyms ("sbp" for systolic blood pressure)
- shorter everyday phrasings ("systolic bp", "visual acuity")
- the plain name of the quantity when the term's label is wordy
  ("intraocular pressure" for "intraocular pressure measurement")

Rules:
- An alias must mean the same variable as the term: not a broader or narrower
  one, and not a related one.
- No values ("male", "high"), units on their own, gene or tool names, or
  dataset-specific codes.
- No alias that only rewords the label trivially (plural, case,
  punctuation). Those are matched already.
- Fewer is better than wrong. If a term has no natural alias, return an empty
  list.

Examples:
- systolic blood pressure -> ["sbp", "systolic bp", "systolic pressure"]
- intraocular pressure measurement -> ["intraocular pressure", "iop"]
- visual acuity measurement -> ["visual acuity", "va"]
"""

SCHEMA = {
    "type": "object",
    "required": ["content_sha256", "answers"],
    "properties": {
        "content_sha256": {"type": "string"},
        "answers": {"type": "array", "items": {
            "type": "object", "required": ["item_id", "aliases"],
            "properties": {"item_id": {"type": "string"},
                           "aliases": {"type": "array", "maxItems": 5, "items": {"type": "string"}}}}},
    },
}


def items() -> list[dict]:
    onto = Ontology.from_dir(Workspace(ROOT / "work/ds-tuning").ontology_dir())
    space = property_space.build(onto)
    syn = onto.usable_terms().set_index("curie").exact_synonyms
    out = []
    for r in space.sort_values("curie").itertuples(index=False):
        syns = syn.get(r.curie)
        out.append({"item_id": r.curie, "label": r.label,
                    "definition": (r.definition or "")[:300],
                    "synonyms": sorted(set(syns)) if syns is not None else []})
    return out


def main() -> None:
    terms = items()
    OUT.mkdir(parents=True, exist_ok=True)
    for n, start in enumerate(range(0, len(terms), BATCH), 1):
        batch_items = terms[start:start + BATCH]
        content = json.dumps({"instructions": INSTRUCTIONS, "items": batch_items}, sort_keys=True)
        batch = {
            "stage": "aliases",
            "instructions": INSTRUCTIONS,
            "items": batch_items,
            "answer_file": f"batch_{n:02}.answer.json",
            "answer_schema": SCHEMA,
            "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        }
        (OUT / f"batch_{n:02}.json").write_text(json.dumps(batch, indent=1) + "\n")
    print(f"{len(terms)} terms in {n} batches in {OUT}")


if __name__ == "__main__":
    main()
