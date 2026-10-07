"""Score predictions against the sealed gold (pre-registered metrics).

    python eval/sealed/score.py WORKSPACE PREDICTIONS.tsv TITLE [OUT.md]

Run columns are mapped back to gold keys with WORKSPACE/key_map.json
(eval/sealed/align.py). Baseline predictions already use gold keys.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize.evaluate import load_gold, report, score  # noqa: E402
from colharmonize.ontology import Ontology  # noqa: E402


def main(workspace: str, predictions: str, title: str, out: str | None = None) -> None:
    ws = Path(workspace)
    gold = load_gold(ROOT / "eval/gold/generalization_columns.tsv", ROOT / "eval/gold/generalization_variables.tsv")
    pred = pd.read_csv(predictions, sep="\t", dtype=str, keep_default_na=False)
    km_path = ws / "key_map.json"
    if km_path.exists():
        back = {(k.split("\t")[0], v): k.split("\t")[1] for k, v in json.loads(km_path.read_text()).items()}
        pred["raw_key"] = [back.get((a, k), k) for a, k in zip(pred.accession, pred.raw_key)]
    labels = None
    settings = ws / "workspace.json"
    if settings.exists() and "ontology" in json.loads(settings.read_text()):
        onto = Ontology.from_dir(json.loads(settings.read_text())["ontology"])
        labels = dict(zip(onto.terms.curie, onto.terms.label))
    text = report(score(gold, pred, labels), title)
    if out:
        Path(out).write_text(text)
    print(text)


if __name__ == "__main__":
    main(*sys.argv[1:5])
