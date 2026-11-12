from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


plan_verifier = load("verify_plan")
result_verifier = load("verify_results")
aggregator = load("aggregate_outcomes")
publisher = load("publish_outcome_issue")


def write(tmp_path: Path, name: str, data: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def plan() -> dict:
    return {
        "schema_version": 2,
        "criteria": [{
            "id": "VC-001",
            "source_ref": "operations/verification#VC-001",
            "system": "splunk-observability",
            "query": {"kind": "signalflow", "reference": "SRC-001"},
            "expected": {"operator": "equals", "value": True},
            "observation_window": "PT30M",
            "owner": "platform",
            "remediation": {
                "route": "implementation",
                "selector": "work-order:WO-001",
                "instructions": "Run the work order, deploy, then recheck.",
            },
        }, {
            "id": "VC-002",
            "source_ref": "operations/verification#VC-002",
            "system": "terraform",
            "query": {"kind": "state-read", "reference": "SRC-002"},
            "expected": {"operator": "exists"},
            "observation_window": "PT1M",
            "owner": "platform",
            "remediation": {
                "route": "human-owner",
                "instructions": "Confirm vendor support and recheck.",
            },
        }],
    }


def acceptance_record(tmp_path: Path, commit: str) -> Path:
    acceptance = tmp_path / "acceptance.yaml"
    acceptance.write_text(
        "schema_version: 2\n"
        "status: accepted\n"
        "version: V1\n"
        "analysis: docs/observability/analysis/app/V1/index.md\n"
        f"analysis_content_commit: {commit}\n"
        f"analysis_content_digest: {'c' * 64}\n"
        "analysis_pr: https://example.invalid/pr/1\n"
        "accepted_via: explicit-human-confirmation\n"
        "accepted_at: 2026-11-09T00:00:00Z\n"
        "qualifications: []\n"
        "rejected_decisions: []\n"
        f"provenance_seal_digest: {'d' * 64}\n"
    )
    return acceptance


def test_plan_requires_actionable_remediation(tmp_path):
    data = plan()
    assert plan_verifier.verify(write(tmp_path, "plan.json", data)) == []
    data["criteria"][0]["remediation"].pop("instructions")
    assert any(
        "remediation instructions" in item
        for item in plan_verifier.verify(write(tmp_path, "bad-plan.json", data))
    )
    data = plan()
    data["criteria"][0]["query"] = {
        "kind": "signalflow",
        "operation": "update",
        "method": "POST",
        "endpoint": "/v2/detector",
    }
    assert any(
        "operation is not read-only" in item
        for item in plan_verifier.verify(write(tmp_path, "mutating-plan.json", data))
    )
    data = plan()
    data["criteria"][0]["query"]["filter"] = "deployment.environment=prod"
    assert plan_verifier.verify(write(tmp_path, "filtered-plan.json", data)) == []


def test_plan_v1_source_section_remains_readable(tmp_path):
    data = plan()
    data["schema_version"] = 1
    for criterion in data["criteria"]:
        criterion["source_section"] = 17
        criterion.pop("source_ref")
    assert plan_verifier.verify(write(tmp_path, "legacy-plan.json", data)) == []


def test_plan_v2_requires_stable_source_ref(tmp_path):
    data = plan()
    data["criteria"][0]["source_ref"] = "17"
    assert any(
        "source_ref is invalid" in item
        for item in plan_verifier.verify(write(tmp_path, "bad-plan.json", data))
    )


def test_results_omit_human_exclusion_and_require_notification(tmp_path):
    commit = "a" * 40
    plan_path = write(tmp_path, "plan.json", plan())
    excluded = write(tmp_path, "exclusions.json", {
        "schema_version": 2,
        "analysis_content_commit": commit,
        "exclusions": [{
            "criterion_id": "VC-002",
            "decision": "unremediable",
            "reason_code": "vendor-limitation",
            "rationale": "No supported control.",
            "approved_by": "owner",
            "approved_at": "2026-11-09T00:00:00Z",
            "review_at": "2027-11-09T00:00:00Z",
            "evidence_refs": ["FACT-001"],
        }],
    })
    row = {
        "criterion_id": "VC-001",
        "status": "unmet",
        "evidence_refs": ["CHECK-001"],
        "expected": True,
        "observed": False,
        "owner": "platform",
        "remediation_route": "implementation",
        "remediation_instructions": "Run WO-001.",
        "next_command": "/ob-implement work-order:WO-001",
        "recheck_instructions": "Deploy, then rerun VC-001.",
        "human_notification": "VC-001 is unmet; run WO-001.",
    }
    results_data = {
        "schema_version": 2,
        "analysis_content_commit": commit,
        "results": [row],
        "summary": {
            "accepted": 2, "excluded": 1, "eligible": 1,
            "met": 0, "unmet": 1, "unmeasurable": 0,
        },
    }
    results = write(tmp_path, "results.json", results_data)
    assert result_verifier.verify(plan_path, results, excluded) == []
    row.pop("human_notification")
    results = write(tmp_path, "results.json", results_data)
    assert any(
        "human_notification" in item
        for item in result_verifier.verify(plan_path, results, excluded)
    )


def test_results_v1_commit_name_remains_readable(tmp_path):
    commit = "a" * 40
    plan_path = write(tmp_path, "plan.json", plan())
    results = write(tmp_path, "results.json", {
        "schema_version": 1,
        "analysis_commit": commit,
        "results": [{
            "criterion_id": criterion["id"],
            "status": "met",
            "evidence_refs": ["CHECK-001"],
        } for criterion in plan()["criteria"]],
        "summary": {
            "accepted": 2, "excluded": 0, "eligible": 2,
            "met": 2, "unmet": 0, "unmeasurable": 0,
        },
    })
    assert result_verifier.verify(plan_path, results) == []


def test_results_cli_exits_nonzero_for_valid_unmet_result(tmp_path):
    commit = "a" * 40
    plan_path = write(tmp_path, "plan.json", plan())
    ledger = write(tmp_path, "ledger.json", {
        "schema_version": 1,
        "engagement": {"application": "app"},
        "contract": {"sealed_ids": []},
        "context_profile": {"predicates": {}, "loaded_references": []},
        "checks": [{"id": "CHECK-001"}],
        "sources": [], "facts": [], "runs": [], "artifacts": [],
        "decisions": [], "unresolved": [],
        "seals": {
            "analysis": {
                "ids": [],
                "digest": hashlib.sha256(b"[]").hexdigest(),
            }
        },
    })
    results = write(tmp_path, "results.json", {
        "schema_version": 2,
        "analysis_content_commit": commit,
        "results": [{
            "criterion_id": "VC-001", "status": "unmet",
            "evidence_refs": ["CHECK-001"], "expected": True,
            "observed": False, "owner": "platform",
            "remediation_route": "implementation",
            "remediation_instructions": "Run WO-001.",
            "next_command": "/ob-implement work-order:WO-001",
            "recheck_instructions": "Deploy and rerun.",
            "human_notification": "VC-001 is unmet.",
        }, {
            "criterion_id": "VC-002", "status": "met",
            "evidence_refs": ["CHECK-001"],
        }],
        "summary": {
            "accepted": 2, "excluded": 0, "eligible": 2,
            "met": 1, "unmet": 1, "unmeasurable": 0,
        },
    })
    acceptance = acceptance_record(tmp_path, commit)
    completed = subprocess.run([
        sys.executable, str(SCRIPTS / "verify_results.py"),
        str(plan_path), str(results), "--ledger", str(ledger),
        "--acceptance", str(acceptance),
    ], capture_output=True, text=True)
    assert completed.returncode == 2
    assert "PASS" in completed.stdout


def test_unmeasurable_lowers_coverage_not_miss_rate():
    output, failures = aggregator.aggregate({"opportunities": [{
        "metric": "dimension-miss", "outcome": "met",
        "cohort": "first-apply-1",
        "collection_point": "first-post-apply-verification",
        "first_apply": "apply-1", "panel": "panel-1", "dimension_key": "market",
    }, {
        "metric": "dimension-miss", "outcome": "unmeasurable",
        "cohort": "first-apply-1",
        "collection_point": "first-post-apply-verification",
        "first_apply": "apply-1", "panel": "panel-2", "dimension_key": "market",
    }]})
    assert failures == []
    metric = output["metrics"]["dimension-miss"]
    assert metric["rate"] == 0
    assert metric["measurement_coverage"] == 0.5
    assert metric["numerator"] == 0
    assert metric["denominator"] == 1


def test_results_reject_invalid_schema_commit_and_evidence_shape(tmp_path):
    plan_path = write(tmp_path, "plan.json", plan())
    results = write(tmp_path, "results.json", {
        "schema_version": 99,
        "analysis_content_commit": "short",
        "results": [{
            "criterion_id": "VC-001", "status": "met",
            "evidence_refs": "CHECK-001",
        }, {
            "criterion_id": "VC-002", "status": "met",
            "evidence_refs": ["CHECK-001"],
        }],
        "summary": {
            "accepted": 2, "excluded": 0, "eligible": 2,
            "met": 2, "unmet": 0, "unmeasurable": 0,
        },
    })
    failures = result_verifier.verify(plan_path, results)
    assert "verification results schema_version must be 1 or 2" in failures
    assert not any("content commit" in failure for failure in failures)
    assert any("needs ledger evidence_refs" in item for item in failures)
    acceptance = acceptance_record(tmp_path, "b" * 40)
    assert "verification results commit does not match acceptance record" in \
        result_verifier.verify(
            plan_path, results, acceptance_path=acceptance
        )


def test_outcome_issue_is_stable_and_rejects_sensitive_data():
    payload = {
        "canonical_reference": "rubric:dimension-budget",
        "spec_commit": "b" * 40,
        "outcome_class": "dimension-miss",
        "defect_class": "attribute-only-grouping",
        "numerator": 2,
        "denominator": 10,
        "coverage": 0.8,
        "consequence_code": "empty-panel",
        "proposed_change": "Require index verification before plan.",
        "deny_terms": ["Example Customer", "owner/private-repo"],
    }
    first = publisher.build(payload)
    assert first == publisher.build(payload)
    payload["customer_url"] = "https://customer.example"
    try:
        publisher.build(payload)
    except ValueError as exc:
        assert "forbidden fields" in str(exc)
    else:
        raise AssertionError("sensitive outcome payload was accepted")
    payload.pop("customer_url")
    payload["spec_commit"] = "short"
    try:
        publisher.build(payload)
    except ValueError as exc:
        assert "full lowercase SHA" in str(exc)
    else:
        raise AssertionError("invalid spec commit was accepted")


def test_outcome_publish_uses_existing_auth_and_creates(monkeypatch):
    calls = []

    def execute(args):
        calls.append(args)
        if args[1:3] == ["auth", "status"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[1:3] == ["issue", "list"]:
            return subprocess.CompletedProcess(args, 0, "[]", "")
        return subprocess.CompletedProcess(args, 0, "https://github.com/x/1\n", "")

    monkeypatch.setattr(publisher.shutil, "which", lambda _: "/usr/bin/gh")
    code, _ = publisher.publish("title", "body", "a" * 64, execute=execute)
    assert code == 0
    assert any(call[1:3] == ["issue", "create"] for call in calls)


def test_outcome_publish_provides_web_login_when_unauthenticated(monkeypatch):
    def execute(args):
        return subprocess.CompletedProcess(args, 1, "", "not logged in")

    monkeypatch.setattr(publisher.shutil, "which", lambda _: "/usr/bin/gh")
    code, message = publisher.publish(
        "title", "body", "a" * 64, execute=execute
    )
    assert code == 2
    assert "gh auth login --web" in message
    assert "https://github.com/login/device" in message


def test_publish_requires_separately_approved_preview_hash(tmp_path):
    payload = write(tmp_path, "outcome.json", {
        "canonical_reference": "rubric:dimension-budget",
        "spec_commit": "b" * 40,
        "outcome_class": "dimension-miss",
        "defect_class": "attribute-only-grouping",
        "numerator": 2,
        "denominator": 10,
        "coverage": 0.8,
        "consequence_code": "empty-panel",
        "proposed_change": "Require index verification.",
        "deny_terms": ["Example Customer", "owner/private-repo"],
    })
    assert publisher.main([
        str(payload), "--publish", "--approved-preview", "wrong"
    ]) == 1
