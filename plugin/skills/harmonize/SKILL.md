---
description: Harmonize metadata columns across GEO series or tables with colharmonize. Use when the user asks to harmonize, clean up, or make interoperable the sample metadata of several datasets.
argument-hint: <workspace dir> [SOFT files | GSE accessions ...]
---

# Harmonize dataset metadata with colharmonize

colharmonize decides which metadata columns pool across datasets and what they
mean in the ontology. The `colharmonize` command does all the deterministic
work. Your job is to run it and to hand each judgment batch to the right
subagent. Never answer a batch yourself, and never edit files under a
workspace's `tasks/` directory or its GEOmend project.

Arguments: `$ARGUMENTS`. The first argument is the workspace directory; any
further arguments are SOFT files, tables or GSE accessions to ingest.

## 0. Check the tool

Run `colharmonize --help`. If the command is missing, stop and tell the user
to install the package (`pip install -e <colharmonize checkout>`) in a Python
3.13 environment.

## 1. Ingest

Skip this step if `<workspace>/columns.parquet` already exists. Otherwise run:

    colharmonize ingest --workspace <workspace> <sources...>

It reads offline by default. Add `--online` only if the user gave GSE
accessions that are not available locally. Report the number of studies,
samples and columns it prints.

## 2. Repair (one run)

    colharmonize tasks write repair --workspace <workspace> --run 1
    colharmonize tasks status repair --workspace <workspace> --run 1

`status` prints one absolute batch path per line for every unanswered batch.
For each path, launch the `colharmonize:repairer` subagent with a message that
contains only that path. Launch all of them in one message so they run in
parallel. Then validate:

    colharmonize tasks collect repair --workspace <workspace> --run 1

If it reports problems, delete the answer files of the batches whose items
they name and launch the repairer again for those batches, at most twice. If problems remain, show them
to the user and stop. When collection is clean, apply the rules:

    colharmonize repair apply --workspace <workspace> --run 1

Show the user the coverage table and any PROBLEM lines. A rule that matched
fewer samples than expected is not an error to hide: say which samples it
missed.

## 3. Candidates

    colharmonize candidates --workspace <workspace> --ontology <pinned ontology dir>

Use the pinned ontology directory the user names; ask if none is given. Add
`--remote` only to let ZOOMA and OLS4 be queried for names not already cached.

## 4. Annotate (two independent runs)

    colharmonize tasks write annotate --workspace <workspace> --run 1 --batch-size 12
    colharmonize tasks write annotate --workspace <workspace> --run 2 --batch-size 12
    colharmonize tasks status annotate --workspace <workspace> --run 1
    colharmonize tasks status annotate --workspace <workspace> --run 2

Launch one `colharmonize:annotator` subagent per pending batch path, each
with a message containing only that path. Both runs can go in one message.
A subagent must answer one batch of one run; never give one subagent batches
from both runs, because the runs are only useful if they are independent.
Collect each run as in step 2 (re-task failing batches at most twice), then:

    colharmonize annotate apply --workspace <workspace> --runs 1 2

Report how many columns were annotated, the share where the two runs agree,
and the number of variables before reconciliation.

## 5. Reconcile (two independent runs)

    colharmonize tasks write reconcile --workspace <workspace> --run 1 --batch-size 6
    colharmonize tasks write reconcile --workspace <workspace> --run 2 --batch-size 6

Launch one `colharmonize:reconciler` subagent per pending batch, one batch
each and never mixing runs, exactly as in step 4. Collect both runs, then:

    colharmonize reconcile apply --workspace <workspace> --runs 1 2

Report the number of variables, how many columns were reconciled, and the
partition agreement between runs.

## 6. Score

    colharmonize score --workspace <workspace>

This assigns every column and variable a review tier from the two runs'
agreement and a fixed set of checks: `pre_accepted`, `quick` or `manual`.
Report the counts per tier. Nothing is accepted without review; the tier sets
the order and depth of review.

## Later stages

Review and publish will be added here as the colharmonize package gains them.
Until then, stop after scoring and summarise.
