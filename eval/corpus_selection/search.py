"""Shortlist GEO series per disease area via NCBI E-utilities (read-only)."""
from pathlib import Path
import json, sys, time, urllib.parse, urllib.request

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
AREAS = {
    "breast_cancer": '"breast cancer"[title] OR "breast tumor"[title]',
    "sepsis": 'sepsis[title] OR "septic shock"[title]',
    "ibd": '"Crohn"[title] OR "ulcerative colitis"[title] OR "inflammatory bowel"[title]',
    "t2d": '"type 2 diabetes"[title] OR "islet"[title] OR "insulin resistance"[title]',
}
FILTER = ('AND "Homo sapiens"[porgn] AND gse[etyp] AND 2016:2025[pdat] '
          'AND ("expression profiling by array"[gdstype] OR "expression profiling by high throughput sequencing"[gdstype]) '
          'AND 30:250[n_samples]')

def get(path, **params):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)

out = {}
for area, q in AREAS.items():
    term = f"({q}) {FILTER}"
    ids = get("esearch.fcgi", db="gds", term=term, retmax=60, retmode="json")["esearchresult"]["idlist"]
    time.sleep(0.4)
    summ = get("esummary.fcgi", db="gds", id=",".join(ids), retmode="json")["result"] if ids else {}
    rows = []
    for uid in summ.get("uids", []):
        s = summ[uid]
        rows.append({"acc": s["accession"], "n": int(s["n_samples"]), "gpl": s["gpl"],
                     "type": s["gdstype"], "pdat": s["pdat"], "title": s["title"],
                     "subseries": "SubSeries" in json.dumps(s.get("relations", []))})
    out[area] = rows
    time.sleep(0.4)
json.dump(out, open(Path(__file__).resolve().parent / "search_results.json", "w"), indent=1)
for area, rows in out.items():
    print(f"\n== {area}: {len(rows)}")
    for r in rows[:60]:
        t = "RNAseq" if "sequencing" in r["type"] else "array"
        print(f"{r['acc']:10} n={r['n']:4} {t:6} GPL{r['gpl'][:12]:12} {r['pdat'][:4]} {r['title'][:95]}")
