"""Score same-model vs cross-model annotation agreement (PROTOCOL.md).

    ./.venv/bin/python eval/models/score.py

Reads the annotate runs in work/ds-tuning-models and work/sealed-models (nothing
is written there) and writes eval/models/out/score.md.
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
from colharmonize.evaluate import _clean, load_gold  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402
from stats import auc, ci, pct  # noqa: E402

B = 5000
SEED = 20261009
CORPORA = {
    "tuning": {"ws": "work/ds-tuning-models", "gold": "ds_tuning", "record": 3, "same": 4, "cross": 5},
    "sealed (post hoc)": {"ws": "work/sealed-models", "gold": "generalization", "record": 1, "same": 2, "cross": 3},
}
MODEL = {"record": "Sonnet", "same": "Sonnet", "cross": "Opus"}


def resolved(ws: Workspace, run: int, resolver) -> pd.DataFrame:
    got = tasks.collect(ws.tasks(annotate.STAGE, run), annotate.AnnotateAnswer)
    got.problems += annotate.validate_answers(ws, got.answers, run=run, resolver=resolver)
    if not got.complete:
        sys.exit(json.dumps({"workspace": str(ws.root), "run": run, "pending": got.pending,
                             "problems": got.problems}, indent=1, default=str))
    return annotate.resolve_run(ws, got.answers, run, resolver).set_index(["study_id", "column"])


def main() -> None:
    rng = np.random.default_rng(SEED)
    lines = ["# Same-model vs cross-model annotation agreement", "",
             "Outcome: the run of record (Sonnet) is right on primary term and predicate. "
             "\"Agree\": the partner run gives the same primary term and predicate. "
             f"95% CIs by paired bootstrap over studies ({B:,} resamples).", ""]
    for corpus, spec in CORPORA.items():
        ws = Workspace(ROOT / spec["ws"])
        resolver = annotate.make_resolver(ws)
        runs = {role: resolved(ws, spec[role], resolver) for role in ("record", "same", "cross")}
        gold = load_gold(ROOT / f"eval/gold/{spec['gold']}_columns.tsv", ROOT / f"eval/gold/{spec['gold']}_variables.tsv")
        km = json.loads((ws.root / "key_map.json").read_text())
        to_run = {tuple(k.split("\t")): v for k, v in km.items()}
        rows = []
        for g in gold.itertuples(index=False):
            key = (g.accession, to_run.get((g.accession, g.raw_key), g.raw_key))
            if key not in runs["record"].index:
                continue
            ann = {role: runs[role].loc[key] for role in runs}
            right = {role: _clean(a.primary_curie) == _clean(g.primary_curie) and _clean(a.predicate) == _clean(g.predicate)
                     for role, a in ann.items()}
            same_as = {role: _clean(a.primary_curie) == _clean(ann["record"].primary_curie)
                       and _clean(a.predicate) == _clean(ann["record"].predicate) for role, a in ann.items()}
            rows.append({"study": g.accession, "right": int(right["record"]), "right_same": int(right["same"]),
                         "right_cross": int(right["cross"]), "agree_same": int(same_as["same"]),
                         "agree_cross": int(same_as["cross"]),
                         "agree_both": int(same_as["same"]) + int(same_as["cross"])})
        df = pd.DataFrame(rows)
        y = df.right.to_numpy()
        lines += [f"## {corpus}: {len(df)} gold columns", "",
                  "| partner | partner's own accuracy | runs agree on | right where they agree | wrong answers flagged | AUC |",
                  "|---|---|---|---|---|---|"]
        aucs = {}
        for role, col in (("same", "agree_same"), ("cross", "agree_cross")):
            x = df[col].to_numpy()
            aucs[role] = auc(x.astype(float), y)
            right_agree = y[x == 1].mean() if (x == 1).any() else float("nan")
            flagged = (x[y == 0] == 0).mean() if (y == 0).any() else float("nan")
            lines.append(f"| {MODEL[role]} run {spec[role]} ({'same model' if role == 'same' else 'cross model'}) "
                         f"| {pct(df[f'right_{role}'].mean())} | {pct(x.mean())} | {pct(right_agree)} "
                         f"| {pct(flagged)} ({int((x[y == 0] == 0).sum())} of {int((y == 0).sum())}) | {aucs[role]:.2f} |")
        x3 = df.agree_both.to_numpy().astype(float)
        a3 = auc(x3, y)
        lines.append(f"| both, as a count 0–2 (exploratory) | — | all three agree on {pct((x3 == 2).mean())} "
                     f"| {pct(y[x3 == 2].mean())} where all agree | {pct((x3[y == 0] < 2).mean())} | {a3:.2f} |")

        studies = sorted(set(df.study))
        idx = {s: np.flatnonzero(df.study.to_numpy() == s) for s in studies}
        diffs = []
        for _ in range(B):
            take = np.concatenate([idx[s] for s in rng.choice(studies, len(studies))])
            yb = y[take]
            diffs.append(auc(df.agree_cross.to_numpy()[take].astype(float), yb)
                         - auc(df.agree_same.to_numpy()[take].astype(float), yb))
        lo, hi = ci(np.array(diffs))
        lines += ["", f"Run of record (Sonnet run {spec['record']}) accuracy: {pct(y.mean())}. "
                  f"AUC, cross minus same: {aucs['cross'] - aucs['same']:+.2f} (95% CI {lo:+.2f} to {hi:+.2f}).", ""]
    out = ROOT / "eval/models/out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "score.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
