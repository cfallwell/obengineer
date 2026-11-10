from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"


def run_install(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INSTALL), *args, "--project", str(project)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


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
        ".gitignore",
        ".env.template",
        "artifacts/README.md",
    }
    for relative, ownership in manifest["created"].items():
        digest = hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
        assert ownership["sha256"] == digest


def test_project_install_and_reinstall_never_overwrite_existing_content(tmp_path):
    (tmp_path / ".gitignore").write_text("custom-ignore\n")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/README.md").write_text("customer artifact instructions\n")
    run_install(tmp_path, "--cursor")
    assert (tmp_path / ".gitignore").read_text() == "custom-ignore\n"
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
