"""Score annotate-3 (runs 6, 7) against annotate-2 (runs 3, 4) on tuning (PROTOCOL.md).

    ./.venv/bin/python eval/prompts/score.py

Annotation alone. Each run is scored as the answer of record with the other
run of its prompt as partner. Writes eval/prompts/out/score.md.
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
from colharmonize.evaluate import _clean, load_gold, parse_qualifiers, qualifier_match, score  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402
import stats as S  # noqa: E402

WS = ROOT / "work/ds-tuning-models"
PROMPTS = {"annotate-2": (3, 4), "annotate-3": (6, 7)}


def predictions(ws: Workspace, runs: tuple[int, int]) -> dict[int, pd.DataFrame]:
    resolver = annotate.make_resolver(ws)
    res = {}
    for run in runs:
        got = tasks.collect(ws.tasks(annotate.STAGE, run), annotate.AnnotateAnswer)
        got.problems += annotate.validate_answers(ws, got.answers, run=run, resolver=resolver)
        if not got.complete:
            sys.exit(json.dumps({"run": run, "pending": got.pending, "problems": got.problems}, default=str))
        res[run] = annotate.resolve_run(ws, got.answers, run, resolver)
    km = json.loads((ws.root / "key_map.json").read_text())
    back = {(k.split("\t")[0], v): k.split("\t")[1] for k, v in km.items()}
    out = {}
    for a, b in (runs, runs[::-1]):
        comb = annotate.combine(res[a], res[b], resolver.ontology.label_map())
        pred = annotate.predictions(comb)
        pred["raw_key"] = [back.get((s, k), k) for s, k in zip(pred.accession, pred.raw_key)]
        pred["agree"] = comb.agree_primary.to_numpy()
        out[a] = pred
    return out


def per_column(gold: pd.DataFrame, pred: pd.DataFrame, labels: dict) -> pd.DataFrame:
    """Per gold column: term-and-predicate right, and qualifier true positives, predicted and gold counts."""
    pby = {(a, k): r for a, k, r in zip(pred.accession, pred.raw_key, pred.itertuples(index=False))}
    rows = []
    for g in gold.itertuples(index=False):
        p = pby.get((g.accession, g.raw_key))
        gq = {q for q in parse_qualifiers(g.qualifiers) if q[0] != "unit"}
        pq = {q for q in parse_qualifiers(p.qualifiers) if q[0] != "unit"} if p is not None else set()
        left, tp = list(pq), 0
        for q in gq:
            hit = next((x for x in left if qualifier_match(q, x, labels)), None)
            if hit is not None:
                left.remove(hit)
                tp += 1
        rows.append({"study": g.accession,
                     "both": int(p is not None and _clean(p.primary_curie) == _clean(g.primary_curie)
                                 and _clean(p.predicate) == _clean(g.predicate)),
                     "q_tp": tp, "q_pred": len(pq), "q_gold": len(gq)})
    return pd.DataFrame(rows)


def main() -> None:
    ws = Workspace(WS)
    labels = annotate.make_resolver(ws).ontology.label_map()
    gold = load_gold(ROOT / "eval/gold/ds_tuning_columns.tsv", ROOT / "eval/gold/ds_tuning_variables.tsv")
    corpus = S.Corpus("tuning", gold, list(zip(gold.accession, gold.raw_key)), None, [], {})
    corpus.studies = sorted(set(gold.accession))
    corpus.study = np.array([corpus.studies.index(a) for a in gold.accession])
    same_g = S.same_matrix(list(gold.variable_id))
    np.fill_diagonal(same_g, 0)

    lines = ["# annotate-3 vs annotate-2 on tuning (annotation alone)", "",
             "| prompt | run | qualifier precision / recall | primary term | term and predicate | pooling F1 | runs agree |",
             "|---|---|---|---|---|---|---|"]
    cols, sames = {}, {}
    for prompt, runs in PROMPTS.items():
        for run, pred in predictions(ws, runs).items():
            s = score(gold, pred, labels)
            a = s.annotation
            cols[(prompt, run)] = per_column(gold, pred, labels)
            same = S.same_matrix(S.partition(corpus, pred))
            np.fill_diagonal(same, 0)
            sames[(prompt, run)] = same
            lines.append(f"| {prompt} | {run} | {S.pct(a['qualifier_precision'])} / {S.pct(a['qualifier_recall'])} "
                         f"| {S.pct(a['primary_accuracy'])} | {S.pct(a['annotation_accuracy'])} "
                         f"| {S.pct(s.pooling['f1'])} | {S.pct(pred.agree.mean())} |")

    rng = np.random.default_rng(S.SEED)
    k = len(corpus.studies)
    W = S.draws(k, rng)

    def sums(c: pd.DataFrame, col: str) -> np.ndarray:
        return W @ np.bincount(corpus.study, weights=c[col].to_numpy(float), minlength=k)

    def metric(prompt: str, name: str):
        """(observed, bootstrap draws) for the mean of the prompt's two runs."""
        obs, draws = [], []
        for run in PROMPTS[prompt]:
            c = cols[(prompt, run)]
            if name == "qualifier precision":
                obs.append(c.q_tp.sum() / c.q_pred.sum())
                draws.append(sums(c, "q_tp") / sums(c, "q_pred"))
            elif name == "qualifier recall":
                obs.append(c.q_tp.sum() / c.q_gold.sum())
                draws.append(sums(c, "q_tp") / sums(c, "q_gold"))
            elif name == "term and predicate":
                obs.append(c.both.mean())
                draws.append(sums(c, "both") / (W @ np.bincount(corpus.study, minlength=k)))
            else:
                obs.append(S._f1(same_g, sames[(prompt, run)]))
                draws.append(S.prf(*S.totals(S.unit_matrices(corpus, same_g, sames[(prompt, run)], "study"), W))[2])
        return float(np.mean(obs)), np.mean(draws, axis=0)

    lines += ["", "annotate-3 minus annotate-2, mean of two runs each, paired bootstrap over studies:", "",
              "| metric | annotate-2 | annotate-3 | Δ, points | 95% CI |", "|---|---|---|---|---|"]
    for name in ("qualifier precision", "qualifier recall", "term and predicate", "pooling F1"):
        o2, d2 = metric("annotate-2", name)
        o3, d3 = metric("annotate-3", name)
        lo, hi = S.ci(d3 - d2)
        lines.append(f"| {name} | {S.pct(o2)} | {S.pct(o3)} | {S.pts(o3 - o2)} | {S.pts(lo)} to {S.pts(hi)} |")
    out = ROOT / "eval/prompts/out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "score.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
