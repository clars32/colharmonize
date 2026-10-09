"""Tokens and time per pipeline stage, from Claude Code subagent transcripts.

    ./.venv/bin/python eval/cost/collect.py ~/.claude/projects/<project-dir>

Handoff task 16. Finds every subagent whose first message names a colharmonize
batch (`work/<workspace>/tasks/<stage>/run<N>/batch_*.json`), sums the token
usage of its model calls, and takes wall time from its first to its last
transcript record. Writes `agents.tsv` (one row per subagent, numbers only;
no transcript text) and `summary.md` here.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_BATCH = re.compile(r"work/([\w\-]+)/tasks/(repair|annotate|reconcile)/run(\d+)/(batch_\d+(?:_retry\d+)?|retry_\w+)\.json")


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def read_agent(path: Path) -> dict | None:
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not lines:
        return None
    first = lines[0].get("message", {}).get("content")
    text = first if isinstance(first, str) else json.dumps(first)
    m = _BATCH.search(text)
    if not m:
        return None
    usage: dict[str, dict] = {}
    models, tools, stamps = set(), 0, []
    for r in lines:
        if r.get("timestamp"):
            stamps.append(ts(r["timestamp"]))
        msg = r.get("message") or {}
        if r.get("type") == "assistant" and msg.get("usage"):
            usage[msg.get("id") or str(len(usage))] = msg["usage"]  # streamed parts repeat one message's usage
            models.add(msg.get("model", ""))
            tools += sum(1 for c in msg.get("content") or [] if isinstance(c, dict) and c.get("type") == "tool_use")
    ws, stage, run, batch = m.group(1), m.group(2), int(m.group(3)), m.group(4)
    batch_file = ROOT / "work" / ws / "tasks" / stage / f"run{run}" / f"{batch}.json"
    n_items = len(json.loads(batch_file.read_text())["items"]) if batch_file.exists() else None
    u = list(usage.values())
    return {
        "session": path.parts[-3][:8], "workspace": ws, "stage": stage, "run": run, "batch": batch,
        "model": ",".join(sorted(models)), "items": n_items, "model_calls": len(u), "tool_calls": tools,
        "input_uncached": sum(x.get("input_tokens", 0) for x in u),
        "cache_write": sum(x.get("cache_creation_input_tokens", 0) for x in u),
        "cache_read": sum(x.get("cache_read_input_tokens", 0) for x in u),
        "output": sum(x.get("output_tokens", 0) for x in u),
        "seconds": round((max(stamps) - min(stamps)).total_seconds(), 1) if stamps else None,
    }


def main(project_dir: str) -> None:
    rows = [r for p in sorted(Path(project_dir).expanduser().glob("*/subagents/*.jsonl")) if (r := read_agent(p))]
    rows.sort(key=lambda r: (r["workspace"], r["stage"], r["run"], r["batch"]))
    cols = list(rows[0])
    with (HERE / "agents.tsv").open("w") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join("" if r[c] is None else str(r[c]) for c in cols) + "\n")

    agg: dict[tuple, dict] = defaultdict(lambda: defaultdict(float))
    for r in rows:
        a = agg[(r["workspace"], r["stage"])]
        a["agents"] += 1
        a["items"] += r["items"] or 0
        a["input"] += r["input_uncached"] + r["cache_write"] + r["cache_read"]
        a["cache_read"] += r["cache_read"]
        # Some Claude Code versions record only the start-of-stream output count
        # (a handful of tokens per call); treat such a stage's output as unknown.
        a["output"] += r["output"]
        a["calls"] += r["model_calls"]
        a["seconds"] += r["seconds"] or 0
        a["max_seconds"] = max(a["max_seconds"], r["seconds"] or 0)
        a["model"] = r["model"]
    lines = ["# Subagent cost per stage", "",
             "From Claude Code transcripts (`collect.py`). Input counts every prompt token, cached or not; "
             "cached reads are shown separately because they are much cheaper. Agents run in parallel, so a "
             "stage's wall time is about its slowest agent, not the sum.", "",
             "| workspace | stage | model | agents | items | input tokens (cached reads) | output tokens "
             "| input per item | agent-minutes | slowest agent |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for (ws, stage), a in sorted(agg.items(), key=lambda kv: (kv[0][0], ["repair", "annotate", "reconcile"].index(kv[0][1]))):
        per_item = f"{a['input'] / a['items'] / 1000:.0f}k" if a["items"] else "—"
        output = f"{a['output'] / 1e3:.0f}k" if a["output"] / max(a["calls"], 1) >= 100 else "not recorded"
        lines.append(f"| {ws} | {stage} | {a['model'].replace('claude-', '')} | {int(a['agents'])} | {int(a['items']) or '—'} "
                     f"| {a['input'] / 1e6:.2f}M ({a['cache_read'] / 1e6:.2f}M) | {output} | {per_item} "
                     f"| {a['seconds'] / 60:.0f} | {a['max_seconds'] / 60:.1f} min |")
    (HERE / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1])
