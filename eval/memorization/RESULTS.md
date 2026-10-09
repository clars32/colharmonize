# Memorization probe: results

Run 2026-10-08 following `PROTOCOL.md`: 8 subagent runs (Sonnet and Opus,
4 batches each), given accessions only. Each transcript shows exactly one tool
call, the hand-back that returns the reply. No run read a file, searched or
fetched anything, so none was discarded. Raw replies are in `answers/`,
per-series scores in `out/per_series.tsv`.

## Result: no memorization signal

| model | corpus | series answered "none" | key recall, strict (control) | value recall (control) | series recalled |
|---|---|---|---|---|---|
| Sonnet | tuning | 13 of 13 | 0.0% (0.0%) | 0.0% (0.0%) | none |
| Sonnet | sealed | 15 of 16 | 1.6% (0.8%) | 0.0% (0.0%) | none |
| Opus | tuning | 10 of 13 | 0.0% (1.2%) | 0.7% (0.1%) | none |
| Opus | sealed | 15 of 16 | 2.3% (0.1%) | 2.1% (0.0%) | none |

No series meets the pre-registered "recalled" rule (strict key recall of at
least 50% and at least 30 points above control). Both models declined to
answer for 53 of 58 series-model pairs. Full table: `out/summary.md`.

## The five partial recollections

All five were marked low confidence.

- **GSE92415 (sealed, both models).** Both named the study as golimumab in
  ulcerative colitis (PURSUIT). Opus listed `disease`, `treatment`, `visit`
  and "mayo response at week 6", against the true `disease`, `treatment`,
  `visit` and `wk6response`, among 8 keys. That is 37.5% strict recall
  (control 1.7%) and 33% value recall. Sonnet got `tissue` and `disease`
  (25%, control 13.5%). This is recognition of a well-known trial dataset,
  and the matched keys are generic.
- **GSE5390, GSE1397, GSE16176 (tuning, Opus).** Opus recalled the papers
  behind them (adult Down syndrome brain; fetal trisomy 21 cerebrum,
  cerebellum, heart and astrocytes). It guessed keys and called its own
  guesses likely wrong. No key matched strictly. GSE1397 has no
  characteristics to score, but the tissues Opus named match its sample
  titles. That is memory of the study design, not of GEO's metadata.

## Post-hoc check on GSE92415

Post-hoc check; no headline changes. In the sealed final output, 6 of
GSE92415's 8 gold columns were annotated correctly (75.0%), against 69.0%
(89 of 129) for the other sealed series. The 6 are its generic columns:
tissue, subject, disease, age, treatment and visit. The two columns specific
to the trial were both wrong (`wk6response` and `mayo score`, given `none`
where gold has `broad`). Memory of the study gave no visible advantage.

## Reading

- The sealed numbers show no sign of inflation from the models remembering
  these series' metadata. That differs from MetaHarmonizer's benchmark,
  which was public and widely copied. These are ordinary GEO series, and
  our gold is new.
- The probe tests memory of the metadata, not of the gold. The gold was
  written in this project and has never been public, so it can't have been
  memorized.
- **Limits:**
  - The probe gives the accession only. A model that recognizes a study from
    its title, which the pipeline does show it, could know more than this
    probe reveals. The GSE92415 and GSE1397 cases show the models know some
    famous studies by name.
  - The subagents ran as general-purpose agents in this project, so they may
    have had the project's `CLAUDE.md` in context. It names no series keys.
