"""The one place colharmonize touches MetaMend.

MetaMend prepares the data: it parses GEO SOFT files, ArrayExpress MAGE-TAB and local tables, profiles
every field, and exports cohort tables. colharmonize reads what MetaMend
produced and, later, writes decisions back through MetaMend's public commands.
Every MetaMend import lives in this module, so a MetaMend upgrade changes one file
and the contract tests in tests/test_metamend_bridge.py say what broke.

Projects are read only through MetaMend's public `ProjectClient`, never its
private engine: fields are listed with `mappings.fields` and their per-sample
values paged with `mappings.field`. Decisions go back only as provider
proposals (`transformations.propose_provider`), which MetaMend validates
against actual values and keeps pending its own review.

Pinned against metamend==0.1.0 (formerly geomend).
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
from metamend.cohort_models import CohortConfig, CohortVariable
from metamend.cohort_transform import specification
from metamend.geo_mapping import resolve_local_ontology
from metamend.models import GraphEdge, GraphNode, OntologyRelease
from metamend.ontology import OntologyStore
from metamend.project import ProjectClient
from metamend.text import canonical_identifier, sha256_text, stable_json

from colharmonize.ontology import Ontology

PAGE = 200   # MetaMend's largest page
STORE_PARSER_VERSION = "colharmonize-pinned-index-projection-2"   # 2: nodes carry source IRIs


def build_ontology_store(
    ontology: Ontology,
    out: str | Path,
    *,
    name: str = "efo",
    retrieved_at: datetime | None = None,
) -> dict[str, object]:
    """Write the pinned ontology as a MetaMend OntologyStore (SQLite).

    MetaMend reads OBO/OWL but not OBO-graph JSON, and defaults to EFO 3.70.0.
    Projecting the pinned index keeps both tools on exactly one release.

    Stored: non-deprecated classes under MetaMend's lowercase CURIEs
    (`efo:0000324`), exact and related synonyms (the store keeps no synonym
    scope), and edges whose two ends are both stored. Each node also carries
    its full IRI from the pinned index (MetaMend 0.0.9), so MetaMend's concept
    interchange names real EFO IRIs instead of placeholders. The pinned index
    stays the authority for colharmonize's own output.
    """
    out = Path(out)
    terms = ontology.terms
    terms = terms[(terms.node_type == "CLASS") & ~terms.deprecated]
    nodes: dict[str, GraphNode] = {}
    iri_to_id: dict[str, str] = {}
    skipped: list[str] = []
    collisions = 0
    for row in terms.itertuples(index=False):
        try:
            node_id = canonical_identifier(row.iri)
        except ValueError:
            skipped.append(row.iri)
            continue
        iri_to_id[row.iri] = node_id
        if node_id in nodes:
            collisions += 1
            continue
        synonyms = sorted(
            {str(s) for col in ("exact_synonyms", "related_synonyms")
             for s in (getattr(row, col) if getattr(row, col) is not None else []) if s}
            - {row.label}
        )
        nodes[node_id] = GraphNode(
            id=node_id, label=row.label or node_id, iri=row.iri, definition=row.definition or None,
            synonyms=synonyms, obsolete=False, replaced_by=[],
        )

    def predicate(iri: str) -> str:
        if iri == "is_a":
            return "is_a"
        if iri == "http://purl.obolibrary.org/obo/BFO_0000050":
            return "part_of"
        try:
            return canonical_identifier(iri)
        except ValueError:
            return iri

    edges: dict[tuple[str, str, str], GraphEdge] = {}
    dropped = 0
    for row in ontology.edge_table.itertuples(index=False):
        s, o = iri_to_id.get(row.sub), iri_to_id.get(row.obj)
        if s is None or o is None:
            dropped += 1
            continue
        p = predicate(row.pred)
        edges[(s, p, o)] = GraphEdge(subject=s, predicate=p, object=o, source_ontology=name)

    version = ontology.release_tag.lstrip("v") or "unknown"
    release = OntologyRelease(
        name=name,
        version=version,
        source=ontology.version_iri or name,
        retrieved_at=retrieved_at or datetime.now(timezone.utc),
        sha256=ontology.version.get("sha256", "") or sha256_text(stable_json(ontology.version)),
        parser_version=STORE_PARSER_VERSION,
    )
    config = {"node_filter": "CLASS and not deprecated", "synonyms": ["exact", "related"],
              "predicates": {"is_a": "is_a", "BFO_0000050": "part_of", "*": "canonical_identifier"},
              "pinned_version": ontology.version}
    if out.exists():
        out.unlink()
    store = OntologyStore(out)
    store.replace_all(release=release, nodes=nodes.values(), edges=edges.values(), targets=[],
                      config_hash=sha256_text(stable_json(config)))
    return {"store": str(out), "name": name, "version": version, "nodes": len(nodes),
            "edges": len(edges), "edges_dropped": dropped, "skipped_iris": len(skipped),
            "curie_collisions": collisions}


def store_node_count(store: str | Path, *, name: str = "efo", version: str) -> int:
    """Open a store through MetaMend's own resolver; it refuses a wrong version."""
    return len(resolve_local_ontology(Path(store), ontology_id=name, ontology_version=version).nodes)


def create_cohort(
    project: str | Path,
    sources: Iterable[str | Path],
    *,
    offline: bool = True,
    workers: int = 4,
    ontology_stores: Iterable[str | Path] = (),
) -> None:
    """Create and run a MetaMend project from SOFT files, tables or accessions.

    Local files are copied into the project, never modified in place.
    MetaMend's own concept enrichment (lexical retrieval, optional hosted OLS4)
    is switched off: matching is colharmonize's job, and hosted search would
    escape the pinned release.
    """
    config = CohortConfig(offline=offline, workers=workers, concept_enrichment=False,
                          ontology_stores=[str(Path(s)) for s in ontology_stores])
    ProjectClient.create([str(s) for s in sources], project, config=config, run=True)


def failed_sources(project: str | Path) -> list[dict]:
    """Sources MetaMend could not read, each with its study_id, source and error.

    MetaMend finishes a cohort run even when sources fail (the job is 'partial'),
    so a caller that doesn't ask sees an empty or short cohort, not an error.
    """
    jobs = ProjectClient.open(project).inputs.jobs()
    return [{"study_id": f["study_id"], "source": f["source"], "error": f["error"]}
            for f in jobs["failed_studies"]]


def _pages(fetch, key: str):
    offset = 0
    while offset is not None:
        page = fetch(offset)
        yield from page[key]
        offset = page["next_offset"]


def _fields(project: str | Path, want=lambda field: True, *, with_values: bool = True) -> list[dict]:
    """Field identities (study_id, field_id, scope, namespace, channel, name, unit,
    reported_count) for every field `want` keeps, with `values` {entity: [raw values]}."""
    client = ProjectClient.open(project)
    out = []
    for f in _pages(lambda o: client.mappings.fields(offset=o, limit=PAGE), "fields"):
        if not want(f):
            continue
        values = {}
        if with_values:
            for v in _pages(lambda o: client.mappings.field(f["field_id"], offset=o, limit=PAGE), "values"):
                if v["total_values"] > len(v["values"]):
                    raise ValueError(f"{f['field_id']}: MetaMend returned {len(v['values'])} of "
                                     f"{v['total_values']} values for {v['entity_id']}")
                values[v["entity_id"]] = v["values"]
        out.append({**f, "values": values})
    return out


def field_table(project: str | Path) -> pd.DataFrame:
    """One row per MetaMend field: study, field id, scope, namespace, name, unit, reported values."""
    rows = [{"study_id": f["study_id"], "field_id": f["field_id"], "scope": f["scope"],
             "namespace": f["namespace"], "channel": f.get("channel"), "name": f["name"], "unit": f.get("unit"),
             "n_reported": f.get("reported_count")}
            for f in _fields(project, with_values=False)]
    return pd.DataFrame(rows, columns=["study_id", "field_id", "scope", "namespace", "channel", "name", "unit",
                                       "n_reported"])


def sample_values(project: str | Path, namespaces: Iterable[str] = ("characteristic",)) -> pd.DataFrame:
    """Long table of sample-scope values: study, sample, field, name, ordinal, raw value.

    Values are returned verbatim as MetaMend stored them. A field with several
    values for one sample yields one row per value (ordinal 0, 1, ...).
    """
    keep = set(namespaces)
    rows = []
    for f in _fields(project, lambda f: f["scope"] == "sample" and f["namespace"] in keep):
        for entity, values in f["values"].items():
            for i, v in enumerate(values):
                rows.append({"study_id": f["study_id"], "sample_id": entity, "field_id": f["field_id"],
                             "namespace": f["namespace"], "name": f["name"], "ordinal": i,
                             "value": None if v is None else str(v)})
    return pd.DataFrame(rows, columns=["study_id", "sample_id", "field_id", "namespace", "name", "ordinal", "value"])


def namespace_counts(project: str | Path) -> Counter:
    """(scope, namespace) counts, a cheap smoke check after ingest."""
    return Counter((r.scope, r.namespace) for r in field_table(project).itertuples(index=False))


def study_attributes(project: str | Path, names: Iterable[str] = ("title", "summary", "overall_design")) -> pd.DataFrame:
    """One row per study with the requested study-scope attributes (first value of each)."""
    keep = list(names)
    rows: dict[str, dict] = {}
    for f in _fields(project, lambda f: f["scope"] == "study" and f["name"] in keep):
        row = rows.setdefault(f["study_id"], {"study_id": f["study_id"]})
        if f["name"] in row:
            continue
        first = next((v for vals in f["values"].values() for v in vals if v is not None), None)
        row[f["name"]] = None if first is None else str(first)
    studies = sorted({f["study_id"] for f in _fields(project, with_values=False)})
    return pd.DataFrame([rows.get(s, {"study_id": s}) for s in studies], columns=["study_id", *keep])


# ---------------------------------------------------------------------------
# Preprocessing evidence (decisions log 1.6): what MetaMend can tell colharmonize
# about a project. All offline, no model, ontology restricted to the pinned store.

def store_ids(ontology: Ontology) -> dict[str, str]:
    """MetaMend store node id (`efo:0004426`) -> pinned CURIE (`EFO:0004426`)."""
    out = {}
    for iri, curie in zip(ontology.terms.iri, ontology.terms.curie):
        if not curie:
            continue
        try:
            out[canonical_identifier(iri)] = curie
        except ValueError:
            continue
    return out


def enable_concepts(project: str | Path, store: str | Path, *, workers: int = 4) -> dict:
    """Turn on MetaMend's lexical concept retrieval against the pinned store only, and run it.

    Offline and with no model: MetaMend then searches only the local store
    (hosted OLS4 needs `offline=False`). `configure` replaces the whole config,
    so the settings colharmonize relies on are restated.
    """
    client = ProjectClient.open(project)
    client.administration.configure(CohortConfig(offline=True, workers=workers, concept_enrichment=True,
                                                 ontology_stores=[str(Path(store).resolve())]))
    return client.concepts.enrich(use_model=False)


def concept_candidates(project: str | Path) -> pd.DataFrame:
    """Per sample characteristic field, MetaMend's lexical candidates with their evidence.

    MetaMend's own `rank` mixes channels and ties, so the strongest evidence score
    is kept for ranking (5 exact label/synonym, 2.4 substring, 1 definition only).
    """
    client = ProjectClient.open(project)
    rows = []
    for f in _fields(project, lambda f: f["scope"] == "sample" and f["namespace"] == "characteristic",
                     with_values=False):
        for c in _pages(lambda o: client.concepts.candidates(f["field_id"], offset=o, limit=PAGE), "candidates"):
            ev = c.get("evidence") or []
            best = max(ev, key=lambda e: e.get("score") or 0, default={})
            rows.append({"study_id": f["study_id"], "name": f["name"], "concept_id": c["concept_id"],
                         "label": c.get("label"), "best_score": float(best.get("score") or 0),
                         "surface": best.get("retrieval_surface"), "query_source": best.get("query_source"),
                         "n_evidence": len(ev)})
    return pd.DataFrame(rows, columns=["study_id", "name", "concept_id", "label", "best_score", "surface",
                                       "query_source", "n_evidence"])


def merge_suggestions(project: str | Path, *, max_pairs: int = 10000) -> pd.DataFrame:
    """MetaMend's suggested joins between its variables, as pairs of sample characteristic fields."""
    client = ProjectClient.open(project)
    chars = _fields(project, lambda f: f["scope"] == "sample" and f["namespace"] == "characteristic",
                    with_values=False)
    variable_ids = sorted({f["mapping"]["variable_id"] for f in chars if f.get("mapping")})
    if len(variable_ids) < 2:
        return pd.DataFrame(columns=["left_study", "left_name", "right_study", "right_name", "header_overlap",
                                     "agreement_fraction", "blockers", "rank"])
    result = client.mappings.suggestions(variable_ids=variable_ids, max_pairs=max_pairs)
    keep = {f["field_id"]: f for f in chars}
    rows = []
    for p in result.get("pairs", []):
        for lf in p.get("left_field_ids", []):
            for rf in p.get("right_field_ids", []):
                if lf in keep and rf in keep:
                    rows.append({"left_study": keep[lf]["study_id"], "left_name": keep[lf]["name"],
                                 "right_study": keep[rf]["study_id"], "right_name": keep[rf]["name"],
                                 "header_overlap": p.get("header_token_overlap"),
                                 "agreement_fraction": p.get("agreement_fraction"),
                                 "blockers": json.dumps(p.get("compatibility_blockers") or []), "rank": p.get("rank")})
    return pd.DataFrame(rows, columns=["left_study", "left_name", "right_study", "right_name", "header_overlap",
                                       "agreement_fraction", "blockers", "rank"])


def _units_in(spec: object, found: set[str]) -> None:
    """Every unit named in a mapping specification: conversions and per-value normalizations."""
    if isinstance(spec, dict):
        for k, v in spec.items():
            if k in ("source_unit", "target_unit", "unit") and isinstance(v, str) and v:
                found.add(v)
            else:
                _units_in(v, found)
    elif isinstance(spec, list):
        for v in spec:
            _units_in(v, found)
    elif isinstance(spec, str) and spec.startswith("{") and '"unit' in spec:
        try:
            _units_in(json.loads(spec), found)
        except ValueError:
            pass


def field_units(project: str | Path) -> pd.DataFrame:
    """Per sample characteristic field, the units MetaMend found: on the field, its variable,
    and in its mapping (unit conversion, per-value unit normalization)."""
    client = ProjectClient.open(project)
    rows = []
    for f in _fields(project, lambda f: f["scope"] == "sample" and f["namespace"] == "characteristic",
                     with_values=False):
        d = client.mappings.field(f["field_id"], limit=1)
        found: set[str] = set()
        if f.get("unit"):
            found.add(f["unit"])
        if (d.get("variable") or {}).get("unit"):
            found.add(d["variable"]["unit"])
        _units_in((d.get("mapping") or {}).get("specification"), found)
        rows.append({"study_id": f["study_id"], "name": f["name"], "units": json.dumps(sorted(found))})
    return pd.DataFrame(rows, columns=["study_id", "name", "units"])


def characteristic_fields(project: str | Path) -> dict[tuple[str, str], tuple[str, list[str]]]:
    """(study_id, characteristic name) -> (MetaMend field id, distinct raw values) for sample fields."""
    out = {}
    for f in _fields(project, lambda f: f["scope"] == "sample" and f["namespace"] == "characteristic"):
        distinct = sorted({str(v) for vs in f["values"].values() for v in vs if v is not None})
        out[(f["study_id"], f["name"])] = (f["field_id"], distinct)
    return out


def propose_mappings(project: str | Path, proposals: list[dict], *, provider_version: str,
                     select: bool = False) -> list[dict]:
    """Send colharmonize variables to MetaMend as provider proposals, one per field.

    Each proposal dict has field_id, variable_id, label, definition,
    ontology_references, mappings (a complete value recode, or None to copy
    values unchanged), locator and rationale. Every proposal is previewed
    against the field's actual values first. One MetaMend would refuse is not
    sent, so the project never collects invalid proposals; its result has
    valid False and the preview's reason. The target is an unconstrained string
    variable: colharmonize decides pooling and meaning, not value domains.
    Nothing is selected unless `select`, and MetaMend never treats a provider
    proposal as a reviewer vote.
    """
    client = ProjectClient.open(project)
    results = []
    for p in proposals:
        variable = CohortVariable(variable_id=p["variable_id"], label=p["label"], definition=p["definition"],
                                  scope="sample", datatype="string",
                                  ontology_references=list(p.get("ontology_references") or []), origin="llm")
        spec = specification(mappings=p["mappings"]) if p.get("mappings") else specification()
        try:
            client.mappings.preview(variable=variable, field_ids=[p["field_id"]], spec=spec)
        except ValueError as error:
            results.append({"field_id": p["field_id"], "proposal_id": "", "valid": False, "selected": False,
                            "failures": [str(error)[:500]]})
            continue
        r = client.transformations.propose_provider(
            p["field_id"], variable, spec, expected_revision=client.summary().revision,
            provider="colharmonize", provider_version=provider_version, locator=p["locator"],
            rationale=p["rationale"], select=select)
        results.append({"field_id": p["field_id"], "proposal_id": r["proposal_id"], "valid": r["valid"],
                        "selected": r["selected"], "failures": [json.dumps(f) for f in r["failures"]][:5]})
    return results
