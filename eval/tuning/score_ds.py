"""Score a tuning workspace against the Down syndrome tuning gold.

Candidate recall (is the gold term retrievable?) and, when predictions.tsv
exists, pooling and annotation scores. Gold keys are mapped to the run's column
names with key_map.json from align_ds.py.

Usage: python eval/tuning/score_ds.py WORKSPACE [PREDICTIONS_FILE]
(default predictions_reconcile.tsv if present, else predictions_annotate.tsv)
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize.candidates import evaluate_recall  # noqa: E402
from colharmonize.evaluate import load_gold, report, score  # noqa: E402
from colharmonize.ontology import Ontology  # noqa: E402


def main(workspace: str, predictions: str | None = None) -> None:
    ws = Path(workspace)
    gold = load_gold(ROOT / "eval/gold/ds_tuning_columns.tsv", ROOT / "eval/gold/ds_tuning_variables.tsv")
    km = {tuple(k.split("\t")): v for k, v in json.loads((ws / "key_map.json").read_text()).items()}
    key_map = {k: (k[0], v) for k, v in km.items()}
    rec = evaluate_recall(pd.read_parquet(ws / "candidates.parquet"), gold, key_map)
    print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rec.items() if k != "primary_misses"}, indent=1))
    for m in rec["primary_misses"]:
        print("  not retrieved:", *m)
    names = [predictions] if predictions else ["predictions_reconcile.tsv", "predictions_annotate.tsv"]
    pred_path = next((ws / n for n in names if (ws / n).exists()), ws / names[0])
    if pred_path.exists():
        pred = pd.read_csv(pred_path, sep="\t", dtype=str, keep_default_na=False)
        back = {(a, v): k[1] for k, (a, v) in key_map.items()}
        pred["raw_key"] = [back.get((a, k), k) for a, k in zip(pred.accession, pred.raw_key)]
        settings = json.loads((ws / "workspace.json").read_text())
        onto = Ontology.from_dir(settings["ontology"])
        labels = dict(zip(onto.terms.curie, onto.terms.label))
        text = report(score(gold, pred, labels), f"Tuning workspace {ws.name} vs tuning gold")
        (ws / f"score_{pred_path.stem}.md").write_text(text)
        print(text)


if __name__ == "__main__":
    main(*sys.argv[1:3])
