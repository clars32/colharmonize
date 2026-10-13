# SapBERT as a third embedding model: results

Handoff task 11, 2026-10-12. Measured by `sapbert.py`, which regenerates
candidates in memory without writing to any workspace. Sealed numbers are
post hoc. Full output: `out/sapbert.md`.

SapBERT (`cambridgeltl/SapBERT-from-PubMedBERT-fulltext`) runs with [CLS]
pooling beside MiniLM and BGE. ZOOMA and OLS4 hits come from the shared
cache, as in the recorded runs. The control, the pipeline's two models,
reproduces the recorded tuning recall exactly: 88.6% in the pool, 84.8%
shown, the same nine misses.

## Results

| gold primary term | tuning: pipeline | tuning: + SapBERT | sealed: pipeline | sealed: + SapBERT |
|---|---|---|---|---|
| in the candidate pool | 88.6% | **91.1%** | 70.6% | **78.2%** |
| shown (cap 40 space terms) | 84.8% | 81.0% | 66.4% | 73.9% |
| shown, cap 50 | 84.8% | **86.1%** | 66.4% | **73.9%** |
| shown, cap 60 | 84.8% | 87.3% | 68.1% | 74.8% |
| grounded qualifiers, pool | 81.8% | 90.9% | 14.3% | 14.3% |

- **SapBERT finds terms the other two miss:**
  - tuning: `MLL`, `flt3-itd`
  - sealed: `er`, `pr`, `til`, `time.os`, `rfs (years)`, `pcr`, `mayoscore`,
    `visit` and others

  These are abbreviated, biomedical names, which is what SapBERT was
  trained for.
- **At the current display cap of 40 space terms, the extra candidates push
  gold terms out of view on tuning.** Shown recall falls from 84.8% to 81.0%.
  This is the same trade the alias dictionary showed (task 10, on the
  parallel branch): the display cap is the bottleneck, not the pool.
- **SapBERT with a cap of 50 is better on both corpora:** +1.3 points shown
  on tuning and +7.5 on sealed.

## Decision

**Not adopted yet.** Two reasons:
- The cap of 50 was chosen after seeing these numbers.
- Shown recall is an intermediate measure. More candidates make each
  annotate item longer, and it is untested whether that helps or distracts
  the annotator.

Next, pre-register "SapBERT plus a cap of 50" as a retrieval change. Measure
annotation accuracy on tuning with two annotate-3 runs, then confirm on the
next sealed corpus. The cost is about 20% more candidate lines per item.

The 13 sealed columns no setting retrieves are mostly not retrieval
failures:
- columns the sealed run never produced (the failed repair batch)
- keys GEOmend 0.0.8 mis-parsed (`fasting glucose,_mm`, `hba1c, %`), which
  GEOmend 0.0.9 fixes
