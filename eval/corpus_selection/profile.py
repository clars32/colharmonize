"""Fetch sample-level SOFT metadata (no data tables) for candidate series and profile characteristics keys."""
from pathlib import Path
import json, re, sys, time, urllib.request
from collections import defaultdict, Counter

CANDIDATES = {
 "breast_cancer": "GSE192341 GSE181466 GSE167213 GSE147472 GSE126870 GSE129551 GSE131027 GSE58984 GSE87377 GSE65095 GSE149322 GSE297605 GSE280902 GSE237290".split(),
 "sepsis": "GSE272769 GSE279448 GSE154918 GSE137340 GSE119217 GSE131411 GSE69063 GSE216902 GSE110487".split(),
 "ibd": "GSE206171 GSE117993 GSE75214 GSE87466 GSE166925 GSE158952 GSE112057 GSE282580 GSE92415".split(),
 "t2d": "GSE164416 GSE152111 GSE201087 GSE189007 GSE117339 GSE245948 GSE104674 GSE231509".split(),
}
URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}&targ=gsm&view=brief&form=text"

def fetch(acc):
    with urllib.request.urlopen(URL.format(acc=acc), timeout=120) as r:
        return r.read().decode("utf-8", "replace")

def profile(text):
    samples = text.split("^SAMPLE = ")[1:]
    keys = defaultdict(Counter); unparsed = 0; channels = Counter(); src = Counter(); titles = []
    for s in samples:
        for line in s.splitlines():
            if line.startswith("!Sample_characteristics_ch"):
                v = line.split(" = ", 1)[1] if " = " in line else ""
                if ":" in v:
                    k, val = v.split(":", 1); keys[k.strip()][val.strip()] += 1
                else:
                    unparsed += 1
            elif line.startswith("!Sample_channel_count"):
                channels[line.split(" = ",1)[1]] += 1
            elif line.startswith("!Sample_source_name_ch1"):
                src[line.split(" = ",1)[1]] += 1
            elif line.startswith("!Sample_title"):
                titles.append(line.split(" = ",1)[1])
    return {"n_samples": len(samples), "channels": dict(channels), "unparsed": unparsed,
            "keys": {k: {"n": sum(c.values()), "distinct": len(c), "top": c.most_common(4)} for k, c in keys.items()},
            "source_names": src.most_common(3), "title_examples": titles[:3]}

out = {}
for area, accs in CANDIDATES.items():
    for acc in accs:
        try:
            out[acc] = {"area": area, **profile(fetch(acc))}
        except Exception as e:
            out[acc] = {"area": area, "error": repr(e)}
        time.sleep(0.6)
json.dump(out, open(Path(__file__).resolve().parent / "profiles.json", "w"), indent=1)
for acc, p in out.items():
    if "error" in p: print(acc, p["area"], "ERROR", p["error"]); continue
    ks = "; ".join(f"{k}({v['distinct']})" for k, v in p["keys"].items())
    print(f"{acc:10} {p['area'][:6]:6} n={p['n_samples']:4} ch={','.join(p['channels'])} keys={len(p['keys']):2} unparsed={p['unparsed']:3} | {ks[:230]}")
