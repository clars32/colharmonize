"""Shortlist GEO series for the genetic-syndromes demo and profile their characteristics.

    ./.venv/bin/python examples/genetic-syndromes/find_series.py

Read-only NCBI E-utilities search per syndrome (human, expression profiling,
10-250 samples), then each candidate's sample-level SOFT header (no data
tables) to see which characteristic keys it records. Writes candidates.json
here. Down syndrome series are excluded: they are colharmonize's tuning set.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
BRIEF = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}&targ=gsm&view=brief&form=text"
SYNDROMES = {
    "sex chromosome aneuploidy": '"Turner syndrome"[title] OR "Klinefelter"[title] OR "sex chromosome aneuploid*"[title] OR "47,XXY"[title] OR "45,X"[title]',
    "autosomal trisomy (not 21)": '"trisomy 18"[title] OR "trisomy 13"[title] OR "Edwards syndrome"[title] OR "Patau"[title]',
    "22q11.2 deletion": '"22q11"[title] OR "DiGeorge"[title] OR "velocardiofacial"[title]',
    "Williams syndrome": '"Williams syndrome"[title] OR "Williams-Beuren"[title] OR "7q11.23"[title]',
    "fragile X": '"fragile X"[title] OR "FMR1"[title]',
    "Rett syndrome": '"Rett"[title] OR "MECP2"[title]',
}
FILTER = ('AND "Homo sapiens"[porgn] AND gse[etyp] AND 2008:2025[pdat] '
          'AND ("expression profiling by array"[gdstype] OR "expression profiling by high throughput sequencing"[gdstype]) '
          'AND 10:250[n_samples]')
PER_AREA = 8


def get_json(path: str, **params) -> dict:
    with urllib.request.urlopen(EUTILS + path + "?" + urllib.parse.urlencode(params), timeout=60) as r:
        return json.load(r)


def profile(acc: str) -> dict:
    with urllib.request.urlopen(BRIEF.format(acc=acc), timeout=120) as r:
        text = r.read().decode("utf-8", "replace")
    keys: dict[str, Counter] = defaultdict(Counter)
    samples = text.split("^SAMPLE = ")[1:]
    channels = Counter()
    for s in samples:
        for line in s.splitlines():
            if line.startswith("!Sample_characteristics_ch1") and ": " in line:
                k, v = line.split(" = ", 1)[1].split(": ", 1)
                keys[k.strip()][v.strip()] += 1
            elif line.startswith("!Sample_channel_count"):
                channels[line.split(" = ", 1)[1]] += 1
    return {"n_samples": len(samples), "channels": dict(channels),
            "keys": {k: {"distinct": len(c), "top": c.most_common(5)} for k, c in keys.items()}}


def main() -> None:
    out = {}
    for area, q in SYNDROMES.items():
        ids = get_json("esearch.fcgi", db="gds", term=f"({q}) {FILTER}", retmax=40,
                       retmode="json")["esearchresult"]["idlist"]
        time.sleep(0.4)
        summ = get_json("esummary.fcgi", db="gds", id=",".join(ids), retmode="json")["result"] if ids else {}
        rows = []
        for uid in summ.get("uids", []):
            s = summ[uid]
            title = s["title"]
            if "down syndrome" in title.casefold() or "trisomy 21" in title.casefold():
                continue
            rows.append({"acc": s["accession"], "n": int(s["n_samples"]), "type": s["gdstype"],
                         "pdat": s["pdat"][:4], "title": title,
                         "superseries": "SubSeries" in json.dumps(s.get("relations", []))})
        time.sleep(0.4)
        for r in rows[:PER_AREA]:
            try:
                r["profile"] = profile(r["acc"])
            except Exception as error:   # a profile that fails to load is just skipped
                r["profile"] = {"error": repr(error)}
            time.sleep(0.5)
        out[area] = rows[:PER_AREA]
    (HERE / "candidates.json").write_text(json.dumps(out, indent=1))
    for area, rows in out.items():
        print(f"\n== {area}")
        for r in rows:
            p = r["profile"]
            keys = "; ".join(f"{k}({v['distinct']})" for k, v in p.get("keys", {}).items())
            print(f"{r['acc']:10} n={r['n']:3} {r['pdat']} {'seq' if 'sequencing' in r['type'] else 'arr'} "
                  f"{'SUPER' if r['superseries'] else '     '} {r['title'][:70]} | {keys[:160]}")


if __name__ == "__main__":
    main()
