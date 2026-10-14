# Installing colharmonize

colharmonize has two parts:
- **the `colharmonize` command**, a Python package that does all the
  deterministic work
- **a Claude Code plugin**, which runs the judgment stages with subagents

Install both. The plugin can't install the command for you, because Claude
Code plugins can't declare Python dependencies. The `/harmonize` skill checks
for the command first and stops with instructions if it is missing.

## Requirements

- Python 3.13 (GEOmend requires it)
- Claude Code 2.1.271 or later (the agents use `omitClaudeMd`)
- About 3 GB of disk for the Python environment (PyTorch, for embeddings)
- Network access the first time, for packages, two small embedding models
  (`all-MiniLM-L6-v2`, `bge-small-en-v1.5`) and the EFO release file. After
  that, every stage runs offline unless you ask for `--remote` lookups or
  `--online` ingest.
- Embeddings and remote lookups are cached in `~/.cache/colharmonize`, shared
  by every workspace. Set `COLHARMONIZE_CACHE` to put the cache elsewhere, or
  pass `--cache DIR` to `colharmonize candidates`.

## 1. Install the command

```bash
python3.13 -m venv ~/colharmonize-env
~/colharmonize-env/bin/pip install -e /path/to/colharmonize
```

Claude Code must be able to find `colharmonize` on its `PATH`. Activate the
environment before starting `claude`, or link the command onto your path:

```bash
ln -s ~/colharmonize-env/bin/colharmonize ~/.local/bin/colharmonize
```

## 2. Pin the ontology

```bash
colharmonize ontology fetch --tag v3.94.0 --out ontology/efo-v3.94.0
```

This downloads `efo.json` for EFO v3.94.0 from the EFO release on GitHub
(about 170 MB). It checks the file's SHA-256 against the copy colharmonize
was measured with, pins it in `ontology/efo-v3.94.0/`, and builds the GEOmend
store beside it as `ontology/efo-v3.94.0.sqlite`. The download itself isn't
kept; `version.tsv` in the pinned directory records its checksum. Running the
command again does nothing.

On a machine without network access, copy `efo.json` there and add
`--url file:///path/to/efo.json`. The checksum is still checked.

Every identifier colharmonize produces is validated against this pinned
copy, never a live service. Keep the directory wherever you like and give its
path when asked. A workspace records both paths the first time they're used,
so later commands don't ask again.

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

Once the repository is on GitHub, others add it by name. A private
repository uses the machine's existing git credentials:

```bash
claude plugin marketplace add OWNER/colharmonize
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

In Claude Code, from the directory where you want the workspace:

```
/colharmonize:harmonize work/my-run /path/to/GSE12345_family.soft.gz /path/to/GSE67890_family.soft.gz
```

The skill runs every stage. It launches the plugin's agents for the judgment
batches:
- `colharmonize:repairer` and `colharmonize:annotator` on Sonnet
- `colharmonize:reconciler` on Opus

The one human step is review: the skill builds `review.html` in the
workspace, you review it in a browser and export your decisions, and it
applies them before publishing.

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
