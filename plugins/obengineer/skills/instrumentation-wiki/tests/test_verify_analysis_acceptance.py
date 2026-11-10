from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
spec = importlib.util.spec_from_file_location(
    "verify_analysis_acceptance",
    SCRIPTS / "verify_analysis_acceptance.py",
)
verify_acceptance = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verify_acceptance
spec.loader.exec_module(verify_acceptance)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def accepted_repo(tmp_path: Path) -> tuple[Path, Path, Path, str, str]:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    docs = tmp_path / "docs" / "observability"
    version = docs / "analysis" / "app" / "V1"
    version.mkdir(parents=True)
    analysis = version / "index.md"
    analysis.write_text("[V1]\n\n# Analysis\n")
    wiki = tmp_path / "wiki" / "apps" / "app" / "versions" / "V1"
    work_orders = wiki / "implementation" / "work-orders"
    work_orders.mkdir(parents=True)
    (wiki / "index.md").write_text("# Wiki V1\n")
    (work_orders / "WO-001.md").write_text("# Ready work\n")
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
            "evidence": ["SRC-account-route"],
        }],
    }))
    seal = hashlib.sha256(b"[]").hexdigest()
    (docs / "provenance-ledger.json").write_text(json.dumps({
        "schema_version": 1,
        "engagement": {"application": "app"},
        "contract": {"sealed_ids": []},
        "context_profile": {"predicates": {}, "loaded_references": []},
        "sources": [{"id": "SRC-account-route"}],
        "facts": [], "runs": [], "checks": [], "artifacts": [],
        "decisions": [], "unresolved": [],
        "seals": {"analysis": {"ids": [], "digest": seal}},
    }))
    (docs / "verification-plan.json").write_text(json.dumps({
        "schema_version": 1,
        "criteria": [{
            "id": "VC-001",
            "source_section": 1,
            "system": "repository",
            "query": {"kind": "contract-check", "reference": "SRC-account-route"},
            "expected": {"operator": "equals", "value": True},
            "observation_window": "PT1M",
            "owner": "engineering",
            "remediation": {
                "route": "implementation",
                "selector": "work-order:WO-001",
                "instructions": "Run WO-001 and recheck.",
            },
        }],
    }))
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "analysis")
    commit = git(tmp_path, "rev-parse", "HEAD")
    paths, failures = verify_acceptance.artifact_paths(tmp_path, analysis, "V1")
    assert failures == []
    digest = verify_acceptance.content_digest(tmp_path, paths)
    record = version / "acceptance.yaml"
    record.write_text(
        "status: accepted\n"
        "version: V1\n"
        "analysis: docs/observability/analysis/app/V1/index.md\n"
        f"analysis_content_commit: {commit}\n"
        f"analysis_content_digest: {digest}\n"
        "analysis_pr: https://example.invalid/pr/1\n"
        "accepted_via: explicit-human-confirmation\n"
        "accepted_at: 2026-01-01T00:00:00Z\n"
        "qualifications: []\n"
        "rejected_decisions: []\n"
        f"provenance_seal_digest: {seal}\n"
    )
    return tmp_path, analysis, record, commit, digest


def test_content_bound_artifacts_pass(tmp_path):
    repo, analysis, _, commit, digest = accepted_repo(tmp_path)
    assert verify_acceptance.verify(repo, analysis, "V1", digest, commit) == []


def test_changed_artifact_fails(tmp_path):
    repo, analysis, _, commit, digest = accepted_repo(tmp_path)
    analysis.write_text("# Changed\n")
    assert any(
        "accepted content digest differs" in failure
        for failure in verify_acceptance.verify(repo, analysis, "V1", digest, commit)
    )


def test_acceptance_record_cli_is_supported(tmp_path):
    repo, _, record, _, _ = accepted_repo(tmp_path)
    assert verify_acceptance.main([
        "--record", str(record), "--repo", str(repo),
    ]) == 0


def test_record_requires_digest_and_no_person_name(tmp_path):
    record = tmp_path / "acceptance.yaml"
    record.write_text("status: accepted\nversion: V1\n")
    _, failures = verify_acceptance.parse_record(record)
    assert "acceptance record has no analysis_content_digest" in failures
    assert not any("accepted_by" in failure for failure in failures)


def test_acceptance_timestamp_must_be_rfc3339(tmp_path):
    _, _, record, _, _ = accepted_repo(tmp_path)
    record.write_text(record.read_text().replace(
        "accepted_at: 2026-01-01T00:00:00Z",
        "accepted_at: yesterday",
    ))
    _, failures = verify_acceptance.parse_record(record)
    assert "accepted_at must be RFC3339" in failures
