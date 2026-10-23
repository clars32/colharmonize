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
colharmonize setup
```

Then, in an empty folder, run `claude` and type:

```
/colharmonize:harmonize GSE12345 GSE67890
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

## 2. Set up

```bash
colharmonize setup
```

Run it once per machine. It does three things, and skips whatever is
already done, so it's safe to run again:

1. **Pins the ontology.** It downloads `efo.json` for EFO v3.94.0 from the
   EFO release on GitHub (about 170 MB, a minute or so), checks its SHA-256
   against the copy colharmonize was measured with, pins it in
   `~/.local/share/colharmonize/ontology/efo-v3.94.0/`, and builds the
   GEOmend store beside it. Every identifier colharmonize produces is
   validated against this pinned copy, never a live service.
2. **Installs the Claude Code plugin** from `clars32/colharmonize`, with the
   `claude` command. The repository is private, so you need access to it.
3. **Lets Claude Code run colharmonize without asking.** It adds two rules to
   `permissions.allow` in `~/.claude/settings.json` and changes nothing else
   there: `Bash(colharmonize *)` for the commands, and
   `Edit(**/tasks/*/run*/*.answer.json)` for the answer files the subagents
   write. Claude Code ignores permissions shipped inside a plugin, which is
   why this step exists. Without it, Claude Code asks before every step.

Options: `--no-plugin` and `--no-permissions` skip those steps.
`colharmonize ontology fetch` does step 1 alone; on a machine without network
access, copy `efo.json` there and add `--url file:///path/to/efo.json`. To
keep the ontology elsewhere, set `COLHARMONIZE_HOME`.

To do steps 2 and 3 by hand instead:

```bash
claude plugin marketplace add clars32/colharmonize
claude plugin install colharmonize@colharmonize
```

and add the two rules above to your Claude Code settings. **Update** the
plugin with `claude plugin marketplace update colharmonize`, then
`claude plugin update colharmonize@colharmonize`; **remove** it with
`claude plugin uninstall colharmonize@colharmonize`. To check the plugin
before sharing it, run `claude plugin validate ./plugin --strict` in a
checkout.

## 3. Run it

In an empty folder, start Claude Code:

```bash
mkdir ~/harmonize-runs && cd ~/harmonize-runs
claude
```

Then, in Claude Code:

```
/colharmonize:harmonize GSE12345 GSE67890
```

Give GSE accessions to have the series downloaded from GEO, or paths to SOFT
files you already have:

```
/colharmonize:harmonize /path/to/GSE12345_family.soft.gz /path/to/GSE67890_family.soft.gz
```

The skill runs every stage. It launches the plugin's agents for the judgment
batches:
- `colharmonize:repairer` and `colharmonize:annotator` on Sonnet
- `colharmonize:reconciler` on Opus

The one human step is review. The skill opens `review.html` in your browser
and stops. Review it, starting with the manual tier, and press Export; the
browser saves `review_harmonized.json` in Downloads. Then type the command
with nothing after it to finish:

```
/colharmonize:harmonize
```

It applies your decisions from Downloads and publishes. The result is in
`harmonized/published/`; start with `pooled_samples.tsv`.

The run lives in the folder `harmonized`. A second run in the same directory
goes to `harmonized-2`, and so on. To choose the name, put it before the
accessions: `/colharmonize:harmonize ra-study GSE12345 GSE67890`.

If a run stops partway, for example at a session limit, start the skill
again with the same workspace. It runs `colharmonize status` first and
resumes at the stage that reports, without redoing finished work. You can
run it yourself at any time:

```bash
colharmonize status
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
