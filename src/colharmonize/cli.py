"""Command line for colharmonize.

    colharmonize ontology pin   --json efo.json --tag v3.94.0 --out DIR
    colharmonize ontology store --ontology DIR --out efo.sqlite
    colharmonize ontology check --ontology DIR CURIE [--label LABEL]
    colharmonize ingest  --workspace DIR SOURCE...          GEOmend project + column profiles
    colharmonize columns --workspace DIR [--out TSV]
    colharmonize tasks write   STAGE --workspace DIR --run N [--batch-size K] [--seed S] [--studies ...]
    colharmonize tasks status  STAGE --workspace DIR --run N   pending batch files, one absolute path per line
    colharmonize tasks collect STAGE --workspace DIR --run N   validate answers
    colharmonize repair apply --workspace DIR --run N          apply validated repair rules
    colharmonize candidates --workspace DIR --ontology DIR [--remote]
    colharmonize annotate apply --workspace DIR --runs 1 2      resolve, combine runs, write annotations
    colharmonize eval    --gold-columns TSV --gold-variables TSV --predictions TSV [--report MD] [--json JSON]

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
    from colharmonize import profile
    from colharmonize.geomend_bridge import create_cohort, namespace_counts
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    ws.root.mkdir(parents=True, exist_ok=True)
    create_cohort(ws.geomend, args.sources, offline=not args.online, workers=args.workers)
    for (scope, ns), n in sorted(namespace_counts(ws.geomend).items()):
        print(f"{scope:9} {ns:15} {n}")
    print(json.dumps(profile.build(ws)))
    return 0


def cmd_columns(args: argparse.Namespace) -> int:
    import pandas as pd
    from colharmonize.workspace import Workspace
    t = pd.read_parquet(Workspace(args.workspace).columns)
    t.to_csv(args.out or sys.stdout, sep="\t", index=False)
    return 0


STAGES = {"repair": "colharmonize.repair", "annotate": "colharmonize.annotate"}


def _stage(name: str):
    import importlib
    if name not in STAGES:
        raise SystemExit(f"unknown stage {name!r}; known: {', '.join(STAGES)}")
    return importlib.import_module(STAGES[name])


def cmd_tasks(args: argparse.Namespace) -> int:
    from colharmonize import tasks
    from colharmonize.workspace import Workspace
    ws, mod = Workspace(args.workspace), _stage(args.stage)
    directory = ws.tasks(args.stage, args.run)
    if args.action == "write":
        if hasattr(mod, "prepare"):
            items = mod.prepare(ws, args.studies or None, args.run)
        else:
            items = mod.build_items(ws, args.studies or None)
        paths = tasks.write_batches(
            directory, stage=mod.STAGE, run=args.run, prompt_version=mod.PROMPT_VERSION,
            instructions=mod.INSTRUCTIONS, items=items, answer_model=mod.ANSWER_MODEL,
            batch_size=args.batch_size, seed=args.seed if args.seed is not None else 1000 * args.run + 1,
        )
        print(f"{len(items)} items in {len(paths)} batches under {directory}")
        return 0
    if args.action == "status":
        manifest = json.loads((directory / "manifest.json").read_text())
        for e in manifest["batches"]:
            if not (directory / e["answer_file"]).exists():
                print((directory / e["batch_file"]).resolve())
        print(json.dumps(tasks.status(directory)), file=sys.stderr)
        return 0
    got = tasks.collect(directory, mod.ANSWER_MODEL)
    # Stage-specific checks (e.g. a repair rule that does not compile) run here,
    # so the skill can re-task the batch instead of discovering it at apply time.
    if hasattr(mod, "validate_answers"):
        got.problems += mod.validate_answers(ws, got.answers, run=args.run)
    print(json.dumps({"answers": len(got.answers), "pending": got.pending, "problems": got.problems}, indent=1))
    return 0 if got.complete else 1


def cmd_repair_apply(args: argparse.Namespace) -> int:
    from colharmonize import geomend_bridge as gb, repair, tasks
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    got = tasks.collect(ws.tasks(repair.STAGE, args.run), repair.RepairAnswer)
    if not got.complete:
        print(json.dumps({"pending": got.pending, "problems": got.problems}, indent=1))
        return 1
    derived, report, problems = repair.apply(ws, got.answers, gb.sample_values(ws.geomend))
    derived.to_parquet(ws.derived, index=False)
    report.to_csv(ws.root / "repair_report.tsv", sep="\t", index=False)
    print(report[["study_id", "column", "expected", "matched", "eligible"]].to_string(index=False) if len(report) else "no rules")
    for p in problems:
        print("PROBLEM", p)
    return 0


def cmd_candidates(args: argparse.Namespace) -> int:
    from colharmonize import candidates as cd, profile, property_space
    from colharmonize.ontology import Ontology
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    onto = Ontology.from_dir(args.ontology)
    cache = Path(args.cache)
    retriever = cd.Retriever(onto, property_space.build(onto), cache / "embeddings",
                             cd.RemoteCache(cache / "remote.json", enabled=args.remote))
    cols = profile.annotation_columns(ws)
    c = cd.generate(retriever, cols)
    c.to_parquet(ws.candidates, index=False)
    ws.remember(ontology=str(Path(args.ontology).resolve()))
    print(f"{len(c)} candidates for {len(cols)} columns; displayed {int(c.displayed.sum())}")
    print(c.groupby("pool").size().to_string())
    return 0


def cmd_annotate_apply(args: argparse.Namespace) -> int:
    from colharmonize import annotate, tasks
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    resolver = annotate.make_resolver(ws)
    runs = []
    for run in args.runs:
        got = tasks.collect(ws.tasks(annotate.STAGE, run), annotate.AnnotateAnswer)
        got.problems += annotate.validate_answers(ws, got.answers, run=run, resolver=resolver)
        if not got.complete:
            print(json.dumps({"run": run, "pending": got.pending, "problems": got.problems}, indent=1))
            return 1
        runs.append(annotate.resolve_run(ws, got.answers, run, resolver))
    combined = annotate.combine(runs[0], runs[1] if len(runs) > 1 else runs[0])
    combined.to_parquet(ws.root / "annotations.parquet", index=False)
    annotate.predictions(combined).to_csv(ws.root / "predictions.tsv", sep="\t", index=False)
    print(f"{len(combined)} columns; primary+predicate agree across runs: {combined.agree_primary.mean():.1%}; "
          f"{combined.variable_id.nunique()} variables before reconciliation")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from dataclasses import asdict
    from colharmonize.evaluate import load_gold, load_predictions, report, score
    s = score(load_gold(args.gold_columns, args.gold_variables), load_predictions(args.predictions))
    text = report(s, args.title or f"Evaluation of {Path(args.predictions).name}")
    if args.report:
        Path(args.report).write_text(text)
    else:
        print(text)
    if args.json:
        Path(args.json).write_text(json.dumps(asdict(s), indent=1, default=str))
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

    ing = sub.add_parser("ingest", help="create a workspace: GEOmend project from SOFT files, tables or accessions, then profiles")
    ing.add_argument("--workspace", required=True)
    ing.add_argument("--workers", type=int, default=4)
    ing.add_argument("--online", action="store_true", help="allow downloading accessions (default: offline)")
    ing.add_argument("sources", nargs="+")
    ing.set_defaults(func=cmd_ingest)

    col = sub.add_parser("columns", help="list a workspace's characteristic columns")
    col.add_argument("--workspace", required=True)
    col.add_argument("--out")
    col.set_defaults(func=cmd_columns)

    tk = sub.add_parser("tasks", help="write, list and collect task batches for Claude Code subagents")
    tk.add_argument("action", choices=["write", "status", "collect"])
    tk.add_argument("stage")
    tk.add_argument("--workspace", required=True)
    tk.add_argument("--run", type=int, required=True)
    tk.add_argument("--batch-size", type=int, default=8)
    tk.add_argument("--seed", type=int)
    tk.add_argument("--studies", nargs="*")
    tk.set_defaults(func=cmd_tasks)

    rp = sub.add_parser("repair", help="apply validated repair rules")
    rp.add_argument("action", choices=["apply"])
    rp.add_argument("--workspace", required=True)
    rp.add_argument("--run", type=int, default=1)
    rp.set_defaults(func=cmd_repair_apply)

    cd = sub.add_parser("candidates", help="retrieve candidate terms for every column")
    cd.add_argument("--workspace", required=True)
    cd.add_argument("--ontology", required=True, help="pinned ontology directory")
    cd.add_argument("--cache", default="work/cache", help="embedding and remote-service cache directory")
    cd.add_argument("--remote", action="store_true", help="query ZOOMA and OLS4 for names not already cached")
    cd.set_defaults(func=cmd_candidates)

    an = sub.add_parser("annotate", help="resolve and combine annotation runs")
    an.add_argument("action", choices=["apply"])
    an.add_argument("--workspace", required=True)
    an.add_argument("--runs", type=int, nargs="+", default=[1, 2])
    an.set_defaults(func=cmd_annotate_apply)

    ev = sub.add_parser("eval", help="score predictions against a gold standard")
    ev.add_argument("--gold-columns", required=True)
    ev.add_argument("--gold-variables", required=True)
    ev.add_argument("--predictions", required=True)
    ev.add_argument("--title")
    ev.add_argument("--report", help="write the markdown report here instead of stdout")
    ev.add_argument("--json", help="also write the full score as JSON")
    ev.set_defaults(func=cmd_eval)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
