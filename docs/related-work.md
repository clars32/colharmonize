# Related work and positioning

Handoff task 20, written 2026-10-12 from the abstracts and listings, then
checked the same day against the bioRxiv full texts of MetaHarmonizer and
GEOMeta. Magneto is described from MetaHarmonizer's account of it and its
listing; its own paper hasn't been read.

Extended 2026-10-13 with Sun et al. (*Scientific Data*, 2026), the metadata
work it cites, and papers those cite in turn. Each was read in full; unread
supplements are noted. EMBERS is the closest: it pools keys across studies
without a schema, so contribution 1 below is narrowed. Cited but not read:
ALE and ChIP-GPT (single-field extraction, cited by Sun et al.), and Hawkins
et al. 2022 and PEPHub (sample-level embeddings, cited by Brown et al.).

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

## EMBERS

Higashi, Nakagawa, Yamada and Mori. *Automated harmonization and large-scale
integration of heterogeneous biomedical sample metadata using large language
models.* bioRxiv, October 2024,
[doi:10.1101/2024.10.26.620145](https://doi.org/10.1101/2024.10.26.620145).
Preprint only (v1); no peer-reviewed version found on 2026-10-13. Read in
full, with the code.

**What it does:**
- Mines 26,435 PubMed Central papers on the human gut microbiome, their
  supplementary tables and the ENA/SRA records they cite: over 400,000
  samples.
- gpt-4-turbo writes a description of each key in its paper's context. The
  descriptions are embedded and clustered hierarchically across all studies,
  with no schema.
- The tree is cut top-down. At each node the model scores a sample of up to
  100 members for semantic consistency; a node above 0.9 becomes a cluster.
  Members must also share a data type.
- Values are then converted per study, by code the model writes, into 12
  hand-defined fields (age, sex, BMI, mode of delivery and others, listed in
  the repository, not the paper). Other clusters keep their raw values.
- No ontology, and no identifiers are produced.

**Evaluation:**
- Gold: 100 papers curated by one co-author, 22,104 samples and 49,712
  values in four fields (age, sex, BMI, mode of delivery). Not described as
  held out.
- Only recovered values are scored: about 50% recall on average (per paper,
  near 0 or near 1) at precision near 100%. A baseline that reads MIxS
  attributes recalls about 10%.
- **The grouping is never scored.** One error they report: sexual
  orientation landed in the biological-sex cluster.
- Released: code only (github.com/khigashi1987/EMBERS, MIT). The web
  database returned 404 on 2026-10-13.

**How colharmonize differs:**
- **The same core step.** EMBERS decides without a schema which keys pool
  across studies, from the key, its context and example values, with an LLM
  judging. Schema-free pooling isn't new. What EMBERS doesn't do is measure
  it: a wrong merge counts against it only if it lands in one of the four
  scored fields.
- **Measured pooling.** colharmonize scores pooling pairwise against a
  no-information-loss gold, on a corpus sealed before any run.
- **Meaning.** EMBERS names a field; colharmonize anchors each variable to a
  validated EFO IRI, with a predicate and qualifiers.
- **Domain.** Microbiome papers and supplements, not GEO characteristics.
- **Reusable:** its tree cut, as a pooling baseline on our 29 series. It
  calls OpenAI models, so it would have to be re-implemented with
  substitutes and reported as such.

## Gonçalves et al.

Gonçalves, Kamdar and Musen. *Aligning biomedical metadata with ontologies
using clustering and embeddings.* ESWC 2019, LNCS 11503,
[doi:10.1007/978-3-030-21348-0_10](https://doi.org/10.1007/978-3-030-21348-0_10).
Read in full as arXiv:1903.08206 v2; the Springer version wasn't reachable.

- Clusters 15,553 normalized BioSample field names by string distance
  (affinity propagation with Jaro-Winkler, 1,387 clusters). There's no
  schema, but values and the study a name came from play no part.
- Aligns each name to terms from 675 BioPortal ontologies using PubMed GloVe
  embeddings and edit similarity, ranked by its cluster neighbours. No LLM.
- No gold standard. Coverage against the NCBO Annotator (93% of clusters get
  an ontology recommendation, against 69%) and four experts rating 12
  names.
- No code or data released.

**Relation:** an early schema-free treatment of field names, but its clusters
are string neighbourhoods for review, not claims that members are one
variable. Pooling is implied only when two names align to the same term, and
it's never measured.

## Standardizing records to fixed fields

Five papers fill fixed fields for each sample or study. None decides which
columns pool across studies, so none competes with contribution 1. They bear
on annotation, retrieval and evaluation.

### MetaSRA

Bernstein, Doan and Dewey. *MetaSRA: normalized human sample-specific
metadata for the Sequence Read Archive.* Bioinformatics 33(18), 2017,
[doi:10.1093/bioinformatics/btx334](https://doi.org/10.1093/bioinformatics/btx334).
Read in full, with the supplement.

- Normalizes each SRA sample's key–value pairs into an ENCODE-like schema:
  ontology terms under five relations (has phenotype, derives from, part
  of, consists of cells of type, underwent), one of six sample types, and
  (property, value, unit) triples for six EFO properties.
- Disease Ontology, Cell Ontology, Uberon, EFO, Cellosaurus and the Unit
  Ontology. Not pinned: the code downloads the latest files.
- Deterministic: 22 lexical stages (n-grams, lexicon variants, a thesaurus,
  fuzzy matching within edit distance 2) and a logistic-regression
  sample-type classifier. No LLM.
- Gold: 422 samples, one per study, drawn from entries added after
  development and normalized by the authors. Per-ontology recall about
  0.74–0.87 at error rates about 0.01–0.12 (read off a figure). Numeric
  properties: precision 0.989, recall 0.672 on 104 samples.
- Still maintained: github.com/deweylab/MetaSRA-pipeline (BSD-3, commits in
  2026); database v1.8 holds 718,384 human and mouse samples.

**Relation:** its five relations and property–value–unit triples are an
earlier form of our `subject`, `object_class` and `unit` qualifiers. It
labels samples and never decides pooling. Its test samples were drawn after
development, the same guard as our sealed corpus. The 422-record gold could
check value-level terms only; its 2016 identifiers would need converting to
EFO v3.94.0 IRIs.

### Ikeda et al.

Ikeda, Zou, Bono, Moriya, Kawashima, Katayama, Oki and Ohta. *Extraction of
biological terms using large language models enhances the usability of
metadata in the BioSample database.* GigaScience 14, giaf070, 2025,
[doi:10.1093/gigascience/giaf070](https://doi.org/10.1093/gigascience/giaf070).
Read in full; the supplement wasn't.

- **The problem in numbers:** in June 2024 BioSample had 76,282 distinct
  attribute names. 75.7% appear in a single project, and the cell line
  HEK293T appears under 27 different names. That's the case for
  colharmonize in one statistic.
- From each human ChIP-seq or ATAC-seq sample's attributes, it extracts a
  cell line (mapped to Cellosaurus) or perturbed genes with a method
  (knockout, knockdown, overexpression; mapped to HGNC). One fixed target
  per prompt.
- Llama 3.1 70B, run locally at temperature 0. MetaSRA's matcher proposes
  candidates; the model picks one or answers "not unique".
- Cell lines, 600 samples: accuracy 0.923 against MetaSRA's 0.903, coverage
  0.930 against 0.721. Gold from ChIP-Atlas curation, checked by four
  experts. Not held out.
- Released: code (github.com/sh-ikeda/bsllmner, MIT); gold and outputs on
  Zenodo (doi:10.5281/zenodo.14881142).

**Relation:** the same design as our annotate step, a model choosing among
retrieved candidates with the option to abstain, but per sample and per
fixed field. Their largest error class, a sample derived from a cell line
rather than the line itself, is a `subject` question in our terms.

### Sundaram et al.

Sundaram, Gonçalves and Musen. *Toward total recall: enhancing data FAIRness
through AI-driven metadata standardization.* GigaScience 15, giag019, 2026,
[doi:10.1093/gigascience/giag019](https://doi.org/10.1093/gigascience/giag019).
Read in full.

- GPT-4 rewrites each record's field names and values into a CEDAR BioSample
  template: 26 fields, with UBERON, DOID and CL labels. No GEO template
  existed, so GEO records used the same one.
- 4,800 human cancer records, 2,400 from BioSample and 2,400 from GEO.
- Measured by findability: exact-match searches for four tissues on the
  tissue field. Average recall rose from 17.65% to 62.87%. On GEO alone it
  rose from 15% to 44%, not significant (p=0.439). Given the BioSample data
  dictionary instead of the template, GEO recall fell to 3%.
- Gold built by the authors from keyword rules on the original field, 5%
  checked by hand. Outputs are labels; nothing validates them against an
  ontology.
- Released: code (github.com/musen-lab/FAIRMetadataCuration, MIT); data on
  Zenodo (doi:10.5281/zenodo.15617182, CC0).

**Relation:** the target-schema approach colharmonize avoids, applied to GEO.
Its search measure would make an extrinsic metric for us: does pooling let a
query find more samples? The GEO result (44% against 3%) favors giving the
model a constrained target over a description of one.

### ARMS

Hardi, O'Connor, Martínez-Romero, Rosario, Fisher and Musen. *Automated
standardization of legacy biomedical metadata using an ontology-constrained
LLM agent.* arXiv:2604.08552 v3, September 2026,
[doi:10.48550/arXiv.2604.08552](https://doi.org/10.48550/arXiv.2604.08552).
Preprint; no venue listed on 2026-10-13. Read in full (v3), with the code.
v1 and v2 used a different model and metric, so cite v3.

- The same group's follow-up to Sundaram et al. An agent maps one legacy
  HuBMAP record at a time onto a fixed CEDAR template (12 assay templates,
  23–48 fields each), matching fields by name, description and value. For
  ontology-constrained fields it must call BioPortal search tools and pick a
  returned term, or leave the field empty.
- Assay metadata (instruments, kits, read structure), not sample
  characteristics. 839 records, 28,257 field instances.
- Gold: HuBMAP's existing curation, by one biologist. No development/test
  split.
- Against Sundaram et al.'s prompt-only method, re-run with the same model:
  ontology-field precision 0.36 to 0.92, recall 0.33 to 0.80. Their
  repository's three runs vary by under a point.
- Labels only, from live BioPortal: no ontology version and no IRIs. EFO
  isn't mentioned.
- Released: github.com/musen-lab/metadata-standardization-agent (BSD-2), with
  the 839 inputs, gold records and predictions.

**Relation:** schema-guided record standardization, the step after
variables are defined, not variable discovery. It shares our discipline of
choosing only among retrieved terms and abstaining otherwise. Pinned
releases and validated IRIs are a real difference. Its deduplicated scoring
(each distinct field–value pair counted once) and its omission, substitution
and insertion error taxonomy are worth borrowing.

### Pre-Meta

Tinn, Sørbø, Jiang, Voutetakis, Giounis, Pilalis, Papadodima and Roman.
*Pre-Meta: priors-augmented retrieval for LLM-based metadata generation.*
Bioinformatics 41(10), btaf519, 2025,
[doi:10.1093/bioinformatics/btaf519](https://doi.org/10.1093/bioinformatics/btaf519).
Read in full.

- Fills five ArrayExpress study-level fields (hardware, organism part,
  experimental design, study type, assay by molecule) from a paper's full
  text. It retrieves chunks of the paper by similarity to the allowed labels
  or to an ontology subtree (EFO among them), and constrains decoding to
  those labels.
- 300 ArrayExpress-labelled items per field. GPT-4o mini: 0.588 average
  accuracy against 0.467 for plain retrieval-augmented generation, and 0.374
  for retrieval alone with no LLM.
- The models favored candidates listed first. The authors shuffle the order
  on every call.
- Released: code (github.com/SINTEF-SE/LLMDap, MIT).

**Relation:** study-level and schema-bound, so far from pooling. Two points
carry over:
- **Position bias.** colharmonize already shuffles candidate order, with a
  different seed for each annotate run (`annotate.py`). This result supports
  that.
- **A no-judge baseline.** Their retrieval-only row shows what the LLM adds.
  We haven't reported the equivalent: how often our top retrieved candidate
  is the gold primary term. Task 18 (SchemaMapper) would fill a similar
  role at more cost.

## Finding and screening datasets

Two papers work before colharmonize does: finding series, and deciding which
belong in an analysis.

### Brown et al.

Brown, Wengler, Fabelico, Muir, Tubbs, Warren, Millett, Xiang Yu, Pavlidis,
Rogic and Piccolo. *Using semantic search to find publicly available
gene-expression datasets.* Bioinformatics 42(3), btag053, 2026,
[doi:10.1093/bioinformatics/btag053](https://doi.org/10.1093/bioinformatics/btag053).
Read in full except the figures and supplement. From the Piccolo lab in
BYU's Department of Biology; the UBC co-authors run Gemma's curation.

- Given series a researcher already has, it ranks other GEO series (48,893
  human) by embedding similarity of their titles, summaries and designs.
  Sample-level metadata is left to future work.
- 30 embedding models, scored on six conditions with Gemma's curation as
  truth. The best were general-domain contrastive models (gte-large,
  all-roberta-large-v1, all-mpnet-base-v2), ahead of the biomedical ones.
  Chunking the text hurt.
- Two curators judged the top 50 series per condition, blind: 62–63% were
  relevant for the best model against 50–53% for GEO's keyword search (odds
  ratio 1.97). Only 41 of the 260 relevant series were found by both.
- Released: github.com/srp33/GEO_NLP (MIT), and the GEOfinder search tool at
  bioapps.byu.edu/geofinder.

**Relation:**
- **Down syndrome is one of the six conditions.** Their 30 Gemma series,
  checked against ours on 2026-10-13:
  - 6 are tuning-gold series: GSE1397, GSE16176, GSE185192, GSE222365,
    GSE4119, GSE5390
  - 14 more are in the 64-series Down syndrome corpus
  - none are sealed
  - 10 are in no corpus of ours: GSE100680, GSE125839, GSE127880,
    GSE160691, GSE208440, GSE220652, GSE42772, GSE42956, GSE48051, GSE63870

  Those 10 could make an in-domain held-out set, though not a test of
  generalization, which is what the sealed corpus measures. Which of them
  have characteristics columns hasn't been checked.
- **Retrieval.** Keyword and embedding search found mostly different
  series, which supports combining exact matches with embeddings as our
  retrieval does. Their model ranking is on long text and may not carry over
  to short column names.

### Sun et al.

Sun, Cheuk, Chon, Kim, Park, Son and Moon. *Large language models accelerate
dataset screening for meta-analysis in biomedical data repositories.*
Scientific Data, 2026 (in press, published 13 October),
[doi:10.1038/s41597-026-08323-8](https://doi.org/10.1038/s41597-026-08323-8).
Read in full; the supplement (prompts, input ablation, confusion matrices)
wasn't.

**What it does:**
- Decides which retrieved datasets meet a meta-analysis's inclusion and
  exclusion criteria. One request per dataset; the model answers each
  criterion with evidence and a justification in a JSON schema, then
  includes or excludes.
- Three case studies:
  - GEO, lung cancer: 536 series. Input: title, description and the GEO2R
    sample table as CSV.
  - ProteomeXchange, ovarian cancer: 258 datasets, titles and descriptions
    only.
  - ArrayExpress, neurodegeneration: 56 datasets from a published
    meta-analysis, screened with no prompt tuning.
- Four OpenAI models: gpt-4o-mini, gpt-4.1-mini, o4-mini, gpt-5-mini. The two
  reasoning models ran 10 times each, with seeds 42–51.
- "Ensemble" means a dataset is included if any model includes it.

**Evaluation:**
- Gold: two reviewers per prospective case (Cohen's κ 0.900 for lung, 0.733
  for ovarian), not blinded to the model outputs, which the authors state as
  a limitation. For ArrayExpress, the published meta-analysis's decisions.
- Prompts were tuned on a development set (about a third of the included
  datasets) and evaluated once on the rest.
- Held-out sensitivity: 7 of 8 for every model (lung); 14 of 15 for the best
  single models (ovarian), with the ensemble reaching 15 of 15 at
  specificity as low as 85.1% (137/161); 9 of 10 for GPT-4.1-mini
  (ArrayExpress), 10 of 10 for the ensemble.
- Few positives: 8, 15 and 10. The authors note one or two decisions move
  the estimates materially.
- Cost $0.01–1.12 per batch; median screening time 6.0 minutes.
- Released: code (github.com/osun24/finding-datasets-with-LLMs); reviewer
  decisions and model outputs on Zenodo (doi:10.5281/zenodo.21302733).

**Relation:**
- **The step before ours.** Iteration 1's corpus triage did this by hand for
  the Down syndrome corpus.
- **The same columns, read implicitly.** The lung criteria ask whether a
  sample table holds survival time and status, or stage. Several held-out
  errors were missed survival or staging columns. A pooled variable
  anchored to overall survival time would turn such criteria into lookups.
  Untested.
- **The ensemble doesn't transfer.** Including on any model's vote raises
  sensitivity because a person checks every include. Applied to pooling it
  would multiply false merges. They report agreement across seeds only as a
  range, not as a confidence score, and list certainty as future work, so
  nothing here helps our confidence gap (see Limits).
- **Precedent.** A development/held-out split, an untuned retrospective
  case, few positives and a gold that isn't independent, all stated as
  limits in a *Scientific Data* paper. Ours has the same shape.

## What colharmonize contributes

Each claim comes with the evidence that supports it and its limits.

1. **Measured pooling across studies, without a target schema and without
   information loss.** Schema-free grouping has precedent: EMBERS clusters
   keys across studies with an LLM judging, and Gonçalves et al. cluster
   field names by string distance. Neither scores its grouping. colharmonize
   measures it, as pairwise pooling precision and recall against a
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
   - Every identifier is checked against a pinned release. None of the
     papers added on 2026-10-13 names an ontology version. Gonçalves et al.
     date their BioPortal extraction; MetaSRA, Ikeda et al. and ARMS use
     whatever release is current; EMBERS, Sundaram et al. and ARMS output
     labels or no ontology at all.
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
