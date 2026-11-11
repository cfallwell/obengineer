from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "representative"
sys.path.insert(0, str(SCRIPTS))

from analysis_contract import (  # noqa: E402
    load_json,
    validate_contract,
    validate_manifest,
    validate_run_timing,
    validate_worker_results,
)
from render_analysis_site import Renderer  # noqa: E402
from validate_analysis import main as validate_analysis_main  # noqa: E402


def contract():
    return load_json(FIXTURE / "analysis-contract.json")


def manifest():
    return load_json(FIXTURE / "job-manifest.json")


def results():
    return [load_json(path) for path in sorted((FIXTURE / "results").glob("*.json"))]


def timing():
    return load_json(FIXTURE / "run-timing.json")


def test_final_worker_validation_requires_run_timing():
    with pytest.raises(SystemExit) as exc:
        validate_analysis_main([
            "--manifest",
            str(FIXTURE / "job-manifest.json"),
            "--results",
            str(FIXTURE / "results"),
        ])
    assert exc.value.code == 2


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
    assert validate_run_timing(manifest(), timing(), results()) == []


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


def test_worker_deadline_limited_degradation_and_run_timing_are_enforced():
    value = results()
    value[0]["completedAt"] = "2026-11-10T20:10:01Z"
    limited = value[3]
    limited["limitations"] = []
    limited["degradation"]["unavailableEvidenceScopes"] = ["invented scope"]
    failures = validate_worker_results(manifest(), value)
    assert any("deadlineSeconds" in failure for failure in failures)
    assert any("limited work requires limitations" in failure for failure in failures)
    assert any("exactly match manifest" in failure for failure in failures)

    run = timing()
    run["phases"]["reconciliation"]["completedAt"] = "2026-11-10T20:14:31Z"
    run["phases"]["render"]["startedAt"] = "2026-11-10T20:14:31Z"
    run["completedAt"] = "2026-11-10T20:20:01Z"
    run["phases"]["validation"]["completedAt"] = run["completedAt"]
    timing_failures = validate_run_timing(manifest(), run)
    assert any("reconciliationSeconds" in failure for failure in timing_failures)
    assert any("totalSeconds" in failure for failure in timing_failures)


def test_runnable_job_failure_is_not_a_green_audit():
    value = results()
    value[0]["status"] = "failed"
    value[0]["error"] = "The production evidence source returned an unrecoverable response."
    assert any(
        "did not produce a usable result" in failure
        for failure in validate_worker_results(manifest(), value)
    )


def test_schema_and_semantic_gates_report_independent_defects_together():
    value = contract()
    del value["operations"]["detectors"][0]["threshold"]
    value["summaries"]["strategy"] = "TBD " + value["summaries"]["strategy"]
    failures = validate_contract(value)
    assert any("missing required field threshold" in failure for failure in failures)
    assert any("placeholder" in failure for failure in failures)

    value = contract()
    value["summaries"]["strategy"] = "TBD " + value["summaries"]["strategy"]
    assert any(
        "placeholder" in failure for failure in validate_contract(value)
    )


def test_published_schema_rejects_unknown_properties_before_semantics():
    value = contract()
    value["unknown"] = "must not be ignored"
    failures = validate_contract(value)
    assert failures == ["contract.unknown: additional property is not allowed"]


def test_published_schema_rejects_path_traversal_ids():
    value = contract()
    value["findings"][0]["id"] = "../../escaped-finding"
    failures = validate_contract(value)
    assert any(
        failure.startswith("contract.findings[0].id: value does not match pattern")
        for failure in failures
    )


def test_unresolved_workflow_mapping_requires_evidence_and_forbids_fake_paths():
    value = contract()
    workflow = value["workflows"][0]
    workflow["codeMapping"] = {
        "status": "unresolved",
        "evidence": (
            "The supplied repository contains analysis artifacts only; application "
            "source and authorized implementation paths were not provided."
        ),
    }
    workflow["codeLocations"] = []
    assert validate_contract(value) == []

    workflow["codeLocations"] = ["invented/source.py"]
    failures = validate_contract(value)
    assert any(
        "unresolved workflow cannot claim code locations" in failure
        or "expected to be empty" in failure
        for failure in failures
    )


def test_unavailable_cardinality_budget_preserves_cost_without_invented_headroom():
    value = contract()
    cardinality = value["contracts"]["cardinality"]
    cardinality.update({
        "budgetStatus": "unavailable",
        "basis": (
            "The proposed MTS cost uses bounded dimension products, while entitlement "
            "and current usage were neither supplied nor measurable in this run."
        ),
        "entitlement": None,
        "inUse": None,
        "reserved": None,
        "headroomAfter": None,
    })
    assert validate_contract(value) == []

    cardinality["entitlement"] = 50000
    failures = validate_contract(value)
    assert any(
        "unavailable budget cannot claim entitlement" in failure
        or "expected null" in failure
        for failure in failures
    )


def test_transaction_catalog_keeps_unpromoted_names_and_allows_bootstrap_only_bundle():
    value = contract()
    value["businessTransactions"][0]["workflowCatalog"].append("checkout.review")

    bootstrap = copy.deepcopy(value["businessTransactions"][0])
    bootstrap.update({
        "id": "global",
        "name": "Global bootstrap",
        "groupingValue": "global",
        "artifact": "src/bootstrap/observability.ts",
        "summary": (
            "The global bootstrap owns provider initialization and shared platform "
            "concerns, so emitting a user workflow from it would misclassify activity."
        ),
        "catalogStatus": "none-by-design",
        "catalogEvidence": (
            "Source ownership assigns initialization, route subscription, consent, "
            "and propagation setup to this artifact rather than a user intent."
        ),
        "workflowCatalog": [],
        "workflowIds": [],
    })
    value["businessTransactions"].append(bootstrap)

    assert validate_contract(value) == []


def test_unresolved_work_order_mapping_stays_blocked_without_invented_legs():
    value = contract()
    order = value["workOrders"][0]
    order.update({
        "status": "blocked",
        "repositoryMapping": {
            "status": "unresolved",
            "evidence": (
                "The engagement repository contains analysis artifacts only; the "
                "application repository and authorized implementation paths were not supplied."
            ),
        },
        "repositoryLegs": [],
    })
    assert validate_contract(value) == []

    order["status"] = "proposed"
    failures = validate_contract(value)
    assert any(
        "unresolved repository mapping requires blocked status" in failure
        or "expected constant 'blocked'" in failure
        for failure in failures
    )


def test_renderer_refuses_to_write_outside_version_root(tmp_path):
    output = tmp_path / "docs" / "observability" / "analysis" / "app" / "V1"
    renderer = Renderer(contract(), output)
    with pytest.raises(ValueError, match="outside version root"):
        renderer.write("findings/../../escaped-finding.md", "escaped")
    assert not (output.parent / "escaped-finding.md").exists()


def test_invalid_path_id_cannot_render_any_output(tmp_path):
    value = contract()
    value["findings"][0]["id"] = "../../escaped-finding"
    output = tmp_path / "docs" / "observability" / "analysis" / "app" / "V1"
    with pytest.raises(ValueError, match="invalid contract"):
        Renderer(value, output).render()
    assert not output.exists()
    assert not (output.parent / "escaped-finding.md").exists()


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
    message = value["contracts"]["crossCutting"]["messagePropagation"]
    message["code"] = message["code"].replace("links", "refs")
    failures = validate_contract(value)
    assert any("attribution.code: missing localStorage" in failure for failure in failures)
    assert any("span-link joins require executable links code" in failure for failure in failures)


def without_bus_and_collector(value):
    value["architecture"]["buses"] = []
    value["contracts"]["crossCutting"]["messagePropagation"] = {
        "applicable": False,
        "evidence": "No message bus or asynchronous carrier exists in the observed application boundary.",
    }
    value["technology"] = [
        item for item in value["technology"] if "collector" not in item["name"].lower()
    ]
    value["contracts"]["collector"] = {
        "applicable": False,
        "evidence": "No Collector deployment or pipeline configuration exists in supplied evidence.",
    }
    return value


def test_api_only_browser_only_and_no_bus_applicability(tmp_path):
    browser = without_bus_and_collector(contract())
    assert validate_contract(browser) == []
    del browser["contracts"]["attribution"]["code"]
    assert any("attribution.code" in failure for failure in validate_contract(browser))

    api = without_bus_and_collector(contract())
    api["architecture"]["frontend"] = {
        "applicable": False,
        "evidence": "The application exposes API services only and has no browser runtime or routes.",
    }
    api["contracts"]["spaRoutes"] = {
        "applicable": False,
        "evidence": "No browser runtime or client-side route transitions exist in the application.",
    }
    api["contracts"]["attribution"] = {
        "applicable": False,
        "evidence": "No browser sessions or campaign parameters exist in the application boundary.",
    }
    assert validate_contract(api) == []
    output = tmp_path / "docs" / "observability" / "analysis" / "api" / "V1"
    Renderer(api, output).render()
    for page in ("attribution.md", "collector.md", "single-init-spa-routes.md"):
        assert not (output / "contracts" / page).exists()
        assert page not in (output / "contracts" / "index.md").read_text()

    invalid = contract()
    invalid["architecture"]["buses"] = []
    assert any(
        "messagePropagation.applicable" in failure
        for failure in validate_contract(invalid)
    )


def test_telemetry_workflow_and_lexical_quality_mutations_fail():
    value = contract()
    del value["currentTelemetry"][0]["applicationScope"]
    value["currentTelemetry"][1]["portfolioEvidence"] = {
        "disposition": "unavailable",
        "reason": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    }
    value["workflows"][0]["codeLocations"] = ["../outside.py"]
    value["workflows"][0]["narrative"] = "word " * 20
    failures = validate_contract(value)
    assert any("applicationScope" in failure for failure in failures)
    assert any("distinct lexical tokens" in failure for failure in failures)
    assert any("authorized relative code path" in failure for failure in failures)


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
    timing_schema = json.loads((SKILL / "schemas" / "analysis-run-timing.schema.json").read_text())
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
    definitions = contract_schema["$defs"]
    assert {"applicationScope", "observedFrom", "observedTo", "readAt", "source",
            "provenance", "portfolioEvidence"} <= set(
        definitions["telemetry"]["required"]
    )
    assert {"codeMapping", "codeLocations"} <= set(definitions["workflow"]["required"])
    assert set(definitions["frontend"]["required"]) == {"applicable", "evidence"}
    message_schema = definitions["contracts"]["properties"]["crossCutting"][
        "properties"
    ]["messagePropagation"]
    assert set(message_schema["required"]) == {"applicable", "evidence"}
    assert message_schema["allOf"][0]["then"]["required"] == ["code"]
    assert set(worker_schema["required"]) >= {"startedAt", "completedAt", "evidence", "facts"}
    assert worker_schema["allOf"][0]["then"]["required"] == ["degradation"]
    assert set(timing_schema["properties"]["phases"]["required"]) == {
        "collection", "reconciliation", "render", "validation"
    }
