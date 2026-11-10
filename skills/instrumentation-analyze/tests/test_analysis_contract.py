from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "representative"
sys.path.insert(0, str(SCRIPTS))

from analysis_contract import (  # noqa: E402
    load_json,
    validate_contract,
    validate_manifest,
    validate_worker_results,
)
from render_analysis_site import Renderer  # noqa: E402


def contract():
    return load_json(FIXTURE / "analysis-contract.json")


def manifest():
    return load_json(FIXTURE / "job-manifest.json")


def results():
    return [load_json(path) for path in sorted((FIXTURE / "results").glob("*.json"))]


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_representative_contract_and_job_audit_pass():
    assert validate_contract(contract()) == []
    assert validate_manifest(manifest()) == []
    assert validate_worker_results(manifest(), results()) == []


def test_manifest_reserves_coordinator_and_never_claims_repository_launch():
    value = manifest()
    value["executionAuthority"] = "repository"
    value["repositoryCapability"] = "spawn"
    value["hostConcurrency"]["coordinatorSlots"] = 0
    failures = validate_manifest(value)
    assert any("cannot launch workers" in failure for failure in failures)
    assert any("audit-only" in failure for failure in failures)
    assert any("exactly one slot" in failure for failure in failures)


def test_manifest_enforces_analysis_time_budgets():
    value = manifest()
    value["performanceBudgets"]["totalSeconds"] = 1201
    value["performanceBudgets"]["progressIntervalSeconds"] = 61
    value["jobs"][0]["deadlineSeconds"] = 601
    failures = validate_manifest(value)
    assert any("totalSeconds" in failure for failure in failures)
    assert any("progressIntervalSeconds" in failure for failure in failures)
    assert any("deadlineSeconds" in failure for failure in failures)


def test_two_or_more_runnable_jobs_must_overlap():
    value = results()
    for index, result in enumerate(value):
        minute = index * 10
        result["startedAt"] = f"2026-11-10T20:{minute:02d}:00Z"
        result["completedAt"] = f"2026-11-10T20:{minute + 5:02d}:00Z"
    assert any(
        "overlapping execution intervals" in failure
        for failure in validate_worker_results(manifest(), value)
    )


def test_collection_wall_time_must_fit_manifest_budget():
    value = results()
    value[-1]["completedAt"] = "2026-11-10T20:11:00Z"
    assert any(
        "collection wall time" in failure
        for failure in validate_worker_results(manifest(), value)
    )


def test_runnable_job_failure_is_not_a_green_audit():
    value = results()
    value[0]["status"] = "failed"
    value[0]["error"] = "The production evidence source returned an unrecoverable response."
    assert any(
        "did not produce a usable result" in failure
        for failure in validate_worker_results(manifest(), value)
    )


def test_semantic_gate_rejects_missing_detector_fields_and_placeholders():
    value = contract()
    del value["operations"]["detectors"][0]["threshold"]
    value["summaries"]["strategy"] = "TBD " + value["summaries"]["strategy"]
    failures = validate_contract(value)
    assert any("missing required field threshold" in failure for failure in failures)
    assert any("placeholder" in failure for failure in failures)


def test_semantic_gate_rejects_malformed_conditional_operations():
    value = contract()
    value["operations"]["synthetics"] = {}
    failures = validate_contract(value)
    assert any("operations.synthetics" in failure for failure in failures)


def test_semantic_gate_requires_first_touch_and_span_link_code():
    value = contract()
    value["contracts"]["attribution"]["code"] = (
        value["contracts"]["attribution"]["code"].replace("localStorage", "memory")
    )
    value["contracts"]["crossCutting"]["messagePropagation"] = (
        value["contracts"]["crossCutting"]["messagePropagation"].replace("links", "refs")
    )
    failures = validate_contract(value)
    assert any("attribution.code: missing localStorage" in failure for failure in failures)
    assert any("span-link joins require executable links code" in failure for failure in failures)


def test_cardinality_arithmetic_is_checked():
    value = contract()
    value["contracts"]["cardinality"]["headroomAfter"] += 1
    assert any(
        "entitlement - inUse - reserved - proposedCost" in failure
        for failure in validate_contract(value)
    )


def test_render_is_deterministic_and_full_tree_is_linked(tmp_path):
    value = contract()
    first = (
        tmp_path / "first" / "docs" / "observability" / "analysis" /
        value["application"]["id"] / value["application"]["version"]
    )
    second = (
        tmp_path / "second" / "docs" / "observability" / "analysis" /
        value["application"]["id"] / value["application"]["version"]
    )
    Renderer(copy.deepcopy(value), first).render()
    Renderer(copy.deepcopy(value), second).render()
    assert digest_tree(first) == digest_tree(second)
    for required in (
        "overview/index.md",
        "technology/index.md",
        "telemetry/index.md",
        "findings/index.md",
        "strategy/index.md",
        "implementation/index.md",
        "work-orders/index.md",
        "use-cases/index.md",
        "workflows/index.md",
        "business-transactions/index.md",
        "contracts/index.md",
        "operations/index.md",
        "reference/index.md",
    ):
        assert (first / required).is_file()
    assert not list((first / "work-orders").glob("WO-*.md"))
    work_order_index = (first / "work-orders" / "index.md").read_text()
    assert "wiki/apps/" in work_order_index
    assert "Open canonical work order" in work_order_index


def test_empty_optional_architecture_catalogue_does_not_render_empty_heading(tmp_path):
    value = contract()
    value["architecture"]["thirdParties"] = []
    output = tmp_path / "docs" / "observability" / "analysis" / "app" / "V1"
    Renderer(value, output).render()
    assert "Third parties by consequence" not in (
        output / "overview" / "index.md"
    ).read_text()


def test_inapplicable_path_products_are_omitted_from_operations_view(tmp_path):
    value = contract()
    value["operations"]["synthetics"]["applicable"] = False
    value["operations"]["thousandEyes"]["applicable"] = False
    output = tmp_path / "docs" / "observability" / "analysis" / "app" / "V1"
    Renderer(value, output).render()
    operations = (output / "operations" / "index.md").read_text()
    assert "**Synthetics:**" not in operations
    assert "**ThousandEyes:**" not in operations


def test_published_json_schemas_capture_bounded_jobs_and_required_objects():
    job_schema = json.loads((SKILL / "schemas" / "analysis-job-manifest.schema.json").read_text())
    contract_schema = json.loads((SKILL / "schemas" / "analysis-contract.schema.json").read_text())
    worker_schema = json.loads((SKILL / "schemas" / "analysis-worker-result.schema.json").read_text())
    assert job_schema["properties"]["jobs"]["maxItems"] == 6
    assert job_schema["properties"]["performanceBudgets"]["properties"][
        "totalSeconds"
    ]["maximum"] == 1200
    assert job_schema["properties"]["hostConcurrency"]["properties"]["coordinatorSlots"]["const"] == 1
    assert set(contract_schema["required"]) >= {
        "architecture",
        "useCases",
        "workflows",
        "contracts",
        "operations",
    }
    assert set(worker_schema["required"]) >= {"startedAt", "completedAt", "evidence", "facts"}
