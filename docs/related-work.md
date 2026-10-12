# Related work and positioning

Handoff task 20, written 2026-10-12. The other tools are described from
their abstracts and listings. Details marked "to verify" were not in the
abstracts and should be checked against the full texts before a paper cites
them.

## MetaHarmonizer

Li, Dhal, Gravel-Pucillo, Long, Waters, de Bruijn, Davis and Oh. *MetaHarmonizer:
robust biomedical metadata harmonization and a contamination control for
inflated LLM performance on public benchmarks.* bioRxiv, June 2026,
[doi:10.64898/2026.06.13.732088](https://doi.org/10.64898/2026.06.13.732088).

**What it does:**
- Two modules. SchemaMapper aligns attribute names to a target schema;
  OntologyMapper maps values to a controlled vocabulary.
- Each is a cascade that escalates to costlier methods only when cheaper ones
  fail.
- Every output is drawn from predefined vocabularies.
- LLMs are used only as bounded preprocessing, such as generating an alias
  dictionary, never at inference time. Inference is local and deterministic.

**Reported results:**
- GDC schema-mapping benchmark: 71.6% top-1 with an LLM-generated alias
  dictionary
- four EFO benchmarks: 77.9–95.5% top-1, up to 16.4 points over text2term
- confidence scores separate right from wrong predictions with AUC 0.73–0.94
- contamination: three of five LLMs recovered 80–100% of GDC identifiers with
  no schema in context, so LLM-only results on that benchmark are inflated

**How colharmonize differs:**
- **No target schema.** SchemaMapper maps each attribute to a schema someone
  wrote. colharmonize decides which columns pool across studies, and their
  meaning, without one. Variables emerge from the data and carry forward
  through a registry.
- **Judgment by LLM, constrained by validation.** colharmonize uses Claude at
  inference time, where MetaHarmonizer avoids LLMs. It gets the same
  guarantee against hallucinated terms another way. The model chooses among
  retrieved candidates or names a term, and every identifier and label is
  validated against the pinned EFO release. An unknown name becomes `none`
  plus a review hint, never an invented identifier.
- **Contamination.** colharmonize adopted their concern.
  - The memorization probe found no recall of our series' metadata
    (decisions log 15.1).
  - Renaming every column cost 2.4 points, within noise (15.3).

  Our gold was written in this project and never published, so it can't have
  been memorized.
- **Confidence.** Their calibrated scores reach AUC 0.73–0.94. Ours:
  - same-model run agreement on unseen data: 0.53 (decisions log 15.2)
  - cross-model agreement: 0.73 (15.8)
  - a three-run agreement count: the candidate to pre-register

  This is where colharmonize is weakest, and the comparison should say so.
- **What we can reuse:**
  - OntologyMapper, if value mapping is un-deferred (task 19)
  - SchemaMapper with the EFO property space as its target, as a
    deterministic baseline for our annotate step (task 18)
  - their alias-dictionary idea for retrieval (task 10)

## GEOMeta

Zhang, Paithankar, Pu, Murtaza, Shankar, Leshchiner, Koirala, Palmer, Nault,
Li, Xie and Chen. *Automating scientific annotations for open transcriptomic
profiles via multi-stage agents.* bioRxiv, August 2026,
[doi:10.64898/2026.08.19.745739](https://doi.org/10.64898/2026.08.19.745739).

**What it does:**
- Task-specialized LLM agents curate GEO metadata in stages: retrieval,
  extraction, field standardization, ontology mapping and quality control.
- It annotated about 600,000 human bulk RNA-seq samples.
- 22 LLMs were evaluated. Open-source "Flash" models matched leading
  reasoning models at about a tenth of the cost.

**To verify in the full text:**
- the fixed field set (the handoff says 27 fields)
- whether consensus across models is used
- whether the annotations are released

**How colharmonize differs:**
- **Scope.** GEOMeta fills a fixed set of fields for a very large corpus.
  colharmonize keeps every column a study reports and pools them only when
  nothing is lost (decisions log 2.1). A fixed schema compresses detail: an
  `age at draw` and an `age at diagnosis` both become age.
- **Scale and cost.** GEOMeta runs at a scale colharmonize hasn't attempted.
  colharmonize's cost is about 130k input tokens, mostly cached, and 3k output
  tokens per gold column (`eval/cost/`).
- **Complementary.** If GEOMeta's labels are released, they could serve as an
  outside check of sex, age, tissue and disease on any series both projects
  cover.

## Magneto

Liu, Peña, Santos, Wu and Freire. *Magneto: Combining Small and Large Language
Models for Schema Matching.* PVLDB 18(8), 2025,
[doi:10.14778/3742728.3742757](https://doi.org/10.14778/3742728.3742757).

**What it does:**
- Small language models retrieve candidate matches; they are fine-tuned
  self-supervised on training data an LLM generates.
- An LLM reranks the candidates.
- It introduced a benchmark of real biomedical datasets built with domain
  experts. MetaHarmonizer evaluates against Magneto on a GDC schema-mapping
  benchmark; whether that is Magneto's benchmark is to verify.

**How colharmonize relates:** it has the same retrieve-then-judge shape.
- **Retrieve:** exact matches, two small embedding models, values-to-category
  and ZOOMA/OLS4 propose candidates.
- **Judge:** Claude chooses among them.

The target is an ontology's property space rather than a table schema, and
colharmonize adds a cross-study reconciliation step that schema matchers
don't have.

## What colharmonize contributes

Each claim comes with the evidence that supports it and its limits.

1. **Pooling across studies without a target schema and without information
   loss.** Measured as pairwise pooling precision and recall against a
   no-information-loss gold. On the sealed corpus, pooling F1 is 83.0%
   (95% CI 75.3–91.6), 29 points above identical-name pooling, with
   intervals that exclude zero (decisions log 15.2).
2. **Directed annotations.** Four predicates (exact, broad, indicator, none)
   and five qualifier slots instead of one term per column. This is what keeps
   `age at diagnosis` from pooling with `age` while both stay anchored to age.
3. **A pre-registered test on unseen data,** plus checks a reviewer would ask
   for:
   - a memorization probe
   - robustness to renaming
   - study-level intervals and paired tests
   - an independent-curation protocol, which is ready
4. **Claude Code-only operation.**
   - Task files are checked against content hashes.
   - Answers are validated and retried item by item.
   - Every identifier is checked against a pinned release.
   - Decisions are written back to GEOmend as reviewable provider proposals.

## Limits a paper must state

- **The corpora are small:** 13 tuning and 16 sealed series. Interval
  half-widths on pooling F1 are 8–14 points.
- **The sealed gold was drafted by Claude** and reviewed by the owner. The
  independent curation (`eval/curation/`) hasn't been done.
- **No confidence signal validated for annotation on unseen data.** The
  cross-model result is post hoc.
- **Reconciliation's benefit over annotation alone is unproven** on both
  corpora.
