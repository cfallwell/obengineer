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
LEGACY_COMMAND_FIXTURES = ROOT / "tests/fixtures/legacy-commands"
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


def run_user_install(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        [str(INSTALL), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def try_user_install(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        [str(INSTALL), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def run_status(scope_root: Path, project: bool) -> subprocess.CompletedProcess[str]:
    command = [str(INSTALL), "--list"]
    env = os.environ.copy()
    if project:
        command.extend(["--project", str(scope_root)])
    else:
        env["HOME"] = str(scope_root)
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def test_installer_help_explains_codex_always_copies_skills():
    result = subprocess.run(
        [str(INSTALL), "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Codex skills are always materialized" in result.stdout
    assert "copy Cursor/Claude skills and inputs" in result.stdout


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


def install_legacy_codex(scope_root: Path, project: bool) -> Path:
    installer.install_host(
        installer.LEGACY_CODEX_HOST,
        scope_root,
        project,
        False,
        installer.Planner(False),
    )
    return installer.LEGACY_CODEX_HOST.base(scope_root, project)


def run_installed_start(script: Path, project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--project-root", str(project)],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )


def test_project_codex_install_uses_explicit_workflow_skills_and_no_prompts(tmp_path):
    result = run_install(tmp_path, "--codex")
    skills = tmp_path / ".agents/skills"

    assert "workflows ->" in result.stdout
    assert not (tmp_path / ".agents/prompts").exists()
    canonical = skills / "engagement-intake"
    assert canonical.is_dir() and not canonical.is_symlink()
    companion = tmp_path / ".agents/obengineer/inputs"
    assert companion.is_dir() and not companion.is_symlink()
    assert (
        companion / "engagement-inputs.template.yaml"
    ).read_bytes() == (
        ROOT / "inputs/engagement-inputs.template.yaml"
    ).read_bytes()
    for name in installer.WORKFLOW_ORDER:
        wrapper = skills / name
        text = (wrapper / "SKILL.md").read_text()
        assert f"name: {name}" in text
        assert "$ARGUMENTS" in text
        assert installer.ROOT_TOKEN not in text
        assert str(ROOT) in text
        assert (
            "allow_implicit_invocation: false"
            in (wrapper / "agents/openai.yaml").read_text()
        )

    manifest = json.loads(
        (tmp_path / ".agents/.obengineer-install.json").read_text()
    )
    assert not any(relative.startswith("prompts/") for relative in manifest["owned"])
    assert {
        f"skills/{name}" for name in installer.WORKFLOW_ORDER
    } <= set(manifest["owned"])
    assert "obengineer/inputs" in manifest["owned"]


def test_user_codex_install_uses_agents_skills_not_codex_home(tmp_path):
    result = run_user_install(tmp_path, "--codex")

    assert "scope: user" in result.stdout
    assert (tmp_path / ".agents/skills/ob-start/SKILL.md").is_file()
    canonical = tmp_path / ".agents/skills/engagement-intake"
    assert canonical.is_dir() and not canonical.is_symlink()
    assert (
        tmp_path / ".agents/obengineer/inputs/engagement-inputs.template.yaml"
    ).is_file()
    assert not (tmp_path / ".codex").exists()


def test_codex_default_install_materializes_canonical_skills_and_wrappers(tmp_path):
    run_install(tmp_path, "--codex")
    canonical = tmp_path / ".agents/skills/engagement-intake"
    wrapper = tmp_path / ".agents/skills/ob-start"

    assert canonical.is_dir() and not canonical.is_symlink()
    assert wrapper.is_dir() and not wrapper.is_symlink()
    assert str(ROOT) in (wrapper / "SKILL.md").read_text()
    assert not (tmp_path / ".agents/prompts").exists()


def test_cursor_and_claude_default_installs_keep_skill_symlinks(tmp_path):
    run_install(tmp_path, "--cursor", "--claude")

    assert (tmp_path / ".cursor/skills/engagement-intake").is_symlink()
    assert (tmp_path / ".claude/skills/engagement-intake").is_symlink()
    assert not (tmp_path / ".cursor/obengineer/inputs").exists()
    assert not (tmp_path / ".claude/obengineer/inputs").exists()


@pytest.mark.parametrize("host", ("cursor", "claude"))
def test_project_copy_install_runs_start_turn_with_namespaced_inputs(
    tmp_path,
    host,
):
    run_install(tmp_path, f"--{host}", "--copy")
    host_base = tmp_path / f".{host}"
    skill = host_base / "skills/engagement-intake"
    companion = host_base / "obengineer/inputs"

    assert skill.is_dir() and not skill.is_symlink()
    assert companion.is_dir() and not companion.is_symlink()
    result = run_installed_start(skill / "scripts/start_turn.py", tmp_path)
    assert result.stdout.startswith(
        "Before I inspect source, the network, or connected tools"
    )
    manifest = json.loads(
        (host_base / installer.MANIFEST_NAME).read_text()
    )
    assert "obengineer/inputs" in manifest["owned"]


@pytest.mark.parametrize("host", ("cursor", "claude"))
def test_user_copy_install_runs_start_turn_with_namespaced_inputs(
    tmp_path,
    host,
):
    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    run_user_install(home, f"--{host}", "--copy")
    host_base = home / f".{host}"
    skill = host_base / "skills/engagement-intake"

    result = run_installed_start(skill / "scripts/start_turn.py", project)

    assert result.stdout.startswith(
        "Before I inspect source, the network, or connected tools"
    )
    assert (host_base / "obengineer/inputs").is_dir()
    assert (
        project / "docs/observability/engagement-inputs.yaml"
    ).is_file()


def test_copy_install_preflights_unowned_inputs_companion(tmp_path):
    template = (
        tmp_path
        / ".cursor/obengineer/inputs/engagement-inputs.template.yaml"
    )
    template.parent.mkdir(parents=True)
    template.write_text("user template\n")

    result = try_install(tmp_path, "--cursor", "--copy")

    assert result.returncode == 1
    assert "not installer-owned" in result.stdout
    assert template.read_text() == "user template\n"
    assert not (tmp_path / ".cursor/skills").exists()


def test_copy_companion_reinstalls_and_uninstalls_with_host_manifest(tmp_path):
    run_install(tmp_path, "--cursor", "--copy")
    companion = tmp_path / ".cursor/obengineer/inputs"

    run_install(tmp_path, "--cursor", "--copy")
    assert companion.is_dir()

    run_install(tmp_path, "--cursor", "--copy", "--uninstall")
    assert not companion.exists()


def test_return_to_default_links_removes_unchanged_copy_companion(tmp_path):
    run_install(tmp_path, "--cursor", "--copy")
    companion = tmp_path / ".cursor/obengineer/inputs"

    run_install(tmp_path, "--cursor")

    assert not companion.exists()
    assert (tmp_path / ".cursor/skills/engagement-intake").is_symlink()
    manifest = json.loads(
        (tmp_path / ".cursor/.obengineer-install.json").read_text()
    )
    assert "obengineer/inputs" not in manifest["owned"]


def test_project_codex_copied_start_turn_uses_installed_inputs(tmp_path):
    run_install(tmp_path, "--codex")
    script = (
        tmp_path
        / ".agents/skills/engagement-intake/scripts/start_turn.py"
    )

    result = run_installed_start(script, tmp_path)

    assert result.stdout.startswith(
        "Before I inspect source, the network, or connected tools"
    )
    assert (
        tmp_path / "docs/observability/engagement-inputs.yaml"
    ).is_file()


def test_user_codex_copied_start_turn_uses_installed_inputs(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    run_user_install(home, "--codex")
    script = home / ".agents/skills/engagement-intake/scripts/start_turn.py"

    result = run_installed_start(script, project)

    assert result.stdout.startswith(
        "Before I inspect source, the network, or connected tools"
    )
    assert (
        project / "docs/observability/engagement-inputs.yaml"
    ).is_file()


def test_codex_inputs_companion_is_digest_checked_on_uninstall(tmp_path):
    run_install(tmp_path, "--codex")
    template = (
        tmp_path
        / ".agents/obengineer/inputs/engagement-inputs.template.yaml"
    )
    template.write_text(template.read_text() + "\n# user change\n")

    run_install(tmp_path, "--codex", "--uninstall")

    assert template.read_text().endswith("\n# user change\n")
    assert not (tmp_path / ".agents/skills/engagement-intake").exists()


def test_codex_install_preserves_unowned_project_prompts(tmp_path):
    prompt = tmp_path / ".agents/prompts/personal.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("keep\n")

    run_install(tmp_path, "--codex")

    assert prompt.read_text() == "keep\n"
    assert (tmp_path / ".agents/skills/ob-start/SKILL.md").is_file()


def test_project_codex_reinstall_removes_only_unchanged_owned_prompts(tmp_path):
    base = install_legacy_codex(tmp_path, True)
    modified = base / "prompts/ob-review.md"
    modified.write_text(modified.read_text() + "\nuser change\n")
    unowned = base / "prompts/personal.md"
    unowned.write_text("keep\n")

    run_install(tmp_path, "--codex")

    assert not (base / "prompts/ob-start.md").exists()
    assert modified.read_text().endswith("\nuser change\n")
    assert unowned.read_text() == "keep\n"
    assert (base / "skills/ob-start/SKILL.md").is_file()
    manifest = json.loads((base / installer.MANIFEST_NAME).read_text())
    prompt_entries = {
        relative
        for relative in manifest["owned"]
        if relative.startswith("prompts/")
    }
    assert prompt_entries == {"prompts/ob-review.md"}


def test_user_codex_migration_preserves_modified_and_unowned_legacy_paths(tmp_path):
    legacy = install_legacy_codex(tmp_path, False)
    modified = legacy / "prompts/ob-review.md"
    modified.write_text(modified.read_text() + "\nuser change\n")
    unowned = legacy / "prompts/personal.md"
    unowned.write_text("keep\n")
    removed_extra = legacy / "retired/installer-owned.txt"
    removed_extra.parent.mkdir()
    removed_extra.write_text("remove\n")
    modified_extra = legacy / "retired/modified.txt"
    modified_extra.write_text("original\n")
    manifest_path = legacy / installer.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    manifest["owned"]["retired/installer-owned.txt"] = installer.path_ownership(
        removed_extra
    )
    manifest["owned"]["retired/modified.txt"] = installer.path_ownership(
        modified_extra
    )
    manifest_path.write_text(json.dumps(manifest))
    modified_extra.write_text("changed\n")

    run_user_install(tmp_path, "--codex")

    assert (tmp_path / ".agents/skills/ob-start/SKILL.md").is_file()
    assert not (legacy / "skills/engagement-intake").exists()
    assert not (legacy / "prompts/ob-start.md").exists()
    assert modified.read_text().endswith("\nuser change\n")
    assert unowned.read_text() == "keep\n"
    assert not removed_extra.exists()
    assert modified_extra.read_text() == "changed\n"
    assert (legacy / installer.MANIFEST_NAME).is_file()
    retained = json.loads((legacy / installer.MANIFEST_NAME).read_text())
    assert set(retained["owned"]) == {
        "prompts/ob-review.md",
        "retired/modified.txt",
    }


def test_user_codex_migration_dry_run_leaves_both_locations_unchanged(tmp_path):
    legacy = install_legacy_codex(tmp_path, False)
    prompt = legacy / "prompts/ob-start.md"
    prompt_before = prompt.read_bytes()
    manifest_before = (legacy / installer.MANIFEST_NAME).read_bytes()

    result = run_user_install(tmp_path, "--codex", "--dry-run")

    assert "would remove unchanged legacy path" in result.stdout
    assert prompt.read_bytes() == prompt_before
    assert (legacy / installer.MANIFEST_NAME).read_bytes() == manifest_before
    assert not (tmp_path / ".agents").exists()


def test_user_codex_migration_removes_clean_legacy_manifest(tmp_path):
    legacy = install_legacy_codex(tmp_path, False)

    run_user_install(tmp_path, "--codex")

    assert not (legacy / installer.MANIFEST_NAME).exists()
    assert (tmp_path / ".agents/skills/ob-start/SKILL.md").is_file()


def test_user_codex_migration_preserves_unverifiable_legacy_install(tmp_path):
    legacy = tmp_path / ".codex"
    prompt = legacy / "prompts/ob-start.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("legacy content\n")
    manifest = legacy / installer.MANIFEST_NAME
    manifest.write_text('{"created": "not-a-list"}\n')

    run_user_install(tmp_path, "--codex")

    assert prompt.read_text() == "legacy content\n"
    assert manifest.exists()
    assert (tmp_path / ".agents/skills/ob-start/SKILL.md").is_file()


def test_user_codex_migration_rolls_back_legacy_paths_on_failure(
    tmp_path,
    monkeypatch,
):
    legacy = install_legacy_codex(tmp_path, False)
    manifest_before = (legacy / installer.MANIFEST_NAME).read_bytes()
    prompt = legacy / "prompts/ob-start.md"
    prompt_before = prompt.read_bytes()
    original_write = installer.Planner.write
    calls = 0

    def fail_second_write(self, destination, text):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated workflow write failure")
        return original_write(self, destination, text)

    monkeypatch.setattr(installer.Planner, "write", fail_second_write)
    with pytest.raises(OSError, match="simulated workflow"):
        installer.install_host(
            installer.HOSTS["codex"],
            tmp_path,
            False,
            False,
            installer.Planner(False),
        )

    assert prompt.read_bytes() == prompt_before
    assert (legacy / installer.MANIFEST_NAME).read_bytes() == manifest_before
    assert not (tmp_path / ".agents/skills/ob-start").exists()


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


@pytest.mark.parametrize("host_key", ("cursor", "claude", "codex"))
@pytest.mark.parametrize("project", (True, False), ids=("project", "user"))
def test_symlinked_host_manifest_blocks_install_uninstall_and_status(
    tmp_path,
    host_key,
    project,
):
    scope_root = tmp_path / ("project" if project else "home")
    scope_root.mkdir()
    host = installer.HOSTS[host_key]
    base = host.base(scope_root, project)
    base.mkdir()
    claimed = base / "claimed-local.txt"
    claimed.write_text("must survive\n")
    external = tmp_path / f"{host_key}-external-manifest.json"
    external.write_text(json.dumps({
        "schema_version": 2,
        "source": "SENTINEL_EXTERNAL_MANIFEST",
        "scope": "project" if project else "user",
        "owned": {
            "claimed-local.txt": installer.path_ownership(claimed),
        },
    }))
    external_before = external.read_bytes()
    manifest_link = base / installer.MANIFEST_NAME
    manifest_link.symlink_to(external)

    install_result = (
        try_install(scope_root, f"--{host_key}")
        if project
        else try_user_install(scope_root, f"--{host_key}")
    )
    status_result = run_status(scope_root, project)
    uninstall_result = (
        try_install(scope_root, f"--{host_key}", "--uninstall")
        if project
        else try_user_install(scope_root, f"--{host_key}", "--uninstall")
    )

    assert install_result.returncode == 1
    assert "unsafe host manifest" in install_result.stdout
    assert "unsafe manifest" in status_result.stdout
    assert "SENTINEL_EXTERNAL_MANIFEST" not in status_result.stdout
    assert uninstall_result.returncode == 1
    assert "REFUSE unsafe host manifest" in uninstall_result.stdout
    assert claimed.read_text() == "must survive\n"
    assert external.read_bytes() == external_before
    assert manifest_link.is_symlink()
    assert not host.skills_dir(scope_root, project).exists()
    if project:
        assert not (scope_root / ".obengineer/scaffold-manifest.json").exists()


@pytest.mark.parametrize("host_key", ("cursor", "claude", "codex"))
@pytest.mark.parametrize("project", (True, False), ids=("project", "user"))
def test_symlinked_host_manifest_blocks_reinstall_before_mutation(
    tmp_path,
    host_key,
    project,
):
    scope_root = tmp_path / ("project" if project else "home")
    scope_root.mkdir()
    host = installer.HOSTS[host_key]
    if project:
        run_install(scope_root, f"--{host_key}")
    else:
        run_user_install(scope_root, f"--{host_key}")
    base = host.base(scope_root, project)
    installed = (
        host.skills_dir(scope_root, project) / "ob-start/SKILL.md"
        if host_key == "codex"
        else host.commands_dir(scope_root, project) / "ob-start.md"
    )
    installed_before = installed.read_bytes()
    claimed = base / "claimed-local.txt"
    claimed.write_text("must survive\n")
    manifest_path = base / installer.MANIFEST_NAME
    manifest_path.unlink()
    external = tmp_path / f"{host_key}-reinstall-manifest.json"
    external.write_text(json.dumps({
        "schema_version": 2,
        "source": "SENTINEL_EXTERNAL_MANIFEST",
        "scope": "project" if project else "user",
        "owned": {
            "claimed-local.txt": installer.path_ownership(claimed),
        },
    }))
    manifest_path.symlink_to(external)

    result = (
        try_install(scope_root, f"--{host_key}")
        if project
        else try_user_install(scope_root, f"--{host_key}")
    )

    assert result.returncode == 1
    assert "unsafe host manifest" in result.stdout
    assert installed.read_bytes() == installed_before
    assert claimed.read_text() == "must survive\n"
    assert manifest_path.is_symlink()


def test_user_codex_migration_ignores_symlinked_legacy_manifest(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    legacy = home / ".codex"
    legacy.mkdir()
    claimed = legacy / "claimed-local.txt"
    claimed.write_text("must survive\n")
    external = tmp_path / "legacy-external-manifest.json"
    external.write_text(json.dumps({
        "schema_version": 2,
        "source": "SENTINEL_EXTERNAL_MANIFEST",
        "scope": "user",
        "owned": {
            "claimed-local.txt": installer.path_ownership(claimed),
        },
    }))
    external_before = external.read_bytes()
    manifest_link = legacy / installer.MANIFEST_NAME
    manifest_link.symlink_to(external)

    run_user_install(home, "--codex")

    assert claimed.read_text() == "must survive\n"
    assert external.read_bytes() == external_before
    assert manifest_link.is_symlink()
    assert (home / ".agents/skills/ob-start/SKILL.md").is_file()


def test_project_uninstall_refuses_symlinked_host_base(tmp_path):
    external = tmp_path.parent / f"{tmp_path.name}-cursor-uninstall"
    external.mkdir()
    manifest = external / installer.MANIFEST_NAME
    manifest.write_text(json.dumps({
        "schema_version": 2,
        "source": str(ROOT),
        "scope": "project",
        "owned": {},
    }))
    (tmp_path / ".cursor").symlink_to(external, target_is_directory=True)

    result = try_install(tmp_path, "--cursor", "--uninstall")

    assert result.returncode == 1
    assert "REFUSE unsafe host manifest" in result.stdout
    assert manifest.is_file()


def test_user_uninstall_refuses_symlinked_host_base(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    external = tmp_path / "external-agents"
    external.mkdir()
    manifest = external / installer.MANIFEST_NAME
    manifest.write_text(json.dumps({
        "schema_version": 2,
        "source": str(ROOT),
        "scope": "user",
        "owned": {},
    }))
    (home / ".agents").symlink_to(external, target_is_directory=True)

    result = try_user_install(home, "--codex", "--uninstall")

    assert result.returncode == 1
    assert "REFUSE unsafe host manifest" in result.stdout
    assert manifest.is_file()


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


def test_reinstall_removes_all_unchanged_stale_owned_path_kinds(tmp_path):
    run_install(tmp_path, "--cursor")
    base = tmp_path / ".cursor"
    manifest_path = base / installer.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    stale = {
        "skills/removed-skill": "skill\n",
        "skills/ob-removed-workflow": "workflow\n",
        "skills/removed-shared-dir": "shared\n",
    }
    stale_paths = []
    for relative, content in stale.items():
        path = base / relative
        path.mkdir()
        (path / "owned.txt").write_text(content)
        manifest["owned"][relative] = installer.path_ownership(path)
        stale_paths.append(path)
    command = base / "commands/removed-command.md"
    command.write_text("removed command\n")
    manifest["owned"]["commands/removed-command.md"] = installer.path_ownership(
        command
    )
    stale_paths.append(command)
    manifest_path.write_text(json.dumps(manifest))

    run_install(tmp_path, "--cursor")

    assert all(not path.exists() for path in stale_paths)
    upgraded = json.loads(manifest_path.read_text())
    assert not (set(stale) | {"commands/removed-command.md"}) & set(
        upgraded["owned"]
    )


def test_reinstall_preserves_and_tracks_modified_stale_owned_path(tmp_path):
    run_install(tmp_path, "--cursor")
    base = tmp_path / ".cursor"
    manifest_path = base / installer.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    stale = base / "skills/removed-skill"
    stale.mkdir()
    content = stale / "owned.txt"
    content.write_text("original\n")
    original_ownership = installer.path_ownership(stale)
    manifest["owned"]["skills/removed-skill"] = original_ownership
    manifest_path.write_text(json.dumps(manifest))
    content.write_text("user change\n")

    run_install(tmp_path, "--cursor")

    assert content.read_text() == "user change\n"
    upgraded = json.loads(manifest_path.read_text())
    assert upgraded["owned"]["skills/removed-skill"] == original_ownership

    run_install(tmp_path, "--cursor", "--uninstall")
    assert content.read_text() == "user change\n"


def test_reinstall_migrates_source_bound_legacy_manifest_to_digests(tmp_path):
    run_install(tmp_path, "--cursor")
    manifest_path = convert_host_install_to_legacy_manifest(tmp_path)
    legacy = json.loads(manifest_path.read_text())
    start = tmp_path / ".cursor/commands/ob-start.md"
    start.write_text(
        (LEGACY_COMMAND_FIXTURES / "ob-start.md").read_text().replace(
            installer.ROOT_TOKEN, legacy["source"]
        )
    )

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
    modified = command.read_text() + "\nUser customization that must survive.\n"
    command.write_text(modified)

    result = try_install(tmp_path, "--cursor")

    assert result.returncode == 1
    assert "not installer-owned" in result.stdout
    assert command.read_text() == modified


def test_legacy_manifest_does_not_claim_retargeted_skill(tmp_path):
    run_install(tmp_path, "--cursor")
    convert_host_install_to_legacy_manifest(tmp_path)
    skill = tmp_path / ".cursor/skills/engagement-intake"
    skill.unlink()
    spoofed = "/tmp/attacker/obengineer/skills/engagement-intake"
    skill.symlink_to(spoofed, target_is_directory=True)

    result = try_install(tmp_path, "--cursor")

    assert result.returncode == 1
    assert "not installer-owned" in result.stdout
    assert skill.is_symlink()
    assert os.readlink(skill) == spoofed


def test_legacy_manifest_removes_verified_retired_command(tmp_path):
    run_install(tmp_path, "--cursor")
    manifest_path = convert_host_install_to_legacy_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    retired = tmp_path / ".cursor/commands/ob-intake.md"
    legacy_source = manifest["source"]
    retired.write_text(
        (LEGACY_COMMAND_FIXTURES / "ob-intake.md").read_text().replace(
            installer.ROOT_TOKEN, legacy_source
        )
    )
    manifest["created"].append(
        "/opt/legacy-project/.cursor/commands/ob-intake.md"
    )
    manifest_path.write_text(json.dumps(manifest))

    installer.install_host(
        installer.HOSTS["cursor"],
        tmp_path,
        True,
        False,
        installer.Planner(False),
    )

    assert not retired.exists()
    upgraded = json.loads(manifest_path.read_text())
    assert "commands/ob-intake.md" not in upgraded["owned"]


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
    run_install(tmp_path, "--cursor", "--copy")
    base = tmp_path / ".cursor"
    manifest_path = base / installer.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    stale = base / "skills/removed-skill"
    stale.mkdir()
    (stale / "owned.txt").write_text("restore on rollback\n")
    manifest["owned"]["skills/removed-skill"] = installer.path_ownership(stale)
    manifest_path.write_text(json.dumps(manifest))
    manifest_before = (base / installer.MANIFEST_NAME).read_bytes()
    command = base / "commands/ob-start.md"
    command_before = command.read_bytes()
    companion = base / "obengineer/inputs/engagement-inputs.template.yaml"
    companion_before = companion.read_bytes()
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
            installer.HOSTS["cursor"], tmp_path, True, True, planner
        )

    assert command.read_bytes() == command_before
    assert (base / installer.MANIFEST_NAME).read_bytes() == manifest_before
    assert (stale / "owned.txt").read_text() == "restore on rollback\n"
    assert companion.read_bytes() == companion_before
