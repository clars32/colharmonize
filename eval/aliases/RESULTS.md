# Alias dictionary: results

Run 2026-10-12 under `PROTOCOL.md` (committed before any alias existed).
Numbers are in `out/recall.md` and `out/validation.md`.

## Aliases

- 20 Haiku subagents, one batch of 100 terms each. All 20 batches passed
  the structural check on the first try, although three agents misreported
  their own item counts (88, 101, 128); the check uses the files, not the
  reports.
- 1,379 aliases proposed for 1,998 terms; 1,333 kept for 1,094 terms. Dropped:
  22 proposed for more than one term, 19 equal to another term's label or
  synonym, 4 equal to the term's own label or synonym, 1 too long.
- They are mostly abbreviations and plain names: FVIII, BPD, EEG, UDCA,
  "visual acuity", "liver fat", "blood type".

## Recall

| corpus | retrieval | gold term in pool | gold term shown |
|---|---|---|---|
| tuning | pipeline (control) | 88.6% | 84.8% |
| tuning | + aliases | 88.6% | 82.3% |
| sealed, post hoc | pipeline (control) | 70.6% | 66.4% |
| sealed, post hoc | + aliases | 73.9% | 68.1% |

The control reproduces the recorded tuning recall.

- **Tuning:** no gold term gained or lost from the pool. Two dropped off the
  display (GSE16176 `condition`, GSE222365 `study`), pushed down by about
  6,200 extra candidates.
- **Sealed (post hoc):** four gold terms newly in the pool (GSE131411 `cell
  type`, GSE237290 `er`, `pr`, `time.os`), three of them newly shown; one
  dropped off the display (GSE137340 `outcome`). The gains are abbreviated
  column names, which the Down syndrome tuning corpus has few of.
- **Exploratory, not pre-registered:** with exact alias matches alone,
  nothing changes on either corpus, because no column name equals an alias.
  Every effect comes from embedding the alias text.

## Decision

**Not adopted.** The pre-registered rule needed shown recall to rise on
tuning; it fell by 2.5 points (two terms), while pool recall stayed level.
Two terms is within noise, but the rule was fixed in advance and the sealed
gain can't decide.

What the result does say:
- The alias effect is a trade. Embedded aliases find abbreviated columns
  (`er`, `pr`, `time.os`) and push other true terms off a display capped at
  40. That matches SapBERT's pattern (pool up, shown down on tuning), from
  the uncommitted `eval/retrieval/sapbert.py` run.
- Recall in the pool is cheap to raise; the display cap is now the
  bottleneck. A change that ranks within the cap better, or one that adds
  aliases without adding a whole source's 50 candidates (for example, alias
  hits only re-rank terms other sources already found), would test the next
  idea. It needs its own pre-registration, and the next sealed corpus, ideally
  one with abbreviated column names, to decide.

The dictionary is kept in `aliases.json` for that.
