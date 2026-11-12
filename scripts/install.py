#!/usr/bin/env python3
"""Install the obengineer skills and commands into an agent host.

    ./install.sh --cursor                 # this user, Cursor
    ./install.sh --claude --codex         # this user, two hosts
    ./install.sh --all                    # every supported host
    ./install.sh --all --project ../..    # scope to one repository instead
    ./install.sh --list                   # what is installed, and where
    ./install.sh --all --uninstall        # remove exactly what was installed

Cursor and Claude skills are symlinked by default so canonical edits take effect
without reinstalling. Codex skills are always materialized because Codex ignores skill
directory symlinks that resolve outside the target repository. `--copy` selects copies
for Cursor and Claude too.

Cursor and Claude commands are written as files because each one carries this bundle's
resolved path. Codex receives explicit-only workflow skills instead: `$ob-start` in the
CLI or `@ob-start` in ChatGPT Desktop.

Every install writes digested ownership records next to what it created. Reinstall
refuses unowned or modified collisions, and `--uninstall` removes only unchanged
installer-owned paths.

A project keeps read-only credentials only in ignored mode-0600 `obconfig.yaml`.
The installer owns the committed template and ignore rules, never the actual config.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    from scripts.codex_workflows import (
        WORKFLOW_ORDER,
        render_openai_yaml,
        render_skill,
    )
except ModuleNotFoundError:  # Direct execution from scripts/.
    from codex_workflows import (  # type: ignore[no-redef]
        WORKFLOW_ORDER,
        render_openai_yaml,
        render_skill,
    )

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SKILLS = ROOT / "skills"
COMMANDS = ROOT / "commands"
MANIFEST_NAME = ".obengineer-install.json"
CONFIG_COMPANION = Path("obengineer/obconfig.yaml.template")
SCAFFOLD_MANIFEST = Path(".obengineer/scaffold-manifest.json")
SCAFFOLD_FILES = (
    (Path("obconfig.yaml.template"), Path("obconfig.yaml.template")),
    (
        Path("templates/memory-repo/artifacts/README.md"),
        Path("artifacts/README.md"),
    ),
)
ROOT_TOKEN = "{{OBENGINEER_ROOT}}"
COMMAND_ORDER = WORKFLOW_ORDER
LEGACY_COMMAND_STEMS = {
    "ob-start": ("ob-intake", "ob-generate", "ob-wiki"),
    "ob-terraform": ("ob-build-terraform",),
}
LEGACY_COMMAND_DIGESTS = {
    "ob-add-inputs.md": {
        "41903bfcaba8877ee1cd1808bb096445be5af924e268ccf6834f9fed92da21fe",
        "7b291c4721eab69744d0abde091cb23d357071f7f87e469097b8fa94e610585c",
        "7b3b08989f741c398e8ed5a3d4a4134b487ba56b9380e1eff03e49ced5341360",
        "a967cb53e0992efde45dea0a7b849a2d10cd051fc2e1e21637bdeba58d10d3d7",
    },
    "ob-analyze.md": {
        "41ce324344fc0823616d650dc954465a779e0bfb16e954e9ff4b25e6edca672e",
        "5814b6a3ae7a880e1294a120648ef2f4c29be5b0f3c42eeca5a96512c531f615",
        "58176e1e5ab35f4a74d651378262e74a7c99e6fe2ef1b0f4c1b79b5428a1111a",
        "aa6526cd18ba76fe8be5a4b80ebeb5fe45e6b6f74de4b787296c038c47a91f00",
        "beb70d9a0d5e57090ae159e7cdf0985419d5fe8adfeefb535db63c9c9bff6ef4",
        "c0ef56511504a7ce6be6a1cf7733468f5710e521531a3fd060581fd86f98aabe",
        "f6c0231f5ccc97e1fd6337499f13e42e87283915055cc4f07344aaa2a7911555",
        "fa3036ffe90bbe9c99247d60f473803341e24b92560f0179a62f698fb2dc0e24",
    },
    "ob-build-terraform.md": {"4ff68bea8d3c47857fab2fe09414f5d649b98c9b2215fc674f8c09643a8d2b97"},
    "ob-edit-inputs.md": {
        "309d6e10260af3138e689a41991103318b1a7261f543f4ae2d0641ddc23afb93",
        "79fdee5312175a03dc6b33cb101cf2a8c2e5fa9bd2f0c01c79b51f04a8a09634",
        "9bbc42c8e6f356e51fa5c62df46f2ae18cd1f1ea5911d2a913380396c27fe545",
        "e90e4dacca1508d1955971a102b83f7b7e6a8f1b40f784973abb2383ddb105f1",
    },
    "ob-generate.md": {
        "43c414fa1232a4bb2bbf20835b13e7c40a8a4f968b14aea93db80c6806932e57",
        "b9aedb4cbf08bcfd28b47ead3a6e3305b2216c56dbe4f4cfd118f1b738b79d71",
    },
    "ob-implement.md": {
        "46d6eda31ded85b76ea12fdd07560ebfbe0fefda933709d74191582dd1be4b0c",
        "83d4479d66d138fc040cbbaf07a63a9923894859e21f115051cafda992dd79ca",
        "b79d149f6c4f31ba7ede20162cdee956b6197a8c3d078427793c80f73f54e7a7",
        "e04b7e8f80a71459d93f9fde76d0a14d10fd8534cb289dd534714c7416afa8b2",
    },
    "ob-intake.md": {
        "882ec30b0b1d87bd09902ee59b9f99455055f4a89f46209cf1829dfb3c083ea4",
        "9aca0d698be7c552937849f71452ae39eca53774d8fd57f5c291edd9aa0ca04c",
        "b377b59b842a61c1c14c452a49460178627ba648a359b51f0f74bad9d6920512",
    },
    "ob-render.md": {
        "29db4f6eca1942fe114a12e07c7d3124614ed9bfe10e4b8ce2f10ad067b26fe3",
        "a15f685ec2efeb373226b4dfb7d7635b35638bb00f7e04c43e2e3c3daff293c8",
    },
    "ob-review.md": {
        "b84f975270e292ffd677e8a40447d54dc5f104c40635222172f796e9d9252e8a",
        "c14cca38f954a8c53bec01b6c58e6278383f75e2326d9e7da11d0d96dd2e8770",
        "d522ac4cb635a0b32b1e5750a7d1bd444ea0291ea91e0a5c3ef9cd3663d10f29",
    },
    "ob-start.md": {
        "385314e5cb15838d7cea0ca4e75e961d2e515eee981b2fe8d91ee0462f9bb5a5",
        "5f667844a3d0063574277fcdde4ed870af4cb0d1ad908acf4dac876c1559c173",
        "993a6a0f5ab146d6c8a9978d7e384bc7bd46206bf2006a57b6a20f961eed5727",
        "a71a0ed85bd0f5a3af9a77eb17b75b5ecf5e6e21d3877ae7b8d181b9ad48fc7a",
    },
    "ob-terraform.md": {
        "159e7f36f358474fb5d2a214edabb24bd46e9c3574008ba9c358b5696c09c133",
        "3964502b267f728116636c69d350830254d81a6900f8317b292601bdb6c35162",
        "4cad06bfb9917d33d63567cafda7e7d7c485036a7fbd30659459df963762f4ef",
    },
    "ob-verify.md": {"309b6fdf99dbe0f31945652ac1854ccee0dbe4031e4c491773ad708111843ac9"},
    "ob-wiki.md": {
        "6c730509fb0145555a7319f2d53bfd303edd9ce6adcc66307191fdbfef002c37",
        "a0e33eb1a091ba523ca43d015ac299c5677def116c13b470e0b819e744d52886",
    },
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
    install_commands: bool = True
    install_workflows: bool = False
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
        user_dir=".agents",
        project_dir=".agents",
        commands_subdir="prompts",
        install_commands=False,
        install_workflows=True,
        notes=(
            "Codex CLI: invoke workflows as $ob-start, $ob-implement, ...",
            "ChatGPT Desktop: invoke workflows as @ob-start, @ob-implement, ...",
        ),
    ),
}

LEGACY_CODEX_HOST = Host(
    key="codex",
    label="Codex",
    user_dir=".codex",
    project_dir=".agents",
    commands_subdir="prompts",
)


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
        if copy:
            try:
                os.mkdir(dst, 0o755)
            except FileExistsError:
                raise IncompleteRollback(
                    f"installer target appeared before exclusive copy: {dst}"
                ) from None
            _mark_installer_mutation(dst)
            try:
                shutil.copytree(
                    src,
                    dst,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            finally:
                _mark_installer_mutation(dst)
        else:
            try:
                dst.symlink_to(
                    os.path.relpath(src, dst.parent),
                    target_is_directory=True,
                )
            except FileExistsError:
                raise IncompleteRollback(
                    f"installer target appeared before exclusive link: {dst}"
                ) from None
        _mark_installer_mutation(dst)

    def write(self, dst: Path, text: str) -> None:
        self.note(f"write {dst}")
        self.created.append(str(dst))
        if self.dry_run:
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                dst,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0),
                0o644,
            )
        except FileExistsError:
            raise IncompleteRollback(
                f"installer target appeared before exclusive write: {dst}"
            ) from None
        _mark_installer_mutation(dst)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            _mark_installer_mutation(dst)

    def remove(self, dst: Path) -> None:
        self.note(f"remove unchanged legacy path {dst}")
        if self.dry_run:
            return
        if dst.is_symlink() or dst.exists():
            shutil.rmtree(dst) if dst.is_dir() and not dst.is_symlink() else dst.unlink()
            _mark_installer_mutation(dst)


class InstallConflict(RuntimeError):
    """A target exists but cannot be proven to be installer-owned and unchanged."""


class IncompleteRollback(RuntimeError):
    """Rollback preserved a path whose identity no longer matched installer output."""


@dataclass(frozen=True)
class PathIdentity:
    kind: str
    device: int
    inode: int
    mode: int
    digest: str


@dataclass
class RollbackEntry:
    path: Path
    backup: Path | None
    before: PathIdentity | None
    written: PathIdentity | None = None
    touched: bool = False


@dataclass
class InstallTransaction:
    staging: Path
    entries: list[RollbackEntry]

    def mark(self, changed: Path) -> None:
        changed = changed.absolute()
        for entry in self.entries:
            candidate = entry.path.absolute()
            if candidate == changed or candidate in changed.parents:
                entry.written = path_identity(entry.path)
                entry.touched = True


_ACTIVE_INSTALL_TRANSACTIONS: list[InstallTransaction] = []


def _digest_directory(path: Path) -> str:
    digest = hashlib.sha256()
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        relative = candidate.relative_to(path).as_posix().encode()
        info = candidate.lstat()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update((info.st_mode & 0o177777).to_bytes(4, "big"))
        if candidate.is_symlink():
            payload = os.readlink(candidate).encode()
        elif candidate.is_file():
            payload = hashlib.sha256(candidate.read_bytes()).digest()
        elif candidate.is_dir():
            payload = b"directory"
        else:
            payload = b"special"
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def path_identity(path: Path) -> PathIdentity | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if path.is_symlink():
        kind = "symlink"
        digest = hashlib.sha256(os.readlink(path).encode()).hexdigest()
    elif path.is_file():
        kind = "file"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    elif path.is_dir():
        kind = "directory"
        digest = _digest_directory(path)
    else:
        kind = "special"
        digest = hashlib.sha256(b"special").hexdigest()
    return PathIdentity(
        kind,
        info.st_dev,
        info.st_ino,
        info.st_mode & 0o177777,
        digest,
    )


def _mark_installer_mutation(path: Path) -> None:
    for transaction in _ACTIVE_INSTALL_TRANSACTIONS:
        transaction.mark(path)


def _remove_owned_path(path: Path, expected: PathIdentity) -> bool:
    """Quarantine and remove only the exact installer-written pathname."""
    parent = path.parent
    quarantine = parent / (
        f".{path.name}.obengineer-rollback-{os.getpid()}-"
        f"{time.time_ns()}"
    )
    try:
        os.rename(path, quarantine)
    except FileNotFoundError:
        return False
    if path_identity(quarantine) != expected:
        try:
            os.rename(quarantine, path)
        except (FileExistsError, OSError):
            pass
        return False
    _remove_path(quarantine)
    return True


def _host_relative(base: Path, path: Path) -> str:
    return path.relative_to(base).as_posix()


def _symlinked_or_escaping_parent(root: Path, path: Path) -> Path | None:
    """Return the first unsafe parent between root and path, without following it."""
    root = root.absolute()
    path = path.absolute()
    try:
        path.relative_to(root)
    except ValueError:
        return path
    current = path.parent
    while current != root:
        if current.is_symlink():
            return current
        try:
            current.resolve(strict=False).relative_to(root.resolve(strict=False))
        except ValueError:
            return current
        if current == current.parent:
            return current
        current = current.parent
    if root.is_symlink():
        return root
    return None


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(path.rglob("*"), key=lambda candidate: candidate.as_posix()):
        relative_path = child.relative_to(path)
        if "__pycache__" in relative_path.parts or child.name.endswith(".pyc"):
            continue
        relative = relative_path.as_posix().encode()
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


def installs_config_companion(host: Host, copy: bool) -> bool:
    return host.install_workflows or copy


def desired_host_targets(
    host: Host,
    scope_root: Path,
    project: bool,
    copy: bool,
) -> list[Path]:
    skills_dir = host.skills_dir(scope_root, project)
    commands_dir = host.commands_dir(scope_root, project)
    return [
        *(skills_dir / name for name in skill_names() + shared_reference_dirs()),
        *(
            (commands_dir / command.name for command in command_files())
            if host.install_commands
            else ()
        ),
        *(
            (skills_dir / name for name in WORKFLOW_ORDER)
            if host.install_workflows
            else ()
        ),
        *(
            [host.base(scope_root, project) / CONFIG_COMPANION]
            if installs_config_companion(host, copy)
            else []
        ),
    ]


def legacy_host_targets(
    host: Host, scope_root: Path, project: bool
) -> list[Path]:
    skills_dir = host.skills_dir(scope_root, project)
    commands_dir = host.commands_dir(scope_root, project)
    retired = {
        commands_dir / f"{stem}.md"
        for stems in LEGACY_COMMAND_STEMS.values()
        for stem in stems
    }
    return [
        *(skills_dir / name for name in skill_names() + shared_reference_dirs()),
        *(commands_dir / command.name for command in command_files()),
        *sorted(retired),
    ]


def legacy_command_digests(name: str) -> set[str]:
    digests = set(LEGACY_COMMAND_DIGESTS.get(name, set()))
    current = COMMANDS / name
    if current.is_file():
        digests.add(hashlib.sha256(current.read_bytes()).hexdigest())
    return digests


def host_owned_entries(manifest: dict) -> dict[str, dict] | None:
    if not manifest:
        return {}
    owned = manifest.get("owned")
    if manifest.get("schema_version") != 2 or not isinstance(owned, dict):
        return None
    if any(not isinstance(relative, str) for relative in owned):
        return None
    return owned


def legacy_host_owned_entries(
    manifest: dict,
    host: Host,
    scope_root: Path,
    project: bool,
) -> dict[str, dict] | None:
    """Recover ownership only for source-bound paths from the pre-digest manifest."""
    source_text = manifest.get("source")
    created = manifest.get("created")
    expected_scope = "project" if project else "user"
    if (
        manifest.get("schema_version") is not None
        or not isinstance(source_text, str)
        or not Path(source_text).is_absolute()
        or manifest.get("scope") != expected_scope
        or not isinstance(created, list)
        or not all(isinstance(item, str) and Path(item).is_absolute() for item in created)
    ):
        return None

    source = Path(source_text)
    base = host.base(scope_root, project)
    legacy_base = Path(host.project_dir if project else host.user_dir)
    created_paths = [Path(item) for item in created]
    recovered: dict[str, dict] = {}
    for path in legacy_host_targets(host, scope_root, project):
        if not (path.exists() or path.is_symlink()):
            continue
        relative = Path(_host_relative(base, path))
        suffix = (*legacy_base.parts, *relative.parts)
        listed = [
            item for item in created_paths
            if len(item.parts) >= len(suffix) and item.parts[-len(suffix):] == suffix
        ]
        if len(listed) != 1:
            continue

        if relative.parts[0] == host.skills_subdir:
            if not path.is_symlink():
                continue
            expected_target = os.path.relpath(
                source / "skills" / Path(*relative.parts[1:]),
                listed[0].parent,
            )
            if os.readlink(path) != expected_target:
                continue
        elif relative.parts[0] == host.commands_subdir:
            if not path.is_file() or path.is_symlink():
                continue
            try:
                text = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            normalized = text.replace(source_text, ROOT_TOKEN)
            digest = hashlib.sha256(normalized.encode()).hexdigest()
            if digest not in legacy_command_digests(path.name):
                continue
        else:
            continue
        recovered[relative.as_posix()] = path_ownership(path)
    return recovered


def host_owned_entries_for_install(
    manifest: dict,
    host: Host,
    scope_root: Path,
    project: bool,
) -> dict[str, dict] | None:
    owned = host_owned_entries(manifest)
    if owned is not None:
        return owned
    return legacy_host_owned_entries(manifest, host, scope_root, project)


def unsafe_host_manifest_reason(scope_root: Path, manifest_path: Path) -> str | None:
    if manifest_path.is_symlink():
        return f"{manifest_path} is a symlink"
    unsafe_parent = _symlinked_or_escaping_parent(scope_root, manifest_path)
    if unsafe_parent is not None:
        return (
            f"{manifest_path} has symlinked or escaping parent "
            f"{unsafe_parent}"
        )
    return None


def host_install_conflicts(
    host: Host,
    scope_root: Path,
    project: bool,
    copy: bool,
) -> list[str]:
    base = host.base(scope_root, project)
    manifest_path = base / MANIFEST_NAME
    unsafe_manifest = unsafe_host_manifest_reason(scope_root, manifest_path)
    if unsafe_manifest is not None:
        return [f"unsafe host manifest: {unsafe_manifest}"]
    manifest = read_manifest(manifest_path)
    owned = host_owned_entries_for_install(
        manifest, host, scope_root, project
    )
    conflicts: list[str] = []
    for path in desired_host_targets(host, scope_root, project, copy):
        unsafe_parent = _symlinked_or_escaping_parent(scope_root, path)
        if unsafe_parent is not None:
            conflicts.append(
                f"{path} has symlinked or escaping parent {unsafe_parent}"
            )
            continue
        if not (path.exists() or path.is_symlink()):
            continue
        relative = _host_relative(base, path)
        if owned is None:
            conflicts.append(
                f"{path} is covered only by an unverifiable legacy manifest"
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


def _owned_host_path(base: Path, relative: str) -> Path | None:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or candidate == Path("."):
        return None
    path = base / candidate
    if _symlinked_or_escaping_parent(base.parent, path) is not None:
        return None
    return path


@dataclass
class StaleCleanup:
    """Prior-owned paths no longer emitted by the current install."""

    paths: list[Path] = field(default_factory=list)
    preserved_owned: dict[str, dict] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _stale_owned_cleanup(
    base: Path,
    previously_owned: dict[str, dict],
    desired: list[Path],
) -> StaleCleanup:
    desired_relatives = {
        _host_relative(base, path)
        for path in desired
    }
    cleanup = StaleCleanup()
    for relative, ownership in sorted(previously_owned.items()):
        if relative in desired_relatives:
            continue
        path = _owned_host_path(base, relative)
        if path is None:
            cleanup.notes.append(
                f"preserve unsafe stale host manifest entry {relative}"
            )
            cleanup.preserved_owned[relative] = ownership
            continue
        if not (path.exists() or path.is_symlink()):
            continue
        if ownership_matches(path, ownership):
            cleanup.paths.append(path)
        else:
            cleanup.notes.append(f"preserve modified stale installer path {path}")
            cleanup.preserved_owned[relative] = ownership
    return cleanup


@dataclass
class LegacyCleanup:
    """Verified legacy paths that can participate in the install transaction."""

    paths: list[Path] = field(default_factory=list)
    manifest: Path | None = None
    manifest_update: tuple[Path, str] | None = None
    notes: list[str] = field(default_factory=list)


def _verified_legacy_cleanup(
    legacy_host: Host,
    scope_root: Path,
    project: bool,
) -> LegacyCleanup:
    base = legacy_host.base(scope_root, project)
    manifest_path = base / MANIFEST_NAME
    unsafe_manifest = unsafe_host_manifest_reason(scope_root, manifest_path)
    if unsafe_manifest is not None:
        return LegacyCleanup(
            notes=[
                f"preserve and ignore unsafe legacy Codex manifest: "
                f"{unsafe_manifest}"
            ]
        )
    manifest = read_manifest(manifest_path)
    if not manifest:
        return LegacyCleanup()
    owned = host_owned_entries_for_install(
        manifest,
        legacy_host,
        scope_root,
        project,
    )
    if owned is None:
        return LegacyCleanup(
            notes=[
                f"preserve unverifiable legacy Codex installation at {base}"
            ]
        )

    cleanup = LegacyCleanup()
    retained_owned: dict[str, dict] = {}
    for relative, ownership in sorted(owned.items()):
        path = _owned_host_path(base, relative)
        if path is None:
            cleanup.notes.append(
                f"preserve unsafe legacy Codex manifest entry {relative}"
            )
            retained_owned[relative] = ownership
            continue
        if not (path.exists() or path.is_symlink()):
            continue
        if ownership_matches(path, ownership):
            cleanup.paths.append(path)
        else:
            cleanup.notes.append(f"preserve modified legacy Codex path {path}")
            retained_owned[relative] = ownership

    manifest_is_safe = (
        manifest_path.is_file()
        and not manifest_path.is_symlink()
        and _symlinked_or_escaping_parent(scope_root, manifest_path) is None
    )
    if manifest_is_safe and not retained_owned:
        cleanup.manifest = manifest_path
    elif manifest_is_safe:
        cleanup.notes.append(
            f"retain legacy Codex manifest for preserved owned paths at {base}"
        )
        if host_owned_entries(manifest) is not None:
            retained_manifest = dict(manifest)
            retained_manifest["owned"] = dict(sorted(retained_owned.items()))
            cleanup.manifest_update = (
                manifest_path,
                json.dumps(retained_manifest, indent=2, sort_keys=True) + "\n",
            )
    else:
        cleanup.notes.append(
            f"preserve unsafe legacy Codex manifest {manifest_path}"
        )
    return cleanup


def _write_workflow(
    planner: Planner,
    command: Path,
    destination: Path,
) -> None:
    planner.write(destination / "SKILL.md", render_skill(command, str(ROOT)))
    planner.write(
        destination / "agents/openai.yaml",
        render_openai_yaml(command.stem),
    )


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
    conflicts = host_install_conflicts(host, scope_root, project, copy)
    if conflicts:
        raise InstallConflict("; ".join(conflicts))
    previous = read_manifest(manifest_path)
    previously_owned = host_owned_entries_for_install(
        previous, host, scope_root, project
    )
    assert previously_owned is not None
    targets = desired_host_targets(host, scope_root, project, copy)
    stale_cleanup = _stale_owned_cleanup(base, previously_owned, targets)
    for note in stale_cleanup.notes:
        planner.note(note)

    external_cleanup = (
        _verified_legacy_cleanup(
            LEGACY_CODEX_HOST,
            scope_root,
            False,
        )
        if host.key == "codex" and not project
        else LegacyCleanup()
    )
    for note in external_cleanup.notes:
        planner.note(note)

    if planner.dry_run:
        for stale_path in [*stale_cleanup.paths, *external_cleanup.paths]:
            planner.remove(stale_path)
        if external_cleanup.manifest is not None:
            planner.remove(external_cleanup.manifest)
        if external_cleanup.manifest_update is not None:
            planner.note(
                f"rewrite retained legacy manifest "
                f"{external_cleanup.manifest_update[0]}"
            )
        for name in skill_names() + shared_reference_dirs():
            planner.link_or_copy(
                CANONICAL_SKILLS / name,
                skills_dir / name,
                copy or host.install_workflows,
            )
        if installs_config_companion(host, copy):
            planner.write(
                base / CONFIG_COMPANION,
                (ROOT / "obconfig.yaml.template").read_text(),
            )
        if host.install_commands:
            for command in command_files():
                planner.write(
                    commands_dir / command.name,
                    command.read_text().replace(ROOT_TOKEN, str(ROOT)),
                )
        if host.install_workflows:
            for command in command_files():
                _write_workflow(planner, command, skills_dir / command.stem)
        return

    base.parent.mkdir(parents=True, exist_ok=True)
    transaction: InstallTransaction | None = None
    rollback_incomplete = False
    try:
        transaction_paths = [
            manifest_path,
            *targets,
            *stale_cleanup.paths,
            *external_cleanup.paths,
            *(
                [external_cleanup.manifest]
                if external_cleanup.manifest is not None
                else []
            ),
            *(
                [external_cleanup.manifest_update[0]]
                if external_cleanup.manifest_update is not None
                else []
            ),
        ]
        transaction = _snapshot_install_paths(transaction_paths)
        _ACTIVE_INSTALL_TRANSACTIONS.append(transaction)
        _vacate_install_paths(transaction)

        for stale_path in [*stale_cleanup.paths, *external_cleanup.paths]:
            planner.remove(stale_path)
        for name in skill_names() + shared_reference_dirs():
            planner.link_or_copy(
                CANONICAL_SKILLS / name,
                skills_dir / name,
                copy or host.install_workflows,
            )
        if installs_config_companion(host, copy):
            planner.write(
                base / CONFIG_COMPANION,
                (ROOT / "obconfig.yaml.template").read_text(),
            )
        if host.install_commands:
            for command in command_files():
                planner.write(
                    commands_dir / command.name,
                    command.read_text().replace(ROOT_TOKEN, str(ROOT)),
                )
        if host.install_workflows:
            for command in command_files():
                _write_workflow(planner, command, skills_dir / command.stem)

        if external_cleanup.manifest_update is not None:
            atomic_write(
                *external_cleanup.manifest_update, expect_absent=True
            )
        owned = {
            _host_relative(base, path): path_ownership(path)
            for path in targets
        }
        owned.update(stale_cleanup.preserved_owned)
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
            expect_absent=True,
        )
    except BaseException as original_error:
        if transaction is not None:
            preserved = _rollback_install_paths(transaction)
            rollback_incomplete = bool(preserved) or isinstance(
                original_error, IncompleteRollback
            )
            if preserved:
                joined = ", ".join(str(path) for path in preserved)
                raise IncompleteRollback(
                    "installer rollback was incomplete; concurrent replacements "
                    f"were preserved at {joined}; backups retained at "
                    f"{transaction.staging}"
                ) from original_error
        raise
    finally:
        if transaction is not None:
            if (
                _ACTIVE_INSTALL_TRANSACTIONS
                and _ACTIVE_INSTALL_TRANSACTIONS[-1] is transaction
            ):
                _ACTIVE_INSTALL_TRANSACTIONS.pop()
            elif transaction in _ACTIVE_INSTALL_TRANSACTIONS:
                _ACTIVE_INSTALL_TRANSACTIONS.remove(transaction)
            if not rollback_incomplete:
                shutil.rmtree(transaction.staging, ignore_errors=True)


def _outer_install_paths(
    selected: list[Host],
    scope_root: Path,
    project: bool,
    copy: bool,
) -> list[Path]:
    paths: list[Path] = []
    if project:
        for directory in (scope_root / ".obengineer", scope_root / "artifacts"):
            if not directory.exists() and not directory.is_symlink():
                paths.append(directory)
        paths.extend(
            [
                scope_root / ".gitignore",
                scope_root / SCAFFOLD_MANIFEST,
                *(scope_root / destination for _, destination in SCAFFOLD_FILES),
                scope_root / ".env.template",
            ]
        )
    for host in selected:
        base = host.base(scope_root, project)
        if not base.exists() and not base.is_symlink():
            paths.append(base)
        paths.append(base / MANIFEST_NAME)
        targets = desired_host_targets(host, scope_root, project, copy)
        for target in targets:
            current = target.parent
            while current != base and current != current.parent:
                if not current.exists() and not current.is_symlink():
                    paths.append(current)
                current = current.parent
        paths.extend(targets)
        previous = read_manifest(base / MANIFEST_NAME)
        owned = host_owned_entries_for_install(previous, host, scope_root, project)
        if owned:
            for relative in owned:
                candidate = base / Path(relative)
                try:
                    candidate.relative_to(base)
                except ValueError:
                    continue
                paths.append(candidate)
    return list(dict.fromkeys(paths))


def _snapshot_install_paths(paths: list[Path]) -> InstallTransaction:
    staging = Path(tempfile.mkdtemp(prefix="obengineer-outer-install-"))
    entries: list[RollbackEntry] = []
    absent_ancestors: list[Path] = []
    ordered = sorted(
        dict.fromkeys(path.absolute() for path in paths),
        key=lambda path: (len(path.parts), path.as_posix()),
    )
    for index, path in enumerate(ordered):
        if any(ancestor == path or ancestor in path.parents for ancestor in absent_ancestors):
            continue
        before = path_identity(path)
        if before is None:
            entries.append(RollbackEntry(path, None, None))
            absent_ancestors.append(path)
            continue
        backup = staging / str(index)
        if path.is_symlink():
            backup.symlink_to(os.readlink(path))
        elif path.is_dir():
            shutil.copytree(path, backup, symlinks=True)
        else:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup, follow_symlinks=False)
        entries.append(RollbackEntry(path, backup, before))
    return InstallTransaction(staging, entries)


def _vacate_install_paths(transaction: InstallTransaction) -> None:
    """Move snapshotted targets aside without deleting a raced-in replacement."""
    for index, entry in enumerate(transaction.entries):
        if entry.before is None:
            entry.written = None
            entry.touched = True
            continue
        moved = transaction.staging / f"moved-{index}"
        try:
            os.rename(entry.path, moved)
        except FileNotFoundError:
            raise IncompleteRollback(
                f"installer target changed before backup move: {entry.path}; "
                f"backups retained at {transaction.staging}"
            ) from None
        moved_identity = path_identity(moved)
        if moved_identity != entry.before:
            try:
                os.rename(moved, entry.path)
            except (FileExistsError, OSError):
                pass
            raise IncompleteRollback(
                f"installer target changed during backup move: {entry.path}; "
                f"backups retained at {transaction.staging}"
            )
        if entry.backup is not None:
            _remove_path(entry.backup)
        entry.backup = moved
        entry.written = None
        entry.touched = True
        _mark_installer_mutation(entry.path)


def _rollback_install_paths(transaction: InstallTransaction) -> list[Path]:
    preserved: list[Path] = []
    for entry in reversed(transaction.entries):
        if not entry.touched:
            continue
        path = entry.path
        backup = entry.backup
        if path_identity(path) != entry.written:
            preserved.append(path)
            continue
        if entry.written is not None and not _remove_owned_path(
            path, entry.written
        ):
            preserved.append(path)
            continue
        if backup is None:
            for active in _ACTIVE_INSTALL_TRANSACTIONS:
                if active is not transaction:
                    active.mark(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if backup.is_symlink():
            path.symlink_to(os.readlink(backup))
        elif backup.is_dir():
            shutil.copytree(backup, path, symlinks=True)
        else:
            shutil.copy2(backup, path, follow_symlinks=False)
        for active in _ACTIVE_INSTALL_TRANSACTIONS:
            if active is not transaction:
                active.mark(path)
    return preserved


def read_manifest(path: Path) -> dict:
    if path.is_symlink():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, text: str, *, expect_absent: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, encoding="utf-8"
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    if expect_absent:
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            raise IncompleteRollback(
                f"installer target appeared before exclusive write: {path}"
            ) from None
        finally:
            temporary.unlink(missing_ok=True)
    else:
        os.replace(temporary, path)
    _mark_installer_mutation(path)


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


def project_scaffold_conflicts(scope_root: Path) -> list[str]:
    targets = [
        scope_root / ".gitignore",
        scope_root / SCAFFOLD_MANIFEST,
        *(scope_root / destination for _, destination in SCAFFOLD_FILES),
    ]
    conflicts: list[str] = []
    for target in targets:
        if target.is_symlink():
            conflicts.append(f"{target} is a symlink")
            continue
        unsafe_parent = _symlinked_or_escaping_parent(scope_root, target)
        if unsafe_parent is not None:
            conflicts.append(
                f"{target} has symlinked or escaping parent {unsafe_parent}"
            )
    return conflicts


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
    conflicts = project_scaffold_conflicts(scope_root)
    if conflicts:
        raise InstallConflict("; ".join(conflicts))
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

    legacy_template = scope_root / ".env.template"
    legacy_owned = created.get(".env.template")
    if isinstance(legacy_owned, dict):
        expected = legacy_owned.get("sha256")
        if (
            legacy_template.is_file()
            and not legacy_template.is_symlink()
            and isinstance(expected, str)
            and file_digest(legacy_template) == expected
        ):
            actions.append(f"remove unchanged installer-owned {legacy_template}")
            if not dry_run:
                legacy_template.unlink()
                _mark_installer_mutation(legacy_template)
                created.pop(".env.template", None)
        else:
            actions.append(f"preserve modified legacy template {legacy_template}")
            if not dry_run:
                created.pop(".env.template", None)

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
        created_info = os.fstat(descriptor)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(source.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                current_info = destination.lstat()
            except FileNotFoundError:
                current_info = None
            if current_info is not None and (
                current_info.st_dev,
                current_info.st_ino,
            ) == (created_info.st_dev, created_info.st_ino):
                destination.unlink(missing_ok=True)
                _mark_installer_mutation(destination)
            raise
        _mark_installer_mutation(destination)
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


def uninstall_project_scaffold(scope_root: Path, dry_run: bool) -> list[str]:
    """Remove only unchanged files proven to be installer-created; never directories."""
    conflicts = project_scaffold_conflicts(scope_root)
    if conflicts:
        return [
            "preserve project scaffold because containment checks failed: "
            + "; ".join(conflicts)
        ]
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
        protected_lines = set()
        if (scope_root / "obconfig.yaml").exists() or (
            scope_root / "obconfig.yaml"
        ).is_symlink():
            protected_lines.add("/obconfig.yaml")
        local_state = scope_root / ".obengineer"
        has_user_local_state = (
            local_state.is_symlink()
            or (
                local_state.is_dir()
                and any(
                    child.name != SCAFFOLD_MANIFEST.name
                    for child in local_state.iterdir()
                )
            )
        )
        if has_user_local_state or "/obconfig.yaml" in protected_lines:
            protected_lines.add("/.obengineer/")
        for line in tracked_lines:
            if line in remaining and line not in protected_lines:
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
    unsafe_manifest = unsafe_host_manifest_reason(scope_root, manifest_path)
    if unsafe_manifest is not None:
        print(
            f"  {host.label}: REFUSE unsafe host manifest: {unsafe_manifest}; "
            "no host files or manifest were removed"
        )
        return -1
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
        manifest_path = base / MANIFEST_NAME
        unsafe_manifest = unsafe_host_manifest_reason(scope_root, manifest_path)
        if unsafe_manifest is not None:
            manifest = {}
            state = f"unsafe manifest ({unsafe_manifest})"
        else:
            manifest = read_manifest(manifest_path)
            state = "installed" if manifest else (
                "host present, not installed"
                if base.is_dir()
                else "host not found"
            )
        print(f"  {host.label:<12} {state}")
        print(f"    skills   {host.skills_dir(scope_root, project)}")
        if host.install_commands:
            print(f"    commands {host.commands_dir(scope_root, project)}")
        else:
            print(f"    workflows {host.skills_dir(scope_root, project) / 'ob-*'}")
        companion = host.base(scope_root, project) / CONFIG_COMPANION
        if unsafe_manifest is None and companion.exists():
            print(
                f"    companion {companion}"
            )
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
                    help=(
                        "copy Cursor/Claude skills and config template "
                        "(Codex skills are always copied)"
                    ))
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
            if failed:
                print("  preserve project scaffold: host uninstall was refused")
            elif remaining:
                print("  preserve project scaffold: other obengineer hosts remain")
            else:
                for action in uninstall_project_scaffold(scope_root, args.dry_run):
                    print(f"  {action}")
        return 1 if failed else 0

    names = skill_names()
    print(
        f"Installing {len(names)} canonical skills and "
        f"{len(command_files())} workflows from {ROOT}"
    )
    print(f"scope: {'project' if project else 'user'} {scope_root}\n")

    conflicts = {
        host.label: host_install_conflicts(
            host,
            scope_root,
            project,
            args.copy,
        )
        for host in selected
    }
    if project:
        scaffold_conflicts = project_scaffold_conflicts(scope_root)
        if scaffold_conflicts:
            conflicts["Project scaffold"] = scaffold_conflicts
    conflicts = {label: rows for label, rows in conflicts.items() if rows}
    if conflicts:
        print("REFUSE — installation would overwrite unowned or modified host files:")
        for label, rows in conflicts.items():
            for row in rows:
                print(f"  {label}: {row}")
        print("Resolve or back up the reported paths, then rerun the installer.")
        return 1

    outer_transaction: InstallTransaction | None = None
    rollback_incomplete = False
    if not args.dry_run:
        outer_transaction = _snapshot_install_paths(
            _outer_install_paths(selected, scope_root, project, args.copy)
        )
        _ACTIVE_INSTALL_TRANSACTIONS.append(outer_transaction)
    try:
        if project:
            print("  Project scaffold")
            for action in install_project_scaffold(scope_root, args.dry_run):
                print(f"    {'would ' if args.dry_run else ''}{action}")

        for host in selected:
            planner = Planner(args.dry_run)
            install_host(host, scope_root, project, args.copy, planner)
            print(f"  {host.label}")
            print(f"    skills   -> {host.skills_dir(scope_root, project)}")
            if host.install_commands:
                print(f"    commands -> {host.commands_dir(scope_root, project)}")
            else:
                print(f"    workflows -> {host.skills_dir(scope_root, project) / 'ob-*'}")
            if installs_config_companion(host, args.copy):
                print(
                    f"    companion -> "
                    f"{host.base(scope_root, project) / CONFIG_COMPANION}"
                )
            if args.dry_run:
                for line in planner.log:
                    print(f"      would {line}")
            for note in host.notes:
                print(f"    {note}")
    except BaseException as original_error:
        if outer_transaction is not None:
            preserved = _rollback_install_paths(outer_transaction)
            rollback_incomplete = bool(preserved) or isinstance(
                original_error, IncompleteRollback
            )
            if preserved:
                joined = ", ".join(str(path) for path in preserved)
                raise IncompleteRollback(
                    "outer installer rollback was incomplete; concurrent "
                    f"replacements were preserved at {joined}; backups retained "
                    f"at {outer_transaction.staging}"
                ) from original_error
        raise
    finally:
        if outer_transaction is not None:
            if (
                _ACTIVE_INSTALL_TRANSACTIONS
                and _ACTIVE_INSTALL_TRANSACTIONS[-1] is outer_transaction
            ):
                _ACTIVE_INSTALL_TRANSACTIONS.pop()
            elif outer_transaction in _ACTIVE_INSTALL_TRANSACTIONS:
                _ACTIVE_INSTALL_TRANSACTIONS.remove(outer_transaction)
            if not rollback_incomplete:
                shutil.rmtree(
                    outer_transaction.staging, ignore_errors=True
                )

    print("\nCursor and Claude Code commands, in order:")
    for command in command_files():
        print(f"  /{command.stem}")
    print("\nCodex CLI uses $ob-start, $ob-add-inputs, ...")
    print("ChatGPT Desktop uses @ob-start, @ob-add-inputs, ...")
    print("\nOr name a skill directly: $engagement-intake, $baggage-propagation, "
          "$cardinality-budget, ...")
    if project:
        print("\nCopy obconfig.yaml.template to obconfig.yaml, chmod 0600, edit it, "
              "then run /ob-start. The command can create the local copy for you.")
    if args.dry_run:
        print("\n(dry run — nothing was written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
