"""The one place colharmonize touches GEOmend.

GEOmend prepares the data: it parses GEO SOFT files and local tables, profiles
every field, and exports cohort tables. colharmonize reads what GEOmend
produced and, later, writes decisions back through GEOmend's public commands.
Every GEOmend import lives in this module, so a GEOmend upgrade changes one file
and the contract tests in tests/test_geomend_bridge.py say what broke.

Pinned against geomend==0.0.2.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
from geomend.cohort import CohortClient
from geomend.cohort_models import CohortConfig
from geomend.geo_mapping import resolve_local_ontology
from geomend.models import GraphEdge, GraphNode, OntologyRelease
from geomend.ontology import OntologyStore
from geomend.text import canonical_identifier, sha256_text, stable_json

from colharmonize.ontology import Ontology

GEOMEND_VERSION = "0.0.2"
STORE_PARSER_VERSION = "colharmonize-pinned-index-projection-1"


def build_ontology_store(
    ontology: Ontology,
    out: str | Path,
    *,
    name: str = "efo",
    retrieved_at: datetime | None = None,
) -> dict[str, object]:
    """Write the pinned ontology as a GEOmend OntologyStore (SQLite).

    GEOmend reads OBO/OWL but not OBO-graph JSON, and defaults to EFO 3.70.0.
    Projecting the pinned index keeps both tools on exactly one release.

    Stored: non-deprecated classes under GEOmend's lowercase CURIEs
    (`efo:0000324`), exact and related synonyms (the store keeps no synonym
    scope), and edges whose two ends are both stored. GEOmend's store keeps
    CURIEs only; full IRIs stay in the pinned index, the authority for output.
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
            id=node_id, label=row.label or node_id, definition=row.definition or None,
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
    """Open a store through GEOmend's own resolver; it refuses a wrong version."""
    return len(resolve_local_ontology(Path(store), ontology_id=name, ontology_version=version).nodes)


def create_cohort(
    project: str | Path,
    sources: Iterable[str | Path],
    *,
    offline: bool = True,
    workers: int = 4,
    ontology_stores: Iterable[str | Path] = (),
) -> None:
    """Create and run a GEOmend cohort project from SOFT files, tables or accessions.

    Local files are copied into the project, never modified in place.
    GEOmend's own concept enrichment (lexical retrieval, optional hosted OLS4)
    is switched off: matching is colharmonize's job, and hosted search would
    escape the pinned release.
    """
    config = CohortConfig(offline=offline, workers=workers, concept_enrichment=False,
                          ontology_stores=[str(Path(s)) for s in ontology_stores])
    CohortClient.create([str(s) for s in sources], project, config=config, run=True)


def _inventories(project: str | Path):
    return CohortClient(Path(project)).inventories()


def field_table(project: str | Path) -> pd.DataFrame:
    """One row per GEOmend field: study, field id, scope, namespace, name, unit, coverage."""
    rows = []
    for inv in _inventories(project):
        for f in inv.fields:
            rows.append({
                "study_id": inv.study_id, "field_id": f.field_id, "scope": f.scope,
                "namespace": f.namespace, "channel": f.channel, "name": f.name, "unit": f.unit,
                "n_entities": len(f.values), "n_values": sum(len(v) for v in f.values.values()),
            })
    return pd.DataFrame(rows)


def sample_values(project: str | Path, namespaces: Iterable[str] = ("characteristic",)) -> pd.DataFrame:
    """Long table of sample-scope values: study, sample, field, name, ordinal, raw value.

    Values are returned verbatim as GEOmend stored them. A field with several
    values for one sample yields one row per value (ordinal 0, 1, ...).
    """
    keep = set(namespaces)
    rows = []
    for inv in _inventories(project):
        for f in inv.fields:
            if f.scope != "sample" or f.namespace not in keep:
                continue
            for entity, values in f.values.items():
                for i, v in enumerate(values):
                    rows.append({"study_id": inv.study_id, "sample_id": entity, "field_id": f.field_id,
                                 "namespace": f.namespace, "name": f.name, "ordinal": i,
                                 "value": None if v is None else str(v)})
    return pd.DataFrame(rows, columns=["study_id", "sample_id", "field_id", "namespace", "name", "ordinal", "value"])


def column_coverage(values: pd.DataFrame) -> dict[str, dict[str, set[str]]]:
    """study -> field name -> set of samples with a value. Feeds the co-occurrence rule."""
    cover: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in values.itertuples(index=False):
        cover[row.study_id][row.name].add(row.sample_id)
    return {s: dict(f) for s, f in cover.items()}


def namespace_counts(project: str | Path) -> Counter:
    """(scope, namespace) counts, a cheap smoke check after ingest."""
    return Counter((r.scope, r.namespace) for r in field_table(project).itertuples(index=False))


def study_attributes(project: str | Path, names: Iterable[str] = ("title", "summary", "overall_design")) -> pd.DataFrame:
    """One row per study with the requested study-scope attributes (first value of each)."""
    keep = list(names)
    rows = []
    for inv in _inventories(project):
        row = {"study_id": inv.study_id}
        for f in inv.fields:
            if f.scope == "study" and f.name in keep and f.name not in row:
                first = next((v for vals in f.values.values() for v in vals if v is not None), None)
                row[f.name] = None if first is None else str(first)
        rows.append(row)
    return pd.DataFrame(rows, columns=["study_id", *keep])
