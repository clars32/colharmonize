"""Command line for colharmonize.

    colharmonize ontology fetch --tag v3.94.0 --out DIR       download, pin, and build DIR.sqlite (the MetaMend store)
    colharmonize ontology pin   --json efo.json --tag v3.94.0 --out DIR
    colharmonize ontology store --ontology DIR --out efo.sqlite
    colharmonize ontology check --ontology DIR CURIE [--label LABEL]
    colharmonize status  --workspace DIR                    which stages are done, and the command to run next
    colharmonize ingest  --workspace DIR SOURCE...          MetaMend project + column profiles
    colharmonize columns --workspace DIR [--out TSV]
    colharmonize tasks write   STAGE --workspace DIR --run N [--batch-size K] [--seed S] [--studies ...]
    colharmonize tasks status  STAGE --workspace DIR --run N   pending batch files, one absolute path per line
    colharmonize tasks collect STAGE --workspace DIR --run N   validate answers, item by item
    colharmonize tasks retry   STAGE --workspace DIR --run N   a batch of just the failed items (at most 2 per item)
    colharmonize repair apply --workspace DIR --run N          apply validated repair rules
    colharmonize preprocess --workspace DIR [--store SQLITE] [--ontology DIR]   MetaMend evidence: concepts, merges, units
    colharmonize candidates --workspace DIR [--ontology DIR] [--cache DIR] [--remote]
    colharmonize annotate apply --workspace DIR --runs 1 2      resolve, combine runs, write annotations
    colharmonize reconcile apply --workspace DIR --runs 1 2     partition groups, write final variables
    colharmonize score   --workspace DIR                        review tiers (pre_accepted / quick / manual)
    colharmonize review page  --workspace DIR [--out HTML]      write the local review page
    colharmonize review apply --workspace DIR EXPORT            validate a page export into the review overlay
    colharmonize publish --workspace DIR [--out DIR] [--license URL] [--mapping-set-id URI]
    colharmonize registry use --workspace DIR REGISTRY          reconcile this workspace against a registry
    colharmonize registry add --workspace DIR [--registry DIR] [--include-pre-accepted]
    colharmonize metamend propose --workspace DIR [--select] [--dry-run]   variables -> MetaMend provider proposals
    colharmonize eval    --gold-columns TSV --gold-variables TSV --predictions TSV [--report MD] [--json JSON]

"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def _ontology(path: str):
    from colharmonize.ontology import Ontology
    return Ontology.from_dir(path)


def cmd_pin(args: argparse.Namespace) -> int:
    from colharmonize.ontology import pin_obograph
    print(json.dumps(pin_obograph(args.json, args.out, args.tag), indent=2))
    return 0


def store_beside(pinned: str | Path) -> Path:
    """Where `ontology fetch` puts the MetaMend store for a pinned directory: DIR.sqlite."""
    pinned = Path(pinned)
    return pinned.with_name(pinned.name + ".sqlite")


def _tilde(path: str | Path) -> str:
    """A path as people write it: ~ for the home directory."""
    path, home = Path(path), Path.home()
    return f"~/{path.relative_to(home)}" if path.is_relative_to(home) else str(path)


class _Progress:
    """Plain status lines on stdout; a download meter on stderr when it's a terminal."""

    def __init__(self, indent: str = ""):
        self.indent, self.tty, self.meter = indent, sys.stderr.isatty(), False

    def say(self, message: str) -> None:
        self._end_meter()
        print(f"{self.indent}{message}", flush=True)

    def download(self, done: int, total: int | None) -> None:
        if not self.tty:
            return
        size = f"{done / 1e6:.0f} of {total / 1e6:.0f} MB" if total else f"{done / 1e6:.0f} MB"
        print(f"\r{self.indent}  {size}", end="", file=sys.stderr, flush=True)
        self.meter = True

    def _end_meter(self) -> None:
        if self.meter:
            print(file=sys.stderr)
            self.meter = False


def _fetch_ontology(tag: str, out: str | Path, url: str | None, progress: _Progress) -> dict:
    """Pin a release and build its store, skipping whatever is already there."""
    import os
    from colharmonize.metamend_bridge import build_ontology_store
    from colharmonize.ontology import EFO_RELEASE_URL, fetch_release
    try:
        result = fetch_release(tag, out, url=url or EFO_RELEASE_URL, say=progress.say, progress=progress.download)
    except (ValueError, OSError) as e:
        sys.exit(f"ontology fetch: {e}")
    store = store_beside(out)
    if store.exists():
        result["store"] = {"status": "already built", "store": str(store)}
    else:
        progress.say("Building the lookup store")
        part = store.with_name(store.name + ".part")   # renamed only once complete
        result["store"] = {"status": "built", **build_ontology_store(_ontology(out), part)}
        os.replace(part, store)
        result["store"]["store"] = str(store)
    return result


def _ontology_line(tag: str, out: str | Path, result: dict) -> str:
    if result["status"] == "already pinned" and result["store"]["status"] == "already built":
        return f"EFO {tag} is already set up in {_tilde(out)}"
    terms = f" ({result['n_terms']:,} terms)" if "n_terms" in result else ""
    return f"EFO {tag} is ready{terms} in {_tilde(out)}"


class _Quiet(_Progress):
    """No output, for --json."""

    def say(self, message: str) -> None:
        pass

    def download(self, done: int, total: int | None) -> None:
        pass


def cmd_fetch(args: argparse.Namespace) -> int:
    from colharmonize.workspace import default_ontology_dir
    out = args.out or str(default_ontology_dir(args.tag))
    result = _fetch_ontology(args.tag, out, args.url, _Quiet() if args.json else _Progress())
    print(json.dumps(result, indent=2) if args.json else _ontology_line(args.tag, out, result))
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    from colharmonize import claude_setup
    from colharmonize.workspace import default_ontology_dir
    out = default_ontology_dir(args.tag)
    print("1/3 Ontology", flush=True)
    result = _fetch_ontology(args.tag, out, args.url, _Progress(indent="    "))
    print(f"    {_ontology_line(args.tag, out, result)}")
    print("2/3 Claude Code plugin", flush=True)
    print(f"    {'skipped (--no-plugin)' if args.no_plugin else claude_setup.install_plugin()}")
    print("3/3 Claude Code permissions", flush=True)
    if args.no_permissions:
        print("    skipped (--no-permissions); Claude Code will ask before each colharmonize step")
    else:
        added = claude_setup.allow()
        where = _tilde(claude_setup.settings_file())
        print(f"    {'allowed' if added else 'already allowed'}: colharmonize commands and its subagents' "
              f"answer files ({where})")
    print("\nReady. In an empty folder, run `claude` and type:\n  /colharmonize:harmonize GSE12345 GSE67890")
    return 0


def cmd_store(args: argparse.Namespace) -> int:
    from colharmonize.metamend_bridge import build_ontology_store
    print(json.dumps(build_ontology_store(_ontology(args.ontology), args.out, name=args.name), indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    v = _ontology(args.ontology).validate(args.curie, args.label)
    print(json.dumps(v.__dict__, indent=2))
    return 0 if v.valid else 1


def cmd_status(args: argparse.Namespace) -> int:
    from colharmonize import status
    from colharmonize.workspace import Workspace
    print(status.render(Workspace(args.workspace), args.workspace))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from colharmonize import profile
    from colharmonize.metamend_bridge import create_cohort, failed_sources, namespace_counts
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    ws.root.mkdir(parents=True, exist_ok=True)
    existed = ws.metamend.exists()
    create_cohort(ws.metamend, args.sources, offline=not args.online, workers=args.workers)
    failed = failed_sources(ws.metamend)
    if failed:
        # All or nothing: a partial cohort would pass as done, and MetaMend refuses
        # to create a project over it, so remove the one this call made.
        if not existed:
            shutil.rmtree(ws.metamend)
        for f in failed:
            print(f"{f['source']}: {f['error']}", file=sys.stderr)
        hint = "" if args.online else " Accessions not cached locally need --online."
        raise SystemExit(f"ingest failed for {len(failed)} of {len(args.sources)} sources; "
                         f"nothing was ingested.{hint}")
    for (scope, ns), n in sorted(namespace_counts(ws.metamend).items()):
        print(f"{scope:9} {ns:15} {n}")
    print(json.dumps(profile.build(ws)))
    return 0


def cmd_columns(args: argparse.Namespace) -> int:
    import pandas as pd
    from colharmonize.workspace import Workspace
    t = pd.read_parquet(Workspace(args.workspace).columns)
    t.to_csv(args.out or sys.stdout, sep="\t", index=False)
    return 0


STAGES = {"repair": "colharmonize.repair", "annotate": "colharmonize.annotate", "reconcile": "colharmonize.reconcile"}


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
        _require_tasks(ws, args.stage, args.run)
        manifest = json.loads((directory / "manifest.json").read_text())
        for e in manifest["batches"]:
            if not (directory / e["answer_file"]).exists():
                print((directory / e["batch_file"]).resolve())
        print(json.dumps(tasks.status(directory)), file=sys.stderr)
        return 0
    got = _collect(ws, mod, args.run)
    if args.action == "retry":
        if got.pending:
            sys.exit(f"answer the pending batches first: {got.pending}")
        path, given_up = tasks.write_retry(directory, sorted(got.failed))
        print(json.dumps({"retry_batch": str(path.resolve()) if path else None, "items": len(got.failed) - len(given_up),
                          "given_up": {i: got.failed[i] for i in given_up}}, indent=1))
        return 0 if path or not given_up else 1
    print(json.dumps({"answers": len(got.answers), "pending": got.pending, "failed_items": got.failed,
                      "problems": got.problems}, indent=1))
    return 0 if got.complete else 1


def _require_tasks(ws, stage: str, run: int) -> None:
    """Exit with a clear message, not a traceback, when a run has no tasks written."""
    import shlex
    if not (ws.tasks(stage, run) / "manifest.json").exists():
        sys.exit(f"{ws.root}: {stage} run {run} has no tasks yet; write them with "
                 f"`colharmonize tasks write {stage} --workspace {shlex.quote(str(ws.root))} --run {run}`")


def _collect(ws, mod, run: int, **kw):
    """Collect a run's answers and run the stage's own checks, item by item.

    Stage checks (a repair rule that does not compile, an unknown term ref)
    run here so a failing item can be re-tasked instead of being discovered at
    apply time; problems are attributed to the items they name.
    """
    from colharmonize import tasks
    _require_tasks(ws, mod.STAGE, run)
    got = tasks.collect(ws.tasks(mod.STAGE, run), mod.ANSWER_MODEL)
    if hasattr(mod, "validate_answers"):
        manifest = json.loads((ws.tasks(mod.STAGE, run) / "manifest.json").read_text())
        ids = [i for e in manifest["batches"] for i in e["items"]]
        by_item, general = tasks.split_problems(mod.validate_answers(ws, got.answers, run=run, **kw), ids)
        got.reject(by_item)
        got.problems += general
    return got


def _ready(got, run: int, drop_failed: bool) -> bool:
    """Whether a run can be applied. Failed items block it unless dropped on purpose."""
    if got.pending or got.problems or (got.failed and not drop_failed):
        print(json.dumps({"run": run, "pending": got.pending, "failed_items": got.failed, "problems": got.problems},
                         indent=1))
        if got.failed and not got.pending and not got.problems:
            print("re-task them with `colharmonize tasks retry`, or pass --drop-failed to apply without them",
                  file=sys.stderr)
        return False
    if got.failed:
        print(f"run {run}: applying without {len(got.failed)} failed item(s): {sorted(got.failed)}", file=sys.stderr)
    return True


def cmd_repair_apply(args: argparse.Namespace) -> int:
    from colharmonize import metamend_bridge as gb, repair
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    got = _collect(ws, repair, args.run)
    if not _ready(got, args.run, args.drop_failed):
        return 1
    derived, report, problems = repair.apply(ws, got.answers, gb.sample_values(ws.metamend))
    derived.to_parquet(ws.derived, index=False)
    report.to_csv(ws.root / "repair_report.tsv", sep="\t", index=False)
    print(report[["study_id", "column", "expected", "matched", "eligible"]].to_string(index=False) if len(report) else "no rules")
    for p in problems:
        print("PROBLEM", p)
    return 0


def cmd_preprocess(args: argparse.Namespace) -> int:
    from colharmonize import preprocess
    from colharmonize.ontology import Ontology
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    # preprocess runs before candidates, so it may be the first step to know the ontology
    onto = Ontology.from_dir(ws.recorded("ontology", args.ontology))
    print(json.dumps(preprocess.run(ws, ws.recorded("geomend_store", args.store), onto), indent=1))
    return 0


def cmd_candidates(args: argparse.Namespace) -> int:
    from colharmonize import candidates as cd, profile, property_space
    from colharmonize.ontology import Ontology
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    onto = Ontology.from_dir(ws.recorded("ontology", args.ontology))
    cache = Path(args.cache).expanduser() if args.cache else cd.default_cache_dir()
    retriever = cd.Retriever(onto, property_space.build(onto), cache / "embeddings",
                             cd.RemoteCache(cache / "remote.json", enabled=args.remote))
    cols = profile.annotation_columns(ws)
    from colharmonize import preprocess
    c = cd.generate(retriever, cols, preprocess.hints(ws))
    c.to_parquet(ws.candidates, index=False)
    print(f"{len(c)} candidates for {len(cols)} columns; displayed {int(c.displayed.sum())}; cache {cache}")
    print(c.groupby("pool").size().to_string())
    return 0


def cmd_annotate_apply(args: argparse.Namespace) -> int:
    from colharmonize import annotate
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    resolver = annotate.make_resolver(ws)
    runs = []
    for run in args.runs:
        got = _collect(ws, annotate, run, resolver=resolver)
        if not _ready(got, run, args.drop_failed):
            return 1
        runs.append(annotate.resolve_run(ws, got.answers, run, resolver))
    combined = annotate.combine(runs[0], runs[1] if len(runs) > 1 else None, resolver.ontology.label_map())
    combined.to_parquet(ws.root / "annotations.parquet", index=False)
    annotate.predictions(combined).to_csv(ws.root / "predictions_annotate.tsv", sep="\t", index=False)
    print(f"{len(combined)} columns; primary+predicate agree across runs: {combined.agree_primary.mean():.1%}; "
          f"{combined.variable_id.nunique()} variables before reconciliation")
    return 0


def cmd_reconcile_apply(args: argparse.Namespace) -> int:
    import pandas as pd
    from colharmonize import annotate, reconcile
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    resolver = annotate.make_resolver(ws)
    runs = []
    for run in args.runs:
        got = _collect(ws, reconcile, run, resolver=resolver)
        if not _ready(got, run, args.drop_failed):
            return 1
        runs.append(reconcile.resolve_run(ws, got.answers, run, resolver))
    ann = pd.read_parquet(ws.root / "annotations.parquet")
    final = reconcile.finalize(ann, runs[0], runs[1] if len(runs) > 1 else None, resolver.ontology.label_map())
    final.to_parquet(ws.root / "variables.parquet", index=False)
    _predictions(final).to_csv(ws.root / "predictions_reconcile.tsv", sep="\t", index=False)
    grouped = final[final.reconciled]
    agreement = "not measured (one run)" if len(runs) < 2 else f"{grouped.partition_agreement.mean():.1%}"
    print(f"{len(final)} columns -> {final.variable_id.nunique()} variables; {len(grouped)} columns reconciled; "
          f"partition agreement across runs {agreement}")
    return 0


def _predictions(final, tier: bool = False):
    """Rows for `colharmonize eval`: (accession, raw_key) -> variable and annotation."""
    import pandas as pd
    pred = pd.DataFrame({"accession": final.study_id, "raw_key": final.column, "variable_id": final.variable_id,
                         "predicate": final.predicate, "primary_curie": final.primary_curie,
                         "qualifiers": final.qualifiers.map(lambda q: "; ".join(f"{a}={b}" for a, b in json.loads(q)))})
    if tier:
        pred["tier"] = final.tier
    return pred


def cmd_score(args: argparse.Namespace) -> int:
    import pandas as pd
    from colharmonize import score
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    scored = score.tiers(pd.read_parquet(ws.root / "variables.parquet"))
    scored.to_parquet(ws.root / "scored.parquet", index=False)
    _predictions(scored, tier=True).to_csv(ws.root / "predictions_scored.tsv", sep="\t", index=False)
    print(score.summary(scored))
    return 0


def _latest_export(ws) -> Path:
    """The page's newest export in ~/Downloads. The page names it review_<workspace>.json, and a
    browser that finds that name taken adds " (1)" and so on; an export older than the page is
    from an earlier review, so it doesn't count."""
    downloads = Path.home() / "Downloads"
    page = ws.root / "review.html"
    since = page.stat().st_mtime if page.exists() else 0
    found = [p for p in downloads.glob(f"review_{ws.root.name}*.json")
             if p.name == f"review_{ws.root.name}.json" or p.name.startswith(f"review_{ws.root.name} (")]
    fresh = [p for p in found if p.stat().st_mtime >= since]
    if not fresh:
        older = f" ({len(found)} older than the review page ignored)" if found else ""
        sys.exit(f"review apply: no export of this review in {downloads}{older}; press Export on "
                 f"{page}, or give the file's path")
    return max(fresh, key=lambda p: p.stat().st_mtime)


def cmd_review(args: argparse.Namespace) -> int:
    from colharmonize import review
    from colharmonize.ontology import Ontology
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    onto = Ontology.from_dir(ws.ontology_dir())
    if args.action == "page":
        out = review.write_page(ws, onto, Path(args.out) if args.out else None).resolve()
        if not args.no_open:
            import webbrowser
            webbrowser.open(out.as_uri())
        print(f"Review page: {out.as_uri()}")
        return 0
    if args.export:
        export = Path(args.export).expanduser()
        if not export.exists():
            sys.exit(f"review apply: {export}: no such file")
    else:
        export = _latest_export(ws)
    from colharmonize import profile
    conflicts = profile.cooccurrence(profile.sample_values(ws))
    result = review.apply_export(ws, export, onto, conflicts)
    print(json.dumps(result, indent=1))
    return 0 if result["saved"] else 1


def cmd_publish(args: argparse.Namespace) -> int:
    from colharmonize import publish
    from colharmonize.ontology import Ontology
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    out = Path(args.out) if args.out else ws.root / "published"
    result = publish.publish(ws, Ontology.from_dir(ws.ontology_dir()), out, args.mapping_set_id, args.license)
    print(json.dumps(result, indent=1))
    print(f"wrote {out}")
    return 0


def cmd_metamend_propose(args: argparse.Namespace) -> int:
    from colharmonize import writeback
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    report = writeback.run(ws, _ontology(str(ws.ontology_dir())), select=args.select, dry_run=args.dry_run)
    print(report.action.value_counts().to_string())
    refused = report[report.action == "refused"]
    for r in refused.itertuples(index=False):
        print(f"REFUSED {r.study_id}/{r.column}: {r.reason}")
    print(f"wrote {ws.root / 'published' / 'geomend_proposals.tsv'}")
    return 1 if len(refused) else 0


def cmd_registry(args: argparse.Namespace) -> int:
    import pandas as pd
    from colharmonize import profile, registry, review
    from colharmonize.workspace import Workspace
    ws = Workspace(args.workspace)
    if args.action == "use":
        if not args.path:
            sys.exit("registry use needs the registry directory")
        ws.remember(registry=str(Path(args.path).resolve()))
        print(f"{ws.root} reconciles against {Path(args.path).resolve()} (takes effect when reconcile tasks are written)")
        return 0
    path = args.path or args.registry or ws.settings().get("registry")
    if not path:
        sys.exit("no registry: pass --registry DIR or run `colharmonize registry use` first")
    rows, stale = review.current(pd.read_parquet(ws.root / "scored.parquet"), review.load_overlay(ws))
    cols = profile.annotation_columns(ws)
    values = {(s_, c): json.loads(v) for s_, c, v in zip(cols.study_id, cols.column, cols["values"])}
    statuses = ("accepted", "edited", "pre_accepted") if args.include_pre_accepted else ("accepted", "edited")
    result = registry.add(path, ws.root.name, rows, values, statuses)
    print(json.dumps({**result, "stale_decisions_skipped": stale}, indent=1))
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


DEFAULT_WORKSPACE = "harmonized"
WORKSPACE = {"default": DEFAULT_WORKSPACE,
             "help": f"the run's folder (default: ./{DEFAULT_WORKSPACE}, the one /colharmonize:harmonize makes)"}

HELP = """\
colharmonize: pool and harmonize sample metadata across GEO studies.

Get started:
  colharmonize setup                      once: ontology, Claude Code plugin, permissions
  claude                                  then, in Claude Code:
  > /colharmonize:harmonize GSE12345 GSE67890

Check on a run:
  colharmonize status                     where ./harmonized stands, and what's next

The other commands are the steps /colharmonize:harmonize runs for you:
  ingest, preprocess, tasks, repair, candidates, annotate, reconcile, score,
  review, publish; and ontology, registry, metamend, columns, eval.
  `colharmonize COMMAND --help` explains each one.
"""


class _HelpParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return HELP


def build_parser() -> argparse.ArgumentParser:
    p = _HelpParser(prog="colharmonize", usage="colharmonize COMMAND [options]")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND", prog="colharmonize",
                           parser_class=argparse.ArgumentParser)

    su = sub.add_parser("setup", help="once per machine: ontology, Claude Code plugin and permissions",
                        description="Get this machine ready, once: download and pin the EFO ontology, install "
                                    "the Claude Code plugin, and let Claude Code run colharmonize without asking "
                                    "at every step. Safe to run again; it skips what's already done.")
    su.add_argument("--tag", default="v3.94.0", help="EFO release (default: v3.94.0, the one measured)")
    su.add_argument("--url", help="download efo.json from here instead of the EFO release on GitHub")
    su.add_argument("--no-plugin", action="store_true", help="don't install the Claude Code plugin")
    su.add_argument("--no-permissions", action="store_true",
                    help="don't add colharmonize to Claude Code's allowed commands (it will ask at each step)")
    su.set_defaults(func=cmd_setup)

    ont = sub.add_parser("ontology", help="setup: download and pin the EFO release every term is checked against")
    osub = ont.add_subparsers(dest="ontology_command", required=True)
    fetch = osub.add_parser("fetch", help="download a release's efo.json, pin it, and build the MetaMend store beside it")
    fetch.add_argument("--tag", default="v3.94.0", help="release tag (default: v3.94.0, the one measured)")
    fetch.add_argument("--out", help="pinned directory; the store is written as DIR.sqlite "
                                     "(default: ~/.local/share/colharmonize/ontology/efo-TAG, "
                                     "under $COLHARMONIZE_HOME if set)")
    fetch.add_argument("--url", help="download from here instead of the EBISPOT/efo GitHub release ({tag} is filled in)")
    fetch.add_argument("--json", action="store_true", help="print the full result as JSON, with no progress lines")
    fetch.set_defaults(func=cmd_fetch)
    pin = osub.add_parser("pin", help="flatten an OBO-graph JSON release into a pinned directory")
    pin.add_argument("--json", required=True)
    pin.add_argument("--tag", required=True, help="release tag, e.g. v3.94.0")
    pin.add_argument("--out", required=True)
    pin.set_defaults(func=cmd_pin)
    store = osub.add_parser("store", help="write the pinned ontology as a MetaMend OntologyStore")
    store.add_argument("--ontology", required=True)
    store.add_argument("--out", required=True)
    store.add_argument("--name", default="efo")
    store.set_defaults(func=cmd_store)
    check = osub.add_parser("check", help="validate one identifier (and optionally its label)")
    check.add_argument("--ontology", required=True)
    check.add_argument("curie")
    check.add_argument("--label")
    check.set_defaults(func=cmd_check)

    st = sub.add_parser("status", help="where a run stands, and the command to run next (changes nothing)")
    st.add_argument("--workspace", **WORKSPACE)
    st.set_defaults(func=cmd_status)

    ing = sub.add_parser("ingest", help="step 1: start a run from GSE accessions (with --online) or SOFT files")
    ing.add_argument("--workspace", **WORKSPACE)
    ing.add_argument("--workers", type=int, default=4, help="studies read in parallel (default: 4)")
    ing.add_argument("--online", action="store_true", help="download GSE accessions from GEO (default: read only local files and the cache)")
    ing.add_argument("sources", nargs="+", metavar="SOURCE", help="GSE accessions (e.g. GSE12345) or paths to SOFT files or tables")
    ing.set_defaults(func=cmd_ingest)

    pp = sub.add_parser("preprocess", help="step 2: collect MetaMend evidence (term candidates, likely merges, units)")
    pp.add_argument("--workspace", **WORKSPACE)
    pp.add_argument("--store", help="the pinned ontology as a MetaMend store (default: the one the workspace recorded)")
    pp.add_argument("--ontology", help="pinned ontology directory (default: the one the workspace recorded)")
    pp.set_defaults(func=cmd_preprocess)

    col = sub.add_parser("columns", help="list a run's metadata columns")
    col.add_argument("--workspace", **WORKSPACE)
    col.add_argument("--out")
    col.set_defaults(func=cmd_columns)

    tk = sub.add_parser("tasks", help="steps 3, 5, 6: hand-off files for Claude subagents (write, status, collect, retry)")
    tk.add_argument("action", choices=["write", "status", "collect", "retry"],
                    help="write batch files; status: list unanswered ones; collect: validate answers; "
                         "retry: re-task failed items")
    tk.add_argument("stage", choices=list(STAGES), help="which judgment step")
    tk.add_argument("--workspace", **WORKSPACE)
    tk.add_argument("--run", type=int, required=True, help="run number; annotate and reconcile use two independent runs, 1 and 2")
    tk.add_argument("--batch-size", type=int, default=8, help="items per subagent (default: 8)")
    tk.add_argument("--seed", type=int)
    tk.add_argument("--studies", nargs="*")
    tk.set_defaults(func=cmd_tasks)

    rp = sub.add_parser("repair", help="step 3: apply the recovered columns")
    rp.add_argument("action", choices=["apply"])
    rp.add_argument("--workspace", **WORKSPACE)
    rp.add_argument("--drop-failed", action="store_true",
                    help="apply without items that still fail after retries (they are listed)")
    rp.add_argument("--run", type=int, default=1)
    rp.set_defaults(func=cmd_repair_apply)

    cd = sub.add_parser("candidates", help="step 4: shortlist ontology terms for every column")
    cd.add_argument("--workspace", **WORKSPACE)
    cd.add_argument("--ontology", help="pinned ontology directory (default: the one the workspace recorded)")
    cd.add_argument("--cache", help="embedding and remote-service cache directory "
                                    "(default: $COLHARMONIZE_CACHE, else ~/.cache/colharmonize)")
    cd.add_argument("--remote", action="store_true", help="query ZOOMA and OLS4 for names not already cached")
    cd.set_defaults(func=cmd_candidates)

    an = sub.add_parser("annotate", help="step 5: combine the two annotation runs")
    an.add_argument("action", choices=["apply"])
    an.add_argument("--workspace", **WORKSPACE)
    an.add_argument("--drop-failed", action="store_true",
                    help="apply without items that still fail after retries (they are listed)")
    an.add_argument("--runs", type=int, nargs="+", default=[1, 2])
    an.set_defaults(func=cmd_annotate_apply)

    rcp = sub.add_parser("reconcile", help="step 6: combine the two runs grouping columns into variables")
    rcp.add_argument("action", choices=["apply"])
    rcp.add_argument("--workspace", **WORKSPACE)
    rcp.add_argument("--drop-failed", action="store_true",
                    help="apply without items that still fail after retries (they are listed)")
    rcp.add_argument("--runs", type=int, nargs="+", default=[1, 2])
    rcp.set_defaults(func=cmd_reconcile_apply)

    sc = sub.add_parser("score", help="step 7: sort variables into review tiers (manual, quick, pre-accepted)")
    sc.add_argument("--workspace", **WORKSPACE)
    sc.set_defaults(func=cmd_score)

    rv = sub.add_parser("review", help="step 8: write the review page, or apply the decisions you exported")
    rv.add_argument("action", choices=["page", "apply"])
    rv.add_argument("export", nargs="?", help="decisions file exported from the page, for apply "
                                              "(default: ~/Downloads/review_<workspace name>.json)")
    rv.add_argument("--workspace", **WORKSPACE)
    rv.add_argument("--out", help="where to write the page (default: <workspace>/review.html)")
    rv.add_argument("--no-open", action="store_true", help="don't open the page in the browser")
    rv.set_defaults(func=cmd_review)

    pb = sub.add_parser("publish", help="step 9: write the pooled sample table, variables, columns and SSSOM mappings")
    pb.add_argument("--workspace", **WORKSPACE)
    pb.add_argument("--out", help="output directory (default: <workspace>/published)")
    pb.add_argument("--license", default="https://w3id.org/sssom/license/unspecified",
                    help="license URL for the SSSOM mapping set")
    pb.add_argument("--mapping-set-id", help="URI identifying the SSSOM mapping set")
    pb.set_defaults(func=cmd_publish)

    rg = sub.add_parser("registry", help="optional: share variables across runs")
    rg.add_argument("action", choices=["use", "add"])
    rg.add_argument("path", nargs="?", help="registry directory")
    rg.add_argument("--workspace", **WORKSPACE)
    rg.add_argument("--registry", help="registry directory for add (default: the one the workspace uses)")
    rg.add_argument("--include-pre-accepted", action="store_true",
                    help="also register variables no one has reviewed but every check passed")
    rg.set_defaults(func=cmd_registry)

    # "geomend" is the name before MetaMend; kept so existing scripts still run.
    gm = sub.add_parser("metamend", aliases=["geomend"], help="optional: send the variables back to the run's MetaMend project")
    gm.add_argument("action", choices=["propose"])
    gm.add_argument("--workspace", **WORKSPACE)
    gm.add_argument("--select", action="store_true",
                    help="also select each valid proposal as the field's mapping (still no reviewer vote)")
    gm.add_argument("--dry-run", action="store_true", help="write the report without changing the MetaMend project")
    gm.set_defaults(func=cmd_metamend_propose)

    ev = sub.add_parser("eval", help="evaluation: score a run against a gold standard")
    ev.add_argument("--gold-columns", required=True)
    ev.add_argument("--gold-variables", required=True)
    ev.add_argument("--predictions", required=True)
    ev.add_argument("--title")
    ev.add_argument("--report", help="write the markdown report here instead of stdout")
    ev.add_argument("--json", help="also write the full score as JSON")
    ev.set_defaults(func=cmd_eval)
    return p


def main(argv: list[str] | None = None) -> int:
    if not (sys.argv[1:] if argv is None else argv):
        print(HELP, end="")
        return 0
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
