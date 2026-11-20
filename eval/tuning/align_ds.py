"""Map tuning-gold column keys to the column names a pipeline run produced.

Characteristic columns keep their raw names, so they map to themselves. Columns
recovered from titles, source names or an unparsed characteristic get whatever
name the repair subagent chose (`title#sample number` for iteration 2's
`title#replicate`). Each such gold column is matched to the run's column whose
per-sample values agree with it most, accepted only when at least 70% of the
gold column's samples agree. Values agree when, after normalisation, they are
equal, or the words of one are whole words of the other and cover at least 60%
of them, or 50% when the shared words include numbers ("18-19" vs "18-19 weeks
gestation", the unit having moved into the column name). "AMKL" does not agree
with "AMKL024", and "fetal" alone does not stand in for "fetal cerebrum".

Gold per-sample values come from iteration 2's harvest and title extraction,
which is what the tuning gold was curated against.

Usage: python eval/tuning/align_ds.py WORKSPACE   -> WORKSPACE/key_map.json
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from colharmonize import metamend_bridge as gb, profile  # noqa: E402
from colharmonize.workspace import Workspace  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
IT2 = ROOT.parent / "efo-column-mapping/data/interim"
MIN_AGREEMENT = 0.7


def norm(v: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(v).casefold()).strip()


def agrees(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = a.split(), b.split()
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    # A numeric value whose unit moved into the column name ("18-19" for
    # "18-19 weeks gestation") keeps half the words and all the numbers.
    floor = 0.5 if any(ch.isdigit() for ch in " ".join(short)) else 0.6
    return set(short) <= set(long_) and len(short) / len(long_) >= floor


def gold_values() -> pd.DataFrame:
    ml = pd.read_parquet(IT2 / "metadata_long.parquet")
    ml = ml[ml.source_field.str.startswith("characteristics") & ml.parsed][["gse", "gsm", "raw_key", "raw_value"]]
    te = pd.read_parquet(IT2 / "title_extracted.parquet")
    te = te.assign(raw_key=[f"{'title' if d == 'title' else 'source_name'}#{k}" for k, d in zip(te.raw_key, te.derived_from)])
    return pd.concat([ml, te[["gse", "gsm", "raw_key", "raw_value"]]], ignore_index=True)


def run_values(ws: Workspace) -> pd.DataFrame:
    chars = gb.sample_values(ws.metamend)[["study_id", "sample_id", "name", "value"]]
    chars = chars.rename(columns={"name": "column"})
    parts = [chars]
    if ws.derived.exists():
        parts.append(pd.read_parquet(ws.derived)[["study_id", "sample_id", "column", "value"]])
    return pd.concat(parts, ignore_index=True)


def main(workspace: str) -> None:
    ws = Workspace(workspace)
    gold = pd.read_csv(ROOT / "eval/gold/ds_tuning_columns.tsv", sep="\t", dtype=str, keep_default_na=False)
    annotated = set(zip(*profile.annotation_columns(ws)[["study_id", "column"]].T.values))
    gv, rv = gold_values(), run_values(ws)
    key_map, report = {}, []
    for r in gold.itertuples(index=False):
        if (r.accession, r.raw_key) in annotated:
            continue
        g = gv[(gv.gse == r.accession) & (gv.raw_key == r.raw_key)]
        best = None
        for col, grp in rv[rv.study_id == r.accession].groupby("column"):
            if (r.accession, col) not in annotated:
                continue
            m = g.merge(grp, left_on="gsm", right_on="sample_id")
            agree = sum(agrees(a, b) for a, b in zip(m.raw_value.map(norm), m.value.map(norm)))
            share = agree / len(g) if len(g) else 0
            if best is None or share > best[1]:
                best = (col, share)
        if best and best[1] >= MIN_AGREEMENT:
            key_map[f"{r.accession}\t{r.raw_key}"] = best[0]
        report.append((r.accession, r.raw_key, best[0] if best else None, round(best[1], 2) if best else 0))
    (ws.root / "key_map.json").write_text(json.dumps(key_map, indent=1))
    for row in report:
        print("{:10} {:42} -> {} ({})".format(*row))


if __name__ == "__main__":
    main(sys.argv[1])
