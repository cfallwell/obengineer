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

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "skills"
PLUGIN = ROOT / "plugins" / "obengineer"
PLUGIN_SKILLS = PLUGIN / "skills"
LINK_DIRS = (ROOT / ".cursor" / "skills", ROOT / ".agents" / "skills")
IGNORE_NAMES = ["__pycache__", ".pytest_cache", ".DS_Store"]
IGNORE = shutil.ignore_patterns(*IGNORE_NAMES, "*.pyc")
# Skills link to ../../agents/ and ../../prompts/, so the bundle carries them too;
# an installed plugin cannot reach back into this repository.
COMPANION_DIRS = ("agents", "prompts")


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


def refresh_links(names: list[str]) -> None:
    for link_dir in LINK_DIRS:
        link_dir.mkdir(parents=True, exist_ok=True)
        for existing in link_dir.iterdir():
            if existing.is_symlink() or existing.is_dir():
                existing.unlink() if existing.is_symlink() else shutil.rmtree(existing)
        for name in names:
            target = os.path.relpath(CANONICAL / name, link_dir)
            (link_dir / name).symlink_to(target, target_is_directory=True)
        print(f"  linked {len(names)} skills into {link_dir.relative_to(ROOT)}")


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
        problems = diff_report(names) + companion_problems()
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
