"""Gold standard for the Down syndrome tuning set.

Converted 2026-10-05 from iteration 2's 84 gold pairs (13 datasets:
`../efo-column-mapping/data/interim/gold_standard*.csv`) into the iteration-3
format: a partition into poolable variables plus an annotation per variable.
Every call was re-read under the owner-confirmed rules in goldlib.py, not
copied. Calls that differ from iteration 2, or that are new judgments, carry a
REVIEW flag until the owner has seen them.

Unlike the generalization corpus, this is TUNING data. Iteration 2 already
showed pipeline candidates for these datasets, so it is not a held-out
measurement.

Columns recovered from titles or source names by iteration 2's extraction are
keyed `title#<key>` or `source_name#<key>`. For those rows the meaningful check
is whether the pipeline recovers a column in the right variable, not whether it
reproduces iteration 2's key spelling.

Run: python eval/gold/build_ds_tuning_gold.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goldlib  # noqa: E402

HERE = Path(__file__).resolve().parent
SNAPSHOT = goldlib.ROOT / "eval/snapshots/ds_tuning_characteristics.json"

# (variable_id, name, predicate, primary_curie, qualifiers, value_type, rationale)
V = [
    ("sex", "biological sex", "exact", "PATO:0000047", [], "categorical", ""),
    ("age", "age", "exact", "EFO:0000246", [], "continuous",
     "Age of the subject at sampling. 'age at draw' belongs here because the draw is the sampling event."),
    ("age_at_diagnosis", "age at diagnosis", "exact", "EFO:0004918", [("unit", "UO:0000033")], "continuous", ""),
    ("age_at_dissection", "age at dissection", "broad", "EFO:0000246",
     [("event_time_anchor", "dissection"), ("unit", "UO:0000033")], "continuous",
     "D59..D136. Fetal samples count from conception and organoids from the start of culture, so not pooled with postnatal age."),
    ("gestational_age", "gestational age", "exact", "EFO:0005112", [("unit", "UO:0000034")], "continuous", ""),
    ("developmental_stage", "developmental stage", "exact", "EFO:0000399", [], "categorical", "fetus."),
    ("organism_part", "organism part", "exact", "EFO:0000635", [], "categorical", ""),
    ("specimen_source", "specimen source", "broad", "OBI:0100051", [], "categorical",
     "What the specimen was derived from: primary fetal tissue, stem-cell-derived organoids, cell lines."),
    ("cell_type", "cell type", "exact", "EFO:0000324", [], "categorical", ""),
    ("cell_line", "cell line", "exact", "CL:0000010", [], "categorical",
     "Values are named lines (K562, AG05397, par/dis): each is a cultured cell, coarse but well formed (iteration 2 decision 8.3)."),
    ("karyotype", "karyotype", "exact", "EFO:0004426", [], "categorical",
     "Chromosome-21 complement: WT/Trisomy 21, T21/D21, Euploid/TS21/TS13, trisomic/disomic, euploid/Down syndrome. Pooling recodes values to one vocabulary; raw values are kept."),
    ("disease", "disease", "exact", "MONDO:0000001", [], "categorical", ""),
    ("down_syndrome_status", "Down syndrome status", "indicator", "MONDO:0008608", [], "categorical",
     "Records only the presence of Down syndrome."),
    ("congenital_abnormality", "congenital abnormality", "exact", "MONDO:0019755", [], "categorical",
     "None / Downs / Other / Unknown (iteration 2 decision 4.8)."),
    ("cohort", "cohort", "exact", "EFO:0004445", [], "categorical", "Study, registry or consortium a sample came from."),
    ("batch", "batch", "exact", "EFO:0005067", [], "categorical",
     "EFO:0005067 is defined as 'a block or batch'."),
    ("amplification_batch", "amplification batch", "broad", "EFO:0005067", [("method", "amplification")], "categorical", ""),
    ("hybridization_batch", "hybridization batch", "broad", "EFO:0005067", [("method", "hybridization")], "categorical", ""),
    ("subject_id", "subject identifier", "none", "", [], "identifier", ""),
    ("replicate", "replicate", "broad", "EFO:0000683", [], "ordinal", "Replicate number."),
    ("group_assignment", "comparison group", "broad", "OBI:0600015", [], "categorical", "Iteration 2 decision 4.8."),
    ("treatment", "treatment", "exact", "EFO:0000727", [], "categorical", ""),
    ("chip_antibody", "ChIP antibody", "broad", "EFO:0000264", [("method", "EFO:0004176")], "categorical", ""),
    ("library_type", "library type", "broad", "OBI:0000711", [], "categorical", "strand-specific."),
    ("sample_pooling", "pooled or single sample", "broad", "OBI:0000747", [], "categorical",
     "pooled organoids / single organoid."),
    ("days_in_vitro", "days in vitro", "broad", "EFO:0000433",
     [("event_time_anchor", "start of culture"), ("unit", "UO:0000033")], "continuous", ""),
    ("braak_stage", "Braak stage", "broad", "EFO:0000410", [("method", "Braak staging")], "ordinal",
     "Iteration 2 gold: disease staging."),
    ("cause_of_death", "cause of death", "none", "", [], "categorical", "No adequate term (iteration 2 gold)."),
    ("post_mortem_interval", "post mortem interval", "broad", "EFO:0000433",
     [("event_time_anchor", "death"), ("unit", "UO:0000032")], "continuous", ""),
    ("bcr_abl", "BCR-ABL1 t(9;22) status", "indicator", "EFO:0004024",
     [("object_class", "BCR-ABL1 t(9;22)")], "categorical",
     "EFO has no BCR-ABL1 fusion term, only diseases defined by it."),
    ("e2a_pbx", "E2A-PBX1 t(1;19) status", "indicator", "EFO:0004024",
     [("object_class", "E2A-PBX1 (TCF3-PBX1) t(1;19)")], "categorical", ""),
    ("mll_rearrangement", "MLL rearrangement status", "indicator", "EFO:0004024",
     [("object_class", "MLL (KMT2A) rearrangement")], "categorical",
     "MLL rearrangements in ALL are almost always translocations."),
    ("tel_aml1", "TEL-AML1 t(12;21) status", "indicator", "EFO:0004024",
     [("object_class", "TEL-AML1 (ETV6-RUNX1) t(12;21)")], "categorical", ""),
    ("trisomy_4_10", "trisomy 4 and 10 status", "indicator", "EFO:0000336",
     [("object_class", "trisomy 4 and 10")], "categorical", ""),
    ("flt3_itd", "FLT3-ITD status", "indicator", "EFO:0004015",
     [("object_class", "FLT3 internal tandem duplication")], "categorical",
     "EFO:0004015 duplication: 'part of the genome is duplicated'."),
    ("cns_status", "CNS status", "broad", "EFO:0000410", [("object_class", "UBERON:0001017")], "ordinal",
     "Degree of central nervous system involvement (CNS1-3), a leukaemia staging element."),
    ("testicular_involvement", "testicular involvement", "none", "", [], "categorical",
     "No term for testicular involvement by leukaemia."),
    ("wbc_count", "white blood cell count", "broad", "EFO:0004586",
     [("object_class", "CL:0000738"), ("unit", "10^3/uL")], "continuous",
     "EFO:0004308 leukocyte count is deprecated in v3.94.0 (iteration 2 decision 6a.5); complete blood cell count + leukocyte expresses it without the deprecated term."),
    ("blast_count", "blast count", "exact", "EFO:0009232", [("unit", "UO:0000187")], "continuous", "-1 marks missing."),
    ("viability", "sample viability", "exact", "PATO:0000169", [("unit", "UO:0000187")], "continuous", "-1 marks missing."),
    ("training_test_set", "training or test set", "none", "", [], "categorical", "Analysis artefact."),
    ("ethnic_group", "ethnic group", "exact", "EFO:0001799", [], "categorical", ""),
    ("crlf2_expression_array", "CRLF2 expression (arrays)", "broad", "EFO:0009865",
     [("object_class", "CRLF2"), ("method", "expression microarray"), ("unit", "log2")], "continuous", ""),
    ("crlf2_expression_qpcr", "CRLF2 expression (qRT-PCR)", "broad", "EFO:0009865",
     [("object_class", "CRLF2"), ("method", "qRT-PCR"), ("unit", "relative to SI-DS-ALL-12")], "continuous",
     "Different method and scale from the array values, so a different variable."),
    ("crlf2_expression_strata", "CRLF2 expression stratum", "broad", "EFO:0009865",
     [("object_class", "CRLF2"), ("method", "expression stratification")], "categorical", ""),
    ("crlf2_fish", "CRLF2 FISH result", "broad", "EFO:0000336",
     [("object_class", "CRLF2"), ("method", "FISH")], "categorical", "Deletion / IGH@-CRLF2 / Normal."),
    ("crlf2_mutation", "CRLF2 mutation", "broad", "EFO:0000513", [("object_class", "CRLF2")], "categorical", ""),
    ("jak2_r683_mutation", "JAK2 R683 mutation", "broad", "EFO:0000513", [("object_class", "JAK2 R683")], "categorical", ""),
    ("genetic_aberration", "genetic aberration", "exact", "EFO:0000336", [], "categorical",
     "TEL-AML1 / High Hyperdiploid / BCR-ABL / MLL / E2A-PBX1."),
    ("snp_dataset", "SNP dataset", "none", "", [], "categorical",
     "Co-occurs with 'gene expression dataset', so it cannot join cohort."),
]

R = "REVIEW"
# (accession, raw_key, source, variable_id, unit, flags, note)
C = [
    ("GSE11877", "BCR-ABL, t(9;22)", "characteristic", "bcr_abl", "", "", "was NO_MATCH (decision 8.1); indicator now expresses it"),
    ("GSE11877", "CNS status", "characteristic", "cns_status", "", "", "was NO_MATCH; owner accepted 2026-10-05"),
    ("GSE11877", "E2A-PBX, t(1;19)", "characteristic", "e2a_pbx", "", "", "was NO_MATCH (decision 8.1)"),
    ("GSE11877", "MLL", "characteristic", "mll_rearrangement", "", "", "was NO_MATCH (decision 8.1)"),
    ("GSE11877", "TEL-AML,t(12;21)", "characteristic", "tel_aml1", "", "", "was NO_MATCH (decision 8.1)"),
    ("GSE11877", "WBC, 1000/microliter", "characteristic", "wbc_count", "10^3/uL", "", "was NO_MATCH; owner accepted 2026-10-05"),
    ("GSE11877", "age in days at diagnosis", "characteristic", "age_at_diagnosis", "UO:0000033", "", ""),
    ("GSE11877", "amplification set", "characteristic", "amplification_batch", "", "", "was NO_MATCH; owner accepted 2026-10-05"),
    ("GSE11877", "blast count, % of sample, -1=unavailable", "characteristic", "blast_count", "UO:0000187", "", ""),
    ("GSE11877", "congenital abnormality", "characteristic", "congenital_abnormality", "", "", ""),
    ("GSE11877", "gender", "characteristic", "sex", "", "", ""),
    ("GSE11877", "hybridization set", "characteristic", "hybridization_batch", "", "", "was NO_MATCH; owner accepted 2026-10-05"),
    ("GSE11877", "race", "characteristic", "ethnic_group", "", "", ""),
    ("GSE11877", "sample viability, % of sample, -1=unavailable", "characteristic", "viability", "UO:0000187", "", ""),
    ("GSE11877", "testicular involvement", "characteristic", "testicular_involvement", "", "", ""),
    ("GSE11877", "tissue type", "characteristic", "organism_part", "", "", ""),
    ("GSE11877", "training or test set", "characteristic", "training_test_set", "", "", ""),
    ("GSE11877", "trisomy 4 and 10", "characteristic", "trisomy_4_10", "", "", "was NO_MATCH (decision 8.1)"),
    ("GSE124252", "age at dissection (day)", "characteristic", "age_at_dissection", "UO:0000033", "", "was age; owner accepted 2026-10-05"),
    ("GSE124252", "days in vitro", "characteristic", "days_in_vitro", "UO:0000033", "", ""),
    ("GSE124252", "karyotype", "characteristic", "karyotype", "", "", ""),
    ("GSE124252", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE124252", "tissue origin", "characteristic", "specimen_source", "", "", "was NO_MATCH; owner accepted 2026-10-05"),
    ("GSE128621", "Sex", "characteristic", "sex", "", "", ""),
    ("GSE128621", "age", "characteristic", "age", "UO:0000036 (inferred)", "", ""),
    ("GSE128621", "cell type", "characteristic", "cell_type", "", "", "WBC"),
    ("GSE128621", "karyotype", "characteristic", "karyotype", "", "", ""),
    ("GSE128621", "library type", "characteristic", "library_type", "", "", ""),
    ("GSE1397", "title#cell type", "title", "cell_type", "", "", ""),
    ("GSE1397", "title#comparison group", "title", "group_assignment", "", "", ""),
    ("GSE1397", "source_name#gestational age", "title", "gestational_age", "UO:0000034", "", ""),
    ("GSE1397", "title#karyotype", "title", "karyotype", "", "", ""),
    ("GSE1397", "title#replicate", "title", "replicate", "", "", ""),
    ("GSE1397", "source_name#source material", "title", "specimen_source", "", "",
     "was organism part; co-occurs with title#tissue with different values, so it cannot share organism part; owner accepted 2026-10-05"),
    ("GSE1397", "title#tissue", "title", "organism_part", "", "", ""),
    ("GSE16176", "condition", "characteristic", "karyotype", "", "", "euploid / Down syndrome; pools with value recode 'Down syndrome' -> 'Trisomy 21' (raw value kept); owner decision 2026-10-05"),
    ("GSE16176", "developmental stage", "characteristic", "developmental_stage", "", "", ""),
    ("GSE16176", "gestational age (weeks, days)", "characteristic", "gestational_age", "UO:0000034", "", "'21 3/7' = weeks and days"),
    ("GSE16176", "sex", "characteristic", "sex", "", "", ""),
    ("GSE16176", "tissue", "characteristic", "organism_part", "", "", "amniotic fluid"),
    ("GSE17459", "cell type", "characteristic", "cell_type", "", "", ""),
    ("GSE17459", "condition", "characteristic", "disease", "", "", ""),
    ("GSE17459", "crlf2 expression levels (gene expression arrays - log2)", "characteristic", "crlf2_expression_array", "log2", "", "was NO_MATCH"),
    ("GSE17459", "crlf2 expression levels (qrt-pcr - relative to si-ds-all-12)", "characteristic", "crlf2_expression_qpcr", "relative", "", "was NO_MATCH"),
    ("GSE17459", "crlf2 expression levels stratification", "characteristic", "crlf2_expression_strata", "", "", "was NO_MATCH"),
    ("GSE17459", "crlf2 fish", "characteristic", "crlf2_fish", "", "", "was chromosomal aberration; now qualified with CRLF2 and FISH"),
    ("GSE17459", "crlf2 mutation", "characteristic", "crlf2_mutation", "", "", "was genotype; now qualified with CRLF2"),
    ("GSE17459", "gene expression dataset", "characteristic", "cohort", "", "", ""),
    ("GSE17459", "genetic aberration", "characteristic", "genetic_aberration", "", "", ""),
    ("GSE17459", "jak2 r683 mutation", "characteristic", "jak2_r683_mutation", "", "", "was genotype; now qualified with JAK2 R683"),
    ("GSE17459", "snp dataset", "characteristic", "snp_dataset", "", "", ""),
    ("GSE183701", "Sex", "characteristic", "sex", "", "", ""),
    ("GSE183701", "age at draw", "characteristic", "age", "UO:0000036 (inferred)", "", "the draw is the sampling event, so this is plain age; owner accepted 2026-10-05"),
    ("GSE183701", "registry", "characteristic", "cohort", "", "", ""),
    ("GSE183701", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE185192", "cell line", "characteristic", "cell_line", "", "", ""),
    ("GSE185192", "cell type", "characteristic", "cell_type", "", "", ""),
    ("GSE185192", "chip antibody", "characteristic", "chip_antibody", "", "", "constant 'none'"),
    ("GSE185192", "strain", "characteristic", "disease", "", "", "values over name (decision 6a.4)"),
    ("GSE185192", "treatment", "characteristic", "treatment", "", "", ""),
    ("GSE222365", "batch", "characteristic", "batch", "", "", "was NO_MATCH; owner accepted 2026-10-05"),
    ("GSE222365", "cell line", "characteristic", "cell_line", "", "", ""),
    ("GSE222365", "cell type", "characteristic", "specimen_source", "", "", "was cell type; an organoid is not a cell type; owner accepted 2026-10-05"),
    ("GSE222365", "genotype", "characteristic", "karyotype", "", "", "was ploidy; owner accepted 2026-10-05"),
    ("GSE222365", "sample type", "characteristic", "sample_pooling", "", "", ""),
    ("GSE222365", "study", "characteristic", "cohort", "", "", "was NO_MATCH; expanded / pilot; owner accepted 2026-10-05"),
    ("GSE4119", "title#diagnosis", "title", "disease", "", "", ""),
    ("GSE4119", "title#down syndrome status", "title", "down_syndrome_status", "", "", "was disease"),
    ("GSE4119", "title#patient id", "title", "subject_id", "", "", ""),
    ("GSE4119", "source_name#tissue", "title", "organism_part", "", "", "'bone marrow or peripheral blood'"),
    ("GSE5390", "Age (years)", "characteristic", "age", "UO:0000036", "", ""),
    ("GSE5390", "Braak stage", "characteristic", "braak_stage", "", "", ""),
    ("GSE5390", "Cause of death", "characteristic", "cause_of_death", "", "", ""),
    ("GSE5390", "Disease_status", "characteristic", "disease", "", "", ""),
    ("GSE5390", "Gender", "characteristic", "sex", "", "", ""),
    ("GSE5390", "Post mortem interval (hours)", "characteristic", "post_mortem_interval", "UO:0000032", "", ""),
    ("GSE61804", "condition", "characteristic", "disease", "", "", ""),
    ("GSE61804", "flt3-itd", "characteristic", "flt3_itd", "", "", "was NO_MATCH (decision 8.1)"),
    ("GSE61804", "gender", "characteristic", "sex", "", "", ""),
    ("GSE61804", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE79842", "age", "characteristic", "age", "UO:0000036", "", "unit in values ('1 Year old', '2 Day old')"),
    ("GSE79842", "batch", "characteristic", "batch", "", "", "was NO_MATCH; owner accepted 2026-10-05"),
    ("GSE79842", "condition", "characteristic", "karyotype", "", "", "was ploidy; owner accepted 2026-10-05"),
    ("GSE79842", "gender", "characteristic", "sex", "", "", ""),
]

if __name__ == "__main__":
    sys.exit(goldlib.build(V, C, SNAPSHOT, HERE, "ds_tuning"))
