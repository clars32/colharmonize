"""Contract tests for the GEOmend boundary. If GEOmend changes, these say where."""
import hashlib
from pathlib import Path

import pytest

from colharmonize import geomend_bridge as gb

SOFT = Path(__file__).parent / "fixtures" / "soft"
# Sample counts verified independently in iteration 2's harvest.
EXPECTED_SAMPLES = {"GSE128621": 14, "GSE79842": 36, "GSE124252": 15}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_ontology_store_opens_through_geomend(tiny, tmp_path):
    out = tmp_path / "tiny.sqlite"
    report = gb.build_ontology_store(tiny, out, name="tiny")
    assert report["nodes"] == 7          # 8 terms, one deprecated; CURIE-less terms included
    assert report["edges"] == 1
    assert gb.store_node_count(out, name="tiny", version="1.0") == 7
    with pytest.raises(ValueError):      # GEOmend refuses the wrong release
        gb.store_node_count(out, name="tiny", version="2.0")


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    before = {p.name: _digest(p) for p in SOFT.glob("*.soft.gz")}
    proj = tmp_path_factory.mktemp("cohort") / "project"
    gb.create_cohort(proj, sorted(SOFT.glob("*.soft.gz")), offline=True, workers=2)
    after = {p.name: _digest(p) for p in SOFT.glob("*.soft.gz")}
    assert before == after, "ingest must not modify input files"
    return proj


def test_ingest_keeps_every_sample(project):
    values = gb.sample_values(project)
    counts = values.groupby("study_id").sample_id.nunique().to_dict()
    assert counts == EXPECTED_SAMPLES


def test_characteristics_keep_raw_spelling_and_values(project):
    values = gb.sample_values(project)
    names = set(values[values.study_id == "GSE128621"].name)
    assert {"Sex", "age", "cell type", "karyotype", "library type"} <= names
    ages = set(values[(values.study_id == "GSE79842") & (values.name == "age")].value)
    assert "1 Year old" in ages and "2 Day old" in ages


def test_values_containing_na_are_not_nulled(project):
    # TidyGEO replaced any value containing "NA" with NA (str_replace_all),
    # wiping "RNA-Seq" and "cDNA". GEOmend must keep them verbatim.
    attrs = gb.sample_values(project, namespaces=("attribute",))
    seen = set(attrs[attrs.study_id == "GSE128621"].value.dropna())
    assert {"polyA RNA", "RNA-Seq", "cDNA"} <= seen


def test_coverage_supports_the_cooccurrence_rule(project):
    cover = gb.column_coverage(gb.sample_values(project))
    gse = cover["GSE128621"]
    assert gse["Sex"] == gse["karyotype"] and len(gse["Sex"]) == 14


def test_field_table_shape(project):
    t = gb.field_table(project)
    chars = t[(t.scope == "sample") & (t.namespace == "characteristic")]
    assert set(chars.study_id) == set(EXPECTED_SAMPLES)
    assert {"study_id", "field_id", "name", "unit", "n_entities"} <= set(t.columns)
