"""Score the renamed-columns test: original vs paraphrased names, annotation alone.

    ./.venv/bin/python eval/robustness/score.py

Builds each annotate run's predictions in memory (nothing in either workspace
is written), with the other run as its agreement partner, maps run columns
back to gold keys, and compares conditions:
  original  work/ds-tuning, annotate runs 3 and 4 (prompt annotate-2)
  renamed   work/ds-tuning-renamed, annotate runs 3 and 4 (same prompt)
Writes eval/robustness/out/score.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval/stats"))
from colharmonize import annotate, tasks  # noqa: E402
from colharmonize.evaluate import _clean, load_gold, score  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402
import stats as S  # noqa: E402

CONDITIONS = {"original": ROOT / "work/ds-tuning", "renamed": ROOT / "work/ds-tuning-renamed"}
RUNS = (3, 4)
OUT = ROOT / "eval/robustness/out"


def run_predictions(ws_path: Path) -> dict[int, pd.DataFrame]:
    ws = Workspace(ws_path)
    resolver = annotate.make_resolver(ws)
    resolved = {}
    for run in RUNS:
        got = tasks.collect(ws.tasks(annotate.STAGE, run), annotate.AnnotateAnswer)
        got.problems += annotate.validate_answers(ws, got.answers, run=run, resolver=resolver)
        if not got.complete:
            sys.exit(json.dumps({"workspace": str(ws_path), "run": run, "pending": got.pending,
                                 "problems": got.problems}, indent=1, default=str))
        resolved[run] = annotate.resolve_run(ws, got.answers, run, resolver)
    labels = resolver.ontology.label_map()
    km = json.loads((ws_path / "key_map.json").read_text())
    back = {(k.split("\t")[0], v): k.split("\t")[1] for k, v in km.items()}
    out = {}
    for a, b in ((3, 4), (4, 3)):
        comb = annotate.combine(resolved[a], resolved[b], labels)
        pred = annotate.predictions(comb)
        pred["raw_key"] = [back.get((s, k), k) for s, k in zip(pred.accession, pred.raw_key)]
        pred["agree"] = comb.agree_primary.to_numpy()
        out[a] = pred
    return out


def main() -> None:
    gold = load_gold(ROOT / "eval/gold/ds_tuning_columns.tsv", ROOT / "eval/gold/ds_tuning_variables.tsv")
    renamed = {tuple(k.split("::", 1)) for k in json.loads((ROOT / "eval/robustness/renames.json").read_text())}
    km = json.loads((ROOT / "work/ds-tuning/key_map.json").read_text())
    run_col = {tuple(k.split("\t")): v for k, v in km.items()}
    # A gold column is "renamed" when the run column it maps to is a renamed characteristic.
    is_renamed = np.array([(a, run_col.get((a, k), k)) in renamed for a, k in zip(gold.accession, gold.raw_key)])
    labels = None
    preds = {c: run_predictions(p) for c, p in CONDITIONS.items()}

    corpus = S.Corpus("tuning", gold, list(zip(gold.accession, gold.raw_key)), None, [], {})
    corpus.studies = sorted(set(gold.accession))
    corpus.study = np.array([corpus.studies.index(a) for a in gold.accession])
    same_g = S.same_matrix(list(gold.variable_id))
    np.fill_diagonal(same_g, 0)

    lines = ["# Renamed columns: annotation alone, tuning gold", "",
             f"{len(gold)} gold columns, {int(is_renamed.sum())} of them renamed characteristics; the other "
             f"{int((~is_renamed).sum())} (repaired title and source-name columns) keep their names in both conditions.", "",
             "| condition | run of record | pooling P | R | F1 | primary term | primary, renamed columns | primary, unrenamed | "
             "term and predicate | qualifiers P / R | runs agree |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    per = {}
    for cond, by_run in preds.items():
        for run, pred in by_run.items():
            s = score(gold, pred, labels)
            pby = {(a, k): r for a, k, r in zip(pred.accession, pred.raw_key, pred.itertuples(index=False))}
            prim = np.array([pby.get(it) is not None and _clean(pby[it].primary_curie) == _clean(g)
                             for it, g in zip(corpus.items, gold.primary_curie)], dtype=float)
            per[(cond, run)] = {"prim": prim, "same": _same(corpus, pred)}
            a = s.annotation
            lines.append(f"| {cond} | {run} | {S.pct(s.pooling['precision'])} | {S.pct(s.pooling['recall'])} "
                         f"| {S.pct(s.pooling['f1'])} | {S.pct(a['primary_accuracy'])} "
                         f"| {S.pct(prim[is_renamed].mean())} | {S.pct(prim[~is_renamed].mean())} "
                         f"| {S.pct(a['annotation_accuracy'])} | {S.pct(a['qualifier_precision'])} / {S.pct(a['qualifier_recall'])} "
                         f"| {S.pct(pred.agree.mean())} |")

    # Paired over studies: mean of the two runs per condition, renamed minus original.
    rng = np.random.default_rng(S.SEED)
    W = S.draws(len(corpus.studies), rng)
    k = len(corpus.studies)

    def acc_draws(v: np.ndarray, mask: np.ndarray) -> np.ndarray:
        per_s = np.bincount(corpus.study[mask], weights=v[mask], minlength=k)
        n_s = np.bincount(corpus.study[mask], minlength=k).astype(float)
        with np.errstate(invalid="ignore", divide="ignore"):
            return (W @ per_s) / (W @ n_s)

    def f1_draws(s: np.ndarray) -> np.ndarray:
        return S.prf(*S.totals(S.unit_matrices(corpus, same_g, s, "study"), W))[2]

    def cond_mean(fn, cond):
        return (fn(cond, 3) + fn(cond, 4)) / 2

    lines += ["", "Renamed minus original, mean of the two runs, paired bootstrap over 13 studies:", "",
              "| metric | original | renamed | Δ, points | 95% CI |", "|---|---|---|---|---|"]
    everything = np.ones(len(gold), dtype=bool)
    for label, mask in (("primary term, all columns", everything), ("primary term, renamed columns", is_renamed),
                        ("primary term, unrenamed columns", ~is_renamed)):
        obs = {c: cond_mean(lambda c_, r: per[(c_, r)]["prim"][mask].mean(), c) for c in CONDITIONS}
        d = cond_mean(lambda c_, r: acc_draws(per[(c_, r)]["prim"], mask), "renamed") - \
            cond_mean(lambda c_, r: acc_draws(per[(c_, r)]["prim"], mask), "original")
        lo, hi = S.ci(d)
        lines.append(f"| {label} | {S.pct(obs['original'])} | {S.pct(obs['renamed'])} "
                     f"| {S.pts(obs['renamed'] - obs['original'])} | {S.pts(lo)} to {S.pts(hi)} |")
    obs = {c: cond_mean(lambda c_, r: S._f1(same_g, per[(c_, r)]["same"]), c) for c in CONDITIONS}
    d = cond_mean(lambda c_, r: f1_draws(per[(c_, r)]["same"]), "renamed") - \
        cond_mean(lambda c_, r: f1_draws(per[(c_, r)]["same"]), "original")
    lo, hi = S.ci(d)
    lines.append(f"| pooling F1 (annotation alone) | {S.pct(obs['original'])} | {S.pct(obs['renamed'])} "
                 f"| {S.pts(obs['renamed'] - obs['original'])} | {S.pts(lo)} to {S.pts(hi)} |")
    noise = {c: per[(c, 4)]["prim"].mean() - per[(c, 3)]["prim"].mean() for c in CONDITIONS}
    lines += ["", "Run-to-run noise, primary term (run 4 − run 3): "
              + ", ".join(f"{c} {S.pts(v)}" for c, v in noise.items()) + " points."]

    # Columns whose annotation changed with the name, both runs agreeing within each condition.
    lines += ["", "## Renamed columns whose primary term changed in both runs", "",
              "| column | new name | gold | original (runs 3, 4) | renamed (runs 3, 4) |", "|---|---|---|---|---|"]
    renames = {tuple(k.split("::", 1)): v for k, v in json.loads((ROOT / "eval/robustness/renames.json").read_text()).items()}
    lab = annotate.make_resolver(Workspace(CONDITIONS["original"])).ontology.label_map()

    def term(cond, run, i):
        pred = preds[cond][run]
        pby = {(a, k): r for a, k, r in zip(pred.accession, pred.raw_key, pred.itertuples(index=False))}
        r = pby.get(corpus.items[i])
        return "—" if r is None else f"{r.predicate} {lab.get(r.primary_curie, r.primary_curie) or '(none)'}"

    for i, (it, g) in enumerate(zip(corpus.items, gold.itertuples(index=False))):
        if not is_renamed[i]:
            continue
        o = {term("original", r, i) for r in RUNS}
        n = {term("renamed", r, i) for r in RUNS}
        if o.isdisjoint(n):
            new = renames.get((it[0], run_col.get(it, it[1])), "")
            lines.append(f"| {it[0]} {it[1]} | {new} | {g.predicate} {lab.get(g.primary_curie, '') or '(none)'} "
                         f"| {' / '.join(term('original', r, i) for r in RUNS)} | {' / '.join(term('renamed', r, i) for r in RUNS)} |")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "score.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def _same(corpus: "S.Corpus", pred: pd.DataFrame) -> np.ndarray:
    s = S.same_matrix(S.partition(corpus, pred))
    np.fill_diagonal(s, 0)
    return s


if __name__ == "__main__":
    main()
