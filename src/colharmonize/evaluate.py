"""Score predicted column annotations against a gold standard.

Two questions are scored separately, because they fail separately:

**Pooling** asks whether the right columns share a variable. It is scored
pairwise over every pair of gold columns:
  precision  of the pairs the prediction pools, the share gold also pools.
             Low precision means over-broad buckets, i.e. information loss.
  recall     of the pairs gold pools, the share the prediction also pools.
             Low recall means columns that should pool were left apart.
Cross-dataset pairs are reported separately, since interoperability is
about them. B-cubed precision and recall are reported alongside, because
pairwise scores are dominated by the largest variables.

**Annotation** asks whether each column's term is right: primary-term
accuracy, predicate accuracy, both together, NO_MATCH precision and recall, and
micro-averaged qualifier precision and recall (unit excluded; units are scored
per column where predictions supply them).

The universe is the gold columns. A gold column with no prediction counts as an
unpooled singleton with no annotation, so missing output is never free.

Gold format is goldlib's: a columns TSV (accession, raw_key, source,
variable_id, unit, flags, note; variable_id "SPLIT" marks a column scored
through its parts) and a variables TSV (variable_id, predicate, primary_curie,
qualifiers, ...).

Predictions TSV: accession, raw_key, variable_id, and optionally predicate,
primary_curie, qualifiers ("slot=VALUE; slot=VALUE"), unit.
"""
from __future__ import annotations

import itertools
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from colharmonize.normalise import normalise_key

_QUAL = re.compile(r'(\w+)=(?:"([^"]*)"(?: \(ungrounded\))?|([A-Za-z]+:\d+)(?: \[[^\]]*\])?|([^;]+))')
_CURIE = re.compile(r"^[A-Za-z]+:\d+$")


def parse_qualifiers(text: object) -> frozenset[tuple[str, str]]:
    """Parse 'slot=CURIE [label]; slot="text" (ungrounded); slot=value' into (slot, value) pairs.

    CURIEs keep their case; free text is normalised so trivial spelling
    differences in an ungrounded qualifier do not count as errors.
    """
    if not isinstance(text, str) or not text.strip():
        return frozenset()
    out = set()
    for m in _QUAL.finditer(text):
        slot = m.group(1)
        value = (m.group(2) or m.group(3) or m.group(4) or "").strip()
        if not value:
            continue
        out.add((slot, value if _CURIE.match(value) else normalise_key(value)))
    return frozenset(out)


def _clean(v: object) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def _unit(v: object) -> str:
    return normalise_key(re.sub(r"\((inferred|ungrounded)[^)]*\)", "", _clean(v)))


def load_gold(columns_tsv: str | Path, variables_tsv: str | Path) -> pd.DataFrame:
    """One row per scored gold column, joined with its variable's annotation."""
    cols = pd.read_csv(columns_tsv, sep="\t", dtype=str, keep_default_na=False)
    vars_ = pd.read_csv(variables_tsv, sep="\t", dtype=str, keep_default_na=False)
    cols = cols[cols.variable_id != "SPLIT"]
    gold = cols.merge(vars_[["variable_id", "predicate", "primary_curie", "qualifiers"]],
                      on="variable_id", how="left", validate="many_to_one")
    if gold.predicate.isna().any():
        raise ValueError("gold columns reference unknown variables")
    return gold.reset_index(drop=True)


def load_predictions(path: str | Path) -> pd.DataFrame:
    pred = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    missing = {"accession", "raw_key", "variable_id"} - set(pred.columns)
    if missing:
        raise ValueError(f"predictions missing columns: {sorted(missing)}")
    dupes = pred.duplicated(["accession", "raw_key"])
    if dupes.any():
        raise ValueError(f"{dupes.sum()} duplicate (accession, raw_key) predictions")
    return pred


def _prf(tp: int, n_pred: int, n_gold: int) -> dict[str, float | int]:
    p = tp / n_pred if n_pred else float("nan")
    r = tp / n_gold if n_gold else float("nan")
    f = 2 * p * r / (p + r) if n_pred and n_gold and (p + r) else float("nan")
    return {"precision": p, "recall": r, "f1": f, "true_pairs": tp, "predicted_pairs": n_pred, "gold_pairs": n_gold}


@dataclass
class Score:
    n_gold_columns: int
    n_predicted: int
    pooling: dict
    pooling_cross_dataset: dict
    bcubed: dict
    annotation: dict
    false_merges: list = field(default_factory=list)
    missed_merges: list = field(default_factory=list)
    breadth: list = field(default_factory=list)
    gold_breadth: list = field(default_factory=list)
    unsplit_parents: list = field(default_factory=list)


def score(gold: pd.DataFrame, pred: pd.DataFrame) -> Score:
    items = list(zip(gold.accession, gold.raw_key))
    g = dict(zip(items, gold.variable_id))
    pred_by_item = {(r.accession, r.raw_key): r for r in pred.itertuples(index=False)}
    # A missing prediction is its own singleton, so it can never pool.
    p = {it: (pred_by_item[it].variable_id if it in pred_by_item else f"__missing__:{it}") for it in items}

    def pair_counts(cross_only: bool) -> dict:
        tp = n_pred = n_gold = 0
        for a, b in itertools.combinations(items, 2):
            if cross_only and a[0] == b[0]:
                continue
            same_g, same_p = g[a] == g[b], p[a] == p[b]
            n_gold += same_g
            n_pred += same_p
            tp += same_g and same_p
        return _prf(tp, n_pred, n_gold)

    g_members, p_members = defaultdict(set), defaultdict(set)
    for it in items:
        g_members[g[it]].add(it)
        p_members[p[it]].add(it)
    bp = sum(len(g_members[g[it]] & p_members[p[it]]) / len(p_members[p[it]]) for it in items) / len(items)
    br = sum(len(g_members[g[it]] & p_members[p[it]]) / len(g_members[g[it]]) for it in items) / len(items)
    bcubed = {"precision": bp, "recall": br, "f1": 2 * bp * br / (bp + br) if bp + br else float("nan")}

    # Annotation, per gold column.
    n = len(items)
    primary_ok = predicate_ok = both_ok = 0
    q_tp = q_pred = q_gold = 0
    nm_tp = nm_pred = nm_gold = 0
    unit_ok = unit_n = 0
    has_pred_cols = {"predicate", "primary_curie"} <= set(pred.columns)
    for row in gold.itertuples(index=False):
        it = (row.accession, row.raw_key)
        pr = pred_by_item.get(it)
        gp, gpred = _clean(row.primary_curie), _clean(row.predicate)
        pp = _clean(getattr(pr, "primary_curie", "")) if pr is not None else None
        ppred = _clean(getattr(pr, "predicate", "")) if pr is not None else None
        if pr is not None and has_pred_cols:
            primary_ok += pp == gp
            predicate_ok += ppred == gpred
            both_ok += pp == gp and ppred == gpred
        gold_none, pred_none = gpred == "none", (pr is not None and has_pred_cols and ppred == "none")
        nm_gold += gold_none
        nm_pred += pred_none
        nm_tp += gold_none and pred_none
        gq = {q for q in parse_qualifiers(row.qualifiers) if q[0] != "unit"}
        pq = {q for q in parse_qualifiers(getattr(pr, "qualifiers", "")) if q[0] != "unit"} if pr is not None else set()
        q_tp += len(gq & pq)
        q_pred += len(pq)
        q_gold += len(gq)
        if pr is not None and "unit" in pred.columns and _unit(row.unit):
            unit_n += 1
            unit_ok += _unit(getattr(pr, "unit", "")) == _unit(row.unit)

    def rate(k: int, d: int) -> float:
        return k / d if d else float("nan")

    annotation = {
        "scored": has_pred_cols,
        "primary_accuracy": rate(primary_ok, n) if has_pred_cols else float("nan"),
        "predicate_accuracy": rate(predicate_ok, n) if has_pred_cols else float("nan"),
        "annotation_accuracy": rate(both_ok, n) if has_pred_cols else float("nan"),
        "no_match_precision": rate(nm_tp, nm_pred), "no_match_recall": rate(nm_tp, nm_gold),
        "qualifier_precision": rate(q_tp, q_pred), "qualifier_recall": rate(q_tp, q_gold),
        "unit_accuracy": rate(unit_ok, unit_n), "unit_scored": unit_n,
    }

    # Where pooling went wrong, grouped so a reviewer can read it.
    false_merges, missed_merges = [], []
    for pv, members in p_members.items():
        gvs = Counter(g[it] for it in members)
        if len(gvs) > 1 and not pv.startswith("__missing__"):
            false_merges.append({"predicted": pv, "gold_variables": dict(gvs),
                                 "columns": sorted(f"{a}/{k}" for a, k in members)})
    for gv, members in g_members.items():
        pvs = Counter(p[it] for it in members)
        if len(pvs) > 1:
            missed_merges.append({"gold": gv, "split_into": len(pvs),
                                  "columns": sorted(f"{a}/{k} -> {p[(a, k)].removeprefix('__missing__:')}"
                                                    for a, k in members)})

    def breadth(members_by_var: dict) -> list:
        rows = []
        for v, members in members_by_var.items():
            if v.startswith("__missing__"):
                continue
            names = sorted({normalise_key(k.split("#")[-1]) for _, k in members})
            rows.append({"variable": v, "columns": len(members), "distinct_names": len(names), "names": names})
        return sorted(rows, key=lambda r: (-r["distinct_names"], -r["columns"]))

    gold_parents = set()
    split_rows = gold[gold.source.str.startswith("split:")]
    for row in split_rows.itertuples(index=False):
        gold_parents.add((row.accession, row.source.removeprefix("split:")))
    unsplit = sorted(f"{a}/{k}" for a, k in gold_parents if (a, k) in pred_by_item)

    return Score(
        n_gold_columns=n, n_predicted=sum(it in pred_by_item for it in items),
        pooling=pair_counts(cross_only=False), pooling_cross_dataset=pair_counts(cross_only=True),
        bcubed=bcubed, annotation=annotation,
        false_merges=sorted(false_merges, key=lambda r: -sum(r["gold_variables"].values())),
        missed_merges=sorted(missed_merges, key=lambda r: -r["split_into"]),
        breadth=breadth(p_members), gold_breadth=breadth(g_members), unsplit_parents=unsplit,
    )


def _pct(x: float) -> str:
    return "—" if x != x else f"{100 * x:.1f}%"


def report(s: Score, title: str = "Evaluation") -> str:
    """Markdown summary of a Score."""
    a = s.annotation
    lines = [
        f"# {title}", "",
        f"Gold columns: {s.n_gold_columns} · predicted: {s.n_predicted}", "",
        "## Pooling", "",
        "| | precision | recall | F1 | pairs (true / predicted / gold) |",
        "|---|---|---|---|---|",
    ]
    for name, d in [("all pairs", s.pooling), ("cross-dataset pairs", s.pooling_cross_dataset)]:
        lines.append(f"| {name} | {_pct(d['precision'])} | {_pct(d['recall'])} | {_pct(d['f1'])} | "
                     f"{d['true_pairs']} / {d['predicted_pairs']} / {d['gold_pairs']} |")
    lines.append(f"| B-cubed | {_pct(s.bcubed['precision'])} | {_pct(s.bcubed['recall'])} | {_pct(s.bcubed['f1'])} | |")
    lines += ["", "## Annotation", ""]
    if a["scored"]:
        lines += [
            f"- primary term: {_pct(a['primary_accuracy'])}",
            f"- predicate: {_pct(a['predicate_accuracy'])}",
            f"- term and predicate together: {_pct(a['annotation_accuracy'])}",
            f"- NO_MATCH precision / recall: {_pct(a['no_match_precision'])} / {_pct(a['no_match_recall'])}",
            f"- qualifiers precision / recall: {_pct(a['qualifier_precision'])} / {_pct(a['qualifier_recall'])}",
        ]
        if a["unit_scored"]:
            lines.append(f"- unit ({a['unit_scored']} columns): {_pct(a['unit_accuracy'])}")
    else:
        lines.append("Not scored: predictions carry no predicate or primary term.")
    lines += ["", "## Broadest predicted variables (distinct column names)", ""]
    for r in s.breadth[:5]:
        lines.append(f"- `{r['variable']}`: {r['distinct_names']} names, {r['columns']} columns: {', '.join(r['names'])}")
    lines += ["", f"## False merges ({len(s.false_merges)})", ""]
    for r in s.false_merges:
        lines.append(f"- `{r['predicted']}` merges gold " + ", ".join(f"{k} ({v})" for k, v in r["gold_variables"].items()))
    lines += ["", f"## Missed merges ({len(s.missed_merges)})", ""]
    for r in s.missed_merges:
        lines.append(f"- `{r['gold']}` split {r['split_into']} ways: " + "; ".join(r["columns"]))
    if s.unsplit_parents:
        lines += ["", f"Predicted on unsplit parent columns (their parts score as missing): {', '.join(s.unsplit_parents)}"]
    return "\n".join(lines) + "\n"
