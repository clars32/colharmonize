"""Confidence-signal discrimination, bootstrap intervals and paired tests.

    ./.venv/bin/python eval/stats/stats.py

Handoff task 8. Reads the recorded prediction files and each workspace's
`scored.parquet`, and writes `eval/stats/out/stats.md`. Nothing in a
workspace is written.

Resampling unit. Pairwise pooling scores are sums over pairs of columns, and
pairs that share a column or a study are not independent. Two bootstraps are
reported: over **studies** (the sampling unit of a corpus, and the honest
one) and over **columns**. A resampled unit drawn k times contributes its
pairs with every other drawn unit, and its own internal pairs k^2 times; a
column is never paired with its own copy.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize.evaluate import _clean, load_gold  # noqa: E402

B = 10_000
SEED = 20261008
OUT = ROOT / "eval/stats/out"
PRED = ROOT / "eval/stats/pred"

# (path, keys are the run's column names and need mapping back to gold keys)
CORPORA = {
    "tuning": {
        "workspace": ROOT / "work/ds-tuning",
        "gold": ("eval/gold/ds_tuning_columns.tsv", "eval/gold/ds_tuning_variables.tsv"),
        "systems": {
            "final (reconcile run 1)": ("work/ds-tuning/predictions_scored.tsv", True),
            "reconcile run 2": ("work/ds-tuning/predictions_reconcile_run2.tsv", True),
            "reconcile run 3 (merge links)": ("eval/stats/pred/tuning_reconcile_run3.tsv", True),
            "reconcile run 4 (merge links)": ("eval/stats/pred/tuning_reconcile_run4.tsv", True),
            "annotation alone": ("work/ds-tuning/predictions_annotate.tsv", True),
            "baseline: iteration 2": ("eval/baselines/iteration2_ds_tuning.tsv", False),
            "baseline: GEOmend propose()": ("eval/baselines/geomend_propose_ds_tuning.tsv", False),
        },
    },
    "sealed": {
        "workspace": ROOT / "work/sealed",
        "gold": ("eval/gold/generalization_columns.tsv", "eval/gold/generalization_variables.tsv"),
        "systems": {
            "final (reconcile run 1)": ("work/sealed/predictions_scored.tsv", True),
            "reconcile run 2": ("eval/sealed/out/pred_reconcile_run2.tsv", True),
            "annotation alone": ("work/sealed/predictions_annotate.tsv", True),
            "baseline: identical names": ("eval/sealed/out/same_name_sealed.tsv", False),
            "baseline: GEOmend propose()": ("eval/sealed/out/geomend_propose_sealed.tsv", False),
        },
    },
}
TIER_RANK = {"manual": 0, "quick": 1, "pre_accepted": 2}


# ---------------------------------------------------------------- loading

@dataclass
class Corpus:
    name: str
    gold: pd.DataFrame
    items: list[tuple[str, str]]
    study: np.ndarray            # study index per item
    studies: list[str]
    back: dict[tuple[str, str], str]   # (accession, run column) -> gold key

    def predictions(self, path: str, mapped: bool) -> pd.DataFrame:
        pred = pd.read_csv(ROOT / path, sep="\t", dtype=str, keep_default_na=False)
        if mapped:
            pred["raw_key"] = [self.back.get((a, k), k) for a, k in zip(pred.accession, pred.raw_key)]
        return pred


def load_corpus(name: str) -> Corpus:
    spec = CORPORA[name]
    gold = load_gold(ROOT / spec["gold"][0], ROOT / spec["gold"][1])
    items = list(zip(gold.accession, gold.raw_key))
    studies = sorted({a for a, _ in items})
    km = json.loads((spec["workspace"] / "key_map.json").read_text())
    back = {(k.split("\t")[0], v): k.split("\t")[1] for k, v in km.items()}
    return Corpus(name, gold, items, np.array([studies.index(a) for a, _ in items]), studies, back)


def partition(c: Corpus, pred: pd.DataFrame) -> list[str]:
    """Each gold item's predicted variable; a missing prediction is its own singleton."""
    by = dict(zip(zip(pred.accession, pred.raw_key), pred.variable_id))
    return [by.get(it, f"__missing__:{it}") for it in c.items]


def same_matrix(labels: list[str]) -> np.ndarray:
    a = np.array(labels, dtype=object)
    return (a[:, None] == a[None, :]).astype(np.int64)


# ---------------------------------------------------------------- pooling bootstrap

def unit_matrices(c: Corpus, same_g: np.ndarray, same_p: np.ndarray, unit: str) -> tuple[np.ndarray, ...]:
    """Upper-triangular (incl. diagonal) per-unit-pair counts of TP, predicted and gold pairs."""
    n = len(c.items)
    iu = np.triu_indices(n, k=1)
    tp, npred, ngold = (same_g & same_p)[iu], same_p[iu], same_g[iu]
    if unit == "column":
        U = np.zeros((n, n), dtype=np.int64)
        mats = []
        for v in (tp, npred, ngold):
            M = U.copy()
            M[iu] = v
            mats.append(M)
        return tuple(mats)
    k = len(c.studies)
    si, sj = c.study[iu[0]], c.study[iu[1]]
    lo, hi = np.minimum(si, sj), np.maximum(si, sj)
    mats = []
    for v in (tp, npred, ngold):
        M = np.zeros((k, k), dtype=np.int64)
        np.add.at(M, (lo, hi), v)
        mats.append(M)
    return tuple(mats)


def draws(k: int, rng: np.random.Generator) -> np.ndarray:
    return rng.multinomial(k, np.full(k, 1 / k), size=B).astype(np.float64)


def totals(Ms: tuple[np.ndarray, ...], W: np.ndarray) -> tuple[np.ndarray, ...]:
    return tuple(np.einsum("bi,ij,bj->b", W, M.astype(np.float64), W) for M in Ms)


def prf(tp, npred, ngold):
    with np.errstate(divide="ignore", invalid="ignore"):
        p = np.where(npred > 0, tp / npred, np.nan)
        r = np.where(ngold > 0, tp / ngold, np.nan)
        f = np.where(npred + ngold > 0, 2 * tp / (npred + ngold), np.nan)
    return p, r, f


def ci(x: np.ndarray) -> tuple[float, float]:
    x = x[~np.isnan(x)]
    if not len(x):
        return float("nan"), float("nan")
    return float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))


def pct(x: float) -> str:
    return "—" if x != x else f"{100 * x:.1f}%"


def pts(x: float) -> str:
    return f"{100 * x:+.1f}"


# ---------------------------------------------------------------- discrimination

def auc(score: np.ndarray, label: np.ndarray) -> float:
    """P(score of a correct item > score of an incorrect one), ties counted half."""
    pos, neg = score[label == 1], score[label == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(pos) * len(neg)))


def cohen_d(score: np.ndarray, label: np.ndarray) -> float:
    a, b = score[label == 1], score[label == 0]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    sp = math.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return float((a.mean() - b.mean()) / sp) if sp else float("nan")


def auc_tests(score: np.ndarray, label: np.ndarray, rng: np.random.Generator) -> dict:
    a = auc(score, label)
    if a != a:
        return {"auc": a, "lo": a, "hi": a, "p": a, "d": a,
                "n_correct": int(label.sum()), "n_wrong": int((1 - label).sum())}
    perm = np.array([auc(score, rng.permutation(label)) for _ in range(2000)])
    p = float((np.abs(perm - 0.5) >= abs(a - 0.5) - 1e-12).mean())
    boots = []
    n = len(score)
    for _ in range(2000):
        idx = rng.integers(0, n, n)
        boots.append(auc(score[idx], label[idx]))
    lo, hi = ci(np.array(boots))
    return {"auc": a, "lo": lo, "hi": hi, "p": p, "d": cohen_d(score, label),
            "n_correct": int(label.sum()), "n_wrong": int((1 - label).sum())}


def binom_two_sided(b: int, c: int) -> float:
    """Exact McNemar p: discordant counts b and c under p = 1/2."""
    n, k = b + c, min(b, c)
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


# ---------------------------------------------------------------- sections

def pooling_section(c: Corpus, rng: np.random.Generator) -> tuple[list[str], dict]:
    gold_labels = list(c.gold.variable_id)
    same_g = same_matrix(gold_labels)
    np.fill_diagonal(same_g, 0)
    parts, sames = {}, {}
    for sys_name, (path, mapped) in CORPORA[c.name]["systems"].items():
        parts[sys_name] = partition(c, c.predictions(path, mapped))
        s = same_matrix(parts[sys_name])
        np.fill_diagonal(s, 0)
        sames[sys_name] = s
    W = {"study": draws(len(c.studies), rng), "column": draws(len(c.items), rng)}
    lines = [f"### Pooling, {c.name} ({len(c.items)} gold columns, {len(c.studies)} studies)", "",
             "| system | precision | recall | F1 | F1 95% CI, studies | F1 95% CI, columns |",
             "|---|---|---|---|---|---|"]
    f1_draws = {}
    for sys_name, s in sames.items():
        row_ci = {}
        for unit in ("study", "column"):
            tp, npd, ngd = totals(unit_matrices(c, same_g, s, unit), W[unit])
            f1_draws[(sys_name, unit)] = prf(tp, npd, ngd)
            row_ci[unit] = ci(f1_draws[(sys_name, unit)][2])
        iu = np.triu_indices(len(c.items), k=1)
        tp, npd, ngd = ((same_g & s)[iu].sum(), s[iu].sum(), same_g[iu].sum())
        p, r, f = (float(x) for x in prf(np.array(tp, float), np.array(npd, float), np.array(ngd, float)))
        lines.append(f"| {sys_name} | {pct(p)} | {pct(r)} | {pct(f)} "
                     f"| {pct(row_ci['study'][0])}–{pct(row_ci['study'][1])} "
                     f"| {pct(row_ci['column'][0])}–{pct(row_ci['column'][1])} |")
    lines += ["", "Paired differences in F1 (same resamples for both systems):", "",
              "| comparison | ΔF1, points | 95% CI, studies | share of study resamples with Δ ≤ 0 |", "|---|---|---|---|"]
    final = "final (reconcile run 1)"
    for other in sames:
        if other == final:
            continue
        a = f1_draws[(final, "study")][2]
        b = f1_draws[(other, "study")][2]
        d = a - b
        obs = _f1(same_g, sames[final]) - _f1(same_g, sames[other])
        lo, hi = ci(d)
        lines.append(f"| final − {other} | {pts(obs)} | {pts(lo)} to {pts(hi)} | {float((d[~np.isnan(d)] <= 0).mean()):.3f} |")
    return lines, {"same_g": same_g, "sames": sames, "parts": parts, "W": W}


def _f1(same_g: np.ndarray, s: np.ndarray) -> float:
    iu = np.triu_indices(len(s), k=1)
    tp, npd, ngd = (same_g & s)[iu].sum(), s[iu].sum(), same_g[iu].sum()
    return 2 * tp / (npd + ngd) if npd + ngd else float("nan")


def merge_link_section(c: Corpus, ctx: dict) -> list[str]:
    """Decisions log 12.3, redone with paired tests: runs 1/2 (no links) vs 3/4 (links)."""
    same_g, sames, W = ctx["same_g"], ctx["sames"], ctx["W"]["study"]
    runs = {1: "final (reconcile run 1)", 2: "reconcile run 2",
            3: "reconcile run 3 (merge links)", 4: "reconcile run 4 (merge links)"}
    stats = {r: prf(*totals(unit_matrices(c, same_g, sames[n], "study"), W)) for r, n in runs.items()}
    obs = {r: _f1(same_g, sames[n]) for r, n in runs.items()}
    prec = {}
    iu = np.triu_indices(len(c.items), k=1)
    for r, n in runs.items():
        s = sames[n]
        prec[r] = (same_g & s)[iu].sum() / s[iu].sum()
    lines = ["### Merge links (decisions log 12.3), tuning, paired over studies", "",
             "Each condition is the mean of its two runs; both use the same study resamples.", "",
             "| metric | no links (runs 1, 2) | links (runs 3, 4) | Δ, points | 95% CI | share of resamples with Δ ≤ 0 |",
             "|---|---|---|---|---|---|"]
    for k, label in ((2, "F1"), (0, "precision"), (1, "recall")):
        a = (stats[1][k] + stats[2][k]) / 2
        b = (stats[3][k] + stats[4][k]) / 2
        d = b - a
        if k == 2:
            oa, ob = (obs[1] + obs[2]) / 2, (obs[3] + obs[4]) / 2
        else:
            def point(r):
                s = sames[runs[r]]
                tp, npd, ngd = (same_g & s)[iu].sum(), s[iu].sum(), same_g[iu].sum()
                return tp / npd if k == 0 else tp / ngd
            oa, ob = (point(1) + point(2)) / 2, (point(3) + point(4)) / 2
        lo, hi = ci(d)
        lines.append(f"| {label} | {pct(oa)} | {pct(ob)} | {pts(ob - oa)} | {pts(lo)} to {pts(hi)} "
                     f"| {float((d[~np.isnan(d)] <= 0).mean()):.3f} |")
    lines += ["", f"Run-to-run noise within a condition, F1: run 2 − run 1 = {pts(obs[2] - obs[1])}, "
              f"run 4 − run 3 = {pts(obs[4] - obs[3])} points.", "",
              "Exact McNemar tests on pair decisions (same variable or not, against gold), over all gold pairs. "
              "Pairs sharing a column are not independent, so these p-values are optimistic:", "",
              "| comparison | right only without links | right only with links | p |", "|---|---|---|---|"]
    for a, b in ((1, 3), (2, 4), (1, 4), (2, 3)):
        ra = (sames[runs[a]] == same_g)[iu]
        rb = (sames[runs[b]] == same_g)[iu]
        only_a, only_b = int((ra & ~rb).sum()), int((rb & ~ra).sum())
        lines.append(f"| run {a} vs run {b} | {only_a} | {only_b} | {binom_two_sided(only_a, only_b):.3f} |")
    return lines


def signals_section(c: Corpus, ctx: dict, rng: np.random.Generator) -> list[str]:
    ws = CORPORA[c.name]["workspace"]
    scored = pd.read_parquet(ws / "scored.parquet")
    scored["gold_key"] = [c.back.get((a, k), k) for a, k in zip(scored.study_id, scored.column)]
    sig = {(a, k): r for a, k, r in zip(scored.study_id, scored.gold_key, scored.itertuples(index=False))}
    final_path, mapped = CORPORA[c.name]["systems"]["final (reconcile run 1)"]
    pred = c.predictions(final_path, mapped)
    pby = {(a, k): r for a, k, r in zip(pred.accession, pred.raw_key, pred.itertuples(index=False))}
    part = ctx["parts"]["final (reconcile run 1)"]
    gold_var = list(c.gold.variable_id)

    rows = []
    for i, (it, g) in enumerate(zip(c.items, c.gold.itertuples(index=False))):
        if it not in sig or it not in pby:
            continue
        s, p = sig[it], pby[it]
        gold_mates = {c.items[j] for j in range(len(c.items)) if j != i and gold_var[j] == gold_var[i]}
        pred_mates = {c.items[j] for j in range(len(c.items)) if j != i and part[j] == part[i]}
        rows.append({
            "annotation_ok": int(_clean(p.primary_curie) == _clean(g.primary_curie) and _clean(p.predicate) == _clean(g.predicate)),
            "pooling_ok": int(gold_mates == pred_mates),
            "no_false_mates": int(pred_mates <= gold_mates),
            "no_missed_mates": int(gold_mates <= pred_mates),
            "annotation_agree": float(bool(s.annotation_agree)),
            "qualifiers_agree": float(bool(s.qualifiers_agree)),
            "partition_agreement": float(s.partition_agreement),
            "reconciled": bool(s.reconciled),
            "tier": float(TIER_RANK[s.tier]),
            "variable_tier": float(TIER_RANK[s.variable_tier]),
        })
    df = pd.DataFrame(rows)
    lines = [f"### Confidence signals, {c.name} ({len(df)} gold columns with a prediction)", "",
             "AUC: the chance a correct column scores higher on the signal than a wrong one (0.5 = no "
             "discrimination). 95% CI by bootstrap over columns; p by permutation of the labels.", "",
             "\"Right, top / rest\": the outcome rate among columns at the signal's best value (runs agree, "
             "agreement 1, pre-accepted) and among the rest.", "",
             "| signal | outcome | right / wrong | right, top / rest | AUC | 95% CI | p | Cohen's d |",
             "|---|---|---|---|---|---|---|---|"]
    specs = [("annotation runs agree", "annotation_agree", "annotation_ok", None),
             ("qualifiers agree", "qualifiers_agree", "annotation_ok", None),
             ("column tier", "tier", "annotation_ok", None),
             ("variable tier", "variable_tier", "annotation_ok", None),
             ("partition agreement (reconciled columns)", "partition_agreement", "pooling_ok", "reconciled"),
             ("partition agreement (reconciled columns)", "partition_agreement", "no_false_mates", "reconciled"),
             ("partition agreement (reconciled columns)", "partition_agreement", "no_missed_mates", "reconciled"),
             ("variable tier", "variable_tier", "pooling_ok", None),
             ("variable tier", "variable_tier", "no_false_mates", None),
             ("variable tier", "variable_tier", "no_missed_mates", None)]
    outcome_label = {"annotation_ok": "annotation right", "pooling_ok": "mates exactly right",
                     "no_false_mates": "no false mates", "no_missed_mates": "no missed mates"}
    for label, col, outcome, only in specs:
        d = df[df[only]] if only else df
        x, y = d[col].to_numpy(float), d[outcome].to_numpy(int)
        top = x == x.max()
        hi_lo = f"{pct(y[top].mean())} / {pct(y[~top].mean()) if (~top).any() else '—'}"
        t = auc_tests(x, y, rng)
        a = "—" if t["auc"] != t["auc"] else f"{t['auc']:.2f}"
        span = "—" if t["auc"] != t["auc"] else f"{t['lo']:.2f}–{t['hi']:.2f}"
        lines.append(f"| {label} | {outcome_label[outcome]} | {t['n_correct']} / {t['n_wrong']} | {hi_lo} | {a} "
                     f"| {span} | {'—' if t['p'] != t['p'] else ('<0.001' if t['p'] == 0 else format(t['p'], '.3f'))} "
                     f"| {'—' if t['d'] != t['d'] else format(t['d'], '.2f')} |")
    return lines + [""] + pair_agreement_lines(c, ctx)


def pair_agreement_lines(c: Corpus, ctx: dict) -> list[str]:
    same_g, sames = ctx["same_g"], ctx["sames"]
    s1, s2 = sames["final (reconcile run 1)"], sames["reconcile run 2"]
    iu = np.triu_indices(len(c.items), k=1)
    pooled = s1[iu] == 1
    agree = (s1 == s2)[iu]
    right = (same_g == 1)[iu]
    a_n, a_ok = int((pooled & agree).sum()), int((pooled & agree & right).sum())
    d_n, d_ok = int((pooled & ~agree).sum()), int((pooled & ~agree & right).sum())
    lab = right[pooled].astype(int)
    sc = agree[pooled].astype(float)
    a = auc(sc, lab)
    a_txt = "undefined" if a != a else f"{a:.2f}"
    return [f"Pooled pairs (run 1 pools them) by whether run 2 pools them too: agreed {a_ok}/{a_n} correct, "
            f"disagreed {d_ok}/{d_n} correct; AUC of pair agreement for pair correctness {a_txt}."]


def annotation_section(c: Corpus, rng: np.random.Generator) -> list[str]:
    lines = [f"### Annotation accuracy, {c.name}, with 95% CI over studies", "",
             "| system | primary term | term and predicate |", "|---|---|---|"]
    for sys_name, (path, mapped) in CORPORA[c.name]["systems"].items():
        pred = c.predictions(path, mapped)
        if not {"primary_curie", "predicate"} <= set(pred.columns):
            continue
        pby = {(a, k): r for a, k, r in zip(pred.accession, pred.raw_key, pred.itertuples(index=False))}
        prim, both = [], []
        for it, g in zip(c.items, c.gold.itertuples(index=False)):
            p = pby.get(it)
            ok_p = p is not None and _clean(p.primary_curie) == _clean(g.primary_curie)
            prim.append(ok_p)
            both.append(ok_p and _clean(p.predicate) == _clean(g.predicate))
        cells = []
        for v in (np.array(prim, float), np.array(both, float)):
            k = len(c.studies)
            per_s = np.bincount(c.study, weights=v, minlength=k)
            n_s = np.bincount(c.study, minlength=k).astype(float)
            W = draws(k, rng)
            acc = (W @ per_s) / (W @ n_s)
            lo, hi = ci(acc)
            cells.append(f"{pct(v.mean())} ({pct(lo)}–{pct(hi)})")
        lines.append(f"| {sys_name} | {cells[0]} | {cells[1]} |")
    return lines


def main() -> None:
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# Statistics: intervals, paired tests and confidence signals", "",
             f"Generated by `eval/stats/stats.py` ({B:,} bootstrap resamples, seed {SEED}). "
             "Sealed numbers are recomputed from the recorded outputs; nothing was re-run.", ""]
    for name in ("tuning", "sealed"):
        c = load_corpus(name)
        pool_lines, ctx = pooling_section(c, rng)
        lines += pool_lines + [""]
        if name == "tuning":
            lines += merge_link_section(c, ctx) + [""]
        lines += annotation_section(c, rng) + [""]
        lines += signals_section(c, ctx, rng) + [""]
    (OUT / "stats.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
