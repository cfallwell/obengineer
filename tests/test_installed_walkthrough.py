from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"


def test_installed_start_sequence_emits_before_network_or_discovery(tmp_path):
    project = tmp_path / "clean-repo"
    project.mkdir()
    subprocess.run(
        [str(INSTALL), "--cursor", "--project", str(project)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    installed = (project / ".cursor/commands/ob-start.md").read_text()
    scripts = re.findall(r'`python3 "([^"]+)"[^`]*`', installed)
    assert [Path(script).name for script in scripts[:1]] == ["start_turn.py"]
    assert "{{OBENGINEER_ROOT}}" not in installed

    instrumentation = tmp_path / "instrumentation"
    instrumentation.mkdir()
    attempts = tmp_path / "attempts.log"
    (instrumentation / "sitecustomize.py").write_text(
        """
import os
import socket
import subprocess

log = os.environ["OB_ATTEMPT_LOG"]

def record(kind):
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(kind + "\\n")

def blocked_connect(self, *args, **kwargs):
    record("network")
    raise AssertionError("network attempted before walkthrough output")

def blocked_popen(*args, **kwargs):
    record("discovery-process")
    raise AssertionError("discovery process attempted before walkthrough output")

socket.socket.connect = blocked_connect
subprocess.Popen = blocked_popen
"""
    )
    env = os.environ.copy()
    env["OB_ATTEMPT_LOG"] = str(attempts)
    env["PYTHONPATH"] = str(instrumentation)

    started = time.monotonic()
    start_process = subprocess.Popen(
        [
            sys.executable,
            scripts[0],
            "--project-root",
            str(project),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert start_process.stdout is not None
    first_visible = start_process.stdout.readline()
    elapsed = time.monotonic() - started
    stderr = start_process.communicate(timeout=5)[1]

    assert elapsed <= 5
    assert first_visible.startswith(
        "Before I inspect source, the network, or connected tools"
    )
    assert start_process.returncode == 0, stderr
    assert not attempts.exists()
