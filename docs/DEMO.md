# Demo script: colharmonize as an end user runs it

A live demo, from a machine with only `uv` and Claude Code on it, of
installing colharmonize from GitHub and harmonizing four rheumatoid arthritis
studies into one pooled sample table. No other chat window is needed.

The series are GSE77298, GSE55457, GSE36700 and GSE153015: synovium studies
with 105 samples, with sex, age, tissue and disease status written
differently in each. None is in any evaluation corpus.

Rough timings (measured 2026-10-22, M3 MacBook Air, warm package cache):

| Step | Time |
|---|---|
| Install the command | a few seconds (a few minutes the first time) |
| Set up (ontology, plugin, permissions) | about 1 min |
| Run up to review | about 4 min |
| Review | as long as you like |
| Apply and publish | about 20 s |

On a machine that has never installed PyTorch, the first install downloads
about 1 GB and takes a few minutes. Run step 1 before the audience arrives
if the network is slow.

## Before the demo: reset to a clean machine

Run these in Terminal to remove everything an earlier run left. Each one is
safe to run when there's nothing to remove.

```bash
claude plugin uninstall colharmonize@colharmonize
```

```bash
claude plugin marketplace remove colharmonize
```

```bash
uv tool uninstall colharmonize
```

```bash
rm -rf ~/.local/share/colharmonize ~/harmonize-demo
```

```bash
rm -f ~/Downloads/review_harmonized.json
```

Then check the two prerequisites:

```bash
claude auth status
```

It should say `"loggedIn": true`; if not, run `claude` and type `/login`.

```bash
uv --version
```

Close every Claude window, so the demo uses only Terminal.

`setup` will report the Claude Code permissions as "already allowed" if an
earlier rehearsal added them. To show it adding them, remove the two
`colharmonize` entries from `permissions.allow` in `~/.claude/settings.json`
first.

## The demo

### 1. Install the command (say: "one command, its own Python")

```bash
uv tool install --python 3.13 git+https://github.com/clars32/colharmonize.git
```

```bash
colharmonize --help
```

### 2. Set up (say: "once per machine")

```bash
colharmonize setup
```

Three numbered steps scroll by:
1. **Ontology:** downloads EFO v3.94.0, checks it against the release
   colharmonize was measured with, and builds the lookup store. Say: "every
   term is checked against one fixed EFO release."
2. **Claude Code plugin:** installed from GitHub.
3. **Claude Code permissions:** colharmonize may run its own commands
   without asking at each step.

### 3. Start Claude Code in an empty folder

```bash
mkdir ~/harmonize-demo && cd ~/harmonize-demo
```

```bash
claude
```

### 4. Run it

In Claude Code, type:

```
/colharmonize:harmonize GSE77298 GSE55457 GSE36700 GSE153015
```

Claude prints one line per stage. What to say over each:
- **Ingest:** the four studies are downloaded from GEO.
- **Repair:** subagents recover columns hidden in sample titles and source
  names, such as subject and tissue.
- **Annotate:** two independent sets of subagents give each column an
  ontology term; their agreement is reported.
- **Reconcile:** columns that mean the same thing are grouped into variables.
- **Score:** each variable gets a review tier (manual, quick or
  pre-accepted).

At review, the page opens in the browser by itself, and Claude prints a link
to it.

### 5. Review (the human step)

If the page didn't open, cmd-click the link. Good things to show:
- **Disease status** pools three studies' columns named `diagnosis`,
  `disease` and `clinical status`, with "normal control" recoded to
  `healthy control`.
- **Tissue** pools all four studies: "synovial tissue", "synovial biopsies"
  and "synovial membrane" all become `synovium`.
- **GSE77298's `disease state`** is kept separate: the study wrote two
  different things under that one key.
- **ACPA/RF positivity** combines two tests, and no single term covers both.

Accept or edit the variables, then press **Export**. The browser saves
`review_harmonized.json` in Downloads.

### 6. Finish

Back in Claude Code, type the command with nothing after it:

```
/colharmonize:harmonize
```

It applies your decisions from Downloads, publishes, and prints a link to
the pooled table. Cmd-click it, or in Claude Code type:

```
!open harmonized/published/pooled_samples.tsv
```

One row per sample across all four studies, one column per harmonized
variable. `pooled_values.tsv` beside it keeps every raw value next to its
harmonized one.

## If something goes wrong

- **GEO or the network is down at step 4.** Use the copies of the four
  series saved in `~/colharmonize-demo-backup`:

  ```
  /colharmonize:harmonize ~/colharmonize-demo-backup/GSE77298_family.soft.gz ~/colharmonize-demo-backup/GSE55457_family.soft.gz ~/colharmonize-demo-backup/GSE36700_family.soft.gz ~/colharmonize-demo-backup/GSE153015_family.soft.gz
  ```

- **Claude Code asks for approval.** Choose "Yes, and don't ask again". A
  run after `colharmonize setup` should need none; note which command asked.
- **The run stops partway** (a session limit, or Claude Code closed). Type
  `/colharmonize:harmonize` again. It picks up at the stage where it
  stopped and redoes nothing.
- **"no export of this review" at step 6.** Export wasn't pressed, or the
  file went somewhere other than Downloads. Press Export again, or tell
  Claude where the file is.
- **`colharmonize: command not found`** in a Terminal tab opened before
  Claude Code was installed. Open a new tab, or run `source ~/.zshrc`.
