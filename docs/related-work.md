# Related work and positioning

Handoff task 20, written 2026-10-12 from the abstracts and listings, then
checked the same day against the bioRxiv full texts of MetaHarmonizer and
GEOMeta. Magneto is described from MetaHarmonizer's account of it and its
listing; its own paper hasn't been read.

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
  dictionary. The benchmark is Magneto's: 10 CPTAC studies whose columns
  domain experts mapped to 736 GDC data-dictionary attributes, 165
  ground-truth pairs.
- four EFO benchmarks: 77.9–95.5% top-1, up to 16.4 points over text2term
- confidence scores separate right from wrong predictions with AUC 0.73–0.94.
  The low end, 0.73, is SchemaMapper's (121 right, 44 wrong top-1 answers).
- contamination: three of five LLMs recovered 80–100% of GDC identifiers with
  no schema in context, so LLM-only results on that benchmark are inflated.
  All five LLMs answered 131 of the 165 queries correctly. Renaming the
  target identifiers cut LLM-only top-1 by 12.1–23.6 points and left
  SchemaMapper unchanged.
- alias dictionaries (relevant to task 10): six proprietary models' alias
  dictionaries each raised top-1 by 12.1–21.8 points, and were statistically
  indistinguishable from one another across a 50-fold cost range. Claude
  Haiku 4.5 was the cost-accuracy choice. Larger models didn't produce wrong
  aliases; they produced too many correct but off-task ones (tool names,
  value-like strings) that pull embedding retrieval toward wrong targets. An
  open-weight 27B model gave no gain.

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
- **Confidence.** Their calibrated scores reach AUC 0.73–0.94; 0.73 is
  their schema-mapping module, the step closest to our annotate step. Ours:
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
  extraction by four agents, deterministic and evidence-checked quality
  control (QA1–QA3), standardization by 21 field-specific agents, ontology
  mapping and a deterministic release check.
- **Fixed schema:** 27 fields per sample (their Supplementary Table S7). The
  release and paper focus on nine: RNA library type, RNA source,
  experimental setting, study- and sample-level perturbation, disease,
  tissue, age group and sex. Chemical perturbations add identity, type, dose
  and duration.
- **Targets:** tissue maps to 56 Human Protein Atlas categories (from 2,246
  labels), disease to CTD MEDIC terms (3,454 labels to 1,235), compounds to
  PubChem. Not EFO.
- **Scale:** 594,989 GSM–GSE records, 594,304 samples from 22,782 series,
  human bulk RNA-seq only (ARCHS4 plus a GEO query). Series with fewer than
  six samples are dropped.

**Models and consensus:**
- Developed with GPT-4. The release and the reported experiments used
  GPT-5, one model per run.
- Cross-model consensus is used only prospectively. 22 LLMs were compared on
  118 samples from five of the authors' own series. Five were chosen (Gemini
  3 Flash Preview, Mistral Large 2512, GPT-5 mini, DeepSeek V4 Flash, Qwen3.7
  Plus), and field-level majority voting over them built a 5,945-sample
  release of series from December 2025–January 2026. Ties were dropped.
- The authors say consensus measures stability, not accuracy, because models
  can share errors. Cheap "Flash" models came within the 92.8–97.9% range of
  consensus agreement at 21–32 times lower API cost.

**Evaluation:**
- 1,000 development samples: 96.8% sex, 92.8% experimental setting, 92.3%
  age, 95.1% disease, 79.3% tissue. The authors note these are on the set
  used to refine the prompts, not a held-out test.
- Outside resources: 96.6% disease and 97.0% tissue agreement with
  DiSignAtlas, 96.3% compound agreement with PharmGEO.
- An expert reviewed 1,000 samples from 96 series submitted in May 2026 and
  confirmed every disease, tissue and age annotation and 99.7% of sex.

**Released:** the annotations, with study-aware train, test and 2024
holdout splits, at huggingface.co/datasets/binchenlab/GEOMeta; the code,
prompts and mapping tables at github.com/Bin-Chen-Lab/GEOMeta.

**QA1, and why handoff task 17 doesn't apply to colharmonize:**
- QA1 fills a missing cell within a series when every non-missing value in
  that series agrees.
- It applies only to fields expected to be constant within a study, and only
  above field-specific minimum-support and maximum-missingness thresholds.
- It never overwrites a value.
- Age, sex and sample-level perturbation are audited but never filled,
  because they can legitimately vary between groups.
- Conflicting or mixed-design cases go to review.

  That only makes sense for a per-sample table. colharmonize publishes
  column-level decisions (variables, member columns, value recodes, SSSOM)
  and no per-sample values, so there is nothing for it to fill. GEOmend's
  export is per sample, so a QA1-style fill would belong there, as a
  reviewable suggestion with the same restrictions. A missing value often
  means "not measured", not "same as the others".

**How colharmonize differs:**
- **Scope.** GEOMeta fills a fixed set of fields for a very large corpus.
  colharmonize keeps every column a study reports and pools them only when
  nothing is lost (decisions log 2.1). A fixed schema compresses detail: an
  `age at draw` and an `age at diagnosis` both become age.
- **Scale and cost.** GEOMeta runs at a scale colharmonize hasn't attempted.
  With GPT-5 it annotated 96 series (7,319 samples) in about 15 hours for
  US$53, about US$0.50 a series. The cheapest selected model cost US$0.0025
  per six-sample study. colharmonize's cost is about 130k input tokens,
  mostly cached, and 3k output tokens per gold column (`eval/cost/`). It runs
  on a Claude Code plan, so it has no per-call price to compare directly.
- **Complementary.** GEOMeta's labels are released, so they could serve as
  an outside check on series both projects cover. It covers only human bulk
  RNA-seq: 7 of our 16 sealed series (GSE104674, GSE131411, GSE152111,
  GSE166925, GSE192341, GSE231509, GSE282580) and 6 of the 13 tuning series
  (GSE79842, GSE124252, GSE128621, GSE183701, GSE185192, GSE222365) are that
  type. Whether they made its release (six samples or more, not a
  SuperSeries) hasn't been checked; that needs the Hugging Face dataset. Its
  labels are per-sample values, so the check would ask whether the column we
  call sex, age, tissue or disease holds the values GEOMeta assigns for that
  field. That is a check of meaning, not of pooling.

## Magneto

Liu, Peña, Santos, Wu and Freire. *Magneto: Combining Small and Large Language
Models for Schema Matching.* PVLDB 18(8), 2025,
[doi:10.14778/3742728.3742757](https://doi.org/10.14778/3742728.3742757).

**What it does:**
- Small language models retrieve candidate matches; they are fine-tuned
  self-supervised on training data an LLM generates.
- An LLM reranks the candidates.
- It introduced a benchmark of real biomedical datasets built with domain
  experts. MetaHarmonizer's GDC benchmark is that one, taken from Magneto's
  repository (github.com/VIDA-NYU/magneto-matcher): 10 CPTAC studies mapped
  to 736 GDC attributes.

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
