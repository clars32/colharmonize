---
description: Harmonize metadata columns across GEO series or tables with colharmonize. Use when the user asks to harmonize, clean up, or make interoperable the sample metadata of several datasets.
argument-hint: <workspace dir> [SOFT files | GSE accessions ...]
allowed-tools: Bash(colharmonize *)
---

# Harmonize dataset metadata with colharmonize

colharmonize decides which metadata columns pool across datasets and what they
mean in the ontology. The `colharmonize` command does all the deterministic
work. Your job is to run it and to hand each judgment batch to the right
subagent. Never answer a batch yourself, and never edit files under a
workspace's `tasks/` directory or its GEOmend project.

Plain `colharmonize ...` commands are pre-approved while this skill runs, so
the user isn't asked about each one. Run every command on its own line by its
bare name: no `cd`, no shell variables, and no `;`, `&&` or pipes, which
would need approval.

Arguments: `$ARGUMENTS`. The first argument is the workspace directory; any
further arguments are SOFT files, tables or GSE accessions to ingest.

## 0. Check the tool and find where the workspace stands

Run `colharmonize --help`. If the command is missing, stop and tell the user
to install it, then start Claude Code again:

    uv tool install --python 3.13 git+https://github.com/clars32/colharmonize.git

Then run:

    colharmonize status --workspace <workspace>

It reads the workspace's files, without changing anything, and reports which
stages are done and which command comes next. A new workspace starts at step
1. Otherwise, resume at the stage it names and continue from there; never
redo a stage it reports done. This is how a run interrupted partway, by a
session limit for example, picks up where it stopped:
- A judgment stage reported **in progress** has tasks written but not all
  answered. `status` names `tasks status`, not `tasks write`: writing again
  would fail, because a run's tasks are never overwritten. Launch subagents
  only for the pending batches `tasks status` lists. A subagent that hit a
  session limit may have written its answer anyway, so always check before
  relaunching.
- If every batch has an answer file, `status` names the stage's apply
  command, which validates the answers first.
- If review is **waiting for you**, run `colharmonize review apply
  --workspace <workspace>`: it finds the export in Downloads (step 7). If
  it says there is none, the review isn't exported yet; tell the user where
  the page is and stop.

Run `status` again whenever you are unsure where the run stands.

## 1. Ingest

Skip this step unless `status` named it. Otherwise run:

    colharmonize ingest --workspace <workspace> <sources...>

It reads offline by default. If the user gave GSE accessions rather than
files, add `--online` so they are downloaded; they are cached in the
workspace. If any source can't be read, ingest stops, names each failing
source and why, and leaves no GEOmend project behind, so correct the sources
and run it again. Report the number of studies, samples and columns it
prints.

## 1b. Preprocess (GEOmend evidence)

    colharmonize preprocess --workspace <workspace>

This collects what GEOmend can tell colharmonize, offline and with no model:
lexical concept candidates from the pinned store, suggested merges between
columns, and units. It is evidence only; later stages decide. The workspace
records both paths, so later commands don't need them. With no options it
uses the pinned ontology at the default location,
`~/.local/share/colharmonize/ontology/efo-v3.94.0`. If it says there is none
there, make it and run preprocess again. This downloads EFO v3.94.0 once
(about 170 MB, a minute or so), checks it and builds the store beside it:

    colharmonize ontology fetch

Only if the user names a different pinned directory, pass
`--ontology DIR --store DIR.sqlite`.
## 2. Repair (one run)

    colharmonize tasks write repair --workspace <workspace> --run 1
    colharmonize tasks status repair --workspace <workspace> --run 1

`status` prints one absolute batch path per line for every unanswered batch.
For each path, launch the `colharmonize:repairer` subagent with a message that
contains only that path. Launch all of them in one message so they run in
parallel. Then validate:

    colharmonize tasks collect repair --workspace <workspace> --run 1

Collection is per item: one bad answer fails only its own item, and the
rest of its batch stands. If it reports `failed_items`, re-task just those:

    colharmonize tasks retry repair --workspace <workspace> --run 1

This writes a retry batch holding only the failed items and prints its path.
Launch the same subagent on it, then collect again. Never edit or delete
answer files yourself. The tool allows two retries per item; after that
`retry` reports the item as given up. Show those items and their reasons to
the user, then apply without them:

    colharmonize repair apply --workspace <workspace> --run 1 [--drop-failed]

Without `--drop-failed`, apply refuses while any item is failing.

Show the user the coverage table and any PROBLEM lines. A rule that matched
fewer samples than expected is not an error to hide: say which samples it
missed.

## 3. Candidates

    colharmonize candidates --workspace <workspace>

It uses the pinned ontology that preprocess recorded. If it says none is
recorded, add `--ontology <pinned ontology dir>`. Add `--remote` only to let
ZOOMA and OLS4 be queried for names not already cached.

## 4. Annotate (two independent runs)

    colharmonize tasks write annotate --workspace <workspace> --run 1 --batch-size 12
    colharmonize tasks write annotate --workspace <workspace> --run 2 --batch-size 12
    colharmonize tasks status annotate --workspace <workspace> --run 1
    colharmonize tasks status annotate --workspace <workspace> --run 2

Launch one `colharmonize:annotator` subagent per pending batch path, each
with a message containing only that path. Both runs can go in one message.
A subagent must answer one batch of one run; never give one subagent batches
from both runs, because the runs are only useful if they are independent.
Collect each run as in step 2 (retry failed items with `tasks retry annotate`, at most twice each), then:

    colharmonize annotate apply --workspace <workspace> --runs 1 2

Report how many columns were annotated, the share where the two runs agree,
and the number of variables before reconciliation.

## 5. Reconcile (two independent runs)

If the user keeps a registry of variables from earlier runs (ask once, if
you don't know), point the workspace at it first, so columns can join
variables that already exist:

    colharmonize registry use --workspace <workspace> <registry-dir>

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

## 7. Review (the human step)

    colharmonize review page --workspace <workspace>

Tell the user the page's full path (`<workspace>/review.html`, made
absolute) so they can open it in a browser. Ask them to review it starting
with the manual tier and press Export; the browser saves the decisions as
`~/Downloads/review_<workspace name>.json`. Do not review on their behalf.
Then stop, and tell them that when they have exported, they finish the run by
typing the same command again:

    /colharmonize:harmonize <workspace>

`status` will then say review is waiting, and this applies the export from
Downloads:

    colharmonize review apply --workspace <workspace>

If the user saved it somewhere else, add its path at the end.

If it reports problems (an identifier not in the pinned ontology, a move that
pools columns that conflict on the same samples), show them to the user;
nothing is saved until the export is clean. Stale decisions were made on
output that has since changed, so the variable needs another look. If the user
split columns out, rebuild the page so they can review the new variables.

## 8. Publish

    colharmonize publish --workspace <workspace> [--license URL]

This writes `variables.tsv`, `columns.tsv` and `mappings.sssom.tsv` under
`<workspace>/published/`, and always applies the review overlay last. It also
writes the pooled table: `pooled_samples.tsv`, with one row per sample across
all studies and one column per variable, holding harmonized values. Its long
form, `pooled_values.tsv`, keeps each value beside its raw value and source
column. Tell the user about the pooled table first: for most people it is the
product. If it reports multi-valued cells, a study repeated a key on its
samples; every value is kept, joined with " | ", so say which variables have
them. Ask the
user for a license before publishing mappings they will share; without one,
the SSSOM header records the license as unspecified. Report the count of
variables per review status.

If the workspace uses a registry, offer to register the reviewed variables so
later runs can join them:

    colharmonize registry add --workspace <workspace>

Only accepted and edited variables are registered unless the user asks for
`--include-pre-accepted`.

## 9. Write back to GEOmend (optional)

If the user also works in the workspace's GEOmend project, or someone who
uses GEOmend without Claude needs the result, offer to send the variables
there:

    colharmonize geomend propose --workspace <workspace>

Each characteristic column of a variable that review didn't reject becomes a
GEOmend provider proposal, with the variable's term and a complete value
recode. GEOmend validates it against the actual values and keeps it pending
its own review. Columns recovered by repair aren't GEOmend fields, so they
aren't sent. The report lists every column and what happened to it. Add
`--select` only if the user asks for the proposals to become the fields'
current mappings. Even then they are not reviewer votes.
