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
path. They are what makes the guided flow invokable — `/ob-start` instead of pasting
a prompt into the chat.

Every install writes a manifest next to what it created, so `--uninstall` removes what
this script put there and nothing else.

A memory repository keeps its API keys in `.env`. The guided setup script creates or
updates that file without printing a credential:
`scripts/setup-splunk-access.sh`. The installer never writes a credential.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SKILLS = ROOT / "skills"
COMMANDS = ROOT / "commands"
MANIFEST_NAME = ".obengineer-install.json"
SCAFFOLD_MANIFEST = Path(".obengineer/scaffold-manifest.json")
SCAFFOLD_FILES = (
    (Path("templates/memory-repo/.env.template"), Path(".env.template")),
    (
        Path("templates/memory-repo/artifacts/README.md"),
        Path("artifacts/README.md"),
    ),
)
ROOT_TOKEN = "{{OBENGINEER_ROOT}}"
COMMAND_ORDER = (
    "ob-start", "ob-add-inputs", "ob-edit-inputs", "ob-analyze",
    "ob-review", "ob-implement", "ob-terraform", "ob-verify", "ob-render",
)
LEGACY_COMMAND_STEMS = {
    "ob-start": ("ob-intake", "ob-generate", "ob-wiki"),
    "ob-terraform": ("ob-build-terraform",),
}


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
        notes=("Type /ob to list /ob-start, /ob-add-inputs, /ob-edit-inputs, /ob-analyze, /ob-implement, /ob-terraform, /ob-verify, /ob-review, and /ob-render.",),
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
    order = {name: index for index, name in enumerate(COMMAND_ORDER)}
    return sorted(
        COMMANDS.glob("*.md"),
        key=lambda path: (order.get(path.stem, len(order)), path.name),
    )


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

    def remove(self, dst: Path) -> None:
        self.note(f"remove retired command {dst}")
        if self.dry_run:
            return
        if dst.is_symlink() or dst.exists():
            shutil.rmtree(dst) if dst.is_dir() and not dst.is_symlink() else dst.unlink()


def install_host(host: Host, scope_root: Path, project: bool, copy: bool,
                 planner: Planner) -> None:
    skills_dir = host.skills_dir(scope_root, project)
    commands_dir = host.commands_dir(scope_root, project)
    previous = read_manifest(host.base(scope_root, project) / MANIFEST_NAME)
    previously_created = set(previous.get("created", []))

    for replacement, retired_stems in LEGACY_COMMAND_STEMS.items():
        if not (COMMANDS / f"{replacement}.md").is_file():
            continue
        for retired in retired_stems:
            retired_path = commands_dir / f"{retired}.md"
            if str(retired_path) in previously_created:
                planner.remove(retired_path)

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


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, encoding="utf-8"
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def read_scaffold_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid project scaffold manifest {path}: {exc}") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or not isinstance(manifest.get("created"), dict)
    ):
        raise ValueError(f"invalid project scaffold manifest {path}")
    return manifest


def install_project_gitignore(
    scope_root: Path,
    dry_run: bool,
    created: dict,
) -> list[str]:
    source = ROOT / "templates/memory-repo/.gitignore"
    destination = scope_root / ".gitignore"
    required = [
        line
        for line in source.read_text().splitlines()
        if line and not line.startswith("#")
    ]
    if not destination.exists():
        action = f"create missing {destination}"
        if not dry_run:
            atomic_write(destination, source.read_text())
            created[".gitignore"] = {"sha256": file_digest(destination)}
        return [action]
    existing_text = destination.read_text()
    existing = set(existing_text.splitlines())
    missing = [line for line in required if line not in existing]
    if not missing:
        return [f"preserve existing {destination}; required ignores already present"]
    action = f"append missing safe ignores to {destination}: {', '.join(missing)}"
    if not dry_run:
        separator = "" if not existing_text or existing_text.endswith("\n") else "\n"
        atomic_write(
            destination,
            existing_text + separator + "\n".join(missing) + "\n",
        )
    return [action]


def install_project_scaffold(scope_root: Path, dry_run: bool) -> list[str]:
    """Create only missing project-root files and record only files we created."""
    manifest_path = scope_root / SCAFFOLD_MANIFEST
    manifest = read_scaffold_manifest(manifest_path)
    created = dict(manifest.get("created", {}))
    actions = install_project_gitignore(scope_root, dry_run, created)

    for source_rel, destination_rel in SCAFFOLD_FILES:
        source = ROOT / source_rel
        destination = scope_root / destination_rel
        if destination.exists() or destination.is_symlink():
            actions.append(f"preserve existing {destination}")
            continue
        actions.append(f"create missing {destination}")
        if dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
            )
        except FileExistsError:
            actions[-1] = f"preserve concurrently-created {destination}"
            continue
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(source.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        created[str(destination_rel)] = {"sha256": file_digest(destination)}

    if not dry_run and (created or manifest):
        atomic_write(
            manifest_path,
            json.dumps(
                {
                    "schema_version": 1,
                    "source": str(ROOT),
                    "created": created,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    return actions


def _owned_scaffold_path(scope_root: Path, relative: str) -> Path | None:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved_root = scope_root.resolve()
    resolved = (scope_root / candidate).resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        return None
    return resolved


def uninstall_project_scaffold(scope_root: Path, dry_run: bool) -> list[str]:
    """Remove only unchanged files proven to be installer-created; never directories."""
    manifest_path = scope_root / SCAFFOLD_MANIFEST
    manifest = read_scaffold_manifest(manifest_path)
    actions: list[str] = []
    if not manifest:
        return actions

    for relative, ownership in sorted(manifest["created"].items()):
        path = _owned_scaffold_path(scope_root, relative)
        expected = ownership.get("sha256") if isinstance(ownership, dict) else None
        if path is None or not isinstance(expected, str):
            actions.append(f"preserve unsafe or invalid scaffold entry {relative}")
            continue
        if not path.exists():
            continue
        if not path.is_file() or path.is_symlink() or file_digest(path) != expected:
            actions.append(f"preserve user-modified scaffold {path}")
            continue
        actions.append(f"remove unchanged installer scaffold {path}")
        if not dry_run:
            path.unlink()

    if not dry_run:
        manifest_path.unlink(missing_ok=True)
    return actions


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
    if project:
        try:
            scaffold = read_scaffold_manifest(scope_root / SCAFFOLD_MANIFEST)
            state = (
                f"{len(scaffold.get('created', {}))} installer-owned file(s)"
                if scaffold
                else "not installed"
            )
        except ValueError as exc:
            state = str(exc)
        print(f"  Project scaffold {state}")
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
        if project:
            selected_keys = {host.key for host in selected}
            remaining = [
                host for host in HOSTS.values()
                if host.key not in selected_keys
                and (host.base(scope_root, True) / MANIFEST_NAME).is_file()
            ]
            if remaining:
                print("  preserve project scaffold: other obengineer hosts remain")
            else:
                for action in uninstall_project_scaffold(scope_root, args.dry_run):
                    print(f"  {action}")
        return 0

    names = skill_names()
    print(f"Installing {len(names)} skills and {len(command_files())} commands "
          f"from {ROOT}")
    print(f"scope: {'project' if project else 'user'} {scope_root}\n")

    if project:
        print("  Project scaffold")
        for action in install_project_scaffold(scope_root, args.dry_run):
            print(f"    {'would ' if args.dry_run else ''}{action}")

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
    if project:
        print("\nOptional read-only Splunk access setup:")
        print(f"  {ROOT / 'scripts' / 'setup-splunk-access.sh'}")
        print("Run it from the memory repository. It writes local .env without "
              "printing credentials.")
    if args.dry_run:
        print("\n(dry run — nothing was written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
