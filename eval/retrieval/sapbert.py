"""Does SapBERT as a third embedding model raise candidate recall? (handoff task 11)

    ./.venv/bin/python eval/retrieval/sapbert.py

Regenerates candidates in memory, without writing to either workspace, with
the pipeline's two models (control, which must reproduce the recorded tuning
recall) and with SapBERT added as a third. SapBERT
(cambridgeltl/SapBERT-from-PubMedBERT-fulltext) is used with [CLS] pooling,
as its authors do. ZOOMA/OLS4 results come from the shared cache only, as in
the recorded runs. Writes eval/retrieval/out/sapbert.md. Sealed is post hoc.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize import candidates as cd, preprocess, profile, property_space  # noqa: E402
from colharmonize.evaluate import load_gold  # noqa: E402
from colharmonize.ontology import Ontology  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402

SAPBERT = ("sap", "cambridgeltl/SapBERT-from-PubMedBERT-fulltext", "")
CORPORA = {
    "tuning": ("work/ds-tuning", "ds_tuning"),
    "sealed (post hoc)": ("work/sealed", "generalization"),
}
_plain_encoder = cd.TermIndex._encoder


def _encoder(self, repo: str):
    """[CLS] pooling for SapBERT; every other model loads as before."""
    if repo == SAPBERT[1] and repo not in self._enc:
        from sentence_transformers import SentenceTransformer, models
        word = models.Transformer(repo, max_seq_length=64)
        self._enc[repo] = SentenceTransformer(modules=[word, models.Pooling(word.get_word_embedding_dimension(),
                                                                            pooling_mode="cls")])
    return _plain_encoder(self, repo)


cd.TermIndex._encoder = _encoder


def recall(ws_dir: str, gold_prefix: str, model_set: list) -> dict:
    ws = Workspace(ROOT / ws_dir)
    onto = Ontology.from_dir(ws.ontology_dir())
    retriever = cd.Retriever(onto, property_space.build(onto), ROOT / "work/cache/embeddings",
                             cd.RemoteCache(ROOT / "work/cache/remote.json", enabled=False))
    retriever.space_ix.models = model_set     # the entity index is queried with the same models
    cands = cd.generate(retriever, profile.annotation_columns(ws), preprocess.hints(ws))
    gold = load_gold(ROOT / f"eval/gold/{gold_prefix}_columns.tsv", ROOT / f"eval/gold/{gold_prefix}_variables.tsv")
    km = {tuple(k.split("\t")): v for k, v in json.loads((ws.root / "key_map.json").read_text()).items()}
    key_map = {k: (k[0], v) for k, v in km.items()}
    rec = cd.evaluate_recall(cands, gold, key_map)
    rec["n_candidates"] = len(cands)
    rec["n_displayed"] = int(cands.displayed.sum())
    rec["shown_at_cap"] = shown_at_caps(cands, gold, key_map)
    return rec


CAPS = (40, 50, 60)   # property-space terms shown; the entity cap stays at its 16


def shown_at_caps(cands: pd.DataFrame, gold: pd.DataFrame, key_map: dict) -> dict[int, float]:
    """Gold primary terms that would be shown if the property-space display cap were larger.

    Candidates come out of `generate` in display order within each (column, pool).
    """
    pos = {}
    for (study, column, pool), g in cands.groupby(["study_id", "column", "pool"], sort=False):
        for i, c in enumerate(g.curie):
            pos[(study, column, c)] = (pool, i)
    out = {}
    for cap in CAPS:
        hit = n = 0
        for row in gold.itertuples(index=False):
            if not row.primary_curie:
                continue
            n += 1
            study, column = key_map.get((row.accession, row.raw_key), (row.accession, row.raw_key))
            p = pos.get((study, column, row.primary_curie))
            hit += p is not None and p[1] < (cap if p[0] == "space" else cd.DISPLAY_ENTITY if p[0] == "entity" else 10)
        out[cap] = hit / n
    return out


def main() -> None:
    rows = []
    for corpus, (ws_dir, gold_prefix) in CORPORA.items():
        for label, model_set in (("mini + bge (pipeline)", cd.MODELS), ("mini + bge + SapBERT", cd.MODELS + [SAPBERT])):
            t = time.time()
            r = recall(ws_dir, gold_prefix, model_set)
            rows.append({"corpus": corpus, "models": label, **{k: r[k] for k in (
                "primary_pool_recall", "primary_displayed_recall", "qualifier_pool_recall",
                "qualifier_displayed_recall", "n_primary", "n_candidates", "n_displayed", "shown_at_cap")},
                "misses": "; ".join(f"{m[0]}/{m[1]}" for m in r["primary_misses"]), "seconds": round(time.time() - t)})
            print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    lines = ["# SapBERT as a third embedding model: candidate recall", "",
             "| corpus | models | gold term in pool | gold term shown | qualifiers in pool / shown | candidates (shown) |",
             "|---|---|---|---|---|---|"]
    for r in df.itertuples(index=False):
        lines.append(f"| {r.corpus} | {r.models} | {100 * r.primary_pool_recall:.1f}% | {100 * r.primary_displayed_recall:.1f}% "
                     f"| {100 * r.qualifier_pool_recall:.1f}% / {100 * r.qualifier_displayed_recall:.1f}% "
                     f"| {r.n_candidates} ({r.n_displayed}) |")
    lines += ["", "Gold term shown if the property-space display cap were larger (entity cap 16):", "",
              "| corpus | models | " + " | ".join(f"cap {c}" for c in CAPS) + " |", "|---|---|" + "---|" * len(CAPS)]
    for r in df.itertuples(index=False):
        lines.append(f"| {r.corpus} | {r.models} | " + " | ".join(f"{100 * r.shown_at_cap[c]:.1f}%" for c in CAPS) + " |")
    lines += ["", "Gold primary terms not retrieved (study/gold column):", ""]
    lines += [f"- {r.corpus}, {r.models}: {r.misses or 'none'}" for r in df.itertuples(index=False)]
    out = ROOT / "eval/retrieval/out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sapbert.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
