from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location(
        "verify_analysis_acceptance",
        SCRIPTS / "verify_analysis_acceptance.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify_acceptance = _load()


def run(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def accepted_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    run(tmp_path, "init", "-q")
    run(tmp_path, "config", "user.email", "test@example.invalid")
    run(tmp_path, "config", "user.name", "Test")
    docs = tmp_path / "docs" / "observability"
    docs.mkdir(parents=True)
    analysis = docs / "analysis-app-2026-01-01.md"
    analysis.write_text("# Analysis\n")
    (docs / "attribute-schema.json").write_text("{}\n")
    (docs / "implementation-map.json").write_text(json.dumps({
        "schema_version": 1,
        "repositories": [{
            "id": "app",
            "remote": "owner/app",
            "authorized_paths": ["src/"],
        }],
        "targets": [{
            "selector": "workflow:account.update",
            "work_order": "WO-001",
            "repositories": ["app"],
            "mapping_status": "complete",
            "evidence": ["source:src/account.ts"],
        }],
    }))
    run(tmp_path, "add", "docs")
    run(tmp_path, "commit", "-qm", "analysis")
    return tmp_path, analysis, run(tmp_path, "rev-parse", "HEAD")


def test_exact_commit_artifacts_pass(tmp_path):
    repo, analysis, commit = accepted_repo(tmp_path)
    assert verify_acceptance.verify(repo, analysis, commit) == []


def test_changed_artifact_fails(tmp_path):
    repo, analysis, commit = accepted_repo(tmp_path)
    analysis.write_text("# Changed\n")
    failures = verify_acceptance.verify(repo, analysis, commit)
    assert failures == [
        "artifact differs from accepted commit: "
        "docs/observability/analysis-app-2026-01-01.md"
    ]


def test_short_sha_is_rejected(tmp_path):
    repo, analysis, commit = accepted_repo(tmp_path)
    assert verify_acceptance.verify(repo, analysis, commit[:12]) == [
        "analysis commit must be a full 40-character lowercase SHA"
    ]


def test_acceptance_record_cli_is_supported(tmp_path):
    repo, analysis, commit = accepted_repo(tmp_path)
    record = repo / "docs" / "observability" / (
        "analysis-app-2026-01-01.acceptance.yaml"
    )
    record.write_text(
        "status: accepted\n"
        "analysis: docs/observability/analysis-app-2026-01-01.md\n"
        f"analysis_commit: {commit}\n"
    )
    assert verify_acceptance.main([
        "--record", str(record), "--repo", str(repo)
    ]) == 0
