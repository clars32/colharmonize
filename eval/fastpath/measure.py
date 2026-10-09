"""Measure easy-first fast-path rules (handoff task 12) from existing outputs.

    ./.venv/bin/python eval/fastpath/measure.py

A fast-path column is annotated by code: predicate exact, primary the term its
name matches exactly, no qualifiers. The rule decides which columns qualify. For each
rule variant and corpus this reports how many annotation items it would take
away from subagents, and how often its annotation is right, next to the
pipeline's final annotation on the same columns. Nothing is written to a
workspace. Sealed numbers are post hoc.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize import profile  # noqa: E402
from colharmonize.candidates import name_forms  # noqa: E402
from colharmonize.evaluate import _clean, load_gold  # noqa: E402
from colharmonize.ontology import Ontology  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402

_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
CORPORA = {
    "tuning": ("work/ds-tuning", "eval/gold/ds_tuning_columns.tsv", "eval/gold/ds_tuning_variables.tsv"),
    "sealed (post hoc)": ("work/sealed", "eval/gold/generalization_columns.tsv", "eval/gold/generalization_variables.tsv"),
}


def mostly_numeric(values: list[str]) -> bool:
    vals = [v for v in values if v.strip() and v.strip().casefold() not in {"na", "n/a", "nan", "."}]
    return bool(vals) and sum(bool(_NUMBER.match(v.strip())) for v in vals) / len(vals) >= 0.9


def facts(ws: Workspace, onto: Ontology) -> pd.DataFrame:
    """Per annotation column: its exact-name terms, value-category ranking, and value shape."""
    cand = pd.read_parquet(ws.candidates)
    cand["src"] = cand.sources.map(json.loads)
    cols = profile.annotation_columns(ws)
    labels = onto.label_map()
    rows = []
    for r in cols.itertuples(index=False):
        g = cand[(cand.study_id == r.study_id) & (cand.column == r.column)]
        exact = [c for c, s in zip(g.curie, g.src) if "exact_space" in s]
        vcat = sorted(((s["value_category"], c) for c, s in zip(g.curie, g.src) if "value_category" in s))
        values = [v for v, _ in json.loads(r.values)]
        plain = name_forms(r.column)["plain"]
        rows.append({"study_id": r.study_id, "column": r.column, "exact": exact,
                     "label_match": [c for c in exact if labels.get(c, "").casefold() == plain],
                     "vcat": [c for _, c in vcat], "numeric": mostly_numeric(values),
                     "n_distinct": int(r.n_distinct)})
    return pd.DataFrame(rows)


# Each rule returns the fast-path term for a column, or None to leave it to the subagents.
def rule_label_and_values(f) -> str | None:
    """Name equals a term's label (not just a synonym), and values agree:
    the term is the values' top category, or the values are numeric and propose
    no category (a quantity such as age)."""
    if len(f.label_match) != 1:
        return None
    t = f.label_match[0]
    if f.vcat:
        return t if f.vcat[0] == t else None
    return t if f.numeric else None


def rule_synonym_and_values(f) -> str | None:
    """As above, but an exact synonym also counts as a name match."""
    if len(f.exact) != 1:
        return None
    t = f.exact[0]
    if f.vcat:
        return t if f.vcat[0] == t else None
    return t if f.numeric else None


def rule_label_only(f) -> str | None:
    """Name equals a term's label; values ignored. The unsafe baseline (decision 5.1)."""
    return f.label_match[0] if len(f.label_match) == 1 else None


RULES = {"label + values agree": rule_label_and_values,
         "synonym + values agree": rule_synonym_and_values,
         "label only (no value guard)": rule_label_only}


def main() -> None:
    lines = ["# Easy-first fast path: what each rule would annotate", "",
             "A fast-path column gets predicate exact and the matched term, with no qualifiers, and no subagent "
             "sees it. \"Right\" means primary term and predicate both match gold. \"Pipeline\" is the final "
             "output on the same gold columns.", "",
             "| corpus | rule | columns taken (of all) | gold columns taken | fast path right | pipeline right on them |",
             "|---|---|---|---|---|---|"]
    detail = []
    for corpus, (ws_dir, gc, gv) in CORPORA.items():
        ws = Workspace(ROOT / ws_dir)
        onto = Ontology.from_dir(ws.ontology_dir())
        labels = onto.label_map()
        fx = facts(ws, onto)
        gold = load_gold(ROOT / gc, ROOT / gv)
        km = json.loads((ROOT / ws_dir / "key_map.json").read_text())
        to_run = {tuple(k.split("\t")): v for k, v in km.items()}
        gold["run_column"] = [to_run.get((a, k), k) for a, k in zip(gold.accession, gold.raw_key)]
        gby = {(r.accession, r.run_column): r for r in gold.itertuples(index=False)}
        pred = pd.read_csv(ROOT / ws_dir / "predictions_scored.tsv", sep="\t", dtype=str, keep_default_na=False)
        pby = {(a, k): r for a, k, r in zip(pred.accession, pred.raw_key, pred.itertuples(index=False))}
        for name, rule in RULES.items():
            taken = [(f, rule(f)) for f in fx.itertuples(index=False)]
            taken = [(f, t) for f, t in taken if t]
            scored = [(f, t, gby[(f.study_id, f.column)]) for f, t in taken if (f.study_id, f.column) in gby]
            fp_ok = sum(_clean(g.primary_curie) == t and _clean(g.predicate) == "exact" for f, t, g in scored)
            pl_ok = sum((p := pby.get((f.study_id, f.column))) is not None
                        and _clean(p.primary_curie) == _clean(g.primary_curie) and _clean(p.predicate) == _clean(g.predicate)
                        for f, t, g in scored)
            n = len(scored)
            lines.append(f"| {corpus} | {name} | {len(taken)} of {len(fx)} | {n} | "
                         f"{fp_ok}/{n} ({100 * fp_ok / n:.0f}%) | {pl_ok}/{n} ({100 * pl_ok / n:.0f}%) |" if n else
                         f"| {corpus} | {name} | {len(taken)} of {len(fx)} | 0 | — | — |")
            if name == "label + values agree":
                for f, t, g in scored:
                    ok = _clean(g.primary_curie) == t and _clean(g.predicate) == "exact"
                    if not ok:
                        detail.append(f"| {corpus} | {f.study_id} {f.column} | exact {labels.get(t, t)} "
                                      f"| {g.predicate} {labels.get(_clean(g.primary_curie), '') or '(none)'} |")
    lines += ["", "## Where the chosen rule (label + values agree) disagrees with gold", "",
              "| corpus | column | fast path | gold |", "|---|---|---|---|"] + (detail or ["| — | — | — | — |"])
    out = ROOT / "eval/fastpath/out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "measure.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
