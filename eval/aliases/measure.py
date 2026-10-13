"""Does an alias dictionary raise candidate recall? (handoff task 10; PROTOCOL.md)

    ./.venv/bin/python eval/aliases/measure.py

Regenerates candidates in memory, writing to neither workspace: once with the
pipeline as it is (control, which must reproduce the recorded tuning recall)
and once with eval/aliases/aliases.json added to the property-space index as
two new sources, `alias_exact` and `<model>_alias`. ZOOMA/OLS4 results come
from the shared cache only, as in the recorded runs. Sealed is post hoc.
Writes eval/aliases/out/recall.md.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from colharmonize import candidates as cd, preprocess, profile, property_space  # noqa: E402
from colharmonize.evaluate import load_gold  # noqa: E402
from colharmonize.ontology import Ontology  # noqa: E402
from colharmonize.text import loose  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402

CORPORA = {
    "tuning": ("work/ds-tuning", "ds_tuning"),
    "sealed (post hoc)": ("work/sealed", "generalization"),
}


class AliasRetriever(cd.Retriever):
    """The pipeline's retriever plus an alias index over the property space."""

    aliases: dict[str, list[str]] = {}
    embed = True                      # False: exact alias matches only (exploratory)

    def __post_init__(self) -> None:
        super().__post_init__()
        rows = [(curie, alias) for curie, names in sorted(self.aliases.items()) for alias in names
                if curie in self.in_space]
        self.alias_curies = [c for c, _ in rows]
        self.alias_text = [a for _, a in rows]
        self.alias_lut: dict[str, set[str]] = defaultdict(set)
        for curie, alias in rows:
            self.alias_lut[loose(alias)].add(curie)
        self.alias_ix = cd.TermIndex(pd.DataFrame({"curie": self.alias_curies, "label": self.alias_text}),
                                     "space-alias", self.cache_dir)

    def for_column(self, column, values, unit, hints=None):
        found = {c["curie"]: c for c in super().for_column(column, values, unit, hints)}

        def add(curie: str, source: str, rank: int) -> None:
            c = found.setdefault(curie, {"curie": curie, "pool": "space", "sources": {}})
            c["sources"].setdefault(source, rank)

        forms = cd.name_forms(column)
        hits = sorted(self.alias_lut.get(loose(forms["plain"]), set()) | self.alias_lut.get(loose(forms["raw"]), set()))
        for rank, curie in enumerate(hits, 1):
            add(curie, "alias_exact", rank)
        for tag, repo, prefix in (self.space_ix.models if self.embed else []):
            query = self.alias_ix.encode(repo, prefix, [forms["plain"]])[0]
            sims = self.alias_ix.matrix(tag, repo) @ query
            rank = 0
            for i in np.argsort(-sims):
                curie = self.alias_curies[i]
                if f"{tag}_alias" in found.get(curie, {}).get("sources", {}):
                    continue                  # rank unique terms by their best alias
                rank += 1
                add(curie, f"{tag}_alias", rank)
                if rank >= cd.TOPK_SPACE:
                    break
        return list(found.values())


class ExactAliasRetriever(AliasRetriever):
    embed = False


def recall(ws_dir: str, gold_prefix: str, retriever_class) -> tuple[dict, pd.DataFrame]:
    ws = Workspace(ROOT / ws_dir)
    onto = Ontology.from_dir(ws.ontology_dir())
    retriever = retriever_class(onto, property_space.build(onto), ROOT / "work/cache/embeddings",
                                cd.RemoteCache(ROOT / "work/cache/remote.json", enabled=False))
    cands = cd.generate(retriever, profile.annotation_columns(ws), preprocess.hints(ws))
    gold = load_gold(ROOT / f"eval/gold/{gold_prefix}_columns.tsv", ROOT / f"eval/gold/{gold_prefix}_variables.tsv")
    km = {tuple(k.split("\t")): v for k, v in json.loads((ws.root / "key_map.json").read_text()).items()}
    key_map = {k: (k[0], v) for k, v in km.items()}
    rec = cd.evaluate_recall(cands, gold, key_map)
    rec["n_candidates"] = len(cands)
    rec["n_displayed"] = int(cands.displayed.sum())
    shown = set()
    for row in gold.itertuples(index=False):
        if row.primary_curie:
            key = key_map.get((row.accession, row.raw_key), (row.accession, row.raw_key))
            hit = cands[(cands.study_id == key[0]) & (cands.column == key[1]) & cands.displayed]
            if row.primary_curie in set(hit.curie):
                shown.add((row.accession, row.raw_key))
    rec["shown"] = shown
    return rec, cands


def main() -> None:
    AliasRetriever.aliases = json.loads((ROOT / "eval/aliases/aliases.json").read_text())
    rows, notes = [], []
    for corpus, (ws_dir, gold_prefix) in CORPORA.items():
        results = {}
        for label, cls in (("pipeline", cd.Retriever), ("pipeline + aliases", AliasRetriever),
                           ("pipeline + exact aliases only (exploratory)", ExactAliasRetriever)):
            t = time.time()
            rec, cands = recall(ws_dir, gold_prefix, cls)
            results[label] = rec
            alias_sourced = cands.sources.str.contains("_alias").sum()
            rows.append({"corpus": corpus, "retrieval": label, **{k: rec[k] for k in (
                "primary_pool_recall", "primary_displayed_recall", "n_primary", "n_candidates", "n_displayed")},
                "alias_candidates": int(alias_sourced), "seconds": round(time.time() - t)})
            print(rows[-1], flush=True)
        base = results["pipeline"]
        for label in ("pipeline + aliases", "pipeline + exact aliases only (exploratory)"):
            alias = results[label]
            pool_gain = {(a, k) for a, k, _ in base["primary_misses"]} - {(a, k) for a, k, _ in alias["primary_misses"]}
            pool_loss = {(a, k) for a, k, _ in alias["primary_misses"]} - {(a, k) for a, k, _ in base["primary_misses"]}
            notes += [f"- {corpus}, {label}: newly in pool {sorted(pool_gain) or 'none'}; "
                      f"lost from pool {sorted(pool_loss) or 'none'}",
                      f"- {corpus}, {label}: newly shown {sorted(alias['shown'] - base['shown']) or 'none'}; "
                      f"no longer shown {sorted(base['shown'] - alias['shown']) or 'none'}"]
    df = pd.DataFrame(rows)
    lines = ["# Alias dictionary: candidate recall", "",
             "| corpus | retrieval | gold term in pool | gold term shown | gold terms | candidates (shown) | from aliases |",
             "|---|---|---|---|---|---|---|"]
    for r in df.itertuples(index=False):
        lines.append(f"| {r.corpus} | {r.retrieval} | {100 * r.primary_pool_recall:.1f}% | "
                     f"{100 * r.primary_displayed_recall:.1f}% | {r.n_primary} | {r.n_candidates} ({r.n_displayed}) "
                     f"| {r.alias_candidates} |")
    lines += ["", "Gold columns that change (accession, gold column):", "", *notes]
    out = ROOT / "eval/aliases/out"
    out.mkdir(exist_ok=True)
    (out / "recall.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
