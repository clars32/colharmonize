# Independent curation: protocol

Written 2026-10-09, before anyone has filled the sheet. Handoff task 6.

## Why

The sealed gold was drafted by Claude and reviewed by the owner, and the
pipeline is Claude too. Agreement between the pipeline and the gold may
partly reflect shared conventions, not correctness. A person annotating the
same columns independently tells us how far one careful human reading is from
the gold, and how the pipeline scores against that reading.

## The sheet

`curation_sheet.xlsx`, built by `make_sheet.py`.

- **Series:** chosen by a fixed rule (`select_series`): 5 sealed series
  - 35–45 gold columns in all
  - at least 3 disease areas
  - no title-derived or split gold columns, so the person annotates only
    what GEO shows
  - the most cross-series gold pairs, so pooling can be compared

  Result: GSE131411 and GSE137340 (sepsis), GSE166925 and GSE92415 (IBD),
  GSE231509 (type 2 diabetes). That is 44 columns, with 43 cross-series gold
  pairs.
- **Contents:**
  - each series' title, summary and design
  - each column's name, values with counts, and which samples it covers
    (the co-occurrence rule needs this)

  Values are read from the raw SOFT files and checked against the corpus
  snapshot. Nothing from the gold or the pipeline is in the sheet.
- **Instructions:**
  - the task definition
  - the owner-confirmed pooling rules (decisions log 2.1–2.4, plus goldlib's
    rule 4: different instruments are different variables)
  - the four predicates and the qualifier slots, with examples from neither
    corpus

  The gold's own conventions are deliberately left out. They include age at
  sampling being plain age, and identifiers getting `none`. Where the person
  departs from them, that is the information we want.

## Who

Someone who has not seen the gold, the gold review (`eval/gold/REVIEW.md`)
or any pipeline output. Ideally they have clinical or biomedical curation
background (handoff item 2, decisions log 9.4). Send them only the `.xlsx`
file, not the repository.

## Scoring (`agreement.py FILLED.xlsx out/agreement.md`)

On the same columns:

| comparison | question |
|---|---|
| person vs gold | how far the gold is from an independent reading |
| pipeline vs gold | the sealed final output, restricted to these 44 columns (pooling F1 81.1%, term and predicate 81.8%) |
| pipeline vs person | the same output, with the person as the reference |

Metrics are the sealed scorer's (`evaluate.score`): pooling precision,
recall and F1, primary term, predicate, term and predicate, and qualifiers.
Predicate agreement also gets Cohen's kappa. The report lists every
annotation and pooling difference between the person and the gold, with the
person's notes, for discussion with the owner.

Terms are validated against pinned EFO v3.94.0. A term the person found in a
newer EFO is reported back for them to replace, not scored as wrong. A label
is accepted when it matches a pinned label exactly.

## Reading the result

Decided before the sheet is filled:
- **Gold reliability.** Person vs gold, term and predicate, and pooling F1
  are reported as inter-annotator agreement. There is no pass mark. Each
  difference is a question for the owner: change the gold, or record the
  convention.
- **Circularity.** If the pipeline scores at least 10 points higher against
  the gold than against the person, on pooling F1 or on term and predicate,
  the sealed numbers are reported as partly measuring agreement with
  Claude's conventions. With 44 columns, smaller gaps are within noise.
- The sealed headline numbers are not changed by this exercise. If the owner
  edits the gold afterwards, rescoring is reported as post hoc.
