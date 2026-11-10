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


def detached_commit(repo: Path, tree: str, message: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "commit-tree", tree],
        check=True,
        capture_output=True,
        text=True,
        input=message,
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
    (docs / "analysis-contract.json").write_text('{"schema_version":2}\n')
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
        "schema_version": 2,
        "criteria": [{
            "id": "VC-001",
            "source_ref": "operations/verification#VC-001",
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
        "schema_version: 2\n"
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


def add_v2(repo: Path) -> tuple[Path, Path, str, str]:
    docs = repo / "docs" / "observability"
    analysis = docs / "analysis" / "app" / "V2" / "index.md"
    analysis.parent.mkdir(parents=True)
    analysis.write_text("[V1] **[V2]**\n\n# Analysis V2\n")
    wiki = repo / "wiki" / "apps" / "app"
    version = wiki / "versions" / "V2"
    work_orders = version / "implementation" / "work-orders"
    work_orders.mkdir(parents=True)
    (version / "index.md").write_text("# Wiki V2\n")
    (work_orders / "WO-001.md").write_text("# Ready V2 work\n")
    (wiki / "index.md").write_text(
        "# App versions\n\nAccepted version: [V2](versions/V2/index.md)\n"
    )
    (docs / "attribute-schema.json").write_text('{"version":"V2"}\n')
    (docs / "analysis-contract.json").write_text('{"schema_version":2,"version":"V2"}\n')
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "analysis V2")
    commit = git(repo, "rev-parse", "HEAD")
    paths, failures = verify_acceptance.artifact_paths(repo, analysis, "V2")
    assert failures == []
    digest = verify_acceptance.content_digest(repo, paths)
    record = analysis.parent / "acceptance.yaml"
    v1_record = docs / "analysis" / "app" / "V1" / "acceptance.yaml"
    record.write_text(
        v1_record.read_text()
        .replace("version: V1", "version: V2")
        .replace(
            "analysis: docs/observability/analysis/app/V1/index.md",
            "analysis: docs/observability/analysis/app/V2/index.md",
        )
        .replace(
            next(
                line for line in v1_record.read_text().splitlines()
                if line.startswith("analysis_content_commit:")
            ),
            f"analysis_content_commit: {commit}",
        )
        .replace(
            next(
                line for line in v1_record.read_text().splitlines()
                if line.startswith("analysis_content_digest:")
            ),
            f"analysis_content_digest: {digest}",
        )
    )
    return analysis, record, commit, digest


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


def test_analysis_commit_must_contain_the_accepted_artifact_tree(tmp_path):
    repo, analysis, _, _, digest = accepted_repo(tmp_path)
    empty_tree = git(repo, "hash-object", "-t", "tree", "/dev/null")
    unrelated = detached_commit(repo, empty_tree, "unrelated\n")
    failures = verify_acceptance.verify(
        repo, analysis, "V1", digest, unrelated
    )
    assert any(
        "has no analysis tree" in failure for failure in failures
    )


def test_content_equivalent_rewritten_commit_remains_valid(tmp_path):
    repo, analysis, _, commit, digest = accepted_repo(tmp_path)
    tree = git(repo, "rev-parse", f"{commit}^{{tree}}")
    rewritten = detached_commit(repo, tree, "rewritten without ancestry\n")
    assert verify_acceptance.verify(
        repo, analysis, "V1", digest, rewritten
    ) == []


def test_legacy_digest_survives_later_analysis_contract(tmp_path):
    repo, analysis, _, commit, _ = accepted_repo(tmp_path)
    paths, failures = verify_acceptance.artifact_paths(
        repo, analysis, "V1", schema_version=1
    )
    assert failures == []
    legacy_paths = [
        path for path in paths if path.name != "analysis-contract.json"
    ]
    legacy_digest = verify_acceptance.content_digest(repo, legacy_paths)
    assert verify_acceptance.verify(
        repo, analysis, "V1", legacy_digest, commit, schema_version=1
    ) == []


def test_selected_v2_discovery_and_historical_v1_are_both_verifiable(tmp_path):
    repo, v1_analysis, v1_record, v1_commit, v1_digest = accepted_repo(tmp_path)
    v2_analysis, v2_record, v2_commit, v2_digest = add_v2(repo)

    discovered, failures = verify_acceptance.discover_acceptance(repo)
    assert failures == []
    assert discovered == v2_record
    assert verify_acceptance.verify(
        repo, v2_analysis, "V2", v2_digest, v2_commit
    ) == []
    assert verify_acceptance.verify(
        repo, v1_analysis, "V1", v1_digest, v1_commit
    ) == []
    assert verify_acceptance.main([
        "--record", str(v1_record), "--repo", str(repo),
    ]) == 0


def test_legacy_v1_uses_commit_companions_after_v2_changes(tmp_path):
    repo, analysis, _, commit, _ = accepted_repo(tmp_path)
    committed, failures = verify_acceptance.commit_artifacts(
        repo, analysis, "V1", commit, schema_version=1
    )
    assert failures == []
    committed.pop("docs/observability/analysis-contract.json", None)
    legacy_digest = verify_acceptance.bytes_digest(committed)
    add_v2(repo)

    assert verify_acceptance.verify(
        repo, analysis, "V1", legacy_digest, commit, schema_version=1
    ) == []


def test_acceptance_record_cli_is_supported(tmp_path):
    repo, _, record, _, _ = accepted_repo(tmp_path)
    assert verify_acceptance.main([
        "--record", str(record), "--repo", str(repo),
    ]) == 0


def test_acceptance_record_is_discovered_at_version_path(tmp_path):
    repo, _, _, _, _ = accepted_repo(tmp_path)
    assert verify_acceptance.main(["--repo", str(repo)]) == 0


def test_acceptance_discovery_rejects_ambiguity(tmp_path):
    repo, _, record, _, _ = accepted_repo(tmp_path)
    other = record.parents[2] / "other" / "V1"
    other.mkdir(parents=True)
    (other / "acceptance.yaml").write_text(record.read_text())
    _, failures = verify_acceptance.discover_acceptance(repo)
    assert any("ambiguous" in failure for failure in failures)


def test_record_requires_digest_and_no_person_name(tmp_path):
    record = tmp_path / "acceptance.yaml"
    record.write_text("schema_version: 2\nstatus: accepted\nversion: V1\n")
    _, failures = verify_acceptance.parse_record(record)
    assert "acceptance record has no analysis_content_digest" in failures
    assert not any("accepted_by" in failure for failure in failures)


def test_legacy_record_migrates_analysis_commit_without_v2_artifacts(tmp_path):
    record = tmp_path / "acceptance.yaml"
    record.write_text(
        "status: accepted\n"
        "version: V1\n"
        "analysis: docs/observability/analysis/app/V1/index.md\n"
        f"analysis_commit: {'a' * 40}\n"
        "analysis_pr: https://example.invalid/pr/1\n"
        "accepted_via: explicit-human-confirmation\n"
        "accepted_at: 2026-01-01T00:00:00Z\n"
        "qualifications: []\n"
        "rejected_decisions: []\n"
    )
    fields, failures = verify_acceptance.parse_record(record)
    assert failures == []
    assert fields["schema_version"] == 1
    assert fields["analysis_content_commit"] == "a" * 40


def test_v2_rejects_legacy_commit_name(tmp_path):
    _, _, record, _, _ = accepted_repo(tmp_path)
    record.write_text(
        record.read_text().replace(
            "analysis_content_commit:", "analysis_commit:"
        )
    )
    _, failures = verify_acceptance.parse_record(record)
    assert any("uses analysis_content_commit" in failure for failure in failures)


def test_acceptance_timestamp_must_be_rfc3339(tmp_path):
    _, _, record, _, _ = accepted_repo(tmp_path)
    record.write_text(record.read_text().replace(
        "accepted_at: 2026-01-01T00:00:00Z",
        "accepted_at: yesterday",
    ))
    _, failures = verify_acceptance.parse_record(record)
    assert "accepted_at must be RFC3339" in failures
