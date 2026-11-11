from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
INSTALL_SCRIPT = ROOT / "scripts/install.py"
spec = importlib.util.spec_from_file_location("obengineer_installer", INSTALL_SCRIPT)
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


def run_install(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INSTALL), *args, "--project", str(project)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def try_install(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INSTALL), *args, "--project", str(project)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def convert_host_install_to_legacy_manifest(project: Path) -> Path:
    base = project / ".cursor"
    manifest_path = base / installer.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    legacy_source = Path("/opt/legacy-workspace/obengineer")
    legacy_project = Path("/opt/legacy-project")
    created = []
    for relative in manifest["owned"]:
        path = base / relative
        created.append(str(legacy_project / ".cursor" / relative))
        if relative.startswith("skills/"):
            path.unlink()
            expected = legacy_source / "skills" / Path(relative).relative_to("skills")
            legacy_path = legacy_project / ".cursor" / relative
            path.symlink_to(
                os.path.relpath(expected, legacy_path.parent),
                target_is_directory=True,
            )
        else:
            path.write_text(path.read_text().replace(str(ROOT), str(legacy_source)))
    manifest_path.write_text(json.dumps({
        "source": str(legacy_source),
        "scope": "project",
        "created": created,
    }))
    return manifest_path


def test_project_install_creates_missing_scaffold_and_tracks_ownership(tmp_path):
    run_install(tmp_path, "--cursor")
    assert (tmp_path / ".gitignore").is_file()
    assert (tmp_path / ".env.template").is_file()
    assert (tmp_path / "artifacts/README.md").is_file()
    assert "PRODUCTION_URL=" in (tmp_path / ".env.template").read_text()
    assert "TEST_LOGIN_ID=" in (tmp_path / ".env.template").read_text()
    assert "PASSWORD_REF=" in (tmp_path / ".env.template").read_text()
    assert ".obengineer/" in (tmp_path / ".gitignore").read_text()

    manifest = json.loads(
        (tmp_path / ".obengineer/scaffold-manifest.json").read_text()
    )
    assert set(manifest["created"]) == {
        ".env.template",
        "artifacts/README.md",
    }
    assert manifest["schema_version"] == 2
    assert manifest["gitignore"]["created"] is True
    assert ".obengineer/" in manifest["gitignore"]["created_lines"]
    for relative, ownership in manifest["created"].items():
        digest = hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
        assert ownership["sha256"] == digest


def test_project_install_and_reinstall_never_overwrite_existing_content(tmp_path):
    (tmp_path / ".gitignore").write_text("custom-ignore\n")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/README.md").write_text("customer artifact instructions\n")
    run_install(tmp_path, "--cursor")
    gitignore = (tmp_path / ".gitignore").read_text()
    assert gitignore.startswith("custom-ignore\n")
    assert "\n.env\n" in gitignore
    assert ".obengineer/" in gitignore
    assert (
        tmp_path / "artifacts/README.md"
    ).read_text() == "customer artifact instructions\n"

    env_template = tmp_path / ".env.template"
    env_template.write_text(env_template.read_text() + "\nCUSTOM_USER_VALUE=yes\n")
    run_install(tmp_path, "--cursor")
    assert "CUSTOM_USER_VALUE=yes" in env_template.read_text()
    manifest = json.loads(
        (tmp_path / ".obengineer/scaffold-manifest.json").read_text()
    )
    assert ".gitignore" not in manifest["created"]
    assert "artifacts/README.md" not in manifest["created"]


def test_uninstall_preserves_user_artifacts_and_modified_scaffold(tmp_path):
    run_install(tmp_path, "--cursor")
    (tmp_path / "artifacts/diagram.txt").write_text("customer-owned\n")
    (tmp_path / ".gitignore").write_text(
        (tmp_path / ".gitignore").read_text() + "\ncustomer-cache/\n"
    )

    run_install(tmp_path, "--cursor", "--uninstall")
    assert (tmp_path / "artifacts/diagram.txt").read_text() == "customer-owned\n"
    assert (tmp_path / "artifacts").is_dir()
    assert "customer-cache/" in (tmp_path / ".gitignore").read_text()
    assert not (tmp_path / ".env.template").exists()
    assert not (tmp_path / "artifacts/README.md").exists()
    assert not (tmp_path / ".obengineer/scaffold-manifest.json").exists()


def test_partial_host_uninstall_keeps_project_scaffold(tmp_path):
    run_install(tmp_path, "--cursor", "--claude")
    run_install(tmp_path, "--cursor", "--uninstall")
    assert (tmp_path / ".env.template").exists()
    assert (tmp_path / ".obengineer/scaffold-manifest.json").exists()


def test_project_install_dry_run_does_not_create_scaffold(tmp_path):
    result = run_install(tmp_path, "--cursor", "--dry-run")
    assert "would create missing" in result.stdout
    assert not (tmp_path / ".gitignore").exists()
    assert not (tmp_path / ".obengineer").exists()


def test_existing_host_command_or_skill_collision_refuses_without_partial_install(
    tmp_path,
):
    command = tmp_path / ".cursor/commands/ob-start.md"
    command.parent.mkdir(parents=True)
    command.write_text("my command\n")

    result = try_install(tmp_path, "--cursor")
    assert result.returncode == 1
    assert "REFUSE" in result.stdout
    assert "not installer-owned" in result.stdout
    assert command.read_text() == "my command\n"
    assert not (tmp_path / ".cursor/skills/engagement-intake").exists()
    assert not (tmp_path / ".env.template").exists()

    command.unlink()
    skill = tmp_path / ".cursor/skills/engagement-intake"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("my skill\n")
    result = try_install(tmp_path, "--cursor")
    assert result.returncode == 1
    assert skill.joinpath("SKILL.md").read_text() == "my skill\n"


def test_symlinked_host_parent_cannot_escape_project(tmp_path):
    external = tmp_path.parent / f"{tmp_path.name}-external"
    external.mkdir()
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor/commands").symlink_to(external, target_is_directory=True)

    result = try_install(tmp_path, "--cursor")
    assert result.returncode == 1
    assert "symlinked or escaping parent" in result.stdout
    assert list(external.iterdir()) == []
    assert not (tmp_path / ".env.template").exists()

    # A malicious manifest cannot make uninstall follow the same parent.
    manifest = tmp_path / ".cursor/.obengineer-install.json"
    manifest.write_text(json.dumps({
        "schema_version": 2,
        "source": str(ROOT),
        "scope": "project",
        "owned": {
            "commands/ob-start.md": {
                "kind": "file",
                "sha256": "0" * 64,
            }
        },
    }))
    outside = external / "ob-start.md"
    outside.write_text("outside\n")
    run_install(tmp_path, "--cursor", "--uninstall")
    assert outside.read_text() == "outside\n"


@pytest.mark.parametrize("target", (".gitignore", "artifacts"))
def test_symlinked_scaffold_target_cannot_escape_or_be_replaced(tmp_path, target):
    external = tmp_path.parent / f"{tmp_path.name}-{target.replace('.', '')}-external"
    if target == "artifacts":
        external.mkdir()
        (tmp_path / target).symlink_to(external, target_is_directory=True)
    else:
        external.write_text("outside-ignore\n")
        (tmp_path / target).symlink_to(external)

    result = try_install(tmp_path, "--cursor")
    assert result.returncode == 1
    assert "Project scaffold" in result.stdout
    assert "symlink" in result.stdout
    if target == "artifacts":
        assert list(external.iterdir()) == []
        assert (tmp_path / target).is_symlink()
    else:
        assert external.read_text() == "outside-ignore\n"
        assert (tmp_path / target).is_symlink()
    assert not (tmp_path / ".cursor/commands").exists()


def test_uninstall_preserves_scaffold_after_symlink_substitution(tmp_path):
    run_install(tmp_path, "--cursor")
    artifacts = tmp_path / "artifacts"
    (artifacts / "README.md").unlink()
    artifacts.rmdir()
    external = tmp_path.parent / f"{tmp_path.name}-uninstall-external"
    external.mkdir()
    protected = external / "protected.txt"
    protected.write_text("keep\n")
    artifacts.symlink_to(external, target_is_directory=True)

    run_install(tmp_path, "--cursor", "--uninstall")
    assert artifacts.is_symlink()
    assert protected.read_text() == "keep\n"


def test_reinstall_is_digest_checked_and_modified_command_survives_uninstall(tmp_path):
    run_install(tmp_path, "--cursor")
    manifest_path = tmp_path / ".cursor/.obengineer-install.json"
    first_manifest = json.loads(manifest_path.read_text())
    assert first_manifest["schema_version"] == 2
    command = tmp_path / ".cursor/commands/ob-start.md"

    run_install(tmp_path, "--cursor")
    assert json.loads(manifest_path.read_text())["owned"] == first_manifest["owned"]

    command.write_text("user-modified command\n")
    result = try_install(tmp_path, "--cursor")
    assert result.returncode == 1
    assert "modified after installation" in result.stdout
    assert command.read_text() == "user-modified command\n"

    run_install(tmp_path, "--cursor", "--uninstall")
    assert command.read_text() == "user-modified command\n"
    assert not (tmp_path / ".cursor/skills/engagement-intake").exists()


def test_reinstall_migrates_source_bound_legacy_manifest_to_digests(tmp_path):
    run_install(tmp_path, "--cursor")
    manifest_path = convert_host_install_to_legacy_manifest(tmp_path)

    run_install(tmp_path, "--cursor")

    manifest = json.loads(manifest_path.read_text())
    assert manifest["schema_version"] == 2
    assert manifest["source"] == str(ROOT)
    assert all("kind" in ownership for ownership in manifest["owned"].values())
    assert (
        tmp_path / ".cursor/commands/ob-start.md"
    ).read_text().count(str(ROOT)) > 0


def test_legacy_manifest_does_not_claim_modified_command(tmp_path):
    run_install(tmp_path, "--cursor")
    convert_host_install_to_legacy_manifest(tmp_path)
    command = tmp_path / ".cursor/commands/ob-start.md"
    command.write_text("user-defined command\n")

    result = try_install(tmp_path, "--cursor")

    assert result.returncode == 1
    assert "not installer-owned" in result.stdout
    assert command.read_text() == "user-defined command\n"


def test_legacy_manifest_does_not_claim_retargeted_skill(tmp_path):
    run_install(tmp_path, "--cursor")
    convert_host_install_to_legacy_manifest(tmp_path)
    skill = tmp_path / ".cursor/skills/engagement-intake"
    skill.unlink()
    skill.symlink_to("../../user-owned-skill", target_is_directory=True)

    result = try_install(tmp_path, "--cursor")

    assert result.returncode == 1
    assert "not installer-owned" in result.stdout
    assert skill.is_symlink()
    assert os.readlink(skill) == "../../user-owned-skill"


def test_gitignore_uninstall_removes_only_tracked_lines(tmp_path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("user-cache/\n.env\n")
    run_install(tmp_path, "--cursor")
    manifest = json.loads(
        (tmp_path / ".obengineer/scaffold-manifest.json").read_text()
    )
    assert ".env" not in manifest["gitignore"]["appended_lines"]
    assert ".obengineer/" in manifest["gitignore"]["appended_lines"]

    run_install(tmp_path, "--cursor")
    assert gitignore.read_text().count(".obengineer/") == 1
    gitignore.write_text(gitignore.read_text() + "later-user-line/\n")
    run_install(tmp_path, "--cursor", "--uninstall")
    assert gitignore.read_text() == "user-cache/\n.env\nlater-user-line/\n"


def test_uninstall_preserves_preexisting_empty_gitignore(tmp_path):
    gitignore = tmp_path / ".gitignore"
    gitignore.touch()
    run_install(tmp_path, "--cursor")
    manifest = json.loads(
        (tmp_path / ".obengineer/scaffold-manifest.json").read_text()
    )
    assert manifest["gitignore"]["created"] is False

    run_install(tmp_path, "--cursor", "--uninstall")
    assert gitignore.is_file()
    assert gitignore.read_text() == ""


def test_failed_reinstall_rolls_back_all_host_paths(tmp_path, monkeypatch):
    run_install(tmp_path, "--cursor")
    base = tmp_path / ".cursor"
    manifest_before = (base / installer.MANIFEST_NAME).read_bytes()
    command = base / "commands/ob-start.md"
    command_before = command.read_bytes()
    original_write = installer.Planner.write
    calls = 0

    def fail_second_write(self, destination, text):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated write failure")
        return original_write(self, destination, text)

    monkeypatch.setattr(installer.Planner, "write", fail_second_write)
    planner = installer.Planner(False)
    with pytest.raises(OSError, match="simulated"):
        installer.install_host(
            installer.HOSTS["cursor"], tmp_path, True, False, planner
        )

    assert command.read_bytes() == command_before
    assert (base / installer.MANIFEST_NAME).read_bytes() == manifest_before
