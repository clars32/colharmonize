"""Build and validate the gold standard for the sealed generalization corpus.

Curated 2026-10-02 from sample characteristics and titles only
(`eval/snapshots/generalization_characteristics.json`), before any candidate
generation ran on these series. Terms were sought across the full allowlisted
pool of pinned EFO v3.94.0, not a restricted search space, so that candidate
recall measured against this gold cannot be circular.

The gold has two layers:

* a partition: every (dataset, column) belongs to exactly one gold variable.
  Columns in one variable are the ones a careful curator would stack into a
  single column of a pooled table without losing meaning.
* an annotation per variable: primary term, predicate and qualifiers.

Predicates:
  exact      the variable means the term; its values are instances or
             measurements of it (sex -> biological sex)
  broad      the term is broader; the variable keeps its own name and the term
             is an anchor (Mayo score -> illness severity status)
  indicator  the variable is a yes/no or 0/1 indicator of the term
             (shock: Yes/No -> septic shock)
  none       no adequate term in the pinned pool; the variable still pools

Partition rules:
  1. Same property, same referent, same reference event, compatible value
     domain (convertible units or a lossless recode).
  2. Columns that both have values on the same samples are never pooled,
     unless their values are identical on every shared sample
     (duplicate encoding, flagged).
  3. Columns of one dataset covering disjoint samples may pool.
  4. Different classification systems or scoring instruments are different
     variables even when they share an anchor term.

Run: python eval/gold/build_generalization_gold.py
Writes generalization_variables.tsv and generalization_columns.tsv next to
this file, and exits non-zero on any validation failure.
"""
from __future__ import annotations

import csv
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SNAPSHOT = ROOT / "eval/snapshots/generalization_characteristics.json"
INDEX = ROOT.parent / "efo-column-mapping/data/ontology/efo_index_v3.94.0.parquet"
ALLOWED = {"EFO", "UBERON", "CL", "MONDO", "PATO", "NCIT", "OBI", "CHEBI", "UO"}
PREDICATES = {"exact", "broad", "indicator", "none"}
SLOTS = {"subject", "object_class", "event_time_anchor", "method", "unit"}
CURIE = re.compile(r"^[A-Za-z]+:\d+$")
FLAGS = {"REVIEW", "assumed_convention", "duplicate_encoding"}

# (variable_id, name, predicate, primary_curie, qualifiers, value_type, rationale)
# qualifiers: list of (slot, curie-or-text); text is recorded as ungrounded.
V = [
    # --- recur across disease areas --------------------------------------
    ("sex", "biological sex", "exact", "PATO:0000047", [], "categorical",
     "Sex/gender columns; values male/female in every member."),
    ("age", "age", "exact", "EFO:0000246", [], "continuous",
     "Age of the subject at sampling. Reference event never stated, so not inferred as age at diagnosis."),
    ("organism_part", "organism part", "exact", "EFO:0000635", [], "categorical",
     "Anatomical source of the sample (blood, colonic mucosa, vastus lateralis, intestine)."),
    ("cell_type", "cell type", "exact", "EFO:0000324", [], "categorical",
     "Values name a cell population (primary islet cells)."),
    ("specimen_type", "specimen type", "broad", "OBI:0100051", [], "categorical",
     "Kind of specimen (biopsy), not its anatomical source."),
    ("subject_id", "subject identifier", "none", "", [], "identifier",
     "Identifiers of individuals. EFO has `individual` but no identifier class; the column names the individual, it is not one."),
    ("sample_id", "sample identifier", "none", "", [], "identifier",
     "Identifiers of samples."),
    ("ethnic_group", "ethnic group", "exact", "EFO:0001799", [], "categorical",
     "Race/ethnicity or population of origin."),
    ("disease", "disease", "exact", "MONDO:0000001", [], "categorical",
     "Values name the subject's diagnosis (incl. healthy/control), sometimes with stage or complication detail kept verbatim. Pooling is lossless: every value is still a diagnosis."),
    ("disease_duration", "disease duration", "broad", "EFO:0000433",
     [("event_time_anchor", "diagnosis"), ("unit", "UO:0000036")], "continuous",
     "Time since diagnosis, any disease; the disease itself is carried by the disease column."),
    ("treatment", "treatment", "exact", "EFO:0000727", [], "categorical",
     "Administered intervention (drug, placebo, meal test, none, trial arm name). `treatment` is the most specific term true of all members; `compound based treatment` would be false for MMTT. Arm names (MK2206 Arm / Control Arm) still identify the regimen, so they pool here."),
    ("time_since_treatment_start", "timepoint (since start of treatment)", "exact", "EFO:0000724",
     [("event_time_anchor", "start of treatment"), ("unit", "UO:0000034")], "temporal",
     "Weeks since start of biologic therapy (golimumab week 0/6; vedolizumab 0W/14W/54W)."),
    ("time_relative_to_meal_test", "timepoint (relative to mixed meal tolerance test)", "exact", "EFO:0000724",
     [("event_time_anchor", "mixed meal tolerance test")], "temporal",
     "Before vs 1 hour after a meal challenge. Different reference event from therapy start."),
    ("sampling_time_hours", "timepoint (hours, reference not stated)", "exact", "EFO:0000724",
     [("unit", "UO:0000032")], "temporal",
     "0 hr / 24 hrs; reference event not stated in metadata."),
    ("timepoint_coded", "timepoint (coded T1-T3)", "exact", "EFO:0000724", [], "ordinal",
     "Coded visits with no interval in metadata; not convertible to the hours variable."),
    ("study_day", "study day", "exact", "EFO:0000724",
     [("event_time_anchor", "study start"), ("unit", "UO:0000033")], "temporal",
     "Day part of D2_ZT_15:30."),
    ("zeitgeber_time", "zeitgeber time", "exact", "EFO:0000724",
     [("event_time_anchor", "lights on (zeitgeber)"), ("unit", "UO:0000032")], "temporal",
     "Circadian clock part of D2_ZT_15:30."),
    # --- breast cancer ---------------------------------------------------
    ("er_status", "estrogen receptor status", "exact", "EFO:0005512", [], "categorical",
     "0/1 coded in both members."),
    ("pr_status", "progesterone receptor status", "exact", "EFO:0005513", [], "categorical",
     "`pr` and `pgr status`."),
    ("her2_status", "HER2 status", "exact", "EFO:0005514", [], "categorical", "0/1 coded."),
    ("hormone_receptor_status", "hormone receptor status", "none", "", [], "categorical",
     "`hr`: ER or PR positive. Broader than either receptor term; EFO has no combined term."),
    ("pam50_subtype", "PAM50 subtype", "broad", "MONDO:0000001",
     [("method", "PAM50")], "categorical",
     "Basal/HER2/LumA/LumB are breast carcinoma subtypes from the PAM50 classifier."),
    ("receptor_subtype", "receptor-defined subtype", "broad", "MONDO:0000001",
     [("method", "receptor status (IHC)")], "categorical",
     "TN vs LUM. Different classification system from PAM50, so a different variable."),
    ("histological_type", "histological type", "broad", "MONDO:0000001",
     [("method", "histopathology")], "categorical", "IDC/ILC/other."),
    ("tumor_size", "tumor size", "exact", "EFO:0004134", [], "continuous",
     "Units unstated: values imply cm in GSE237290 and mm in GSE58984. Pools after conversion."),
    ("tumor_grade", "tumor grade", "none", "", [], "ordinal",
     "I/II/III. EFO has only grade instances (MONDO tumor grade 1..4), no grade category; `disease staging` is stage, not grade."),
    ("t_stage", "T stage", "exact", "EFO:0004928", [], "ordinal", "1-4."),
    ("nodal_status", "nodal status", "broad", "EFO:0004927", [], "categorical",
     "0 = node negative, 1 = node positive: a coarsening of N stage."),
    ("positive_lymph_node_count", "number of positive lymph nodes", "none", "", [], "continuous",
     "A count. Derivable into nodal status but not equivalent to it, so not pooled."),
    ("pcr", "pathological complete response", "indicator", "EFO:0009697", [], "categorical",
     "pCR/No pCR and 0/1/-1."),
    ("neoadjuvant_response_index", "neoadjuvant response index", "broad", "EFO:0008383",
     [("method", "neoadjuvant response index")], "continuous", "NRI score."),
    ("chemotherapy_received", "chemotherapy received", "indicator", "EFO:0000727",
     [("object_class", "chemotherapy")], "categorical", "0/1."),
    ("stromal_til", "stromal tumour-infiltrating lymphocytes", "broad", "EFO:0009832",
     [("object_class", "stromal lymphocytes"), ("unit", "UO:0000187")], "continuous",
     "Percent stromal TILs. GSE237290 `til` states no compartment; the usual convention "
     "(International TILs Working Group scores stromal TILs) is assumed and flagged."),
    ("intratumoral_til", "intratumoral lymphocytic infiltration", "broad", "EFO:0009832",
     [("object_class", "intratumoral lymphocytes")], "continuous", ""),
    ("tls_score", "tertiary lymphoid structure score", "none", "", [], "ordinal", "0/1+/2+/3+."),
    ("gc", "gc (meaning not stated)", "none", "", [], "categorical",
     "0/1; the abbreviation is not explained in the metadata."),
    ("os_time", "overall survival time", "exact", "EFO:0000638", [], "continuous", "Units unstated (years by magnitude)."),
    ("os_event", "overall survival event (death)", "indicator", "EFO:0000480", [], "categorical", "0/1."),
    ("rfi_time", "recurrence-free interval", "broad", "EFO:0000409", [], "continuous",
     "RFI does not count death as an event; RFS does. Different endpoints, so not pooled with rfs_time."),
    ("rfs_time", "relapse-free survival time", "broad", "EFO:0000409",
     [("unit", "UO:0000036")], "continuous", ""),
    ("recurrence_event", "recurrence", "indicator", "EFO:0004952", [], "categorical",
     "event.rfi 0/1 and recurrence No/Yes."),
    ("dss_time", "disease-specific survival time", "broad", "EFO:0000714",
     [("object_class", "EFO:0030050")], "continuous", ""),
    ("dss_event", "disease-specific death", "indicator", "EFO:0030050", [], "categorical", "0/1."),
    ("ddfs_time", "distant disease-free survival time", "exact", "EFO:0000412", [], "continuous",
     "Units unstated (days by magnitude)."),
    ("distant_metastasis_event", "distant metastasis", "indicator", "EFO:0009708",
     [("object_class", "distant")], "categorical", "0/1."),
    # --- sepsis ----------------------------------------------------------
    ("septic_shock_status", "septic shock", "indicator", "EFO:0006834", [], "categorical",
     "shock Yes/No and shock_status shock/no_shock/control."),
    ("sepsis_severity", "sepsis severity", "exact", "EFO:0007863",
     [("object_class", "sepsis")], "categorical",
     "no_shock / fluid_responsive / vasopressor-responsive / control."),
    ("infection_type", "infection type", "broad", "EFO:0000544", [], "categorical",
     "viral / bacterial / viral_bacterial / no_source."),
    ("mortality_30d", "30-day mortality", "indicator", "EFO:0000480",
     [("event_time_anchor", "within 30 days")], "categorical",
     "Fixed 30-day window, so not pooled with follow_up_status (window not stated)."),
    ("follow_up_status", "follow-up status", "exact", "EFO:0030038", [], "categorical", "Survived/Died."),
    # --- inflammatory bowel disease --------------------------------------
    ("inflammation_status", "inflammation status", "none", "", [], "categorical",
     "inflamed/uninflamed sample site. No general inflammation term in the allowlisted pool."),
    ("mayo_score", "Mayo score", "broad", "EFO:0007863", [("method", "Mayo score")], "ordinal",
     "UC disease-activity index, 0-12."),
    ("nancy_index", "Nancy histological index", "broad", "EFO:0007863",
     [("method", "Nancy histological index")], "ordinal",
     "Different instrument from the Mayo score, so a different variable."),
    ("uc_activity_status", "UC activity status", "broad", "EFO:0007863",
     [("object_class", "MONDO:0005101")], "categorical", "Active/Inactive part of a combined column."),
    ("treatment_response_wk6", "treatment response at week 6", "broad", "EFO:0008383",
     [("event_time_anchor", "week 6 of treatment")], "categorical", ""),
    ("sample_age", "sample age (meaning unclear)", "none", "", [], "continuous",
     "`sample_age(y)` 1/2/3, alongside a separate patient_age. Probably storage time; not stated."),
    ("qc_status", "QC status", "none", "", [], "categorical", "include/EXCLUDE."),
    # --- type 2 diabetes -------------------------------------------------
    ("bmi", "body mass index", "exact", "EFO:0004340", [], "continuous", "kg/m2 (ungrounded unit)."),
    ("hba1c", "HbA1c", "exact", "EFO:0004541", [], "continuous",
     "Reported in % (NGSP) and mmol/mol (IFCC); convertible."),
    ("fasting_glucose", "fasting glucose", "broad", "EFO:0004468",
     [("event_time_anchor", "fasting")], "continuous",
     "mmol/L in one series, mg/dL ('Glucose (AC)', before meals) in the other; convertible."),
    ("fasting_insulin", "fasting insulin", "broad", "EFO:0004467",
     [("event_time_anchor", "fasting")], "continuous", ""),
    ("fasting_c_peptide", "fasting C-peptide", "exact", "EFO:0010813", [], "continuous", ""),
    ("homa_ir", "HOMA-IR", "exact", "EFO:0004501", [], "continuous", ""),
    ("clinical_phenotype_notes", "clinical phenotype notes", "broad", "EFO:0000352", [], "free_text",
     "Free-text medical-record descriptions."),
    ("uacr", "urinary albumin to creatinine ratio", "exact", "EFO:0007778", [], "continuous",
     "Split out of GSE189007 `phenotype`, where it appears as 'UARC: <value> (mg/g)'."),
    ("recruitment_site", "recruitment site", "none", "", [], "categorical", "Hospital names."),
]

# (accession, raw_key, source, variable_id, unit, flags, note)
#   source: characteristic | title | split:<parent raw_key>
#   variable_id "SPLIT" marks a column whose parts are listed separately.
#   flags: comma-separated, from FLAGS. REVIEW marks a judgment call awaiting the
#   owner; assumed_convention marks a usual convention assumed because the metadata
#   does not say (added automatically when a unit is inferred); duplicate_encoding
#   marks co-occurring columns pooled because their values are identical.
C = [
    # breast cancer
    ("GSE237290", "age", "characteristic", "age", "UO:0000036 (inferred)", "", ""),
    ("GSE237290", "pam50", "characteristic", "pam50_subtype", "", "", ""),
    ("GSE237290", "tumor_size", "characteristic", "tumor_size", "UO:0000015 (inferred)", "", "unit inferred from magnitude; owner accepted 2026-10-05"),
    ("GSE237290", "tumor_grade", "characteristic", "tumor_grade", "", "", ""),
    ("GSE237290", "histology", "characteristic", "histological_type", "", "", ""),
    ("GSE237290", "er", "characteristic", "er_status", "", "", "0/1"),
    ("GSE237290", "pr", "characteristic", "pr_status", "", "", "0/1"),
    ("GSE237290", "her2", "characteristic", "her2_status", "", "", "0/1"),
    ("GSE237290", "chemo", "characteristic", "chemotherapy_received", "", "", ""),
    ("GSE237290", "til", "characteristic", "stromal_til", "UO:0000187", "assumed_convention", "compartment not stated; stromal assumed (TIL Working Group convention). Owner decision 2026-10-05"),
    ("GSE237290", "tls", "characteristic", "tls_score", "", "", ""),
    ("GSE237290", "gc", "characteristic", "gc", "", "", "meaning unknown; owner accepted 2026-10-05"),
    ("GSE237290", "time.os", "characteristic", "os_time", "UO:0000036 (inferred)", "", ""),
    ("GSE237290", "event.os", "characteristic", "os_event", "", "", ""),
    ("GSE237290", "time.rfi", "characteristic", "rfi_time", "UO:0000036 (inferred)", "", ""),
    ("GSE237290", "event.rfi", "characteristic", "recurrence_event", "", "", ""),
    ("GSE237290", "time.dss", "characteristic", "dss_time", "UO:0000036 (inferred)", "", ""),
    ("GSE237290", "event.dss", "characteristic", "dss_event", "", "", ""),
    ("GSE58984", "tissue", "characteristic", "organism_part", "", "", "value 'HER2 breast cancer tumor' folds disease state into the anatomical source; owner accepted 2026-10-05"),
    ("GSE58984", "treatment", "characteristic", "treatment", "", "", "constant: trastuzumab"),
    ("GSE58984", "age", "characteristic", "age", "UO:0000036 (inferred)", "", ""),
    ("GSE58984", "tumor size", "characteristic", "tumor_size", "UO:0000016 (inferred)", "", "unit inferred from magnitude; owner accepted 2026-10-05"),
    ("GSE58984", "nodes positive", "characteristic", "positive_lymph_node_count", "", "", ""),
    ("GSE58984", "er status", "characteristic", "er_status", "", "", "0/1"),
    ("GSE58984", "pgr status", "characteristic", "pr_status", "", "", "0/1"),
    ("GSE58984", "distant metastasis", "characteristic", "distant_metastasis_event", "", "", ""),
    ("GSE58984", "time to ddfs", "characteristic", "ddfs_time", "UO:0000033 (inferred)", "", ""),
    ("GSE58984", "intratumoral lymphocytic infiltration", "characteristic", "intratumoral_til", "", "", ""),
    ("GSE58984", "stromal lymphocytic infiltration", "characteristic", "stromal_til", "", "", ""),
    ("GSE192341", "tissue type", "characteristic", "specimen_type", "", "", "constant: biopsy"),
    ("GSE192341", "pathological complete response (pcr)", "characteristic", "pcr", "", "", ""),
    ("GSE192341", "subtype", "characteristic", "receptor_subtype", "", "", ""),
    ("GSE192341", "sample_id", "characteristic", "sample_id", "", "", ""),
    ("GSE192341", "age", "characteristic", "age", "UO:0000036 (inferred)", "", ""),
    ("GSE192341", "neoadjuvant response index (nri)", "characteristic", "neoadjuvant_response_index", "", "", ""),
    ("GSE192341", "t-stage", "characteristic", "t_stage", "", "", ""),
    ("GSE192341", "n-stage (0, neg; 1, pos)", "characteristic", "nodal_status", "", "", "legend inside the key"),
    ("GSE192341", "recurrence", "characteristic", "recurrence_event", "", "", ""),
    ("GSE192341", "rfs (years)", "characteristic", "rfs_time", "UO:0000036", "", ""),
    ("GSE149322", "her2", "characteristic", "her2_status", "", "", "0/1"),
    ("GSE149322", "hr", "characteristic", "hormone_receptor_status", "", "", ""),
    ("GSE149322", "pcr", "characteristic", "pcr", "", "", "-1 for one sample (missing?)"),
    ("GSE149322", "arm", "characteristic", "treatment", "", "", "arm names identify the regimen; owner decision 2026-10-05"),
    # sepsis
    ("GSE272769", "age", "characteristic", "age", "UO:0000036 (inferred)", "", ""),
    ("GSE272769", "Sex", "characteristic", "sex", "", "", ""),
    ("GSE272769", "mort30", "characteristic", "mortality_30d", "", "", ""),
    ("GSE272769", "shock", "characteristic", "septic_shock_status", "", "", ""),
    ("GSE137340", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE137340", "age", "characteristic", "age", "UO:0000036 (inferred)", "", ""),
    ("GSE137340", "Sex", "characteristic", "sex", "", "", ""),
    ("GSE137340", "diagnosis", "characteristic", "disease", "", "", ""),
    ("GSE137340", "time of sample collection", "characteristic", "sampling_time_hours", "UO:0000032", "", ""),
    ("GSE137340", "outcome", "characteristic", "follow_up_status", "", "", "not pooled with 30-day mortality: the window would be lost; owner decision 2026-10-05"),
    ("GSE119217", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE119217", "sepsis_severity", "characteristic", "sepsis_severity", "", "", ""),
    ("GSE119217", "shock_status", "characteristic", "septic_shock_status", "", "", ""),
    ("GSE119217", "infection_source", "characteristic", "infection_type", "", "", ""),
    ("GSE119217", "Sex", "characteristic", "sex", "", "", ""),
    ("GSE119217", "race_ethnicity", "characteristic", "ethnic_group", "", "", ""),
    ("GSE131411", "patient", "characteristic", "subject_id", "", "", ""),
    ("GSE131411", "timepoint", "characteristic", "timepoint_coded", "", "", ""),
    ("GSE131411", "clinical classification", "characteristic", "disease", "", "", "SS/CS = septic vs cardiogenic shock"),
    ("GSE131411", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE131411", "Sex", "characteristic", "sex", "", "", "present for 10/106 samples"),
    ("GSE131411", "cell type", "characteristic", "organism_part", "", "duplicate_encoding", "identical to tissue on all 10 shared samples; owner accepted 2026-10-05"),
    # inflammatory bowel disease
    ("GSE166925", "disease", "characteristic", "disease", "", "", ""),
    ("GSE166925", "inflammation_status", "characteristic", "inflammation_status", "", "", ""),
    ("GSE166925", "site_taken", "characteristic", "organism_part", "", "", "large/small intestine"),
    ("GSE166925", "gender", "characteristic", "sex", "", "", ""),
    ("GSE166925", "patient_id", "characteristic", "subject_id", "", "", ""),
    ("GSE166925", "sample_id", "characteristic", "sample_id", "", "", ""),
    ("GSE166925", "nancy_score", "characteristic", "nancy_index", "", "", ""),
    ("GSE166925", "patient_age", "characteristic", "age", "UO:0000036 (inferred)", "", ""),
    ("GSE166925", "sample_age(y)", "characteristic", "sample_age", "UO:0000036", "", "meaning unclear; owner accepted 2026-10-05"),
    ("GSE166925", "disease_duration (y)", "characteristic", "disease_duration", "UO:0000036", "", ""),
    ("GSE166925", "qc", "characteristic", "qc_status", "", "", ""),
    ("GSE206171", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE206171", "Sex", "characteristic", "sex", "", "", ""),
    ("GSE206171", "uc or healthy control", "characteristic", "SPLIT", "", "", "two things: diagnosis and activity"),
    ("GSE206171", "uc or healthy control#diagnosis", "split:uc or healthy control", "disease", "", "", "UC / Healthy control"),
    ("GSE206171", "uc or healthy control#activity", "split:uc or healthy control", "uc_activity_status", "", "", "Active / Inactive"),
    ("GSE206171", "mayoscore", "characteristic", "mayo_score", "", "", ""),
    ("GSE206171", "diagnose duration (years)", "characteristic", "disease_duration", "UO:0000036", "", ""),
    ("GSE92415", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE92415", "subject", "characteristic", "subject_id", "", "", ""),
    ("GSE92415", "disease", "characteristic", "disease", "", "", ""),
    ("GSE92415", "age", "characteristic", "age", "UO:0000036 (inferred)", "", ""),
    ("GSE92415", "treatment", "characteristic", "treatment", "", "", ""),
    ("GSE92415", "visit", "characteristic", "time_since_treatment_start", "UO:0000034", "", "Week 0 / Week 6 / Healthy"),
    ("GSE92415", "wk6response", "characteristic", "treatment_response_wk6", "", "", ""),
    ("GSE92415", "mayo score", "characteristic", "mayo_score", "", "", "'.' marks missing"),
    ("GSE282580", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE282580", "title#subject", "title", "subject_id", "", "", "'subject 1, inf, 14W'"),
    ("GSE282580", "title#inflammation", "title", "inflammation_status", "", "", "inf / non-inf"),
    ("GSE282580", "title#week", "title", "time_since_treatment_start", "UO:0000034", "", "0W / 14W / 54W"),
    # type 2 diabetes
    ("GSE152111", "cell type", "characteristic", "cell_type", "", "", "islets are also an organism part (UBERON:0000006); owner accepted 2026-10-05"),
    ("GSE152111", "donor gender (m=male; f=female)", "characteristic", "sex", "", "", "legend inside the key"),
    ("GSE152111", "donor age (yrs)", "characteristic", "age", "UO:0000036", "", ""),
    ("GSE152111", "donor bmi (bmi kg/m2)", "characteristic", "bmi", "kg/m2 (ungrounded)", "", ""),
    ("GSE104674", "subject status", "characteristic", "disease", "", "", ""),
    ("GSE104674", "subject id #", "characteristic", "subject_id", "", "", ""),
    ("GSE104674", "gender", "characteristic", "sex", "", "", "constant: male"),
    ("GSE104674", "age", "characteristic", "age", "UO:0000036 (inferred)", "", ""),
    ("GSE104674", "bmi (kg/m2)", "characteristic", "bmi", "kg/m2 (ungrounded)", "", ""),
    ("GSE104674", "hba1c (mmol/mol)", "characteristic", "hba1c", "mmol/mol (ungrounded)", "", ""),
    ("GSE104674", "timepoint", "characteristic", "SPLIT", "", "", "two things: study day and zeitgeber time"),
    ("GSE104674", "timepoint#day", "split:timepoint", "study_day", "UO:0000033", "", "D2 / D3"),
    ("GSE104674", "timepoint#zeitgeber_time", "split:timepoint", "zeitgeber_time", "UO:0000032", "", "ZT 0:15 .. 15:30"),
    ("GSE231509", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE231509", "Sex", "characteristic", "sex", "", "", ""),
    ("GSE231509", "individual", "characteristic", "subject_id", "", "", ""),
    ("GSE231509", "treatment", "characteristic", "treatment", "", "", "No treatment / MMTT"),
    ("GSE231509", "time point", "characteristic", "time_relative_to_meal_test", "", "", "not pooled: 'before' samples are labelled 'No treatment', so the reference event would be lost; owner decision 2026-10-05"),
    ("GSE231509", "age", "characteristic", "age", "UO:0000036 (inferred)", "", ""),
    ("GSE231509", "diagnosis", "characteristic", "disease", "", "", ""),
    ("GSE231509", "bmi", "characteristic", "bmi", "kg/m2 (inferred, ungrounded)", "", ""),
    ("GSE231509", "fasting glucose,_mm", "characteristic", "fasting_glucose", "UO:0000063", "", "mM = mmol/L"),
    ("GSE231509", "fasting insulin,_miu/l", "characteristic", "fasting_insulin", "mIU/L (ungrounded)", "", ""),
    ("GSE231509", "fasting c-peptid,_ng/ml", "characteristic", "fasting_c_peptide", "UO:0000275", "", ""),
    ("GSE231509", "hba1c, %", "characteristic", "hba1c", "UO:0000187", "", ""),
    ("GSE231509", "homa ir", "characteristic", "homa_ir", "", "", ""),
    ("GSE189007", "tissue", "characteristic", "organism_part", "", "", ""),
    ("GSE189007", "disease group", "characteristic", "disease", "", "", "sub-cohort A; owner decision 2026-10-05"),
    ("GSE189007", "phenotype", "characteristic", "SPLIT", "", "", "free text, with a UACR measurement in 10 rows; owner decision 2026-10-05"),
    ("GSE189007", "phenotype#notes", "split:phenotype", "clinical_phenotype_notes", "", "", "medical-record descriptions"),
    ("GSE189007", "phenotype#uacr", "split:phenotype", "uacr", "mg/g (ungrounded)", "", "'UARC: 672.45 (mg/g)'"),
    ("GSE189007", "blood glucose", "characteristic", "SPLIT", "", "", "two things: fasting glucose and HbA1c"),
    ("GSE189007", "blood glucose#glucose", "split:blood glucose", "fasting_glucose", "mg/dL (ungrounded)", "", "'Glucose (AC): 158 mg/dL'"),
    ("GSE189007", "blood glucose#hba1c", "split:blood glucose", "hba1c", "UO:0000187", "", "'HbA1C: 10%'"),
    ("GSE189007", "bmi (kg/m2)", "characteristic", "bmi", "kg/m2 (ungrounded)", "", "sub-cohort A"),
    ("GSE189007", "duration (yr)", "characteristic", "disease_duration", "UO:0000036", "", "sub-cohort A"),
    ("GSE189007", "age (yr)", "characteristic", "age", "UO:0000036", "", "sub-cohort A"),
    ("GSE189007", "gender", "characteristic", "sex", "", "", "Male/male casing"),
    ("GSE189007", "population", "characteristic", "ethnic_group", "", "", "'Taiwanese' is a nationality as much as an ethnic group; owner accepted 2026-10-05"),
    ("GSE189007", "age", "characteristic", "age", "UO:0000036", "", "sub-cohort B; '43 years old'"),
    ("GSE189007", "t2d duration", "characteristic", "disease_duration", "UO:0000036", "", "sub-cohort B"),
    ("GSE189007", "hba1c (%) of the sample", "characteristic", "hba1c", "UO:0000187", "", "sub-cohort B; includes ranges"),
    ("GSE189007", "bmi", "characteristic", "bmi", "kg/m2 (ungrounded)", "", "sub-cohort B; unit inside the value"),
    ("GSE189007", "sampling in t2d stage", "characteristic", "disease", "", "", "sub-cohort B, first half; owner decision 2026-10-05"),
    ("GSE189007", "reference", "characteristic", "recruitment_site", "", "", ""),
    ("GSE189007", "sampling t2d stage", "characteristic", "disease", "", "", "sub-cohort B, second half; typo duplicate; owner decision 2026-10-05"),
]


def main() -> int:
    errors: list[str] = []
    snap = json.loads(SNAPSHOT.read_text())
    ix = pd.read_parquet(INDEX).set_index("curie")

    def check_curie(c: str, where: str) -> str:
        if c not in ix.index:
            errors.append(f"{where}: {c} not in pinned file"); return ""
        row = ix.loc[c]
        if bool(row.deprecated): errors.append(f"{where}: {c} is deprecated")
        if c.split(":")[0] not in ALLOWED: errors.append(f"{where}: {c} prefix not allowlisted")
        return str(row.label)

    var = {}
    for vid, name, pred, prim, quals, vtype, why in V:
        if vid in var: errors.append(f"duplicate variable {vid}")
        if pred not in PREDICATES: errors.append(f"{vid}: bad predicate {pred}")
        if (pred == "none") != (prim == ""): errors.append(f"{vid}: predicate/term mismatch")
        label = check_curie(prim, vid) if prim else ""
        qs = []
        for slot, val in quals:
            if slot not in SLOTS: errors.append(f"{vid}: bad slot {slot}")
            if CURIE.match(val):
                qs.append(f"{slot}={val} [{check_curie(val, vid)}]")
            else:
                qs.append(f'{slot}="{val}" (ungrounded)')
        var[vid] = dict(variable_id=vid, name=name, predicate=pred, primary_curie=prim,
                        primary_label=label, qualifiers="; ".join(qs), value_type=vtype, rationale=why)

    seen = Counter((a, k) for a, k, src, *_ in C if src == "characteristic")
    for (a, k), n in seen.items():
        if n > 1: errors.append(f"{a}/{k} listed {n} times")
    for acc, x in snap.items():
        for k in x["characteristics"]:
            if (acc, k) not in seen: errors.append(f"{acc}/{k} has no gold row")
    rows = []
    for a, k, src, vid, unit, flags, note in C:
        fl = [f for f in flags.split(",") if f]
        if "inferred" in unit and "assumed_convention" not in fl:
            fl.append("assumed_convention")
        for f in fl:
            if f not in FLAGS: errors.append(f"{a}/{k}: unknown flag {f}")
        rows.append((a, k, src, vid, unit, ",".join(fl), note))
    for a, k, src, vid, *_ in C:
        if src == "characteristic" and k not in snap[a]["characteristics"]:
            errors.append(f"{a}/{k} not in snapshot")
        if vid != "SPLIT" and vid not in var: errors.append(f"{a}/{k}: unknown variable {vid}")
        if src.startswith("split:") and (a, src[6:]) not in seen: errors.append(f"{a}/{k}: split parent missing")

    # co-occurrence: two characteristic members of one variable from the same
    # dataset must cover disjoint samples unless flagged duplicate_encoding.
    members = defaultdict(list)
    for a, k, src, vid, unit, flags, note in C:
        if vid != "SPLIT": members[vid].append((a, k, src, flags))
    for vid, ms in members.items():
        for (a1, k1, s1, f1), (a2, k2, s2, f2) in itertools.combinations(ms, 2):
            if a1 != a2: continue
            if s1.startswith("split:") and s1 == s2:
                errors.append(f"{vid}: two parts of one split column in one variable"); continue
            if s1 == s2 == "characteristic":
                disjoint = (f"{k1} || {k2}" in snap[a1]["disjoint_pairs"]
                            or f"{k2} || {k1}" in snap[a1]["disjoint_pairs"])
                if not disjoint and "duplicate_encoding" not in f1 + f2:
                    errors.append(f"{vid}: {a1} '{k1}' and '{k2}' co-occur")
    for vid in var:
        if vid not in members: errors.append(f"variable {vid} has no members")

    if errors:
        print("\n".join(errors)); return 1

    for vid, v in var.items():
        ms = members[vid]
        v["n_members"] = len(ms)
        v["n_datasets"] = len({a for a, *_ in ms})
    cols = ["variable_id", "name", "predicate", "primary_curie", "primary_label", "qualifiers",
            "value_type", "n_members", "n_datasets", "rationale"]
    with open(HERE / "generalization_variables.tsv", "w", newline="") as f:
        w = csv.DictWriter(f, cols, delimiter="\t", lineterminator="\n"); w.writeheader()
        w.writerows(var.values())
    with open(HERE / "generalization_columns.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["accession", "raw_key", "source", "variable_id", "unit", "flags", "note"])
        w.writerows(rows)

    pooled = [v for v in var.values() if v["n_datasets"] > 1]
    print(f"OK: {len(C)} column rows, {len(var)} variables, {len(pooled)} span >1 dataset")
    print(f"predicates: {dict(Counter(v['predicate'] for v in var.values()))}")
    print(f"flags: {dict(Counter(f for r in rows for f in r[5].split(',') if f))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
