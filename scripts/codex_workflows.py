#!/usr/bin/env python3
"""Render explicit-only Codex workflow skills from canonical command contracts."""

from __future__ import annotations

import re
from pathlib import Path

ROOT_TOKEN = "{{OBENGINEER_ROOT}}"
WORKFLOW_ORDER = (
    "ob-start",
    "ob-add-inputs",
    "ob-edit-inputs",
    "ob-analyze",
    "ob-review",
    "ob-implement",
    "ob-revise",
    "ob-terraform",
    "ob-verify",
    "ob-render",
)

SHORT_DESCRIPTIONS = {
    "ob-start": "Start a guided obengineer analysis",
    "ob-add-inputs": "Add evidence and run the next analysis",
    "ob-edit-inputs": "Edit inputs and run the next analysis",
    "ob-analyze": "Rerun analysis after editing inputs",
    "ob-review": "Review an analysis and its wiki",
    "ob-implement": "Implement one Ready work order",
    "ob-revise": "Revise one subordinate work order",
    "ob-terraform": "Generate an accepted Terraform plan",
    "ob-verify": "Verify accepted outcomes read-only",
    "ob-render": "Render the optional Word summary",
}


def command_files(commands_dir: Path) -> list[Path]:
    """Return exactly the supported workflow commands in invocation order."""
    files = [commands_dir / f"{name}.md" for name in WORKFLOW_ORDER]
    missing = [path.name for path in files if not path.is_file()]
    if missing:
        raise ValueError(f"missing Codex workflow command(s): {', '.join(missing)}")
    extra = sorted(
        path.name
        for path in commands_dir.glob("ob-*.md")
        if path.stem not in WORKFLOW_ORDER
    )
    if extra:
        raise ValueError(
            "Codex workflow order is missing command(s): " + ", ".join(extra)
        )
    return files


def _command_parts(command: Path) -> tuple[str, str]:
    text = command.read_text()
    match = re.fullmatch(
        r"---\ndescription: ([^\n]+)\n---\n\n(.*)",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError(f"invalid command frontmatter: {command}")
    return match.group(1).strip(), match.group(2).rstrip()


def render_skill(command: Path, root_value: str = ROOT_TOKEN) -> str:
    """Render one self-contained workflow wrapper from its command contract."""
    description, contract = _command_parts(command)
    name = command.stem
    if name not in WORKFLOW_ORDER:
        raise ValueError(f"unsupported Codex workflow command: {command.name}")
    contract = contract.replace(ROOT_TOKEN, root_value)
    unresolved_root_note = (
        f"""
If the contract still contains the literal `{ROOT_TOKEN}` placeholder, resolve it to
the obengineer toolkit root associated with this skill before following any referenced
file or command.
"""
        if root_value == ROOT_TOKEN
        else ""
    )
    return f"""---
name: {name}
description: >-
  {description}. Explicit workflow wrapper for ${name} in Codex CLI and
  @{name} in ChatGPT Desktop; do not invoke implicitly.
---

# {name}

Follow the matching obengineer command contract below as the authoritative workflow.
Preserve all user-supplied text accompanying the explicit invocation exactly and make
it available wherever the contract refers to `$ARGUMENTS`; do not drop, summarize, or
reinterpret those arguments before dispatch.
{unresolved_root_note}

## Command contract

{contract}
"""


def render_openai_yaml(name: str) -> str:
    """Render explicit-invocation UI metadata for one workflow wrapper."""
    if name not in WORKFLOW_ORDER:
        raise ValueError(f"unsupported Codex workflow: {name}")
    short = SHORT_DESCRIPTIONS[name]
    return f"""interface:
  display_name: "{name}"
  short_description: "{short}"
  default_prompt: "Use ${name} to {short[0].lower() + short[1:]}."

policy:
  allow_implicit_invocation: false
"""


def write_workflow_skills(
    destination: Path,
    commands_dir: Path,
    root_value: str = ROOT_TOKEN,
) -> None:
    """Materialize all wrappers without retaining stale workflow directories."""
    destination.mkdir(parents=True, exist_ok=True)
    wanted = set(WORKFLOW_ORDER)
    for existing in destination.iterdir():
        if existing.is_dir() and existing.name.startswith("ob-") and existing.name not in wanted:
            raise ValueError(f"unexpected Codex workflow directory: {existing}")
    for command in command_files(commands_dir):
        skill_dir = destination / command.stem
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(render_skill(command, root_value))
        agents = skill_dir / "agents"
        agents.mkdir(exist_ok=True)
        (agents / "openai.yaml").write_text(render_openai_yaml(command.stem))
