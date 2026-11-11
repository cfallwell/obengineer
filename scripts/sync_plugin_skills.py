#!/usr/bin/env python3
"""Mirror canonical skills into the distributable plugin.

`skills/` is the single source. The plugin needs its own copy because a plugin
bundle must be self-contained when it is installed from a marketplace, and hosts
resolve skills relative to the plugin root rather than the repository root.

    python3 scripts/sync_plugin_skills.py           # copy canonical -> plugin
    python3 scripts/sync_plugin_skills.py --check    # fail if they differ

Also refreshes `.cursor/skills/` and `.agents/skills/`, which are links rather
than copies so local edits land on the canonical file.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys
from pathlib import Path

try:
    from scripts.codex_workflows import (
        ROOT_TOKEN as WORKFLOW_ROOT_TOKEN,
        WORKFLOW_ORDER,
        render_openai_yaml,
        render_skill,
        write_workflow_skills,
    )
except ModuleNotFoundError:  # Direct execution from scripts/.
    from codex_workflows import (  # type: ignore[no-redef]
        ROOT_TOKEN as WORKFLOW_ROOT_TOKEN,
        WORKFLOW_ORDER,
        render_openai_yaml,
        render_skill,
        write_workflow_skills,
    )

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "skills"
PLUGIN = ROOT / "plugins" / "obengineer"
PLUGIN_SKILLS = PLUGIN / "skills"
PLUGIN_CODEX_SKILLS = PLUGIN / "codex-skills"
PLUGIN_COMMANDS = PLUGIN / "commands"
COMMANDS = ROOT / "commands"
ROOT_TOKEN = "{{OBENGINEER_ROOT}}"
PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}"
CODEX_PLUGIN_ROOT_TOKEN = "${PLUGIN_ROOT}"
CURSOR_LINKS = ROOT / ".cursor" / "skills"
CODEX_LINKS = ROOT / ".agents" / "skills"
IGNORE_NAMES = ["__pycache__", ".pytest_cache", ".DS_Store"]
IGNORE = shutil.ignore_patterns(*IGNORE_NAMES, "*.pyc")
# Skills and prompts link to agents, prompts, and the engagement input template, so the bundle carries them too;
# an installed plugin cannot reach back into this repository.
COMPANION_DIRS = ("agents", "prompts", "inputs", "templates")
COMPANION_SCRIPTS = ("setup-splunk-access.sh",)


def skill_names() -> list[str]:
    return sorted(p.parent.name for p in CANONICAL.glob("*/SKILL.md"))


def shared_dirs() -> list[str]:
    """Directories under skills/ that are shared references, not skills."""
    return sorted(
        p.name for p in CANONICAL.iterdir()
        if p.is_dir() and not (p / "SKILL.md").exists()
    )


def diff_report(names: list[str]) -> list[str]:
    problems: list[str] = []
    for name in names + shared_dirs():
        src, dst = CANONICAL / name, PLUGIN_SKILLS / name
        if not dst.exists():
            problems.append(f"missing from plugin: {name}")
            continue
        cmp = filecmp.dircmp(src, dst, ignore=IGNORE_NAMES)

        def walk(node, prefix=""):
            for f in node.left_only:
                problems.append(f"only in canonical: {prefix}{f}")
            for f in node.right_only:
                problems.append(f"only in plugin: {prefix}{f}")
            for f in node.diff_files:
                problems.append(f"differs: {prefix}{f}")
            for sub, child in node.subdirs.items():
                walk(child, f"{prefix}{sub}/")

        walk(cmp, f"{name}/")
    extra = set(p.name for p in PLUGIN_SKILLS.iterdir() if p.is_dir()) - set(
        names + shared_dirs()
    ) if PLUGIN_SKILLS.exists() else set()
    problems += [f"stale directory in plugin: {name}" for name in sorted(extra)]
    return problems


def codex_root_problems(root: Path, expected: set[str]) -> list[str]:
    problems: list[str] = []
    if not root.is_dir():
        return ["missing Codex plugin skills root"]
    for entry in sorted(root.iterdir(), key=lambda path: path.name):
        if entry.is_symlink():
            problems.append(f"unexpected root symlink in Codex plugin skills: {entry.name}")
        elif not entry.is_dir():
            problems.append(f"unexpected root file in Codex plugin skills: {entry.name}")
        elif entry.name not in expected:
            problems.append(f"stale directory in Codex plugin skills: {entry.name}")
    return problems


def codex_skill_problems(names: list[str]) -> list[str]:
    problems: list[str] = []
    expected = set(names + shared_dirs() + list(WORKFLOW_ORDER))
    problems.extend(codex_root_problems(PLUGIN_CODEX_SKILLS, expected))
    actual = (
        {
            path.name
            for path in PLUGIN_CODEX_SKILLS.iterdir()
            if path.is_dir() and not path.is_symlink()
        }
        if PLUGIN_CODEX_SKILLS.exists()
        else set()
    )
    for name in sorted(set(names + shared_dirs())):
        source = CANONICAL / name
        target = PLUGIN_CODEX_SKILLS / name
        if not target.is_dir():
            problems.append(f"missing from Codex plugin skills: {name}")
            continue
        comparison = filecmp.dircmp(source, target, ignore=IGNORE_NAMES)

        def walk(node, prefix=""):
            for filename in node.left_only:
                problems.append(f"only in canonical: codex-skills/{prefix}{filename}")
            for filename in node.right_only:
                problems.append(f"only in Codex plugin: {prefix}{filename}")
            for filename in node.diff_files:
                problems.append(f"differs: codex-skills/{prefix}{filename}")
            for subdir, child in node.subdirs.items():
                walk(child, f"{prefix}{subdir}/")

        walk(comparison, f"{name}/")
    for name in WORKFLOW_ORDER:
        command = COMMANDS / f"{name}.md"
        skill = PLUGIN_CODEX_SKILLS / name
        expected_skill = render_skill(command, CODEX_PLUGIN_ROOT_TOKEN)
        expected_openai = render_openai_yaml(name)
        if not (skill / "SKILL.md").is_file():
            problems.append(f"missing from Codex plugin skills: {name}/SKILL.md")
        elif (skill / "SKILL.md").read_text() != expected_skill:
            problems.append(f"differs: codex-skills/{name}/SKILL.md")
        if not (skill / "agents/openai.yaml").is_file():
            problems.append(
                f"missing from Codex plugin skills: {name}/agents/openai.yaml"
            )
        elif (skill / "agents/openai.yaml").read_text() != expected_openai:
            problems.append(f"differs: codex-skills/{name}/agents/openai.yaml")
        actual_files = (
            {
                path.relative_to(skill).as_posix()
                for path in skill.rglob("*")
                if path.is_file()
            }
            if skill.is_dir()
            else set()
        )
        expected_files = {"SKILL.md", "agents/openai.yaml"}
        for extra in sorted(actual_files - expected_files):
            problems.append(f"only in Codex plugin: {name}/{extra}")
    return problems


def companion_problems() -> list[str]:
    problems: list[str] = []
    for name in COMPANION_DIRS:
        src, dst = ROOT / name, PLUGIN / name
        if not dst.exists():
            problems.append(f"missing from plugin: {name}")
            continue
        for f in sorted(src.rglob("*")):
            if not f.is_file() or any(part in IGNORE_NAMES for part in f.parts):
                continue
            rel = f.relative_to(src)
            mirror = dst / rel
            if not mirror.exists():
                problems.append(f"only in canonical: {name}/{rel}")
            elif not filecmp.cmp(f, mirror, shallow=False):
                problems.append(f"differs: {name}/{rel}")
        for f in sorted(dst.rglob("*")):
            if any(part in IGNORE_NAMES for part in f.parts):
                continue
            if f.is_file() and not (src / f.relative_to(dst)).exists():
                problems.append(f"only in plugin: {name}/{f.relative_to(dst)}")
    for name in COMPANION_SCRIPTS:
        src, dst = ROOT / "scripts" / name, PLUGIN / "scripts" / name
        if not dst.is_file():
            problems.append(f"missing from plugin: scripts/{name}")
        elif not filecmp.cmp(src, dst, shallow=False):
            problems.append(f"differs: scripts/{name}")
    return problems


def command_problems() -> list[str]:
    problems: list[str] = []
    expected_names = {path.name for path in COMMANDS.glob("*.md")}
    actual_names = (
        {path.name for path in PLUGIN_COMMANDS.glob("*.md")}
        if PLUGIN_COMMANDS.exists() else set()
    )
    for name in sorted(expected_names):
        source = (COMMANDS / name).read_text().replace(ROOT_TOKEN, PLUGIN_ROOT_TOKEN)
        target = PLUGIN_COMMANDS / name
        if not target.is_file():
            problems.append(f"missing from plugin: commands/{name}")
        elif target.read_text() != source:
            problems.append(f"differs: commands/{name}")
    for name in sorted(actual_names - expected_names):
        problems.append(f"only in plugin: commands/{name}")
    return problems


def sync(names: list[str]) -> None:
    PLUGIN_SKILLS.mkdir(parents=True, exist_ok=True)
    wanted = set(names + shared_dirs())
    for existing in PLUGIN_SKILLS.iterdir():
        if existing.is_dir() and existing.name not in wanted:
            shutil.rmtree(existing)
    for name in sorted(wanted):
        dst = PLUGIN_SKILLS / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(CANONICAL / name, dst, ignore=IGNORE)
        print(f"  synced {name}")
    for name in COMPANION_DIRS:
        dst = PLUGIN / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ROOT / name, dst, ignore=IGNORE)
        print(f"  synced {name}/ (companion)")
    (PLUGIN / "scripts").mkdir(parents=True, exist_ok=True)
    for name in COMPANION_SCRIPTS:
        shutil.copy2(ROOT / "scripts" / name, PLUGIN / "scripts" / name)
        print(f"  synced scripts/{name} (companion)")
    if PLUGIN_COMMANDS.exists():
        shutil.rmtree(PLUGIN_COMMANDS)
    PLUGIN_COMMANDS.mkdir(parents=True)
    for source in sorted(COMMANDS.glob("*.md")):
        (PLUGIN_COMMANDS / source.name).write_text(
            source.read_text().replace(ROOT_TOKEN, PLUGIN_ROOT_TOKEN)
        )
    print("  synced commands/ (plugin root resolved)")

    if PLUGIN_CODEX_SKILLS.exists():
        shutil.rmtree(PLUGIN_CODEX_SKILLS)
    PLUGIN_CODEX_SKILLS.mkdir(parents=True)
    for name in sorted(set(names + shared_dirs())):
        shutil.copytree(
            CANONICAL / name,
            PLUGIN_CODEX_SKILLS / name,
            ignore=IGNORE,
        )
    write_workflow_skills(
        PLUGIN_CODEX_SKILLS,
        COMMANDS,
        root_value=CODEX_PLUGIN_ROOT_TOKEN,
    )
    print(
        f"  synced codex-skills/ ({len(names)} canonical + "
        f"{len(WORKFLOW_ORDER)} workflows)"
    )


def refresh_links(names: list[str]) -> None:
    for link_dir in (CURSOR_LINKS, CODEX_LINKS):
        link_dir.mkdir(parents=True, exist_ok=True)
        for existing in link_dir.iterdir():
            if existing.is_symlink() or existing.is_dir():
                existing.unlink() if existing.is_symlink() else shutil.rmtree(existing)
        for name in names:
            target = os.path.relpath(CANONICAL / name, link_dir)
            (link_dir / name).symlink_to(target, target_is_directory=True)
        print(f"  linked {len(names)} skills into {link_dir.relative_to(ROOT)}")
    write_workflow_skills(CODEX_LINKS, COMMANDS, WORKFLOW_ROOT_TOKEN)
    print(
        f"  generated {len(WORKFLOW_ORDER)} workflows into "
        f"{CODEX_LINKS.relative_to(ROOT)}"
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="report drift and exit non-zero instead of copying")
    args = ap.parse_args(argv)

    names = skill_names()
    if not names:
        sys.exit("no skills found under skills/")

    if args.check:
        problems = (
            diff_report(names)
            + codex_skill_problems(names)
            + companion_problems()
            + command_problems()
        )
        if problems:
            print(f"FAIL — plugin skills drifted ({len(problems)}):")
            for p in problems:
                print(f"  - {p}")
            print("Run: python3 scripts/sync_plugin_skills.py")
            return 1
        print(f"PASS — plugin mirrors {len(names)} canonical skills")
        return 0

    print(f"Syncing {len(names)} skills into the plugin:")
    sync(names)
    refresh_links(names)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
