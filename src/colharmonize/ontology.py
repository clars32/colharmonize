"""The pinned ontology: the only authority on whether an identifier is valid.

Live services (ZOOMA, OLS4) and Claude propose; this module disposes. An
identifier is valid only if the pinned release contains it, its prefix is on
the allowlist, and it is not deprecated. When an identifier arrives together
with a label, the label must match the pinned label too, so a fabricated
identifier has to get two linked facts right (the check OntoGPT added in 1.2).

Ported from iteration 2's `efo_validate.py` and `s00b_pin_efo.py`, with the
corpus-specific configuration removed: the ontology directory, allowlist and
rejected prefixes are arguments, not module globals.

A pinned directory holds three files written by `pin_obograph`:
  index.parquet   one row per term (iri, curie, prefix, label, node_type,
                  definition, exact/related/broad/narrow synonyms, deprecated)
  edges.parquet   sub, pred, obj as full IRIs
  version.tsv     release tag, version IRI, source sha256, counts

`fetch_release` downloads a release's `efo.json` and pins it in one step.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Iterable

import pandas as pd

from colharmonize.normalise import normalise_key

OK = "OK"
NOT_IN_PINNED_FILE = "NOT_IN_PINNED_FILE"
OFF_ALLOWLIST = "OFF_ALLOWLIST"
REJECTED_PREFIX = "REJECTED_PREFIX"
DEPRECATED = "DEPRECATED"
UNPARSEABLE = "UNPARSEABLE"
LABEL_MISMATCH = "LABEL_MISMATCH"

# Ontologies EFO imports and that column annotations may use. UO supplies unit
# qualifiers (98 unit terms are imported into EFO v3.94.0).
DEFAULT_ALLOWED = frozenset({"EFO", "UBERON", "CL", "MONDO", "PATO", "NCIT", "OBI", "CHEBI", "HsapDv", "UO"})
# Returned by ZOOMA but not part of EFO. Named so their rejection is auditable.
DEFAULT_REJECTED = frozenset({"BTO", "AFR", "AFRL", "AFQ"})

OBO_BASE = "http://purl.obolibrary.org/obo/"
EFO_BASE = "http://www.ebi.ac.uk/efo/"

EFO_RELEASE_URL = "https://github.com/EBISPOT/efo/releases/download/{tag}/efo.json"
# SHA-256 of `efo.json` for releases colharmonize has been measured with. A
# fetch of one of these tags must match, so every install pins the same bytes.
KNOWN_SHA256 = {"v3.94.0": "76ef7edef6f392848afa1fe2e61db9eec88dd77d2f00e1798d5415294011b314"}

_SYNONYM_PREDS = {
    "hasExactSynonym": "exact",
    "hasRelatedSynonym": "related",
    "hasBroadSynonym": "broad",
    "hasNarrowSynonym": "narrow",
}


def curie_from_iri(iri: str) -> tuple[str, str]:
    """Return (prefix, curie) for an OBO-shaped IRI, or ('', '')."""
    tail = iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    if "_" not in tail:
        return "", ""
    prefix, local = tail.rsplit("_", 1)
    if not prefix:
        return "", ""
    return prefix, f"{prefix}:{local}"


def to_curie(ident: str) -> str:
    """Accept an IRI, a CURIE, or an OBO-style 'PATO_0000047'. Return a CURIE or ''."""
    if not ident:
        return ""
    s = str(ident).strip()
    if s.startswith(("http://", "https://")):
        s = s.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    if ":" in s and "_" not in s:
        prefix, _, local = s.partition(":")
        return f"{prefix}:{local}" if prefix and local else ""
    if "_" in s:
        prefix, _, local = s.rpartition("_")
        return f"{prefix}:{local}" if prefix and local else ""
    return ""


@dataclass(frozen=True)
class Verdict:
    input: str
    curie: str
    iri: str
    label: str
    prefix: str
    valid: bool
    reason: str


class Ontology:
    """A pinned ontology release with an allowlist."""

    def __init__(
        self,
        index: pd.DataFrame,
        edges: pd.DataFrame,
        version: dict[str, str],
        *,
        allowed: Iterable[str] = DEFAULT_ALLOWED,
        rejected: Iterable[str] = DEFAULT_REJECTED,
    ) -> None:
        # Terms are unique by IRI. Non-OBO IRIs (EFO imports dbpedia and NCBI
        # resources) have no CURIE, so CURIE lookup uses only rows that have
        # one; collapsing on CURIE would merge every CURIE-less term into one.
        self._terms = index.drop_duplicates(subset="iri").reset_index(drop=True)
        self._index = self._terms[self._terms.curie != ""].set_index("curie", drop=False)
        self._edges = edges
        self.version = dict(version)
        self.allowed = frozenset(allowed)
        self.rejected = frozenset(rejected)

    @classmethod
    def from_dir(cls, path: str | Path, **kwargs) -> "Ontology":
        """Load a pinned directory. Also reads iteration 2's file names
        (`efo_index_v3.94.0.parquet`, `efo_edges_...`, `version_iri.txt`)."""
        path = Path(path)

        def find(primary: str, pattern: str) -> Path:
            if (path / primary).exists():
                return path / primary
            matches = sorted(path.glob(pattern))
            if not matches:
                raise FileNotFoundError(f"{path}: no {primary} (or {pattern})")
            return matches[0]

        index = pd.read_parquet(find("index.parquet", "*_index_*.parquet"))
        edges = pd.read_parquet(find("edges.parquet", "*_edges_*.parquet"))
        version_file = find("version.tsv", "version_iri.txt")
        version = dict(line.split("\t", 1) for line in version_file.read_text().splitlines() if "\t" in line)
        return cls(index, edges, version, **kwargs)

    @property
    def terms(self) -> pd.DataFrame:
        """The full pinned index, one row per IRI, deprecated and CURIE-less terms included."""
        return self._terms

    @property
    def edge_table(self) -> pd.DataFrame:
        """All pinned edges as full IRIs (sub, pred, obj)."""
        return self._edges

    @property
    def version_iri(self) -> str:
        return self.version.get("version_iri", "")

    @property
    def release_tag(self) -> str:
        return self.version.get("release_tag", "")

    def iri(self, curie: str) -> str:
        """Full IRI for a CURIE: the pinned one when present, else constructed."""
        if curie in self._index.index:
            return str(self._index.at[curie, "iri"])
        prefix, _, local = curie.partition(":")
        if not local:
            return ""
        return f"{EFO_BASE if prefix == 'EFO' else OBO_BASE}{prefix}_{local}"

    def label(self, curie: str) -> str:
        return str(self._index.at[curie, "label"]) if curie in self._index.index else ""

    def definition(self, curie: str) -> str:
        if curie not in self._index.index:
            return ""
        d = self._index.at[curie, "definition"]
        return "" if d is None or (isinstance(d, float) and d != d) else str(d)

    def label_map(self) -> dict[str, str]:
        """CURIE -> label for every term with a CURIE."""
        return dict(zip(self._index.index, self._index.label))

    def validate(self, ident: str, expected_label: str | None = None) -> Verdict:
        """Validate an identifier, and its label when one is supplied.

        The label check compares normalised forms of the supplied label and the
        pinned canonical label. Synonyms do not count: a model that knows the
        identifier should know its name.
        """
        curie = to_curie(ident)
        prefix = curie.split(":", 1)[0] if curie else ""

        def verdict(reason: str, iri: str = "", label: str = "") -> Verdict:
            return Verdict(str(ident), curie, iri, label, prefix, reason == OK, reason)

        if not curie:
            return verdict(UNPARSEABLE)
        if prefix in self.rejected:
            return verdict(REJECTED_PREFIX)
        if curie not in self._index.index:
            return verdict(NOT_IN_PINNED_FILE)
        row = self._index.loc[curie]
        iri, label = str(row["iri"]), str(row["label"])
        if prefix not in self.allowed:
            return verdict(OFF_ALLOWLIST, iri, label)
        if bool(row["deprecated"]):
            return verdict(DEPRECATED, iri, label)
        if expected_label is not None and normalise_key(expected_label) != normalise_key(label):
            return verdict(LABEL_MISMATCH, iri, label)
        return verdict(OK, iri, label)

    @cached_property
    def _usable(self) -> pd.DataFrame:
        ix = self._index
        return ix[ix.prefix.isin(self.allowed) & ~ix.deprecated & (ix.node_type == "CLASS")].reset_index(drop=True)

    def usable_terms(self) -> pd.DataFrame:
        """Every term a candidate generator may propose. Allowlist membership is
        evaluated here, not read from a column stored at pin time."""
        return self._usable

    @cached_property
    def _is_a(self) -> pd.DataFrame:
        return self._edges[self._edges.pred == "is_a"]

    def parents(self, curie: str) -> list[str]:
        """is_a parents as CURIEs."""
        iri = self.iri(curie)
        return sorted(c for c in (curie_from_iri(o)[1] for o in self._is_a[self._is_a["sub"] == iri].obj) if c)

    def children(self, curie: str) -> list[str]:
        """is_a children as CURIEs."""
        iri = self.iri(curie)
        return sorted(c for c in (curie_from_iri(s)[1] for s in self._is_a[self._is_a.obj == iri]["sub"]) if c)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pin_obograph(json_path: str | Path, out_dir: str | Path, release_tag: str) -> dict[str, object]:
    """Flatten an OBO-graph JSON release (e.g. EFO's `efo.json`) into a pinned directory.

    Works for any OBO-graph JSON, not only EFO. Returns a summary dict.
    """
    src, out = Path(json_path), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    digest = _sha256(src)
    doc = json.loads(src.read_text())
    graphs = doc["graphs"]
    version_iri = (graphs[0].get("meta") or {}).get("version", "")

    rows, edges = [], []
    for graph in graphs:
        for node in graph.get("nodes", []) or []:
            iri = node.get("id", "")
            prefix, curie = curie_from_iri(iri)
            meta = node.get("meta") or {}
            syns: dict[str, list[str]] = {v: [] for v in _SYNONYM_PREDS.values()}
            for s in meta.get("synonyms") or []:
                bucket = _SYNONYM_PREDS.get(str(s.get("pred", "")).split("#")[-1])
                if bucket and s.get("val"):
                    syns[bucket].append(s["val"])
            rows.append({
                "iri": iri, "curie": curie, "prefix": prefix,
                "label": node.get("lbl") or "", "node_type": node.get("type", ""),
                "definition": (meta.get("definition") or {}).get("val", ""),
                "exact_synonyms": syns["exact"], "related_synonyms": syns["related"],
                "broad_synonyms": syns["broad"], "narrow_synonyms": syns["narrow"],
                "deprecated": bool(meta.get("deprecated", False)),
            })
        for e in graph.get("edges", []) or []:
            edges.append({"sub": e.get("sub"), "pred": e.get("pred"), "obj": e.get("obj")})

    index = pd.DataFrame(rows).drop_duplicates(subset="iri")
    edge_df = pd.DataFrame(edges, columns=["sub", "pred", "obj"]).drop_duplicates()
    index.to_parquet(out / "index.parquet", index=False)
    edge_df.to_parquet(out / "edges.parquet", index=False)
    summary = {
        "release_tag": release_tag, "version_iri": version_iri, "source_file": src.name,
        "sha256": digest, "n_terms": len(index), "n_edges": len(edge_df),
    }
    (out / "version.tsv").write_text("".join(f"{k}\t{v}\n" for k, v in summary.items()))
    return summary


def pinned_tag(out_dir: str | Path) -> str | None:
    """The release tag a directory is pinned to, or None if it holds no complete pin.

    `pin_obograph` writes version.tsv last, so its presence means the index and
    edges were written in full.
    """
    version = Path(out_dir) / "version.tsv"
    if not version.exists():
        return None
    fields = dict(line.split("\t", 1) for line in version.read_text().splitlines() if "\t" in line)
    return fields.get("release_tag", "")


def _download(url: str, dest: Path) -> None:
    import ssl
    import urllib.request

    import certifi   # installed with requests; python.org builds on macOS ship without CA certificates
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, timeout=60, context=context) as response, dest.open("wb") as fh:
        shutil.copyfileobj(response, fh, 1 << 20)


def fetch_release(release_tag: str, out_dir: str | Path, *, url: str = EFO_RELEASE_URL) -> dict[str, object]:
    """Download a release's OBO-graph JSON and pin it into `out_dir`.

    Does nothing if `out_dir` is already pinned to this tag, and refuses a
    directory pinned to another one. For a tag in KNOWN_SHA256 the download
    must match the known checksum. The JSON itself is not kept; version.tsv
    records its SHA-256. `url` may contain `{tag}`.
    """
    out = Path(out_dir)
    tag = pinned_tag(out)
    if tag is not None:
        if tag != release_tag:
            raise ValueError(f"{out} is already pinned to {tag or 'an unknown release'}, not {release_tag}")
        return {"status": "already pinned", "ontology": str(out)}
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=f".{out.name}-download-") as tmp:
        src = Path(tmp) / "efo.json"
        _download(url.format(tag=release_tag), src)
        digest = _sha256(src)
        expected = KNOWN_SHA256.get(release_tag)
        if expected and digest != expected:
            raise ValueError(f"efo.json for {release_tag} has SHA-256 {digest}, not the known {expected}; "
                             "nothing was pinned")
        summary = pin_obograph(src, out, release_tag)
    return {"status": "pinned", "ontology": str(out), **summary}
