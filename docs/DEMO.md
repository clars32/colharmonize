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
| Fetch the ontology | about 50 s |
| Install the plugin | about 10 s |
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

## The demo

### 1. Install the command (say: "one command, its own Python")

```bash
uv tool install --python 3.13 git+https://github.com/clars32/colharmonize.git
```

```bash
colharmonize --help
```

### 2. Pin the ontology (say: "every term is checked against one fixed EFO release")

```bash
colharmonize ontology fetch
```

It downloads EFO v3.94.0, checks its checksum and builds the lookup store.

### 3. Install the Claude Code plugin

```bash
claude plugin marketplace add clars32/colharmonize
```

```bash
claude plugin install colharmonize@colharmonize
```

### 4. Start Claude Code in an empty folder

```bash
mkdir ~/harmonize-demo && cd ~/harmonize-demo
```

```bash
claude --permission-mode acceptEdits
```

The flag lets the subagents write their answer files without asking each
time. The skill is already allowed to run `colharmonize` commands.

### 5. Run it

In Claude Code, type:

```
/colharmonize:harmonize GSE77298 GSE55457 GSE36700 GSE153015
```

What the audience sees, stage by stage:
- **Ingest:** 4 studies, 105 samples, 17 columns downloaded from GEO.
- **Repair:** columns hidden in sample titles and source names are recovered,
  such as subject and tissue.
- **Annotate:** two independent sets of subagents give each column an
  ontology term. Their agreement is reported.
- **Reconcile:** columns that mean the same thing are grouped into variables.
- **Score:** each variable gets a review tier (manual, quick or
  pre-accepted).

It stops at review and prints the path of `review.html`.

### 6. Review (the human step)

Cmd-click the path, or open `~/harmonize-demo/harmonized/review.html` in a
browser. Good things to show:
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

### 7. Finish

Back in Claude Code, type the command with nothing after it:

```
/colharmonize:harmonize
```

It applies your decisions from Downloads and publishes. Then show the
result, in Terminal (type `!` first to run it from inside Claude Code):

```bash
open ~/harmonize-demo/harmonized/published/pooled_samples.tsv
```

One row per sample across all four studies, one column per harmonized
variable. `pooled_values.tsv` beside it keeps every raw value next to its
harmonized one.

## If something goes wrong

- **GEO or the network is down at step 5.** Use the copies of the four
  series saved in `~/colharmonize-demo-backup`:

  ```
  /colharmonize:harmonize ~/colharmonize-demo-backup/GSE77298_family.soft.gz ~/colharmonize-demo-backup/GSE55457_family.soft.gz ~/colharmonize-demo-backup/GSE36700_family.soft.gz ~/colharmonize-demo-backup/GSE153015_family.soft.gz
  ```

- **Claude Code asks for approval.** Choose "Yes". A run should need none;
  note which command asked.
- **The run stops partway** (a session limit, or Claude Code closed). Type
  `/colharmonize:harmonize` again. It picks up at the stage where it
  stopped and redoes nothing.
- **"no exported decisions" at step 7.** The export isn't in Downloads under
  `review_harmonized.json`. Give its path:
  `/colharmonize:harmonize` and then tell Claude where the file is.
- **`colharmonize: command not found`** in a Terminal tab opened before
  Claude Code was installed. Open a new tab, or run `source ~/.zshrc`.
