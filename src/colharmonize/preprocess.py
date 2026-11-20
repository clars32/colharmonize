"""Preprocess: collect what MetaMend can tell colharmonize about a project, as evidence.

The owners decided colharmonize takes any help MetaMend offers, as
preprocessing (decisions log 1.6). Nothing here decides anything. It records
three kinds of MetaMend evidence in `<workspace>/geomend_evidence/` for later
stages to weigh:

  concepts.parquet   lexical ontology candidates per characteristic, from the
                     pinned store only (a candidate source for annotation)
  merges.parquet     MetaMend's suggested joins between characteristics (extra
                     links for reconciliation's candidate groups)
  units.parquet      units MetaMend found per characteristic (unit hints)

Everything runs offline with no model.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from colharmonize import metamend_bridge as gb
from colharmonize.ontology import Ontology
from colharmonize.workspace import Workspace


def evidence_dir(ws: Workspace) -> Path:
    return ws.root / "geomend_evidence"


def run(ws: Workspace, store: str | Path, ontology: Ontology) -> dict:
    out = evidence_dir(ws)
    out.mkdir(exist_ok=True)
    enrich = gb.enable_concepts(ws.metamend, store)
    ids = gb.store_ids(ontology)
    concepts = gb.concept_candidates(ws.metamend)
    concepts["curie"] = concepts.concept_id.map(ids).fillna("")
    concepts.to_parquet(out / "concepts.parquet", index=False)
    merges = gb.merge_suggestions(ws.metamend)
    merges.to_parquet(out / "merges.parquet", index=False)
    units = gb.field_units(ws.metamend)
    units.to_parquet(out / "units.parquet", index=False)
    return {"concept_candidates": len(concepts), "unmapped_concepts": int((concepts.curie == "").sum()),
            "merge_pairs": len(merges), "fields_with_units": int((units.units != "[]").sum()),
            "enrich": {k: v for k, v in (enrich or {}).items() if isinstance(v, (int, float, str))}}


def load(ws: Workspace, name: str) -> pd.DataFrame | None:
    path = evidence_dir(ws) / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else None


# Which evidence feeds the pipeline, decided by measurement on the tuning set
# (decisions log 12). All three are always collected.
USE_CONCEPTS = False   # added no gold term; substring matches crowded the display
USE_UNITS = False      # only units colharmonize already finds
USE_MERGES = True      # reconcile precision and run agreement up, recall unchanged

# MetaMend evidence scores: 5 exact label or synonym of the field name, 4 exact
# match of a value, 2.4 substring, 1 or less definition-only.
MIN_CONCEPT_SCORE = 4.0


def hints(ws: Workspace, min_score: float = MIN_CONCEPT_SCORE, *, concepts_on: bool = USE_CONCEPTS,
          units_on: bool = USE_UNITS) -> dict[tuple[str, str], dict]:
    """(study_id, column) -> {"terms": CURIEs strongest first, "units": unit names} from saved evidence."""
    out: dict[tuple[str, str], dict] = {}
    concepts = load(ws, "concepts") if concepts_on else None
    units = load(ws, "units") if units_on else None
    if concepts is not None:
        keep = concepts[(concepts.best_score >= min_score) & (concepts.curie != "")]
        for (study, name), g in keep.sort_values(["best_score", "curie"], ascending=[False, True]).groupby(
                ["study_id", "name"], sort=False):
            out.setdefault((study, name), {})["terms"] = list(dict.fromkeys(g.curie))
    if units is not None:
        import json
        for study, name, u in zip(units.study_id, units.name, units.units):
            if json.loads(u):
                out.setdefault((study, name), {})["units"] = json.loads(u)
    return out
