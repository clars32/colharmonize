"""The property space: terms a column's primary annotation is drawn from.

Column names are characteristic categories (`tissue`, `sex`, `disease state`),
not entities. Searching every allowlisted term for a category name is what
returned "periapical tissue disease" for `tissue` in iteration 1. Primary-term
retrieval therefore searches this smaller space. Qualifiers and indicator
targets are entities, so they are retrieved from the full pool instead
(candidates.py).

Built from four kinds of evidence (ported from iteration 2's s00c; see its
decisions_log 0c.2-0c.3 and 6a.7):
  1. ZOOMA's curated propertyType vocabulary (a snapshot ships with the package)
  2. every usable PATO and OBI class
  3. the labels of entity roots (`organism part`, `disease`, ...), never their subtrees
  4. a bounded walk of category roots (`measurement`, `quality`, `process`, ...),
     skipping nodes with very large fan-out, which are instance buckets such as
     the thousands of GWAS traits under `measurement`
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from importlib import resources

import pandas as pd

from colharmonize.ontology import Ontology
from colharmonize.text import loose

# Iteration 2's roots, found by its pilot gold (its decisions_log 0c.2, 6a.7), plus
# `disposition`. Entity roots' subtrees are excluded even when a category walk
# reaches them (BFO treats a disease as a disposition).
CATEGORY_ROOTS = {
    "EFO:0001444": "measurement",
    "BFO:0000019": "quality",
    "EFO:0004542": "planned process",
    "OBI:0000181": "population",
    "BFO:0000015": "process",
    "IAO:0000030": "information entity",
    "BFO:0000023": "role",
    "BFO:0000034": "function",
    # Added in iteration 3 (decisions_log 5.2): `disease staging` and the stage
    # and grade categories (T/N/M stage, tumour stage, Clark level) sit under
    # BFO disposition, which no root covered, so `Braak stage` and `CNS status`
    # could not retrieve them. Also admits ~30 injury/fracture terms; accepted.
    "BFO:0000016": "disposition",
}
ENTITY_ROOTS = {
    "EFO:0000635": "organism part",
    "EFO:0000324": "cell type",
    "MONDO:0000001": "disease",
    "EFO:0000399": "developmental stage",
    "CL:0000010": "cultured cell",
}


@dataclass(frozen=True)
class SpaceConfig:
    category_roots: dict[str, str] = field(default_factory=lambda: dict(CATEGORY_ROOTS))
    entity_roots: dict[str, str] = field(default_factory=lambda: dict(ENTITY_ROOTS))
    whole_prefixes: tuple[str, ...] = ("PATO", "OBI")
    # Units are qualifiers (unit slot), never a column's primary term.
    exclude_prefixes: tuple[str, ...] = ("UO",)
    max_depth: int = 3
    max_fanout: int = 40


def zooma_property_types() -> list[str]:
    return json.loads(resources.files("colharmonize.data").joinpath("zooma_property_types.json").read_text())


def build(ontology: Ontology, config: SpaceConfig = SpaceConfig()) -> pd.DataFrame:
    """Return the property space: curie, label, definition, prefix, origin."""
    use = ontology.usable_terms()
    usable = set(use.curie)
    lut: dict[str, set[str]] = defaultdict(set)
    for r in use.itertuples(index=False):
        for s in [r.label, *(list(r.exact_synonyms) if r.exact_synonyms is not None else [])]:
            if s:
                lut[loose(s)].add(r.curie)

    def resolve(term: str) -> set[str]:
        if "," in term:
            return set()
        k = loose(term)
        for cand in (k, k[:-1] if k.endswith("s") else k, k + "s"):
            if cand in lut:
                return lut[cand]
        return set()

    origin: dict[str, str] = {}
    for t in zooma_property_types():
        for c in sorted(resolve(t)):
            origin.setdefault(c, "zooma_property_type")
    for prefix in config.whole_prefixes:
        for c in use[use.prefix == prefix].curie:
            origin.setdefault(c, f"whole_prefix:{prefix}")
    for c in config.entity_roots:
        if c in usable:
            origin.setdefault(c, "entity_root_label")

    terms = ontology.terms
    isa = ontology.edge_table[ontology.edge_table.pred == "is_a"]
    kids: dict[str, list[str]] = defaultdict(list)
    for s, o in zip(isa["sub"], isa["obj"]):
        kids[o].append(s)
    i2c = dict(zip(terms.iri, terms.curie))
    # Entity roots' labels are admitted, their subtrees never: a category walk
    # that reaches a disease or an anatomical part through another route (BFO
    # treats a disease as a disposition) must not let it in.
    entity_subtree: set[str] = set()
    for root in config.entity_roots:
        stack = [ontology.iri(root)]
        while stack:
            for ch in kids.get(stack.pop(), []):
                c = i2c.get(ch)
                if c and c not in entity_subtree:
                    entity_subtree.add(c)
                    stack.append(ch)
    for root in config.category_roots:
        start = ontology.iri(root)
        seen, q = {start}, deque([(start, 0)])
        while q:
            node, d = q.popleft()
            if d and i2c.get(node) in usable and i2c[node] not in entity_subtree:
                origin.setdefault(i2c[node], f"category_root:{root}")
            if d >= config.max_depth or (d > 0 and len(kids.get(node, [])) > config.max_fanout):
                continue
            for ch in kids.get(node, []):
                if ch not in seen:
                    seen.add(ch)
                    q.append((ch, d + 1))

    by = use.set_index("curie")
    rows = [{"curie": c, "label": by.at[c, "label"], "definition": by.at[c, "definition"],
             "prefix": by.at[c, "prefix"], "origin": o} for c, o in sorted(origin.items())
            if c in by.index and c.split(":")[0] not in config.exclude_prefixes]
    return pd.DataFrame(rows)
