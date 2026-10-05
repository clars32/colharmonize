"""Search the pinned EFO v3.94.0 index (allowlisted, non-deprecated) by label/synonym substring."""
import sys
from pathlib import Path
import pandas as pd
IX = Path(__file__).resolve().parents[3] / "efo-column-mapping/data/ontology/efo_index_v3.94.0.parquet"
ALLOW = {"EFO","UBERON","CL","MONDO","PATO","NCIT","OBI","CHEBI","UO"}
ix = pd.read_parquet(IX)
ix = ix[(~ix.deprecated) & ix.prefix.isin(ALLOW)].copy()
def syn(r):
    out=[]
    for c in ("exact_synonyms","related_synonyms"):
        v=r[c]
        if v is not None and len(v): out += list(v)
    return out
ix["syns"] = ix.apply(syn, axis=1)
ix["lab"] = ix.label.str.lower()
def search(q, n=8):
    ql = q.lower()
    exact = ix[(ix.lab == ql) | ix.syns.apply(lambda s: any(x.lower()==ql for x in s))]
    sub = ix[ix.lab.str.contains(ql, regex=False) & ~ix.index.isin(exact.index)]
    sub = sub.assign(L=sub.lab.str.len()).sort_values("L").head(n)
    rows = [("=", r) for _, r in exact.iterrows()] + [("~", r) for _, r in sub.iterrows()]
    return rows
if __name__ == "__main__":
    for q in sys.argv[1:]:
        res = search(q)
        print(f"[{q}] " + (" | ".join(f"{m}{r.curie} {r.label}" for m, r in res[:9]) if res else "— none"))
