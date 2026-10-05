"""Command line for colharmonize.

    colharmonize ontology pin   --json efo.json --tag v3.94.0 --out DIR
    colharmonize ontology store --ontology DIR --out efo.sqlite
    colharmonize ontology check --ontology DIR CURIE [--label LABEL]
    colharmonize ingest  --project DIR SOURCE...
    colharmonize columns --project DIR [--out TSV]

Later stages (task files, ingesting subagent answers, reconciliation, review,
publish) are added as they are built.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ontology(path: str):
    from colharmonize.ontology import Ontology
    return Ontology.from_dir(path)


def cmd_pin(args: argparse.Namespace) -> int:
    from colharmonize.ontology import pin_obograph
    print(json.dumps(pin_obograph(args.json, args.out, args.tag), indent=2))
    return 0


def cmd_store(args: argparse.Namespace) -> int:
    from colharmonize.geomend_bridge import build_ontology_store
    print(json.dumps(build_ontology_store(_ontology(args.ontology), args.out, name=args.name), indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    v = _ontology(args.ontology).validate(args.curie, args.label)
    print(json.dumps(v.__dict__, indent=2))
    return 0 if v.valid else 1


def cmd_ingest(args: argparse.Namespace) -> int:
    from colharmonize.geomend_bridge import create_cohort, namespace_counts
    create_cohort(args.project, args.sources, offline=not args.online, workers=args.workers)
    for (scope, ns), n in sorted(namespace_counts(args.project).items()):
        print(f"{scope:9} {ns:15} {n}")
    return 0


def cmd_columns(args: argparse.Namespace) -> int:
    from colharmonize.geomend_bridge import field_table
    t = field_table(args.project)
    t = t[(t.scope == "sample") & (t.namespace == "characteristic")]
    if args.out:
        t.to_csv(args.out, sep="\t", index=False)
    else:
        t.to_csv(sys.stdout, sep="\t", index=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="colharmonize", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    ont = sub.add_parser("ontology", help="pin, project and query the pinned ontology")
    osub = ont.add_subparsers(dest="ontology_command", required=True)
    pin = osub.add_parser("pin", help="flatten an OBO-graph JSON release into a pinned directory")
    pin.add_argument("--json", required=True)
    pin.add_argument("--tag", required=True, help="release tag, e.g. v3.94.0")
    pin.add_argument("--out", required=True)
    pin.set_defaults(func=cmd_pin)
    store = osub.add_parser("store", help="write the pinned ontology as a GEOmend OntologyStore")
    store.add_argument("--ontology", required=True)
    store.add_argument("--out", required=True)
    store.add_argument("--name", default="efo")
    store.set_defaults(func=cmd_store)
    check = osub.add_parser("check", help="validate one identifier (and optionally its label)")
    check.add_argument("--ontology", required=True)
    check.add_argument("curie")
    check.add_argument("--label")
    check.set_defaults(func=cmd_check)

    ing = sub.add_parser("ingest", help="create a GEOmend project from SOFT files, tables or accessions")
    ing.add_argument("--project", required=True)
    ing.add_argument("--workers", type=int, default=4)
    ing.add_argument("--online", action="store_true", help="allow downloading accessions (default: offline)")
    ing.add_argument("sources", nargs="+")
    ing.set_defaults(func=cmd_ingest)

    col = sub.add_parser("columns", help="list the characteristic columns of a project")
    col.add_argument("--project", required=True)
    col.add_argument("--out")
    col.set_defaults(func=cmd_columns)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
