#!/usr/bin/env python3
"""Install the obengineer skills and commands into an agent host.

    ./install.sh --cursor                 # this user, Cursor
    ./install.sh --claude --codex         # this user, two hosts
    ./install.sh --all                    # every supported host
    ./install.sh --all --project ../..    # scope to one repository instead
    ./install.sh --list                   # what is installed, and where
    ./install.sh --all --uninstall        # remove exactly what was installed

Skills are symlinked by default so an edit to the canonical file takes effect without
reinstalling. `--copy` writes copies instead, for a host that cannot follow links or a
bundle that will be distributed.

Commands are always written as files, because each one carries this bundle's resolved
path. They are what makes the runs invokable — `/obengineer-analyze` instead of pasting
a prompt into the chat.

Every install writes a manifest next to what it created, so `--uninstall` removes what
this script put there and nothing else.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SKILLS = ROOT / "skills"
COMMANDS = ROOT / "commands"
MANIFEST_NAME = ".obengineer-install.json"
ROOT_TOKEN = "{{OBENGINEER_ROOT}}"


@dataclass(frozen=True)
class Host:
    """Where one agent host looks for skills and for user-defined commands.

    These paths are host conventions, not standards, and they move between
    versions. `--list` prints the resolved paths and `--dest` overrides them, so a
    wrong guess here is a visible inconvenience rather than a silent no-op.
    """

    key: str
    label: str
    user_dir: str                    # relative to $HOME
    project_dir: str                 # relative to the project root
    skills_subdir: str = "skills"
    commands_subdir: str = "commands"
    project_skills_subdir: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def base(self, scope_root: Path, project: bool) -> Path:
        return scope_root / (self.project_dir if project else self.user_dir)

    def skills_dir(self, scope_root: Path, project: bool) -> Path:
        sub = (self.project_skills_subdir or self.skills_subdir) if project else self.skills_subdir
        return self.base(scope_root, project) / sub

    def commands_dir(self, scope_root: Path, project: bool) -> Path:
        return self.base(scope_root, project) / self.commands_subdir


HOSTS: dict[str, Host] = {
    "cursor": Host(
        key="cursor",
        label="Cursor",
        user_dir=".cursor",
        project_dir=".cursor",
        notes=("Commands appear as /obengineer-* in the chat.",),
    ),
    "claude": Host(
        key="claude",
        label="Claude Code",
        user_dir=".claude",
        project_dir=".claude",
        notes=(
            "For the full plugin bundle instead of skills alone, add the marketplace:",
            f"  claude plugin marketplace add {ROOT}",
            "  then install the obengineer plugin.",
        ),
    ),
    "codex": Host(
        key="codex",
        label="Codex",
        user_dir=".codex",
        project_dir=".agents",
        commands_subdir="prompts",
        notes=("Codex reads user-defined prompts from ~/.codex/prompts.",),
    ),
}


def skill_names() -> list[str]:
    names = sorted(p.parent.name for p in CANONICAL_SKILLS.glob("*/SKILL.md"))
    if not names:
        sys.exit(f"no skills found under {CANONICAL_SKILLS}")
    return names


def shared_reference_dirs() -> list[str]:
    """Skills link to ../references/, so a host that gets skills needs it too."""
    return sorted(
        p.name for p in CANONICAL_SKILLS.iterdir()
        if p.is_dir() and not (p / "SKILL.md").exists() and p.name != "__pycache__"
    )


def command_files() -> list[Path]:
    return sorted(COMMANDS.glob("*.md"))


class Planner:
    """Collects the actions an install would take, so --dry-run is exact."""

    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run
        self.created: list[str] = []
        self.log: list[str] = []

    def note(self, message: str) -> None:
        self.log.append(message)

    def link_or_copy(self, src: Path, dst: Path, copy: bool) -> None:
        self.note(f"{'copy' if copy else 'link'} {dst}")
        self.created.append(str(dst))
        if self.dry_run:
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.is_symlink() or dst.exists():
            shutil.rmtree(dst) if dst.is_dir() and not dst.is_symlink() else dst.unlink()
        if copy:
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            dst.symlink_to(os.path.relpath(src, dst.parent), target_is_directory=True)

    def write(self, dst: Path, text: str) -> None:
        self.note(f"write {dst}")
        self.created.append(str(dst))
        if self.dry_run:
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text)


def install_host(host: Host, scope_root: Path, project: bool, copy: bool,
                 planner: Planner) -> None:
    skills_dir = host.skills_dir(scope_root, project)
    commands_dir = host.commands_dir(scope_root, project)

    for name in skill_names() + shared_reference_dirs():
        planner.link_or_copy(CANONICAL_SKILLS / name, skills_dir / name, copy)

    for command in command_files():
        planner.write(commands_dir / command.name,
                      command.read_text().replace(ROOT_TOKEN, str(ROOT)))


def read_manifest(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def write_manifest(host: Host, scope_root: Path, project: bool, created: list[str],
                   dry_run: bool) -> None:
    if dry_run:
        return
    path = host.base(scope_root, project) / MANIFEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "source": str(ROOT),
        "scope": "project" if project else "user",
        "created": sorted(created),
    }, indent=2) + "\n")


def uninstall_host(host: Host, scope_root: Path, project: bool, dry_run: bool) -> int:
    base = host.base(scope_root, project)
    manifest_path = base / MANIFEST_NAME
    manifest = read_manifest(manifest_path)
    if not manifest:
        print(f"  {host.label}: nothing installed by obengineer at {base}")
        return 0

    removed = 0
    for entry in manifest.get("created", []):
        path = Path(entry)
        if not (path.is_symlink() or path.exists()):
            continue
        print(f"  remove {path}")
        removed += 1
        if dry_run:
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    if not dry_run:
        manifest_path.unlink(missing_ok=True)
        # Leave the host directory itself; other tools live there too.
        for parent in {Path(e).parent for e in manifest.get("created", [])}:
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
    print(f"  {host.label}: removed {removed} item(s)")
    return removed


def show_status(scope_root: Path, project: bool) -> None:
    print(f"obengineer at {ROOT}")
    print(f"scope: {'project ' + str(scope_root) if project else 'user ' + str(scope_root)}\n")
    for host in HOSTS.values():
        base = host.base(scope_root, project)
        manifest = read_manifest(base / MANIFEST_NAME)
        state = "installed" if manifest else ("host present, not installed"
                                             if base.is_dir() else "host not found")
        print(f"  {host.label:<12} {state}")
        print(f"    skills   {host.skills_dir(scope_root, project)}")
        print(f"    commands {host.commands_dir(scope_root, project)}")
        if manifest and manifest.get("source") != str(ROOT):
            print(f"    note: installed from a different source: {manifest['source']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="install.sh",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    for key, host in HOSTS.items():
        ap.add_argument(f"--{key}", action="store_true", help=f"install for {host.label}")
    ap.add_argument("--all", action="store_true", help="install for every supported host")
    ap.add_argument("--project", metavar="PATH",
                    help="scope to one repository instead of this user")
    ap.add_argument("--copy", action="store_true",
                    help="copy skills instead of symlinking them")
    ap.add_argument("--uninstall", action="store_true",
                    help="remove what a previous install created")
    ap.add_argument("--list", action="store_true", dest="list_only",
                    help="show what is installed, and where, then exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the actions without taking them")
    args = ap.parse_args(argv)

    project = args.project is not None
    scope_root = Path(args.project).resolve() if project else Path.home()

    if args.list_only:
        show_status(scope_root, project)
        return 0

    selected = [h for k, h in HOSTS.items() if args.all or getattr(args, k)]
    if not selected:
        ap.print_usage()
        print(f"\nchoose at least one host: --{' --'.join(HOSTS)} or --all")
        return 2

    if args.uninstall:
        print(f"Uninstalling from {scope_root}:")
        for host in selected:
            uninstall_host(host, scope_root, project, args.dry_run)
        return 0

    names = skill_names()
    print(f"Installing {len(names)} skills and {len(command_files())} commands "
          f"from {ROOT}")
    print(f"scope: {'project' if project else 'user'} {scope_root}\n")

    for host in selected:
        planner = Planner(args.dry_run)
        install_host(host, scope_root, project, args.copy, planner)
        print(f"  {host.label}")
        print(f"    skills   -> {host.skills_dir(scope_root, project)}")
        print(f"    commands -> {host.commands_dir(scope_root, project)}")
        if args.dry_run:
            for line in planner.log:
                print(f"      would {line}")
        write_manifest(host, scope_root, project, planner.created, args.dry_run)
        for note in host.notes:
            print(f"    {note}")

    print("\nInvoke a run with a command, in this order:")
    for command in command_files():
        print(f"  /{command.stem}")
    print("\nOr name a skill directly: $engagement-intake, $baggage-propagation, "
          "$cardinality-budget, ...")
    if args.dry_run:
        print("\n(dry run — nothing was written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
