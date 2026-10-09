"""Score the memorization probe against the characteristic snapshots.

    python eval/memorization/score.py

Reads `answers/<model>_batch<n>.json` and writes `out/per_series.tsv` and
`out/summary.md`. See PROTOCOL.md for the metrics and the control.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from colharmonize.normalise import normalise_key  # noqa: E402
from colharmonize.text import loose, same_meaning  # noqa: E402

SNAPSHOTS = {
    "tuning": ROOT / "eval/snapshots/ds_tuning_characteristics.json",
    "sealed": ROOT / "eval/snapshots/generalization_characteristics.json",
}
MAX_CATEGORIES = 30
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_WORD = re.compile(r"[a-z0-9]+")


def load_truth() -> tuple[dict[str, dict], dict[str, str]]:
    truth, corpus = {}, {}
    for name, path in SNAPSHOTS.items():
        for acc, rec in json.loads(path.read_text()).items():
            truth[acc] = rec["characteristics"]
            corpus[acc] = name
    return truth, corpus


def load_titles() -> dict[str, str]:
    import pandas as pd

    titles = {}
    for ws in ("work/ds-tuning", "work/sealed"):
        studies = pd.read_parquet(ROOT / ws / "studies.parquet")
        titles.update(dict(zip(studies.study_id, studies.title)))
    return titles


def load_answers() -> dict[str, dict[str, dict]]:
    """{model: {accession: answer}}."""
    out: dict[str, dict[str, dict]] = {}
    for path in sorted((HERE / "answers").glob("*_batch*.json")):
        model = path.stem.split("_batch")[0]
        out.setdefault(model, {}).update(json.loads(path.read_text()))
    return out


def categorical_values(values: dict[str, int]) -> set[str] | None:
    """The true key's distinct values, or None if it is numeric or too varied."""
    names = [v for v in values if v.strip()]
    if not names or len(names) > MAX_CATEGORIES:
        return None
    if sum(bool(_NUMBER.match(v.strip())) for v in names) > len(names) / 2:
        return None
    return {v.strip().casefold() for v in names}


def match_keys(true_keys: list[str], pred_keys: list[str], loose_rule: bool) -> dict[str, str]:
    """Greedy one-to-one: each true key to the first unused predicted key it matches."""
    def same(t: str, p: str) -> bool:
        if normalise_key(t) == normalise_key(p):
            return True
        return loose_rule and same_meaning(loose(t), loose(p))

    used: set[int] = set()
    pairs = {}
    for t in true_keys:
        for i, p in enumerate(pred_keys):
            if i not in used and same(t, p):
                used.add(i)
                pairs[t] = p
                break
    return pairs


def score_pair(answer: dict, true_chars: dict[str, dict[str, int]]) -> dict[str, float | int | None]:
    """Score one series' answer against one series' truth."""
    preds = answer.get("characteristics") or []
    pred_keys = [str(c.get("key", "")) for c in preds if c.get("key")]
    pred_values = {str(c.get("key")): {str(v).strip().casefold() for v in c.get("values") or []} for c in preds}
    true_keys = list(true_chars)
    row: dict[str, float | int | None] = {"n_true": len(true_keys), "n_pred": len(pred_keys)}
    for label, rule in (("strict", False), ("loose", True)):
        pairs = match_keys(true_keys, pred_keys, rule)
        row[f"key_recall_{label}"] = len(pairs) / len(true_keys) if true_keys else None
        row[f"key_precision_{label}"] = len(pairs) / len(pred_keys) if pred_keys else None
        if label == "loose":
            hit = total = 0
            for t, values in true_chars.items():
                cats = categorical_values(values)
                if cats is None:
                    continue
                total += len(cats)
                if t in pairs:
                    hit += len(cats & pred_values.get(pairs[t], set()))
            row["value_hits"], row["value_total"] = hit, total
    return row


def title_similarity(predicted: str | None, true: str) -> float:
    if not predicted:
        return 0.0
    a, b = set(_WORD.findall(predicted.casefold())), set(_WORD.findall(true.casefold()))
    return len(a & b) / len(a | b) if a | b else 0.0


def mean(xs: list[float | None]) -> float | None:
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def pct(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f}%"


def main() -> None:
    truth, corpus = load_truth()
    titles = load_titles()
    answers = load_answers()
    rows = []
    for model, by_acc in sorted(answers.items()):
        for acc in sorted(truth):
            ans = by_acc.get(acc)
            if ans is None:
                rows.append({"model": model, "accession": acc, "corpus": corpus[acc], "answered": False})
                continue
            own = score_pair(ans, truth[acc])
            others = [score_pair(ans, truth[o]) for o in truth if o != acc and corpus[o] == corpus[acc] and truth[o]]
            row = {"model": model, "accession": acc, "corpus": corpus[acc], "answered": True,
                   "confidence": ans.get("confidence"), **own,
                   "title_sim": title_similarity(ans.get("title"), titles[acc]),
                   "title_sim_control": mean([title_similarity(ans.get("title"), titles[o])
                                              for o in truth if o != acc and corpus[o] == corpus[acc]])}
            for k in ("key_recall_strict", "key_recall_loose", "key_precision_strict", "key_precision_loose"):
                row[f"{k}_control"] = mean([o[k] for o in others])
            row["value_recall"] = own["value_hits"] / own["value_total"] if own["value_total"] else None
            row["value_recall_control"] = mean([o["value_hits"] / o["value_total"] for o in others if o["value_total"]])
            rk, rc = row["key_recall_strict"], row["key_recall_strict_control"]
            row["recalled"] = rk is not None and rc is not None and rk >= 0.5 and rk - rc >= 0.3
            rows.append(row)

    out = HERE / "out"
    out.mkdir(exist_ok=True)
    cols = ["model", "accession", "corpus", "answered", "confidence", "n_true", "n_pred",
            "key_recall_strict", "key_recall_strict_control", "key_recall_loose", "key_recall_loose_control",
            "key_precision_strict", "key_precision_loose", "value_recall", "value_recall_control",
            "title_sim", "title_sim_control", "recalled"]
    with (out / "per_series.tsv").open("w") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join("" if r.get(c) is None else (f"{r[c]:.3f}" if isinstance(r.get(c), float) else str(r[c]))
                               for c in cols) + "\n")

    lines = ["# Memorization probe: summary", "",
             "Means over series with characteristics (GSE1397 and GSE4119 have none, so they count only for title).",
             "Control: the same answer scored against the other series of the same corpus.", "",
             "| model | corpus | series | key recall strict (control) | key recall loose (control) "
             "| key precision strict / loose | value recall (control) | title similarity (control) | confidence none | recalled |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for model in sorted(answers):
        for name in ("tuning", "sealed"):
            rs = [r for r in rows if r["model"] == model and r["corpus"] == name and r["answered"]]
            keyed = [r for r in rs if r["n_true"]]
            lines.append(
                f"| {model} | {name} | {len(rs)} "
                f"| {pct(mean([r['key_recall_strict'] for r in keyed]))} ({pct(mean([r['key_recall_strict_control'] for r in keyed]))}) "
                f"| {pct(mean([r['key_recall_loose'] for r in keyed]))} ({pct(mean([r['key_recall_loose_control'] for r in keyed]))}) "
                f"| {pct(mean([r['key_precision_strict'] for r in keyed]))} / {pct(mean([r['key_precision_loose'] for r in keyed]))} "
                f"| {pct(mean([r['value_recall'] for r in keyed]))} ({pct(mean([r['value_recall_control'] for r in keyed]))}) "
                f"| {pct(mean([r['title_sim'] for r in rs]))} ({pct(mean([r['title_sim_control'] for r in rs]))}) "
                f"| {sum(r.get('confidence') == 'none' for r in rs)} "
                f"| {', '.join(r['accession'] for r in rs if r['recalled']) or 'none'} |")
        missing = [r["accession"] for r in rows if r["model"] == model and not r["answered"]]
        if missing:
            lines.append(f"\n{model}: no answer for {', '.join(missing)}")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
