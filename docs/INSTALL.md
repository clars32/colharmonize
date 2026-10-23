# Installing colharmonize

colharmonize has two parts:
- **the `colharmonize` command**, a Python package that does all the
  deterministic work
- **a Claude Code plugin**, which runs the judgment stages with subagents

Install both. The plugin can't install the command for you, because Claude
Code plugins can't declare Python dependencies. The `/harmonize` skill checks
for the command first and stops with instructions if it is missing.

## Quickstart

You need [uv](https://docs.astral.sh/uv/) and
[Claude Code](https://code.claude.com/docs/en/setup), signed in (run `claude`
once and type `/login`). Then:

```bash
uv tool install --python 3.13 git+https://github.com/clars32/colharmonize.git
colharmonize ontology fetch
claude plugin marketplace add clars32/colharmonize
claude plugin install colharmonize@colharmonize
```

Then, in an empty folder:

```bash
claude --permission-mode acceptEdits
```

and in Claude Code:

```
/colharmonize:harmonize work/my-run GSE12345 GSE67890
```

The sections below explain each step.

## Requirements

- Python 3.13 (GEOmend requires it). uv installs it for colharmonize if you
  don't have it.
- Claude Code 2.1.271 or later (the agents use `omitClaudeMd`)
- About 1.5 GB of disk for the command and its dependencies (PyTorch, for
  embeddings), and 200 MB for the ontology
- Network access the first time, for packages, two small embedding models
  (`all-MiniLM-L6-v2`, `bge-small-en-v1.5`) and the EFO release file. After
  that, every stage runs offline unless you ask for `--remote` lookups or
  `--online` ingest.
- Embeddings and remote lookups are cached in `~/.cache/colharmonize`, shared
  by every workspace. Set `COLHARMONIZE_CACHE` to put the cache elsewhere, or
  pass `--cache DIR` to `colharmonize candidates`.

## 1. Install the command

```bash
uv tool install --python 3.13 git+https://github.com/clars32/colharmonize.git
```

This makes its own Python 3.13 environment and puts `colharmonize` in
`~/.local/bin`, which Claude Code's installer already adds to your `PATH`.
Check with `colharmonize --help`. Update it later with
`uv tool upgrade colharmonize`; remove it with `uv tool uninstall colharmonize`.

To work on colharmonize itself, install a checkout in editable mode instead:

```bash
git clone https://github.com/clars32/colharmonize.git
uv venv --python 3.13 ~/colharmonize-env
uv pip install --python ~/colharmonize-env/bin/python -e ./colharmonize
```

Then put `~/colharmonize-env/bin` on your `PATH` before starting `claude`.

## 2. Pin the ontology

```bash
colharmonize ontology fetch
```

This downloads `efo.json` for EFO v3.94.0 from the EFO release on GitHub
(about 170 MB, a minute or so). It checks the file's SHA-256 against the copy
colharmonize was measured with, pins it in
`~/.local/share/colharmonize/ontology/efo-v3.94.0/`, and builds the GEOmend
store beside it as `efo-v3.94.0.sqlite`. The download itself isn't kept;
`version.tsv` in the pinned directory records its checksum. Running the
command again does nothing.

Every workspace uses this location unless told otherwise, so you're never
asked for a path. To keep the ontology elsewhere, set `COLHARMONIZE_HOME`, or
pass `--out DIR` here and `--ontology DIR --store DIR.sqlite` to
`colharmonize preprocess`. A workspace records both paths the first time
they're used.

On a machine without network access, copy `efo.json` there and add
`--url file:///path/to/efo.json`. The checksum is still checked.

Every identifier colharmonize produces is validated against this pinned
copy, never a live service.

## 3. Install the plugin

The repository root is a plugin marketplace (`.claude-plugin/marketplace.json`),
and the plugin is in `plugin/`. From a local checkout:

```bash
claude plugin marketplace add /path/to/colharmonize
claude plugin install colharmonize@colharmonize
```

Inside a Claude Code session, the same thing is
`/plugin marketplace add /path/to/colharmonize`, then
`/plugin install colharmonize@colharmonize`.

The repository is on GitHub at `clars32/colharmonize`, so others add it by
name. It is private: ask the owner for access first. The install uses the
machine's existing git credentials:

```bash
claude plugin marketplace add clars32/colharmonize
claude plugin install colharmonize@colharmonize
```

To check the plugin before sharing it:

```bash
claude plugin validate ./plugin --strict
```

**Update** with `claude plugin marketplace update colharmonize`, then
`claude plugin update colharmonize@colharmonize`. Git-hosted installs only
pick up a release whose `plugin/.claude-plugin/plugin.json` version was
bumped. **Remove** with `claude plugin uninstall colharmonize@colharmonize`.

## 4. Run it

Make an empty folder for your runs, and start Claude Code there with file
edits accepted:

```bash
mkdir ~/harmonize-runs && cd ~/harmonize-runs
claude --permission-mode acceptEdits
```

The flag matters. The judgment stages are done by subagents, each writing one
answer file in the workspace. Without it, Claude Code asks you to approve
every one of those writes. The skill itself is allowed to run `colharmonize`
commands without asking. Then, in Claude Code:

```
/colharmonize:harmonize work/my-run GSE12345 GSE67890
```

Give GSE accessions to have the series downloaded from GEO, or paths to SOFT
files you already have:

```
/colharmonize:harmonize work/my-run /path/to/GSE12345_family.soft.gz /path/to/GSE67890_family.soft.gz
```

The skill runs every stage. It launches the plugin's agents for the judgment
batches:
- `colharmonize:repairer` and `colharmonize:annotator` on Sonnet
- `colharmonize:reconciler` on Opus

The one human step is review. The skill stops and gives you the path of
`review.html`. Open it in a browser, review it starting with the manual tier,
and press Export; the browser saves `review_my-run.json` in Downloads. Then
type the same command again to finish:

```
/colharmonize:harmonize work/my-run
```

It applies your decisions from Downloads and publishes. The result is in
`work/my-run/published/`; start with `pooled_samples.tsv`.

If a run stops partway, for example at a session limit, start the skill
again with the same workspace. It runs `colharmonize status` first and
resumes at the stage that reports, without redoing finished work. You can
run it yourself at any time:

```bash
colharmonize status --workspace work/my-run
```

What a run costs: the 16-series evaluation run used 41 subagent calls and
about 18M input tokens, mostly cached reads. Its critical path took about
7 minutes of agent time. See `eval/cost/RESULTS.md`.

## What to expect

- **Review tiers set the order of review, nothing more.** `score` sorts
  variables into pre-accepted, quick and manual. On the sealed evaluation
  corpus, no confidence signal told right annotations from wrong ones: the
  tiers' AUC was 0.54, no better than chance (`docs/decisions_log.md` 15.2
  and 15.8). A pre-accepted variable hasn't been checked; if a result
  matters, review it too.
- **Missed pools aren't flagged.** On that corpus everything colharmonize
  pooled belonged together (pooling precision 100%), but recall was 70.9%,
  and every pooling error was a merge it missed. Look for columns that
  should pool and don't.
- **The manual tier needs a reviewer with clinical background.** It is where
  run disagreement concentrates real errors, and its calls, such as exact or
  broad terms and whether disease status and karyotype pool, take domain
  judgment. A reviewer without that background accepted all 21 manual-tier
  variables on the tuning corpus, and only 2 matched the curated gold
  (decisions log 9.4).

## Without the plugin

The skill and agents are plain files, so they work uninstalled. Follow
`plugin/skills/harmonize/SKILL.md` by hand, and launch general-purpose
subagents with the text of `plugin/agents/<stage>.md` plus the batch path.
Add to every prompt: "Use only the Read and Write tools, and write nothing
except the answer file." The plugin's agents have only those tools; general
agents that can run commands share a scratchpad and have collided there
(`docs/decisions_log.md` 15.3).
