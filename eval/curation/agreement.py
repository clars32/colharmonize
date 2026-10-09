"""Score an independent annotator's filled curation sheet against the gold.

    ./.venv/bin/python eval/curation/agreement.py FILLED.xlsx [OUT.md]

Handoff task 6. Three comparisons on the same columns:
  person vs gold      how far the Claude-drafted, owner-reviewed gold is from
                      an independent human reading
  pipeline vs gold    the sealed final output, restricted to these columns
  pipeline vs person  the same output, scored with the person as reference

If the pipeline scores much higher against the gold than against the person,
the gold shares the pipeline's conventions, and the sealed numbers measure
agreement with Claude as much as correctness.
"""
from __future__ import annotations

import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize.evaluate import _clean, load_gold, score  # noqa: E402
from colharmonize.normalise import normalise_key  # noqa: E402
from colharmonize.ontology import Ontology  # noqa: E402

PREDICATES = {"exact", "broad", "indicator", "none"}
QUALIFIER_SLOTS = ["subject", "object_class", "event_time_anchor", "method"]
_CURIE = re.compile(r"^[A-Za-z]+[:_]\d+$")


def read_sheet(path: str | Path) -> pd.DataFrame:
    ws = load_workbook(path, data_only=True)["Columns"]
    rows = list(ws.iter_rows(values_only=True))
    head = [str(h) for h in rows[0]]
    df = pd.DataFrame([["" if v is None else str(v).strip() for v in r] for r in rows[1:]], columns=head)
    return df[(df["id"] != "EXAMPLE") & (df["id"] != "")].reset_index(drop=True)


def resolve_term(text: str, onto: Ontology, by_label: dict[str, str]) -> tuple[str, str]:
    """(CURIE, problem). Accepts a CURIE, an IRI or an exact label."""
    if not text:
        return "", ""
    if _CURIE.match(text) or text.startswith("http"):
        v = onto.validate(text)
        return (v.curie, "") if v.valid else (v.curie, f"{text}: {v.reason}")
    curie = by_label.get(normalise_key(text))
    return (curie, "") if curie else ("", f"{text}: no term with this exact label in EFO v3.94.0")


def person_predictions(sheet: pd.DataFrame, onto: Ontology) -> tuple[pd.DataFrame, list[str]]:
    usable = onto.usable_terms()
    by_label = {normalise_key(lab): c for c, lab in zip(usable.curie, usable.label)}
    rows, problems = [], []
    for r in sheet.itertuples(index=False):
        rd = r._asdict() if hasattr(r, "_asdict") else dict(zip(sheet.columns, r))
        rid = rd["id"]
        pred = rd["predicate"].casefold()
        if not rd["variable"]:
            problems.append(f"{rid}: no variable name")
        if pred not in PREDICATES:
            problems.append(f"{rid}: predicate {rd['predicate']!r} is not exact/broad/indicator/none")
        curie, problem = resolve_term(rd["primary_term"], onto, by_label)
        if problem:
            problems.append(f"{rid}: primary term {problem}")
        if pred in {"exact", "broad", "indicator"} and not rd["primary_term"]:
            problems.append(f"{rid}: predicate {pred} needs a primary term")
        quals = []
        for slot in QUALIFIER_SLOTS + ["unit"]:
            v = rd[slot]
            if not v:
                continue
            if _CURIE.match(v):
                c, problem = resolve_term(v, onto, by_label)
                if problem:
                    problems.append(f"{rid}: {slot} {problem}")
                quals.append(f"{slot}={c or v}")
            else:
                quals.append(f'{slot}="{v}"')
        rows.append({"accession": rd["series"], "raw_key": rd["column"],
                     "variable_id": "person:" + normalise_key(rd["variable"]) if rd["variable"] else f"person:__blank__:{rid}",
                     "predicate": pred, "primary_curie": curie,
                     "qualifiers": "; ".join(q for q in quals if not q.startswith("unit=")),
                     "unit": next((q.split("=", 1)[1].strip('"') for q in quals if q.startswith("unit=")), ""),
                     "assumed_convention": rd["assumed_convention"], "note": rd["note"]})
    return pd.DataFrame(rows), problems


def as_reference(pred: pd.DataFrame) -> pd.DataFrame:
    """A prediction table in the gold layout, so it can be the reference."""
    ref = pred[["accession", "raw_key", "variable_id", "predicate", "primary_curie", "qualifiers", "unit"]].copy()
    ref["source"] = "characteristic"
    return ref


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def pct(x: float) -> str:
    return "—" if x != x else f"{100 * x:.1f}%"


def main(filled: str, out: str | None = None) -> None:
    settings = json.loads((ROOT / "work/sealed/workspace.json").read_text())
    onto = Ontology.from_dir(settings["ontology"])
    labels = onto.label_map()
    sheet = read_sheet(filled)
    sheet.columns = [c.replace(" ", "_") for c in sheet.columns]
    person, problems = person_predictions(sheet, onto)
    series = sorted(set(person.accession))

    gold = load_gold(ROOT / "eval/gold/generalization_columns.tsv", ROOT / "eval/gold/generalization_variables.tsv")
    gold = gold[gold.accession.isin(series)].reset_index(drop=True)
    missing = set(zip(gold.accession, gold.raw_key)) - set(zip(person.accession, person.raw_key))
    if missing:
        problems.append(f"sheet lacks gold columns: {sorted(missing)}")

    pipe = pd.read_csv(ROOT / "work/sealed/predictions_scored.tsv", sep="\t", dtype=str, keep_default_na=False)
    km = json.loads((ROOT / "work/sealed/key_map.json").read_text())
    back = {(k.split("\t")[0], v): k.split("\t")[1] for k, v in km.items()}
    pipe["raw_key"] = [back.get((a, k), k) for a, k in zip(pipe.accession, pipe.raw_key)]
    pipe = pipe[pipe.accession.isin(series)]

    ref_person = as_reference(person)
    comparisons = {
        "person vs gold": score(gold, person, labels),
        "pipeline vs gold": score(gold, pipe, labels),
        "pipeline vs person": score(ref_person, pipe, labels),
    }
    lines = [f"# Independent curation: agreement on {len(person)} columns from {len(series)} sealed series", "",
             f"Sheet: `{filled}`", ""]
    if problems:
        lines += ["## Problems in the sheet (fix and rerun before reading the scores)", ""] + [f"- {p}" for p in problems] + [""]
    lines += ["## Scores", "", "The reference is the second name in each row.", "",
              "| comparison | pooling precision | recall | F1 | primary term | predicate | term and predicate | qualifiers P / R |",
              "|---|---|---|---|---|---|---|---|"]
    for name, s in comparisons.items():
        a = s.annotation
        lines.append(f"| {name} | {pct(s.pooling['precision'])} | {pct(s.pooling['recall'])} | {pct(s.pooling['f1'])} "
                     f"| {pct(a['primary_accuracy'])} | {pct(a['predicate_accuracy'])} | {pct(a['annotation_accuracy'])} "
                     f"| {pct(a['qualifier_precision'])} / {pct(a['qualifier_recall'])} |")

    pg = dict(zip(zip(gold.accession, gold.raw_key), gold.predicate))
    pp = dict(zip(zip(person.accession, person.raw_key), person.predicate))
    common = [k for k in pg if k in pp]
    lines += ["", f"Predicate agreement, person vs gold: Cohen's kappa {kappa([pg[k] for k in common], [pp[k] for k in common]):.2f} "
              f"over {len(common)} columns.", ""]

    # Where the person and the gold differ.
    gold_by = {(r.accession, r.raw_key): r for r in gold.itertuples(index=False)}
    lines += ["## Annotation differences, person vs gold", "",
              "| column | gold | person | person's note |", "|---|---|---|---|"]
    for r in person.itertuples(index=False):
        g = gold_by.get((r.accession, r.raw_key))
        if g is None:
            continue
        if _clean(g.primary_curie) == r.primary_curie and _clean(g.predicate) == r.predicate:
            continue
        def show(pred, curie):
            return f"{pred} {curie} {labels.get(curie, '')}".strip()
        lines.append(f"| {r.accession} {r.raw_key} | {show(g.predicate, g.primary_curie)} | {show(r.predicate, r.primary_curie)} "
                     f"| {r.note.replace('|', '/')} |")
    s = comparisons["person vs gold"]
    lines += ["", "## Pooling differences, person vs gold", "",
              "Gold variables the person split:", ""]
    lines += [f"- {m['gold']}: {', '.join(m['columns'])}" for m in s.missed_merges] or ["- none"]
    lines += ["", "Person's variables that join gold variables:", ""]
    lines += [f"- {m['predicted'].removeprefix('person:')}: {', '.join(m['columns'])}" for m in s.false_merges] or ["- none"]

    text = "\n".join(lines) + "\n"
    if out:
        Path(out).write_text(text)
    print(text)


if __name__ == "__main__":
    main(*sys.argv[1:3])
