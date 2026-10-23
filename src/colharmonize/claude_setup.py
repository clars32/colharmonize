"""`colharmonize setup`: get Claude Code ready to run /colharmonize:harmonize without questions.

Two things a plugin can't do for itself:
- **Permissions.** Claude Code drops permission settings shipped in a plugin,
  and a skill's `allowed-tools` lasts only for the turn that invoked it. So
  two allow rules go into the user's own settings: plain `colharmonize`
  commands, and the subagents' answer files under a workspace's `tasks/`.
- **The plugin itself,** installed from GitHub with the `claude` command.

Nothing else in the settings file is changed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

PERMISSIONS = ["Bash(colharmonize *)", "Edit(**/tasks/*/run*/*.answer.json)"]
MARKETPLACE = "clars32/colharmonize"
PLUGIN = "colharmonize@colharmonize"


def settings_file() -> Path:
    """Claude Code's user settings: $CLAUDE_CONFIG_DIR/settings.json, else ~/.claude/settings.json."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"


def allow(path: Path | None = None, rules: list[str] = PERMISSIONS) -> list[str]:
    """Add `rules` to permissions.allow in the settings file; return the ones that were missing."""
    path = path or settings_file()
    settings = {}
    if path.exists():
        try:
            settings = json.loads(path.read_text() or "{}")
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path} isn't valid JSON ({e}); fix it, or add these permissions yourself: "
                             f"{', '.join(rules)}")
    allowed = settings.setdefault("permissions", {}).setdefault("allow", [])
    added = [r for r in rules if r not in allowed]
    if added:
        allowed.extend(added)
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".colharmonize-part")
        part.write_text(json.dumps(settings, indent=2) + "\n")
        os.replace(part, path)
    return added


def install_plugin(run=subprocess.run) -> str:
    """Install the plugin from GitHub with the `claude` command; say what happened."""
    claude = shutil.which("claude")
    if not claude:
        return "skipped: the `claude` command isn't on your PATH (install Claude Code, then run setup again)"
    if PLUGIN in run([claude, "plugin", "list"], capture_output=True, text=True).stdout:
        return f"already installed (`claude plugin update {PLUGIN}` updates it)"
    steps = [["plugin", "install", PLUGIN]]
    if MARKETPLACE not in run([claude, "plugin", "marketplace", "list"], capture_output=True, text=True).stdout:
        steps.insert(0, ["plugin", "marketplace", "add", MARKETPLACE])
    for args in steps:
        done = run([claude, *args], capture_output=True, text=True)
        if done.returncode != 0:
            raise SystemExit(f"`claude {' '.join(args)}` failed:\n{(done.stderr or done.stdout).strip()}")
    return f"installed from {MARKETPLACE}"
