"""Candidate terms for every column, from several independent sources.

Retrieval decides whether the right term is even available to choose, and a
failure here is invisible downstream, so recall is measured on its own
(`evaluate_recall`). Three pools serve the three roles a term can play:

  space   primary terms for exact/broad annotations, from the property space
  entity  indicator targets and qualifiers (diseases, anatomy, cells, genes,
          events), from the full allowlisted pool
  unit    unit qualifiers, from UO

Sources (ported from iteration 2's s03, which measured them):
  exact_space / exact_entity   label or exact-synonym match of a name form
  <model>_name / <model>_values  embeddings of the name, and of name plus values;
                               two models, because they fail on different columns
  <model>_entity               embeddings of name forms over the full pool
  unit                         lexical match of unit strings against UO
  value_term / value_category  the column's values matched to terms, and the
                               property-space ancestors those terms share. Values
                               are instances of the column's category ("Down
                               syndrome" is_a ... disease), so this finds `disease`
                               for a column named `strain` (iteration 2, 6a.4).
  zooma / ols4                 remote services, validated against the pinned
                               release; optional, cached on disk

Every candidate keeps every source that found it with that source's rank, so
agreement across sources is available later as evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from colharmonize.ontology import Ontology
from colharmonize.text import loose, parenthetical, strip_parenthetical

MODELS = [
    ("mini", "sentence-transformers/all-MiniLM-L6-v2", ""),
    ("bge", "BAAI/bge-small-en-v1.5", "Represent this sentence for searching relevant passages: "),
]
TOPK_SPACE = 50
TOPK_ENTITY = 15
DISPLAY_SPACE = 40
DISPLAY_ENTITY = 16
VALUES_IN_QUERY = 8
VALUES_FOR_CATEGORY = 12        # most common distinct values matched to terms
VALUE_MATCH_MIN_SIM = 0.80      # cosine (MiniLM) for a value to count as naming a term
ANCESTOR_DEPTH = 10
# Words that make a column name narrower than the entity it is about:
# "down syndrome status" is about Down syndrome; "shock_status" about shock.
_STATUS_WORDS = re.compile(r"\b(status|state|type|group|level|levels|score|positive|negative|result|results)\b")
ZOOMA_ANNOTATE = "https://www.ebi.ac.uk/spot/zooma/v2/api/services/annotate"
OLS4_SEARCH = "https://www.ebi.ac.uk/ols4/api/search"


def default_cache_dir() -> Path:
    """The per-user cache for embeddings and remote lookups: $COLHARMONIZE_CACHE, else ~/.cache/colharmonize.

    Cached embeddings are keyed by their content, so one cache serves every
    workspace. Remote lookups are not: a run without --remote still uses the
    ZOOMA and OLS4 answers its cache holds, so the cache is part of a run's input.
    """
    return Path(os.environ.get("COLHARMONIZE_CACHE") or "~/.cache/colharmonize").expanduser()


def name_forms(column: str) -> dict[str, str]:
    """Query strings derived from a column name.

    Derived columns from repair are `<source>#<name>`; the part after '#' is the
    variable name, the part before is where it came from.
    """
    base = column.split("#", 1)[1] if "#" in column else column
    plain = loose(strip_parenthetical(base)) or loose(base)
    forms = {"raw": loose(base), "plain": plain}
    stripped = _STATUS_WORDS.sub(" ", plain)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if stripped and stripped != plain:
        forms["entity"] = stripped
    return forms


def unit_strings(column: str, unit: str | None) -> list[str]:
    """Candidate unit spellings: GEOmend's detected unit, parentheticals, and text after a comma."""
    out = [u for u in parenthetical(column)]
    if "," in column:
        out.append(column.rsplit(",", 1)[1].strip(" _"))
    if unit:
        out.append(str(unit))
    return [u for u in dict.fromkeys(s.strip() for s in out) if u]


class TermIndex:
    """Lexical and embedding lookup over one set of terms. Embeddings are cached on disk."""

    def __init__(self, terms: pd.DataFrame, name: str, cache_dir: Path, models=MODELS) -> None:
        self.terms = terms.reset_index(drop=True)
        self.curies = self.terms.curie.tolist()
        self.lut: dict[str, list[str]] = defaultdict(list)
        for r in self.terms.itertuples(index=False):
            syns = getattr(r, "exact_synonyms", None)
            for s in [r.label, *(list(syns) if syns is not None else [])]:
                if s:
                    self.lut[loose(s)].append(r.curie)
        self.models = models
        self.name = name
        self.cache_dir = Path(cache_dir)
        self._enc: dict[str, object] = {}
        self._mat: dict[str, np.ndarray] = {}

    def exact(self, text: str) -> list[str]:
        k = loose(text)
        for cand in (k, k[:-1] if k.endswith("s") else k, k + "s"):
            if cand in self.lut:
                return sorted(set(self.lut[cand]))
        return []

    def _encoder(self, repo: str):
        if repo not in self._enc:
            from sentence_transformers import SentenceTransformer
            self._enc[repo] = SentenceTransformer(repo)
        return self._enc[repo]

    def matrix(self, tag: str, repo: str) -> np.ndarray:
        if tag not in self._mat:
            labels = self.terms.label.tolist()
            key = hashlib.sha256(("\n".join(labels) + repo).encode()).hexdigest()[:16]
            path = self.cache_dir / f"{self.name}-{tag}-{key}.npy"
            if path.exists():
                self._mat[tag] = np.load(path)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                m = self._encoder(repo).encode(labels, normalize_embeddings=True, batch_size=128,
                                               show_progress_bar=False)
                np.save(path, m)
                self._mat[tag] = m
        return self._mat[tag]

    def encode(self, repo: str, prefix: str, texts: list[str]) -> np.ndarray:
        return self._encoder(repo).encode([prefix + t for t in texts], normalize_embeddings=True,
                                          show_progress_bar=False)

    def nearest(self, tag: str, repo: str, query: np.ndarray, k: int) -> list[tuple[str, float]]:
        sims = self.matrix(tag, repo) @ query
        top = np.argsort(-sims)[:k]
        return [(self.curies[i], float(sims[i])) for i in top]


class RemoteCache:
    """ZOOMA and OLS4 lookups, cached in one JSON file so reruns never hit the network."""

    def __init__(self, path: Path, enabled: bool) -> None:
        self.path, self.enabled = Path(path), enabled
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.dirty = False

    def _get(self, key: str, fetch) -> list[str]:
        if key not in self.data:
            if not self.enabled:
                return []
            try:
                self.data[key] = fetch()
            except Exception:
                self.data[key] = []
            self.dirty = True
            time.sleep(0.15)
        return self.data[key]

    def zooma(self, term: str) -> list[str]:
        import requests

        def fetch():
            r = requests.get(ZOOMA_ANNOTATE, params={"propertyValue": term}, timeout=30)
            return [t for a in r.json() for t in a.get("semanticTags", [])]
        return self._get(f"zooma::{term}", fetch)

    def ols4(self, term: str) -> list[str]:
        import requests

        def fetch():
            r = requests.get(OLS4_SEARCH, params={"q": term, "ontology": "efo", "rows": 10}, timeout=30)
            return [d.get("iri", "") for d in r.json().get("response", {}).get("docs", []) if d.get("iri")]
        return self._get(f"ols4::{term}", fetch)

    def save(self) -> None:
        if self.dirty:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=1))


@dataclass
class Retriever:
    ontology: Ontology
    space: pd.DataFrame
    cache_dir: Path
    remote: RemoteCache | None = None

    def __post_init__(self) -> None:
        usable = self.ontology.usable_terms()
        in_space = set(self.space.curie)
        syn = usable.set_index("curie").exact_synonyms
        space_terms = self.space.assign(exact_synonyms=self.space.curie.map(syn))
        entity_terms = usable[~usable.curie.isin(in_space) & (usable.prefix != "UO")]
        unit_terms = usable[usable.prefix == "UO"]
        self.space_ix = TermIndex(space_terms, "space", self.cache_dir)
        self.entity_ix = TermIndex(entity_terms, "entity", self.cache_dir)
        self.unit_ix = TermIndex(unit_terms, "unit", self.cache_dir)
        self.in_space = in_space
        terms = self.ontology.terms
        i2c = dict(zip(terms.iri, terms.curie))
        isa = self.ontology.edge_table[self.ontology.edge_table.pred == "is_a"]
        self.parents: dict[str, list[str]] = defaultdict(list)
        for sub, obj in zip(isa["sub"], isa["obj"]):
            a, b = i2c.get(sub), i2c.get(obj)
            if a and b:
                self.parents[a].append(b)

    def space_ancestors(self, curie: str) -> dict[str, int]:
        """Property-space ancestors of a term (the term itself excluded), with distance."""
        out, frontier, seen = {}, [curie], {curie}
        for depth in range(1, ANCESTOR_DEPTH + 1):
            nxt = []
            for c in frontier:
                for p in self.parents.get(c, []):
                    if p not in seen:
                        seen.add(p)
                        nxt.append(p)
                        if p in self.in_space:
                            out.setdefault(p, depth)
            frontier = nxt
        return out

    def value_terms(self, values: list[str]) -> dict[str, list[str]]:
        """value -> terms it names: exact label/synonym match in either pool, else the
        nearest entity term when similarity is high (MiniLM, the first model)."""
        tag, repo, prefix = self.entity_ix.models[0]
        out: dict[str, list[str]] = {}
        pending = []
        for v in values:
            hits = self.entity_ix.exact(v) or self.space_ix.exact(v)
            if hits:
                out[v] = hits
            else:
                pending.append(v)
        if pending:
            q = self.entity_ix.encode(repo, prefix, pending)
            for v, vec in zip(pending, q):
                c, sim = self.entity_ix.nearest(tag, repo, vec, 1)[0]
                if sim >= VALUE_MATCH_MIN_SIM:
                    out[v] = [c]
        return out

    def for_column(self, column: str, values: list[str], unit: str | None, hints: dict | None = None) -> list[dict]:
        """All candidates for one column: dicts with curie, pool, sources {source: rank}.

        `hints` is GEOmend preprocessing evidence for this column (decisions log
        1.6): `terms`, its lexical candidates in rank order, and `units`."""
        found: dict[str, dict] = {}
        hints = hints or {}

        def add(curie: str, pool: str, source: str, rank: int) -> None:
            c = found.setdefault(curie, {"curie": curie, "pool": pool, "sources": {}})
            c["sources"].setdefault(source, rank)

        forms = name_forms(column)
        for rank, c in enumerate(self.space_ix.exact(forms["plain"]) or self.space_ix.exact(forms["raw"]), 1):
            add(c, "space", "exact_space", rank)
        for form in {forms.get("entity"), forms["plain"]} - {None}:
            for rank, c in enumerate(self.entity_ix.exact(form), 1):
                add(c, "entity", "exact_entity", rank)
        plain_values = [str(v).rsplit(" (", 1)[0] for v in values][:VALUES_IN_QUERY]
        for tag, repo, prefix in self.space_ix.models:
            qn, qv = self.space_ix.encode(repo, prefix, [forms["plain"], f"{forms['plain']}: " + ", ".join(plain_values)])
            for rank, (c, _) in enumerate(self.space_ix.nearest(tag, repo, qn, TOPK_SPACE), 1):
                add(c, "space", f"{tag}_name", rank)
            for rank, (c, _) in enumerate(self.space_ix.nearest(tag, repo, qv, TOPK_SPACE), 1):
                add(c, "space", f"{tag}_values", rank)
            qe = self.entity_ix.encode(repo, prefix, [forms.get("entity", forms["plain"])])[0]
            for rank, (c, _) in enumerate(self.entity_ix.nearest(tag, repo, qe, TOPK_ENTITY), 1):
                add(c, "entity", f"{tag}_entity", rank)
        named = self.value_terms([str(v) for v in values[:VALUES_FOR_CATEGORY]])
        support: dict[str, set[str]] = defaultdict(set)
        closest: dict[str, int] = {}
        for v, terms in named.items():
            for t in terms:
                add(t, "space" if t in self.in_space else "entity", "value_term", 1)
                for anc, d in self.space_ancestors(t).items():
                    support[anc].add(v)
                    closest[anc] = min(closest.get(anc, d), d)
        ordered = sorted(support, key=lambda a: (-len(support[a]), closest[a], a))
        for rank, anc in enumerate(ordered[:8], 1):
            add(anc, "space", "value_category", rank)
        for u in unit_strings(column, unit):
            for rank, c in enumerate(self.unit_ix.exact(u), 1):
                add(c, "unit", "unit", rank)
        for u in hints.get("units", []):
            for rank, c in enumerate(self.unit_ix.exact(u), 1):
                add(c, "unit", "geomend_unit", rank)
        rank = 0
        for ident in hints.get("terms", []):
            v = self.ontology.validate(ident)
            if v.valid:
                rank += 1
                pool = "space" if v.curie in self.in_space else ("unit" if v.prefix == "UO" else "entity")
                add(v.curie, pool, "geomend", rank)
        if self.remote is not None:
            for source, hits in (("zooma", self.remote.zooma(forms["raw"])), ("ols4", self.remote.ols4(forms["raw"]))):
                rank = 0
                for ident in hits:
                    v = self.ontology.validate(ident)
                    if v.valid:
                        rank += 1
                        pool = "space" if v.curie in self.in_space else ("unit" if v.prefix == "UO" else "entity")
                        add(v.curie, pool, source, rank)
        return list(found.values())


def rank_and_display(cands: list[dict]) -> list[dict]:
    """Order candidates within each pool by number of sources, then best rank,
    and mark which are shown to the annotator. Iteration 2 measured this order
    against reciprocal-rank fusion and kept it (decision 7.3)."""
    out = []
    for pool, limit in (("space", DISPLAY_SPACE), ("entity", DISPLAY_ENTITY), ("unit", 10)):
        group = [c for c in cands if c["pool"] == pool]
        group.sort(key=lambda c: (-len(c["sources"]), min(c["sources"].values()), c["curie"]))
        for i, c in enumerate(group):
            out.append({**c, "n_sources": len(c["sources"]), "best_rank": min(c["sources"].values()),
                        "displayed": i < limit})
    return out


def generate(retriever: Retriever, columns: pd.DataFrame, hints: dict | None = None) -> pd.DataFrame:
    """Candidates for every row of a columns table (study_id, column, values json, unit).
    `hints` maps (study_id, column) to GEOmend evidence (see `Retriever.for_column`)."""
    rows = []
    for r in columns.itertuples(index=False):
        values = [v for v, _ in json.loads(r.values)]
        h = (hints or {}).get((r.study_id, r.column))
        for c in rank_and_display(retriever.for_column(r.column, values, getattr(r, "unit", None), h)):
            rows.append({"study_id": r.study_id, "column": r.column, "curie": c["curie"],
                         "label": retriever.ontology.label(c["curie"]), "pool": c["pool"],
                         "sources": json.dumps(c["sources"], sort_keys=True), "n_sources": c["n_sources"],
                         "best_rank": c["best_rank"], "displayed": c["displayed"]})
    if retriever.remote is not None:
        retriever.remote.save()
    return pd.DataFrame(rows)


def evaluate_recall(candidates: pd.DataFrame, gold: pd.DataFrame, key_map: dict | None = None) -> dict:
    """Share of gold columns whose gold primary term (and grounded qualifiers) are retrieved.

    `gold` is evaluate.load_gold output. `key_map` maps (accession, gold raw_key)
    to (study_id, column) when names differ (columns recovered by repair).
    """
    from colharmonize.evaluate import parse_qualifiers
    by_col = {k: g for k, g in candidates.groupby(["study_id", "column"])}
    prim_any = prim_shown = n_prim = q_any = q_shown = n_q = 0
    misses = []
    for row in gold.itertuples(index=False):
        key = (key_map or {}).get((row.accession, row.raw_key), (row.accession, row.raw_key))
        g = by_col.get(key)
        pool = set() if g is None else set(g.curie)
        shown = set() if g is None else set(g[g.displayed].curie)
        if row.primary_curie:
            n_prim += 1
            prim_any += row.primary_curie in pool
            prim_shown += row.primary_curie in shown
            if row.primary_curie not in pool:
                misses.append((row.accession, row.raw_key, row.primary_curie))
        for slot, value in parse_qualifiers(row.qualifiers):
            if re.match(r"^[A-Za-z]+:\d+$", value):
                n_q += 1
                q_any += value in pool
                q_shown += value in shown
    rate = lambda a, b: a / b if b else float("nan")
    return {"primary_pool_recall": rate(prim_any, n_prim), "primary_displayed_recall": rate(prim_shown, n_prim),
            "qualifier_pool_recall": rate(q_any, n_q), "qualifier_displayed_recall": rate(q_shown, n_q),
            "n_primary": n_prim, "n_qualifiers": n_q, "primary_misses": misses}
