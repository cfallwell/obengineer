from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"


def test_installed_start_creates_local_config_before_discovery(tmp_path):
    project = tmp_path / "clean-repo"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(
        [str(INSTALL), "--cursor", "--project", str(project)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    script = (
        project
        / ".cursor/skills/engagement-intake/scripts/manage_obconfig.py"
    ).resolve()
    started = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project),
            "init",
        ],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    elapsed = time.monotonic() - started
    assert elapsed <= 5
    assert result.stdout == (
        "Created local obconfig.yaml. Edit it and rerun /ob-start.\n"
    )
    actual = project / "obconfig.yaml"
    assert actual.is_file() and not actual.is_symlink()
    assert actual.stat().st_mode & 0o777 == 0o600
    assert subprocess.run(
        ["git", "-C", str(project), "check-ignore", "-q", "obconfig.yaml"],
        check=False,
    ).returncode == 0
