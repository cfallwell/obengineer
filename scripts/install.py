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

Every install writes digested ownership records next to what it created. Reinstall
refuses unowned or modified collisions, and `--uninstall` removes only unchanged
installer-owned paths.

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


class InstallConflict(RuntimeError):
    """A target exists but cannot be proven to be installer-owned and unchanged."""


def _host_relative(base: Path, path: Path) -> str:
    return path.relative_to(base).as_posix()


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(path.rglob("*"), key=lambda candidate: candidate.as_posix()):
        relative = child.relative_to(path).as_posix().encode()
        if child.is_symlink():
            digest.update(b"L\0" + relative + b"\0" + os.readlink(child).encode())
        elif child.is_file():
            digest.update(b"F\0" + relative + b"\0" + child.read_bytes())
        elif child.is_dir():
            digest.update(b"D\0" + relative)
    return digest.hexdigest()


def path_ownership(path: Path) -> dict:
    if path.is_symlink():
        return {"kind": "symlink", "target": os.readlink(path)}
    if path.is_file():
        return {"kind": "file", "sha256": file_digest(path)}
    if path.is_dir():
        return {"kind": "directory", "sha256": _tree_digest(path)}
    raise ValueError(f"cannot record unsupported installed path {path}")


def ownership_matches(path: Path, ownership: object) -> bool:
    if not isinstance(ownership, dict):
        return False
    try:
        return path_ownership(path) == ownership
    except (OSError, ValueError):
        return False


def desired_host_targets(
    host: Host, scope_root: Path, project: bool
) -> list[Path]:
    skills_dir = host.skills_dir(scope_root, project)
    commands_dir = host.commands_dir(scope_root, project)
    return [
        *(skills_dir / name for name in skill_names() + shared_reference_dirs()),
        *(commands_dir / command.name for command in command_files()),
    ]


def host_owned_entries(manifest: dict) -> dict[str, dict] | None:
    if not manifest:
        return {}
    owned = manifest.get("owned")
    if manifest.get("schema_version") != 2 or not isinstance(owned, dict):
        return None
    if any(not isinstance(relative, str) for relative in owned):
        return None
    return owned


def host_install_conflicts(
    host: Host, scope_root: Path, project: bool
) -> list[str]:
    base = host.base(scope_root, project)
    manifest = read_manifest(base / MANIFEST_NAME)
    owned = host_owned_entries(manifest)
    conflicts: list[str] = []
    for path in desired_host_targets(host, scope_root, project):
        if not (path.exists() or path.is_symlink()):
            continue
        relative = _host_relative(base, path)
        if owned is None:
            conflicts.append(
                f"{path} is covered only by a legacy manifest without digests"
            )
        elif relative not in owned:
            conflicts.append(f"{path} already exists and is not installer-owned")
        elif not ownership_matches(path, owned[relative]):
            conflicts.append(f"{path} was modified after installation")
    return conflicts


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def install_host(
    host: Host,
    scope_root: Path,
    project: bool,
    copy: bool,
    planner: Planner,
) -> None:
    skills_dir = host.skills_dir(scope_root, project)
    commands_dir = host.commands_dir(scope_root, project)
    base = host.base(scope_root, project)
    manifest_path = base / MANIFEST_NAME
    previous = read_manifest(manifest_path)
    previously_owned = host_owned_entries(previous)
    conflicts = host_install_conflicts(host, scope_root, project)
    if conflicts:
        raise InstallConflict("; ".join(conflicts))
    assert previously_owned is not None

    retired_paths: list[Path] = []
    for replacement, retired_stems in LEGACY_COMMAND_STEMS.items():
        if not (COMMANDS / f"{replacement}.md").is_file():
            continue
        for retired in retired_stems:
            retired_path = commands_dir / f"{retired}.md"
            relative = _host_relative(base, retired_path)
            ownership = previously_owned.get(relative)
            if ownership and ownership_matches(retired_path, ownership):
                retired_paths.append(retired_path)
            elif ownership and (retired_path.exists() or retired_path.is_symlink()):
                planner.note(f"preserve modified retired command {retired_path}")

    targets = desired_host_targets(host, scope_root, project)
    if planner.dry_run:
        for retired_path in retired_paths:
            planner.remove(retired_path)
        for name in skill_names() + shared_reference_dirs():
            planner.link_or_copy(CANONICAL_SKILLS / name, skills_dir / name, copy)
        for command in command_files():
            planner.write(
                commands_dir / command.name,
                command.read_text().replace(ROOT_TOKEN, str(ROOT)),
            )
        return

    base.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".obengineer-install-", dir=base.parent))
    backups: list[tuple[Path, Path]] = []
    try:
        for index, path in enumerate([*targets, *retired_paths]):
            if path.exists() or path.is_symlink():
                backup = staging / str(index)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(backup))
                backups.append((path, backup))

        for retired_path in retired_paths:
            planner.remove(retired_path)
        for name in skill_names() + shared_reference_dirs():
            planner.link_or_copy(CANONICAL_SKILLS / name, skills_dir / name, copy)
        for command in command_files():
            planner.write(
                commands_dir / command.name,
                command.read_text().replace(ROOT_TOKEN, str(ROOT)),
            )

        owned = {
            _host_relative(base, path): path_ownership(path)
            for path in targets
        }
        atomic_write(
            manifest_path,
            json.dumps(
                {
                    "schema_version": 2,
                    "source": str(ROOT),
                    "scope": "project" if project else "user",
                    "owned": dict(sorted(owned.items())),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    except BaseException:
        for path in targets:
            _remove_path(path)
        for path, backup in reversed(backups):
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(backup), str(path))
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


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
    if not isinstance(manifest, dict) or manifest.get("schema_version") not in (1, 2):
        raise ValueError(f"invalid project scaffold manifest {path}")
    if not isinstance(manifest.get("created"), dict):
        raise ValueError(f"invalid project scaffold manifest {path}")
    if manifest.get("schema_version") == 2 and not isinstance(
        manifest.get("gitignore"), dict
    ):
        raise ValueError(f"invalid project scaffold manifest {path}")
    return manifest


def install_project_gitignore(
    scope_root: Path,
    dry_run: bool,
    manifest: dict,
) -> list[str]:
    source = ROOT / "templates/memory-repo/.gitignore"
    destination = scope_root / ".gitignore"
    required = [
        line
        for line in source.read_text().splitlines()
        if line and not line.startswith("#")
    ]
    gitignore = dict(manifest.get("gitignore", {}))
    tracked = list(gitignore.get("appended_lines", []))
    if not destination.exists():
        action = f"create missing {destination}"
        if not dry_run:
            atomic_write(destination, source.read_text())
            manifest["gitignore"] = {
                "created": True,
                "created_lines": source.read_text().splitlines(),
                "appended_lines": [],
            }
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
        manifest["gitignore"] = {
            "created": bool(gitignore.get("created", False)),
            "created_lines": list(gitignore.get("created_lines", [])),
            "appended_lines": [*tracked, *(
                line for line in missing
                if line not in tracked
                and line not in gitignore.get("created_lines", [])
            )],
        }
    return [action]


def install_project_scaffold(scope_root: Path, dry_run: bool) -> list[str]:
    """Create only missing project-root files and record only files we created."""
    manifest_path = scope_root / SCAFFOLD_MANIFEST
    manifest = read_scaffold_manifest(manifest_path)
    created = dict(manifest.get("created", {}))
    working_manifest = {
        "schema_version": 2,
        "source": str(ROOT),
        "created": created,
        "gitignore": dict(manifest.get("gitignore", {})),
    }
    if manifest.get("schema_version") == 1 and ".gitignore" in created:
        ownership = created.pop(".gitignore")
        destination = scope_root / ".gitignore"
        if (
            destination.is_file()
            and isinstance(ownership, dict)
            and ownership.get("sha256") == file_digest(destination)
        ):
            working_manifest["gitignore"] = {
                "created": True,
                "created_lines": destination.read_text().splitlines(),
                "appended_lines": [],
            }
    actions = install_project_gitignore(scope_root, dry_run, working_manifest)

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

    if not dry_run and (
        created or working_manifest["gitignore"] or manifest
    ):
        atomic_write(
            manifest_path,
            json.dumps(
                {
                    "schema_version": 2,
                    "source": str(ROOT),
                    "created": created,
                    "gitignore": working_manifest["gitignore"],
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


def _owned_host_path(base: Path, relative: str) -> Path | None:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or candidate == Path("."):
        return None
    return base / candidate


def uninstall_project_scaffold(scope_root: Path, dry_run: bool) -> list[str]:
    """Remove only unchanged files proven to be installer-created; never directories."""
    manifest_path = scope_root / SCAFFOLD_MANIFEST
    manifest = read_scaffold_manifest(manifest_path)
    actions: list[str] = []
    if not manifest:
        return actions

    gitignore_path = scope_root / ".gitignore"
    gitignore = manifest.get("gitignore", {})
    if manifest.get("schema_version") == 1 and ".gitignore" in manifest["created"]:
        ownership = manifest["created"].pop(".gitignore")
        if (
            gitignore_path.is_file()
            and isinstance(ownership, dict)
            and ownership.get("sha256") == file_digest(gitignore_path)
        ):
            gitignore = {
                "created": True,
                "created_lines": gitignore_path.read_text().splitlines(),
                "appended_lines": [],
            }
    tracked_lines = [
        *gitignore.get("created_lines", []),
        *gitignore.get("appended_lines", []),
    ] if isinstance(gitignore, dict) else []
    if gitignore_path.is_file() and tracked_lines:
        remaining = gitignore_path.read_text().splitlines()
        for line in tracked_lines:
            if line in remaining:
                remaining.remove(line)
        if remaining:
            actions.append(
                f"remove only installer-added ignores from {gitignore_path}"
            )
            if not dry_run:
                atomic_write(gitignore_path, "\n".join(remaining) + "\n")
        elif gitignore.get("created") is True:
            actions.append(f"remove installer-created {gitignore_path}")
            if not dry_run:
                gitignore_path.unlink()
        else:
            actions.append(
                f"remove only installer-added ignores from {gitignore_path}"
            )
            if not dry_run:
                atomic_write(gitignore_path, "")

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


def uninstall_host(host: Host, scope_root: Path, project: bool, dry_run: bool) -> int:
    base = host.base(scope_root, project)
    manifest_path = base / MANIFEST_NAME
    manifest = read_manifest(manifest_path)
    if not manifest:
        print(f"  {host.label}: nothing installed by obengineer at {base}")
        return 0
    owned = host_owned_entries(manifest)
    if owned is None:
        print(
            f"  {host.label}: REFUSE legacy or invalid manifest without digests; "
            "no host files were removed"
        )
        return -1

    removed = 0
    for relative, ownership in sorted(owned.items()):
        path = _owned_host_path(base, relative)
        if path is None:
            print(f"  preserve unsafe host manifest entry {relative}")
            continue
        if not (path.is_symlink() or path.exists()):
            continue
        if not ownership_matches(path, ownership):
            print(f"  preserve modified installer-owned path {path}")
            continue
        print(f"  remove {path}")
        removed += 1
        if dry_run:
            continue
        _remove_path(path)
    if not dry_run:
        manifest_path.unlink(missing_ok=True)
        # Leave the host directory itself; other tools live there too.
        parents = {
            (base / relative).parent
            for relative in owned
            if _owned_host_path(base, relative) is not None
        }
        for parent in sorted(parents, key=lambda item: len(item.parts), reverse=True):
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
        failed = False
        for host in selected:
            failed = uninstall_host(
                host, scope_root, project, args.dry_run
            ) < 0 or failed
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
        return 1 if failed else 0

    names = skill_names()
    print(f"Installing {len(names)} skills and {len(command_files())} commands "
          f"from {ROOT}")
    print(f"scope: {'project' if project else 'user'} {scope_root}\n")

    conflicts = {
        host.label: host_install_conflicts(host, scope_root, project)
        for host in selected
    }
    conflicts = {label: rows for label, rows in conflicts.items() if rows}
    if conflicts:
        print("REFUSE — installation would overwrite unowned or modified host files:")
        for label, rows in conflicts.items():
            for row in rows:
                print(f"  {label}: {row}")
        print("Resolve or back up the reported paths, then rerun the installer.")
        return 1

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
