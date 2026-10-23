---
description: Harmonize metadata columns across GEO series or tables with colharmonize. Use when the user asks to harmonize, clean up, or make interoperable the sample metadata of several datasets.
argument-hint: GSE accessions or SOFT files to harmonize (none, to finish a run)
allowed-tools: Bash(colharmonize *)
---

# Harmonize dataset metadata with colharmonize

colharmonize decides which metadata columns pool across datasets and what they
mean in the ontology. The `colharmonize` command does all the deterministic
work. Your job is to run it and to hand each judgment batch to the right
subagent. Never answer a batch yourself, and never edit files under a
workspace's `tasks/` directory or its GEOmend project.

`colharmonize setup` lets Claude Code run plain `colharmonize ...` commands
without asking. Run every command on its own line by its bare name: no `cd`,
no shell variables, and no `;`, `&&` or pipes, which would need approval.
Launch every subagent in the foreground (never with `run_in_background`), all
of a stage's batches in one message; they still run in parallel. If the user
is asked to approve colharmonize commands anyway, tell them once, at the end,
that `colharmonize setup` stops that.

## Talking to the user

Keep it minimal. The user wants the result, not a log; they can ask for
details. Use these messages and nothing more:
- **Start:** `Harmonizing N studies in <workspace, as a full path>.` When
  coming back to a run: `Resuming the run in <workspace>.`
- **After each stage:** one short line, such as `Ingest: 4 studies, 105
  samples, 17 columns.` No tables, no explanations, no lists.
- **Only if something needs the user's attention** (a failed source, an
  item given up after retries, a repair rule that missed samples): one more
  line saying what and where.
- **At review:** exactly these two lines, with the link from `review page`:

      Ready for review: [review.html](<file:// link>), opened in your browser.
      Check the manual tier first, press Export, then type `/colharmonize:harmonize` to finish.

- **At the end:** this one line, with a link to the pooled table, and no
  sentence before it:

      Done: [pooled_samples.tsv](<file:// link>), N samples × M variables from K studies.

  Add a second line only if publish reports multi-valued cells or rejected
  variables. Don't offer licenses, registries or GEOmend unless asked.

Arguments: `$ARGUMENTS`. Read them loosely; the user may type a plain
request such as "harmonize GSE77298 and GSE55457".
- **Sources** are GSE accessions (`GSE` and digits) and paths to SOFT files
  or tables.
- **The workspace** is the folder the run lives in. If the arguments name
  one (any other path-like word, such as `work/ra` or `ra-study`), use it.
  Otherwise pick it:
  - With sources: `harmonized` in the current directory. If that folder
    already holds a run, use `harmonized-2`, `harmonized-3` and so on, so an
    earlier run is never touched.
  - With no sources, the user is coming back to a run: find the runs in the
    current directory with Glob (`*/columns.parquet` and
    `*/*/columns.parquet`; each match's folder is a workspace). With one,
    use it. With several, use the one changed most recently, and say which
    one; the user can name another.
  - With no sources and no run, tell the user how to start one:
    `/colharmonize:harmonize GSE12345 GSE67890`, then stop.

## 0. Check the tool and find where the workspace stands

Run `colharmonize --help`. If the command is missing, stop and tell the user
to install and set it up, then start Claude Code again:

    uv tool install --python 3.13 git+https://github.com/clars32/colharmonize.git
    colharmonize setup

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
and run it again.

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
contains only that path. Launch all of them in one message, in the
foreground, so they run in
parallel. Then validate:

    colharmonize tasks collect repair --workspace <workspace> --run 1

Collection is per item: one bad answer fails only its own item, and the
rest of its batch stands. If it reports `failed_items`, re-task just those:

    colharmonize tasks retry repair --workspace <workspace> --run 1

This writes a retry batch holding only the failed items and prints its path.
Launch the same subagent on it, then collect again. Never edit or delete
answer files yourself. The tool allows two retries per item; after that
`retry` reports the item as given up. Tell the user which items and why, in
one line, then apply without them:

    colharmonize repair apply --workspace <workspace> --run 1 [--drop-failed]

Without `--drop-failed`, apply refuses while any item is failing.

If apply prints PROBLEM lines, a rule matched fewer samples than expected:
say which column and how many samples it missed, in one line. Don't show the
coverage table.

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

Report one line: columns annotated, and the share where the two runs agree.

## 5. Reconcile (two independent runs)

Only if the user has mentioned a registry of variables from earlier runs
(don't ask about one, and don't bring it up in reports), point the workspace
at it first, so columns can join variables that already exist:

    colharmonize registry use --workspace <workspace> <registry-dir>

    colharmonize tasks write reconcile --workspace <workspace> --run 1 --batch-size 6
    colharmonize tasks write reconcile --workspace <workspace> --run 2 --batch-size 6

Launch one `colharmonize:reconciler` subagent per pending batch, one batch
each and never mixing runs, exactly as in step 4. Collect both runs, then:

    colharmonize reconcile apply --workspace <workspace> --runs 1 2

Report one line: the number of variables, and how many pool two or more
studies.

## 6. Score

    colharmonize score --workspace <workspace>

This assigns every column and variable a review tier from the two runs'
agreement and a fixed set of checks: `pre_accepted`, `quick` or `manual`.
Nothing is accepted without review; the tier sets the order and depth of
review. Report one line: variables per tier.

## 7. Review (the human step)

    colharmonize review page --workspace <workspace>

It writes the page, opens it in the browser and prints its `file://` link.
Send the two review lines (see "Talking to the user") and stop. Do not
review on their behalf. The browser saves the export as
`~/Downloads/review_<workspace name>.json`. If you used a workspace other
than the most recent one in this directory, put its name after the command
in the second line.

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
column. For most people the pooled table is the product, so the final
message links to it (see "Talking to the user"). If publish reports
multi-valued cells, a study repeated a key on its samples and every value is
kept, joined with " | ". Without `--license`, the SSSOM header records the
license as unspecified; pass one only if the user gives it.

If the workspace uses a registry and the user asks, register the reviewed
variables so later runs can join them:

    colharmonize registry add --workspace <workspace>

Only accepted and edited variables are registered unless the user asks for
`--include-pre-accepted`.

## 9. Write back to GEOmend (optional)

Only if the user asks to send the variables to the workspace's GEOmend
project:

    colharmonize geomend propose --workspace <workspace>

Each characteristic column of a variable that review didn't reject becomes a
GEOmend provider proposal, with the variable's term and a complete value
recode. GEOmend validates it against the actual values and keeps it pending
its own review. Columns recovered by repair aren't GEOmend fields, so they
aren't sent. The report lists every column and what happened to it. Add
`--select` only if the user asks for the proposals to become the fields'
current mappings. Even then they are not reviewer votes.
