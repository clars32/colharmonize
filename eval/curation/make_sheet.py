"""Build the blind curation sheet for an independent annotator.

    ./.venv/bin/python eval/curation/make_sheet.py

Handoff task 6. Writes `eval/curation/curation_sheet.xlsx` from the raw SOFT
files of the series named in `SERIES` (chosen by `select_series`, see
PROTOCOL.md). The sheet holds only what a curator would see in GEO: series
text, column names, values and sample coverage. It never reads the gold or any
pipeline output.
"""
from __future__ import annotations

import gzip
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "work/sealed/raw"
OUT = ROOT / "eval/curation/curation_sheet.xlsx"
SNAPSHOT = ROOT / "eval/snapshots/generalization_characteristics.json"

MAX_VALUES = 25
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")

FONT = "Arial"
HEAD = Font(name=FONT, bold=True)
BODY = Font(name=FONT)
EXAMPLE = Font(name=FONT, italic=True, color="808080")
FILL_INPUT = PatternFill("solid", fgColor="FFFF99")
FILL_HEAD = PatternFill("solid", fgColor="D9D9D9")
WRAP = Alignment(wrap_text=True, vertical="top")

ANNOTATION_FIELDS = ["variable", "primary term", "predicate", "subject", "object_class",
                     "event_time_anchor", "method", "unit", "assumed convention", "note"]


def select_series() -> list[str]:
    """The rule in PROTOCOL.md: 5 sealed series, 35-45 gold columns, at least
    3 disease areas, no title or split columns, most cross-series gold pairs.

    Reads the gold only to choose which series to show; nothing from the gold
    reaches the sheet.
    """
    sys.path.insert(0, str(ROOT / "src"))
    from colharmonize.evaluate import load_gold

    gold = load_gold(ROOT / "eval/gold/generalization_columns.tsv", ROOT / "eval/gold/generalization_variables.tsv")
    raw = pd.read_csv(ROOT / "eval/gold/generalization_columns.tsv", sep="\t", dtype=str, keep_default_na=False)
    area = dict(pd.read_csv(ROOT / "eval/generalization_corpus.tsv", sep="\t")[["accession", "area"]].values)
    derived = set(raw.accession[raw.source != "characteristic"])
    eligible = sorted(a for a in area if a not in derived)
    best = None
    for combo in itertools.combinations(eligible, 5):
        sub = gold[gold.accession.isin(combo)]
        if not 35 <= len(sub) <= 45 or len({area[a] for a in combo}) < 3:
            continue
        cross = sum(a != b for _, grp in sub.groupby("variable_id")
                    for a, b in itertools.combinations(list(grp.accession), 2))
        key = (cross, -len(sub), combo)
        if best is None or key > best:
            best = key
    return list(best[2])


def read_soft(path: Path) -> tuple[list[str], dict[str, dict[str, str]], list[str]]:
    """Samples in file order, their characteristics, and keys in first-seen order.

    A characteristic line is `key: value`; the key ends at the first ": "
    (colon and space), so keys holding commas, '=' or '%' stay whole.
    """
    samples: list[str] = []
    chars: dict[str, dict[str, str]] = {}
    keys: list[str] = []
    current = None
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("^SAMPLE"):
                current = line.split("=", 1)[1].strip()
                samples.append(current)
                chars[current] = {}
            elif current and line.startswith("!Sample_characteristics_ch1"):
                text = line.split("=", 1)[1].strip()
                key, sep, value = text.partition(": ")
                if not sep:
                    continue
                key, value = key.strip(), value.strip()
                chars[current][key] = value
                if key not in keys:
                    keys.append(key)
    return samples, chars, keys


def describe_values(values: list[str]) -> str:
    counts = Counter(values)
    numeric = sum(bool(_NUMBER.match(v)) for v in counts) > len(counts) / 2
    if numeric and len(counts) > MAX_VALUES:
        nums = sorted(float(v) for v in values if _NUMBER.match(v))
        other = sorted({v for v in counts if not _NUMBER.match(v)})
        text = (f"numeric: {len(counts)} distinct values, min {nums[0]:g}, max {nums[-1]:g}; "
                f"examples: {', '.join(v for v, _ in counts.most_common(8))}")
        if other:
            text += f"; non-numeric values: {' | '.join(f'{v} ({counts[v]})' for v in other)}"
        return text
    shown = counts.most_common(MAX_VALUES)
    text = " | ".join(f"{v} ({n})" for v, n in shown)
    if len(counts) > MAX_VALUES:
        text += f" | … and {len(counts) - MAX_VALUES} more distinct values"
    return text


def coverage_note(key: str, keys: list[str], has: dict[str, set[str]], n: int) -> str:
    mine = has[key]
    if len(mine) == n:
        return "all samples"
    disjoint = [k for k in keys if k != key and not (has[k] & mine)]
    note = f"{len(mine)} of {n} samples"
    if disjoint:
        note += f"; shares no samples with: {', '.join(disjoint)}"
    return note


def build(series: list[str]) -> None:
    snapshot = json.loads(SNAPSHOT.read_text())
    studies = pd.read_parquet(ROOT / "work/sealed/studies.parquet").set_index("study_id")

    wb = Workbook()
    ins = wb.active
    ins.title = "Instructions"
    for i, line in enumerate(INSTRUCTIONS.strip("\n").split("\n"), 1):
        c = ins.cell(row=i, column=1, value=line)
        c.font = HEAD if line and not line.startswith((" ", "-", "•")) and line.endswith(":") else BODY
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ins.column_dimensions["A"].width = 120

    st = wb.create_sheet("Studies")
    st_head = ["series", "title", "samples", "summary", "overall design", "GEO page"]
    st.append(st_head)
    for a in series:
        r = studies.loc[a]
        st.append([a, r.title, int(r.n_samples), r.summary, r.overall_design,
                   f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={a}"])
    for c in st[1]:
        c.font, c.fill = HEAD, FILL_HEAD
    for row in st.iter_rows(min_row=2):
        for c in row:
            c.font, c.alignment = BODY, WRAP
    for col, w in zip("ABCDEF", (12, 45, 9, 90, 70, 30)):
        st.column_dimensions[col].width = w
    st.freeze_panes = "B2"

    ws = wb.create_sheet("Columns")
    given = ["id", "series", "column", "samples with a value", "values (count)"]
    ws.append(given + ANNOTATION_FIELDS)
    for c in ws[1]:
        c.font, c.fill = HEAD, FILL_HEAD
        c.alignment = WRAP
    for c in ws[1][len(given):]:
        c.fill = PatternFill("solid", fgColor="FFE066")
    example = ["EXAMPLE", "(example, not scored)", "age at enrolment (yrs)", "all samples",
               "numeric: 41 distinct values, min 23, max 79; examples: 54, 61, 47",
               "age at enrolment", "EFO:0000246", "broad", "", "", "enrolment", "", "UO:0000036", "", ""]
    ws.append(example)
    for c in ws[2]:
        c.font, c.alignment = EXAMPLE, WRAP

    n_rows = 0
    for a in series:
        samples, chars, keys = read_soft(RAW / f"{a}_family.soft.gz")
        truth = snapshot[a]["characteristics"]
        has = {k: {s for s in samples if chars[s].get(k, "") != ""} for k in keys}
        values = {k: [chars[s][k] for s in samples if chars[s].get(k, "") != ""] for k in keys}
        # The parse must reproduce the corpus snapshot exactly.
        assert set(keys) == set(truth), (a, sorted(set(keys) ^ set(truth)))
        for k in keys:
            assert Counter(values[k]) == Counter(truth[k]), (a, k)
        for k in keys:
            ws.append([f"{a}::{k}", a, k, coverage_note(k, keys, has, len(samples)), describe_values(values[k])]
                      + [""] * len(ANNOTATION_FIELDS))
            n_rows += 1
    last = ws.max_row
    for row in ws.iter_rows(min_row=3, max_row=last):
        for c in row[:len(given)]:
            c.font, c.alignment = BODY, WRAP
        for c in row[len(given):]:
            c.font, c.alignment, c.fill = BODY, WRAP, FILL_INPUT

    col = {name: chr(ord("A") + i) for i, name in enumerate(given + ANNOTATION_FIELDS)}
    dv = DataValidation(type="list", formula1='"exact,broad,indicator,none"', allow_blank=True,
                        error="Choose exact, broad, indicator or none.", showErrorMessage=True)
    dv.add(f"{col['predicate']}3:{col['predicate']}{last}")
    ws.add_data_validation(dv)
    yes = DataValidation(type="list", formula1='"yes"', allow_blank=True)
    yes.add(f"{col['assumed convention']}3:{col['assumed convention']}{last}")
    ws.add_data_validation(yes)
    widths = {"id": 18, "series": 11, "column": 26, "samples with a value": 22, "values (count)": 60,
              "variable": 24, "primary term": 16, "predicate": 11, "subject": 12, "object_class": 14,
              "event_time_anchor": 16, "method": 14, "unit": 12, "assumed convention": 12, "note": 40}
    for name, w in widths.items():
        ws.column_dimensions[col[name]].width = w
    ws.column_dimensions[col["id"]].hidden = True
    ws.freeze_panes = "D3"
    wb.move_sheet("Columns", offset=-1)
    wb.active = 0
    wb.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(series)} series, {n_rows} columns")


INSTRUCTIONS = """
What this is:
You are annotating sample-metadata columns from 5 public GEO gene-expression series, independently. Another annotator has done the same set, and we will compare the two. Please work only from this workbook and the GEO pages linked in the Studies tab. Don't look at anything in the colharmonize project (its gold standard or its outputs), and don't discuss particular columns with anyone who has seen them.

What to fill in:
Fill in the yellow cells on the Columns tab, one row per column. Row 2 is a worked example and is not scored. The Studies tab gives each series' title, summary and design. Expect about 2 hours.

Your two decisions for each column:
1. Which columns pool. Give every column a short "variable" name. Columns, in the same series or in different ones, that you would stack into one column of a pooled table get exactly the same variable name. Columns that shouldn't pool get different names, even when they are related.
2. What the column means in the Experimental Factor Ontology (EFO): a primary term, a predicate, and any qualifiers.

Pooling rules (agreed with the project owner; please follow them):
- Pool two columns only if no information is lost: every value must keep its meaning once it sits in the pooled column. Differently named columns can pool ("gender" with "sex").
- Different classification systems or scoring instruments are different variables, even when they measure the same kind of thing.
- Restructuring values is allowed to achieve that: recoding ("F" → "female"), converting units, or splitting a column that records two things. Write any recode or split you assume in "note".
- Two columns of the same series that have values on the same samples never pool, unless their values are identical on every sample. Columns that cover different samples of one series may pool. The "samples with a value" field tells you which columns cover which samples.
- When the metadata doesn't say something you need (a unit, for instance), you may assume the usual convention. If you do, write "yes" under "assumed convention" and say what you assumed in "note".

Primary term:
- Write an EFO term identifier such as EFO:0000246 (age). Terms EFO imports from other ontologies count as well, such as PATO:0000047 (biological sex), MONDO:0000001 (disease) or UBERON:… for anatomy. If you can't find an identifier, write the term's exact label. Leave it blank when the predicate is "none".
- Search for terms at https://www.ebi.ac.uk/ols4/ontologies/efo. Its version is newer than ours (EFO v3.94.0), and identifiers are checked against v3.94.0 afterwards, so an identifier added later will be reported back to you rather than counted wrong.
- Choose the most specific term that is true of the column.

Predicate, one of four:
- exact: the column records exactly what the term means, and every value is an instance or a measurement of it. Example: "gender" with values male/female is exactly biological sex.
- broad: the term is correct but broader than the column, which keeps its own, narrower meaning. Example: "age at enrolment" is anchored by age.
- indicator: the values only say yes/no, present/absent or 0/1 about one thing, and the term is that thing. Example: "hypertension: yes/no" is an indicator of hypertension.
- none: no ontology term fits, for instance a patient identifier. This is a valid answer; don't force a term.

Qualifiers (optional; fill one only if the column carries it):
- subject: whose property it is, when not the sampled individual (for example "mother", "donor").
- object_class: what the column is about when the term is general (for example the gene in "TP53 expression").
- event_time_anchor: the reference event of an age, time or duration (for example "diagnosis", "start of treatment").
- method: how the values were measured or classified, when that changes them (for example "RT-qPCR", or a named scoring system).
- unit: the unit of numeric values, as a UO identifier (UO:0000036 is year) or as text.
Write a term identifier or short text.

When you're done:
Save the workbook and send it back. If a column seems to need a decision these rules don't cover, make the call you think is right and explain it in "note". The disagreements are what we most want to learn from.
"""


if __name__ == "__main__":
    chosen = select_series()
    print("series:", ", ".join(chosen))
    build(chosen)
