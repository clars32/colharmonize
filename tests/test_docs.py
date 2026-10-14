"""The commands the skill and install guide tell people to run are ones the CLI accepts."""
from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from colharmonize import cli

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugin" / "skills" / "harmonize" / "SKILL.md"
DOCS = [SKILL, ROOT / "docs" / "INSTALL.md", ROOT / "README.md"]


def _commands(text: str) -> list[str]:
    """`colharmonize` lines in code blocks (indented or fenced), placeholders filled in."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        if not (fenced or line.startswith("    ")):
            continue
        command = line.strip().removeprefix("./.venv/bin/")
        if command.startswith("colharmonize "):
            command = re.sub(r"\[[^\]]*\]", "", command)     # optional arguments
            out.append(re.sub(r"<[^>]*>", "X", command))      # <workspace>, <pinned ontology dir>
    return out


@pytest.mark.parametrize("command", [c for p in DOCS for c in _commands(p.read_text())])
def test_documented_commands_parse(command):
    cli.build_parser().parse_args(shlex.split(command)[1:])


def test_skill_resumes_from_status_and_setup_fetches_the_ontology():
    step0 = SKILL.read_text().split("## 0.", 1)[1].split("\n## ", 1)[0]
    assert "colharmonize status --workspace X" in _commands(step0)
    install = _commands((ROOT / "docs" / "INSTALL.md").read_text())
    assert any(c.startswith("colharmonize ontology fetch --tag v3.94.0") for c in install)
