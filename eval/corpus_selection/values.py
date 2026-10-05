"""Full distinct values, per-sample key coverage and titles for the sealed corpus (metadata only)."""
import csv, json, time, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent
from collections import Counter, defaultdict
URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}&targ=gsm&view=brief&form=text"
accs = [r["accession"] for r in csv.DictReader(open(HERE.parent / "generalization_corpus.tsv"), delimiter="\t")]
out = {}
for acc in accs:
    text = urllib.request.urlopen(URL.format(acc=acc), timeout=120).read().decode("utf-8", "replace")
    samples = {}
    for block in text.split("^SAMPLE = ")[1:]:
        gsm = block.split("\n", 1)[0].strip()
        rec = {"title": "", "source": "", "chars": [], "unparsed": []}
        for line in block.splitlines():
            if " = " not in line: continue
            tag, val = line.split(" = ", 1)
            if tag == "!Sample_title": rec["title"] = val
            elif tag == "!Sample_source_name_ch1": rec["source"] = val
            elif tag.startswith("!Sample_characteristics_ch"):
                if ":" in val:
                    k, v = val.split(":", 1); rec["chars"].append([k.strip(), v.strip()])
                else: rec["unparsed"].append(val)
        samples[gsm] = rec
    keys = defaultdict(Counter); cover = defaultdict(set)
    for gsm, rec in samples.items():
        for k, v in rec["chars"]:
            keys[k][v] += 1; cover[k].add(gsm)
    ks = list(keys)
    cooc = {f"{a} || {b}": len(cover[a] & cover[b]) for i, a in enumerate(ks) for b in ks[i+1:]}
    out[acc] = {"n": len(samples), "keys": {k: dict(c.most_common()) for k, c in keys.items()},
                "coverage": {k: len(v) for k, v in cover.items()},
                "disjoint_pairs": [p for p, n in cooc.items() if n == 0],
                "titles": [r["title"] for r in samples.values()],
                "sources": dict(Counter(r["source"] for r in samples.values())),
                "unparsed": sum(len(r["unparsed"]) for r in samples.values())}
    time.sleep(0.6)
json.dump(out, open(HERE / "values.json", "w"), indent=1)
for acc, d in out.items():
    print(acc, d["n"], "keys", len(d["keys"]), "disjoint pairs", len(d["disjoint_pairs"]), "unparsed", d["unparsed"])
