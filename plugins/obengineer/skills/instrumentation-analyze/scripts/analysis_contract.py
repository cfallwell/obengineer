#!/usr/bin/env python3
"""Deterministic structural and semantic validation for analysis artifacts."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

JOB_IDS = (
    "production",
    "source-technology",
    "diagrams-prior-artifacts",
    "observability-cloud",
    "platform-cloud-messaging",
    "public-security",
)
SUMMARY_KEYS = (
    "architecture",
    "technology",
    "currentTelemetry",
    "findings",
    "strategy",
    "implementationPath",
    "workOrders",
    "useCases",
    "workflows",
    "businessTransactions",
    "contracts",
    "operations",
    "reference",
)
TOP_LEVEL_KEYS = (
    "schemaVersion",
    "application",
    "summaries",
    "architecture",
    "technology",
    "currentTelemetry",
    "findings",
    "strategy",
    "implementationPhases",
    "workOrders",
    "useCases",
    "workflows",
    "businessTransactions",
    "contracts",
    "operations",
    "reference",
)
PLACEHOLDER = re.compile(
    r"(?:\bTBD\b|\bTODO\b|\bFIXME\b|lorem ipsum|not in evidence|"
    r"\bplaceholder\b|<(?!(?:https?://|/?[a-z][a-z0-9-]*>))[A-Za-z][^>\n]{0,50}>)",
    re.IGNORECASE,
)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _require(
    obj: Any,
    fields: Iterable[str],
    path: str,
    failures: list[str],
) -> bool:
    if not isinstance(obj, dict):
        failures.append(f"{path}: expected object")
        return False
    for field in fields:
        if field not in obj:
            failures.append(f"{path}: missing required field {field}")
        elif obj[field] is None or obj[field] == "":
            failures.append(f"{path}.{field}: required value is empty")
    return True


def _list(obj: Any, path: str, failures: list[str], minimum: int = 1) -> list[Any]:
    if not isinstance(obj, list):
        failures.append(f"{path}: expected array")
        return []
    if len(obj) < minimum:
        failures.append(f"{path}: expected at least {minimum} item(s)")
    return obj


def _substantive(value: Any, path: str, failures: list[str], minimum: int = 80) -> None:
    if not isinstance(value, str) or len(value.strip()) < minimum:
        failures.append(f"{path}: requires at least {minimum} characters of substantive content")


def _scan_placeholders(value: Any, path: str, failures: list[str]) -> None:
    if isinstance(value, dict):
        for key in sorted(value):
            _scan_placeholders(value[key], f"{path}.{key}", failures)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_placeholders(item, f"{path}[{index}]", failures)
    elif isinstance(value, str) and PLACEHOLDER.search(value):
        failures.append(f"{path}: unresolved placeholder text")


def _scan_join_types(value: Any, path: str, failures: list[str]) -> None:
    if isinstance(value, dict):
        if {"from", "to", "type", "carrier", "reason"} <= set(value):
            if value["type"] not in {"continue-trace", "span-link", "attribute-pivot"}:
                failures.append(
                    f"{path}.type: join must be continue-trace, span-link, or attribute-pivot"
                )
        for key in sorted(value):
            _scan_join_types(value[key], f"{path}.{key}", failures)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_join_types(item, f"{path}[{index}]", failures)


def _collect_evidence_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "evidenceIds" and isinstance(child, list):
                refs.update(item for item in child if isinstance(item, str))
            else:
                refs.update(_collect_evidence_refs(child))
    elif isinstance(value, list):
        for item in value:
            refs.update(_collect_evidence_refs(item))
    return refs


def _parse_time(value: Any, path: str, failures: list[str]) -> datetime | None:
    if not isinstance(value, str):
        failures.append(f"{path}: expected RFC3339 timestamp")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            failures.append(f"{path}: RFC3339 timestamp requires a timezone")
            return None
        return parsed
    except ValueError:
        failures.append(f"{path}: invalid RFC3339 timestamp")
        return None


def _unique_ids(
    values: list[Any],
    path: str,
    failures: list[str],
    key: str = "id",
) -> set[str]:
    ids: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, dict) or not isinstance(value.get(key), str):
            failures.append(f"{path}[{index}]: missing string {key}")
            continue
        identifier = value[key]
        if identifier in ids:
            failures.append(f"{path}: duplicate {key} {identifier}")
        ids.add(identifier)
    return ids


def validate_manifest(manifest: Any) -> list[str]:
    failures: list[str] = []
    if not _require(
        manifest,
        (
            "schemaVersion",
            "analysisId",
            "executionAuthority",
            "repositoryCapability",
            "hostConcurrency",
            "jobs",
        ),
        "manifest",
        failures,
    ):
        return failures
    if manifest.get("schemaVersion") != 1:
        failures.append("manifest.schemaVersion: expected 1")
    if manifest.get("executionAuthority") != "host":
        failures.append("manifest.executionAuthority: repository cannot launch workers; expected host")
    if manifest.get("repositoryCapability") != "audit-only":
        failures.append("manifest.repositoryCapability: expected audit-only")
    concurrency = manifest.get("hostConcurrency")
    if _require(concurrency, ("maxConcurrentAgents", "coordinatorSlots"), "manifest.hostConcurrency", failures):
        if concurrency.get("coordinatorSlots") != 1:
            failures.append("manifest.hostConcurrency.coordinatorSlots: exactly one slot is required")
        if not isinstance(concurrency.get("maxConcurrentAgents"), int) or concurrency["maxConcurrentAgents"] < 2:
            failures.append("manifest.hostConcurrency.maxConcurrentAgents: expected integer >= 2")
    jobs = _list(manifest.get("jobs"), "manifest.jobs", failures, 6)
    if len(jobs) > 6:
        failures.append("manifest.jobs: at most 6 jobs are allowed")
    ids = _unique_ids(jobs, "manifest.jobs", failures)
    if ids != set(JOB_IDS):
        missing = sorted(set(JOB_IDS) - ids)
        extra = sorted(ids - set(JOB_IDS))
        failures.append(f"manifest.jobs: required workstreams differ; missing={missing}, extra={extra}")
    for index, job in enumerate(jobs):
        path = f"manifest.jobs[{index}]"
        if not _require(
            job,
            ("id", "title", "runnable", "evidenceScopes", "requiredOutputs"),
            path,
            failures,
        ):
            continue
        _list(job.get("evidenceScopes"), f"{path}.evidenceScopes", failures)
        _list(job.get("requiredOutputs"), f"{path}.requiredOutputs", failures)
        if job.get("runnable") is False and not job.get("skipReason"):
            failures.append(f"{path}.skipReason: required for a non-runnable job")
    runnable_count = sum(job.get("runnable") is True for job in jobs if isinstance(job, dict))
    if (
        runnable_count >= 2
        and isinstance(concurrency, dict)
        and concurrency.get("maxConcurrentAgents", 0) < 3
    ):
        failures.append(
            "manifest.hostConcurrency.maxConcurrentAgents: two runnable jobs require "
            "two worker slots plus the coordinator"
        )
    _scan_placeholders(manifest, "manifest", failures)
    return sorted(set(failures))


def validate_worker_results(manifest: Any, results: list[Any]) -> list[str]:
    failures = validate_manifest(manifest)
    if failures:
        return failures
    manifest_jobs = {job["id"]: job for job in manifest["jobs"]}
    result_ids = _unique_ids(results, "results", failures, key="jobId")
    expected = {job_id for job_id, job in manifest_jobs.items() if job["runnable"]}
    if result_ids != expected:
        failures.append(
            f"results: runnable job coverage differs; missing={sorted(expected - result_ids)}, "
            f"extra={sorted(result_ids - expected)}"
        )
    intervals: list[tuple[datetime, datetime, str]] = []
    global_evidence_ids: set[str] = set()
    global_fact_ids: set[str] = set()
    for index, result in enumerate(results):
        path = f"results[{index}]"
        if not _require(
            result,
            (
                "schemaVersion",
                "analysisId",
                "jobId",
                "status",
                "startedAt",
                "completedAt",
                "evidence",
                "facts",
                "limitations",
            ),
            path,
            failures,
        ):
            continue
        if result.get("schemaVersion") != 1:
            failures.append(f"{path}.schemaVersion: expected 1")
        if result.get("analysisId") != manifest["analysisId"]:
            failures.append(f"{path}.analysisId: does not match manifest")
        if result.get("status") not in {"completed", "limited", "skipped", "failed"}:
            failures.append(f"{path}.status: unsupported value")
        elif result.get("status") in {"skipped", "failed"}:
            failures.append(f"{path}.status: runnable job did not produce a usable result")
        started = _parse_time(result.get("startedAt"), f"{path}.startedAt", failures)
        completed = _parse_time(result.get("completedAt"), f"{path}.completedAt", failures)
        if started and completed:
            if completed <= started:
                failures.append(f"{path}: completedAt must be after startedAt")
            else:
                intervals.append((started, completed, result["jobId"]))
        evidence = _list(result.get("evidence"), f"{path}.evidence", failures, 0)
        evidence_ids = _unique_ids(evidence, f"{path}.evidence", failures)
        duplicate_evidence = global_evidence_ids & evidence_ids
        if duplicate_evidence:
            failures.append(f"{path}.evidence: duplicate global ids {sorted(duplicate_evidence)}")
        global_evidence_ids.update(evidence_ids)
        facts = _list(result.get("facts"), f"{path}.facts", failures, 0)
        fact_ids = _unique_ids(facts, f"{path}.facts", failures)
        duplicate_facts = global_fact_ids & fact_ids
        if duplicate_facts:
            failures.append(f"{path}.facts: duplicate global ids {sorted(duplicate_facts)}")
        global_fact_ids.update(fact_ids)
        if result.get("status") in {"completed", "limited"} and not evidence:
            failures.append(f"{path}.evidence: completed work must cite evidence")
        for fact_index, fact in enumerate(facts):
            fact_path = f"{path}.facts[{fact_index}]"
            if not _require(fact, ("id", "evidenceIds", "statement", "confidence"), fact_path, failures):
                continue
            unknown = set(fact.get("evidenceIds", [])) - evidence_ids
            if unknown:
                failures.append(f"{fact_path}.evidenceIds: unknown ids {sorted(unknown)}")
    capacity = (
        manifest["hostConcurrency"]["maxConcurrentAgents"]
        - manifest["hostConcurrency"]["coordinatorSlots"]
    )
    events: list[tuple[datetime, int, str]] = []
    for started, completed, job_id in intervals:
        events.append((started, 1, job_id))
        events.append((completed, -1, job_id))
    active = 0
    maximum = 0
    # End events sort before start events at an identical instant.
    for _, delta, _ in sorted(events, key=lambda event: (event[0], event[1])):
        active += delta
        maximum = max(maximum, active)
    if maximum > capacity:
        failures.append(
            f"results: observed worker concurrency {maximum} exceeds host worker capacity "
            f"{capacity} after reserving the coordinator"
        )
    if len(expected) >= 2 and maximum < 2:
        failures.append("results: two or more runnable jobs require overlapping execution intervals")
    _scan_placeholders(results, "results", failures)
    return sorted(set(failures))


def validate_contract(contract: Any) -> list[str]:
    failures: list[str] = []
    if not _require(contract, TOP_LEVEL_KEYS, "contract", failures):
        return failures
    if contract.get("schemaVersion") != 1:
        failures.append("contract.schemaVersion: expected 1")
    app = contract.get("application")
    _require(app, ("id", "name", "version", "status", "scope", "changes", "nextSteps"), "contract.application", failures)
    _substantive(app.get("scope") if isinstance(app, dict) else None, "contract.application.scope", failures)
    summaries = contract.get("summaries")
    if _require(summaries, SUMMARY_KEYS, "contract.summaries", failures):
        for key in SUMMARY_KEYS:
            _substantive(summaries.get(key), f"contract.summaries.{key}", failures)

    architecture = contract.get("architecture")
    if _require(
        architecture,
        (
            "narrative",
            "frontend",
            "backends",
            "accounts",
            "buses",
            "downstreams",
            "thirdParties",
            "failurePoints",
            "diagrams",
        ),
        "contract.architecture",
        failures,
    ):
        _substantive(architecture.get("narrative"), "contract.architecture.narrative", failures)
        frontend = architecture.get("frontend")
        if _require(
            frontend,
            ("runtimeModel", "router", "initOwner", "singleInit", "routes", "evidenceIds"),
            "contract.architecture.frontend",
            failures,
        ):
            if frontend.get("singleInit") is not True:
                failures.append("contract.architecture.frontend.singleInit: one provider init is required")
            _list(frontend.get("routes"), "contract.architecture.frontend.routes", failures)
        for key in ("backends", "accounts", "failurePoints"):
            _list(architecture.get(key), f"contract.architecture.{key}", failures)
        for index, route in enumerate(frontend.get("routes", []) if isinstance(frontend, dict) else []):
            _require(
                route,
                ("pathClass", "pageType", "navigation", "evidenceIds"),
                f"contract.architecture.frontend.routes[{index}]",
                failures,
            )
        architecture_fields = {
            "backends": ("id", "name", "runtime", "accountId", "role", "failurePoints", "evidenceIds"),
            "accounts": ("id", "provider", "boundary", "evidenceIds"),
            "buses": ("id", "technology", "crossesAccounts", "contextCarrier", "failurePoints", "evidenceIds"),
            "downstreams": ("id", "role", "protocol", "consequence", "evidenceIds"),
            "thirdParties": ("name", "category", "consequence", "controls", "evidenceIds"),
            "failurePoints": ("id", "surface", "effect", "detection", "evidenceIds"),
            "diagrams": ("id", "label", "provenance"),
        }
        for key, fields in architecture_fields.items():
            for index, item in enumerate(architecture.get(key, [])):
                _require(item, fields, f"contract.architecture.{key}[{index}]", failures)

    technology = _list(contract.get("technology"), "contract.technology", failures)
    telemetry = _list(contract.get("currentTelemetry"), "contract.currentTelemetry", failures)
    findings = _list(contract.get("findings"), "contract.findings", failures)
    strategies = _list(contract.get("strategy"), "contract.strategy", failures)
    phases = _list(contract.get("implementationPhases"), "contract.implementationPhases", failures)
    work_orders = _list(contract.get("workOrders"), "contract.workOrders", failures)
    use_cases = _list(contract.get("useCases"), "contract.useCases", failures)
    workflows = _list(contract.get("workflows"), "contract.workflows", failures)
    transactions = _list(contract.get("businessTransactions"), "contract.businessTransactions", failures)

    for name, values in (
        ("technology", technology),
        ("currentTelemetry", telemetry),
        ("findings", findings),
        ("strategy", strategies),
        ("implementationPhases", phases),
        ("workOrders", work_orders),
        ("useCases", use_cases),
        ("workflows", workflows),
        ("businessTransactions", transactions),
    ):
        key = (
            "name"
            if name == "technology"
            else "component"
            if name == "currentTelemetry"
            else "id"
        )
        _unique_ids(values, f"contract.{name}", failures, key=key)

    for index, item in enumerate(technology):
        _require(
            item,
            ("name", "category", "versionEvidence", "observabilityConsequence", "evidenceIds"),
            f"contract.technology[{index}]",
            failures,
        )
    for index, item in enumerate(telemetry):
        path = f"contract.currentTelemetry[{index}]"
        if _require(item, ("component", "status", "trust", "observed", "gaps", "evidenceIds"), path, failures):
            _list(item.get("gaps"), f"{path}.gaps", failures)
    for index, item in enumerate(strategies):
        _require(
            item,
            ("id", "title", "question", "productSurface", "retentionClass", "recommendation", "evidenceIds"),
            f"contract.strategy[{index}]",
            failures,
        )
        _substantive(item.get("recommendation"), f"contract.strategy[{index}].recommendation", failures)
    for index, item in enumerate(phases):
        path = f"contract.implementationPhases[{index}]"
        if _require(item, ("id", "title", "outcome", "dependsOn", "workOrderIds", "exitCriteria"), path, failures):
            _list(item.get("workOrderIds"), f"{path}.workOrderIds", failures)
            _list(item.get("exitCriteria"), f"{path}.exitCriteria", failures)
    for index, item in enumerate(work_orders):
        path = f"contract.workOrders[{index}]"
        if not _require(
            item,
            (
                "id", "title", "outcome", "status", "dependsOn", "unlocks",
                "repositoryLegs", "acceptanceCriteria", "verification",
            ),
            path,
            failures,
        ):
            continue
        for key in ("repositoryLegs", "acceptanceCriteria", "verification"):
            _list(item.get(key), f"{path}.{key}", failures)
        for leg_index, leg in enumerate(item.get("repositoryLegs", [])):
            leg_path = f"{path}.repositoryLegs[{leg_index}]"
            if _require(leg, ("repository", "paths", "changes", "tests"), leg_path, failures):
                for key in ("paths", "changes", "tests"):
                    _list(leg.get(key), f"{leg_path}.{key}", failures)

    workflow_ids = {item.get("id") for item in workflows if isinstance(item, dict)}
    transaction_ids = {item.get("id") for item in transactions if isinstance(item, dict)}
    work_order_ids = {item.get("id") for item in work_orders if isinstance(item, dict)}
    use_case_ids = {item.get("id") for item in use_cases if isinstance(item, dict)}
    detector_ids: set[str] = set()
    objective_ids: set[str] = set()
    dashboard_ids: set[str] = set()

    for index, finding in enumerate(findings):
        _require(
            finding,
            (
                "id", "title", "severity", "confidence", "priority", "class", "observed",
                "evidenceIds", "surfaces", "exposure", "risk", "remediation", "verification",
                "useCaseIds", "workflowIds", "businessTransactionIds", "contractIds", "workOrderIds",
            ),
            f"contract.findings[{index}]",
            failures,
        )
        _substantive(finding.get("observed"), f"contract.findings[{index}].observed", failures)
        reference_sets = (
            ("useCaseIds", use_case_ids),
            ("workflowIds", workflow_ids),
            ("businessTransactionIds", transaction_ids),
            ("workOrderIds", work_order_ids),
        )
        for key, known in reference_sets:
            unknown = set(finding.get(key, [])) - known
            if unknown:
                failures.append(f"contract.findings[{index}].{key}: unknown ids {sorted(unknown)}")

    for index, transaction in enumerate(transactions):
        path = f"contract.businessTransactions[{index}]"
        if not _require(
            transaction,
            (
                "id", "name", "groupingValue", "artifact", "summary", "workflowIds",
                "whereSet", "propagation", "tenantRule", "verification", "workOrderIds", "evidenceIds",
            ),
            path,
            failures,
        ):
            continue
        linked = set(transaction.get("workflowIds", []))
        if len(linked) < 2:
            failures.append(f"{path}.workflowIds: transaction requires an evidence-derived workflow catalogue")
        unknown = linked - workflow_ids
        if unknown:
            failures.append(f"{path}.workflowIds: unknown ids {sorted(unknown)}")
        if set(transaction.get("workOrderIds", [])) - work_order_ids:
            failures.append(f"{path}.workOrderIds: contains unknown work order")

    for index, workflow in enumerate(workflows):
        path = f"contract.workflows[{index}]"
        if not _require(
            workflow,
            (
                "id", "name", "narrative", "businessTransactionIds", "spans", "events",
                "metrics", "joins", "dashboardId", "detectorIds", "objectiveIds",
                "verification", "workOrderIds", "evidenceIds",
            ),
            path,
            failures,
        ):
            continue
        for key in ("spans", "events", "metrics", "joins", "verification"):
            _list(workflow.get(key), f"{path}.{key}", failures)
        unknown_transactions = set(workflow.get("businessTransactionIds", [])) - transaction_ids
        if unknown_transactions:
            failures.append(f"{path}.businessTransactionIds: unknown ids {sorted(unknown_transactions)}")
        for metric_index, metric in enumerate(workflow.get("metrics", [])):
            _require(
                metric,
                ("name", "type", "unit", "purpose", "dimensions"),
                f"{path}.metrics[{metric_index}]",
                failures,
            )
            dimensions = metric.get("dimensions", []) if isinstance(metric, dict) else []
            if not 3 <= len(dimensions) <= 6:
                failures.append(f"{path}.metrics[{metric_index}].dimensions: expected 3 to 6 bounded dimensions")
        for span_index, span in enumerate(workflow.get("spans", [])):
            _require(
                span,
                ("id", "name", "kind", "joinType", "service", "attributes"),
                f"{path}.spans[{span_index}]",
                failures,
            )
            if isinstance(span, dict) and "parentId" not in span:
                failures.append(f"{path}.spans[{span_index}]: missing required field parentId")
        for event_index, event in enumerate(workflow.get("events", [])):
            _require(
                event,
                ("name", "when", "attributes"),
                f"{path}.events[{event_index}]",
                failures,
            )
        for join_index, join in enumerate(workflow.get("joins", [])):
            _require(
                join,
                ("from", "to", "type", "carrier", "reason"),
                f"{path}.joins[{join_index}]",
                failures,
            )

    operations = contract.get("operations")
    if _require(
        operations,
        (
            "dashboards",
            "detectors",
            "objectives",
            "releaseCorrelation",
            "synthetics",
            "thousandEyes",
            "logCorrelation",
            "verificationCriteria",
            "performanceBudgets",
        ),
        "contract.operations",
        failures,
    ):
        dashboards = _list(operations.get("dashboards"), "contract.operations.dashboards", failures)
        detectors = _list(operations.get("detectors"), "contract.operations.detectors", failures)
        objectives = _list(operations.get("objectives"), "contract.operations.objectives", failures)
        criteria = _list(operations.get("verificationCriteria"), "contract.operations.verificationCriteria", failures)
        dashboard_ids = _unique_ids(dashboards, "contract.operations.dashboards", failures)
        detector_ids = _unique_ids(detectors, "contract.operations.detectors", failures)
        objective_ids = _unique_ids(objectives, "contract.operations.objectives", failures)
        _unique_ids(criteria, "contract.operations.verificationCriteria", failures)
        for index, dashboard in enumerate(dashboards):
            _require(
                dashboard,
                ("id", "title", "variables", "panels", "releaseOverlay"),
                f"contract.operations.dashboards[{index}]",
                failures,
            )
        for index, detector in enumerate(detectors):
            _require(
                detector,
                ("id", "name", "signal", "threshold", "window", "groupBy", "severity", "runbook", "verification"),
                f"contract.operations.detectors[{index}]",
                failures,
            )
        for index, objective in enumerate(objectives):
            _require(
                objective,
                ("id", "name", "sli", "target", "window", "errorBudget", "verification"),
                f"contract.operations.objectives[{index}]",
                failures,
            )
        for index, criterion in enumerate(criteria):
            _require(
                criterion,
                ("id", "criterion", "method", "expected"),
                f"contract.operations.verificationCriteria[{index}]",
                failures,
            )
        budgets = operations.get("performanceBudgets")
        _require(
            budgets,
            ("validationSeconds", "renderSeconds", "maxOutputFiles", "maxOutputBytes"),
            "contract.operations.performanceBudgets",
            failures,
        )

    for index, workflow in enumerate(workflows):
        path = f"contract.workflows[{index}]"
        if workflow.get("dashboardId") not in dashboard_ids:
            failures.append(f"{path}.dashboardId: unknown dashboard {workflow.get('dashboardId')}")
        unknown_detectors = set(workflow.get("detectorIds", [])) - detector_ids
        if unknown_detectors:
            failures.append(f"{path}.detectorIds: unknown ids {sorted(unknown_detectors)}")
        unknown_objectives = set(workflow.get("objectiveIds", [])) - objective_ids
        if unknown_objectives:
            failures.append(f"{path}.objectiveIds: unknown ids {sorted(unknown_objectives)}")
        unknown_orders = set(workflow.get("workOrderIds", [])) - work_order_ids
        if unknown_orders:
            failures.append(f"{path}.workOrderIds: unknown ids {sorted(unknown_orders)}")

    phase_ids = {item.get("id") for item in phases if isinstance(item, dict)}
    for index, phase in enumerate(phases):
        path = f"contract.implementationPhases[{index}]"
        if set(phase.get("dependsOn", [])) - phase_ids:
            failures.append(f"{path}.dependsOn: contains unknown phase")
        if set(phase.get("workOrderIds", [])) - work_order_ids:
            failures.append(f"{path}.workOrderIds: contains unknown work order")
    for index, order in enumerate(work_orders):
        path = f"contract.workOrders[{index}]"
        if set(order.get("dependsOn", [])) - work_order_ids:
            failures.append(f"{path}.dependsOn: contains unknown work order")
        if set(order.get("unlocks", [])) - work_order_ids:
            failures.append(f"{path}.unlocks: contains unknown work order")

    for index, use_case in enumerate(use_cases):
        path = f"contract.useCases[{index}]"
        if not _require(
            use_case,
            (
                "id", "title", "narrative", "question", "workflowIds", "businessTransactionIds",
                "spanIds", "eventNames", "metricNames", "dashboardId", "detectorIds",
                "objectiveIds", "joins", "verification", "workOrderIds", "evidenceIds",
            ),
            path,
            failures,
        ):
            continue
        _substantive(use_case.get("narrative"), f"{path}.narrative", failures)
        for key in ("workflowIds", "businessTransactionIds", "spanIds", "eventNames", "metricNames", "detectorIds", "objectiveIds", "joins", "verification", "workOrderIds"):
            _list(use_case.get(key), f"{path}.{key}", failures)
        if set(use_case.get("workflowIds", [])) - workflow_ids:
            failures.append(f"{path}.workflowIds: contains unknown workflow")
        if set(use_case.get("businessTransactionIds", [])) - transaction_ids:
            failures.append(f"{path}.businessTransactionIds: contains unknown transaction")
        if use_case.get("dashboardId") not in dashboard_ids:
            failures.append(f"{path}.dashboardId: unknown dashboard")
        if set(use_case.get("detectorIds", [])) - detector_ids:
            failures.append(f"{path}.detectorIds: contains unknown detector")
        if set(use_case.get("objectiveIds", [])) - objective_ids:
            failures.append(f"{path}.objectiveIds: contains unknown objective")
        selected_workflows = [
            workflow
            for workflow in workflows
            if workflow.get("id") in set(use_case.get("workflowIds", []))
        ]
        known_span_ids = {
            span.get("id")
            for workflow in selected_workflows
            for span in workflow.get("spans", [])
        }
        known_event_names = {
            event.get("name")
            for workflow in selected_workflows
            for event in workflow.get("events", [])
        }
        known_metric_names = {
            metric.get("name")
            for workflow in selected_workflows
            for metric in workflow.get("metrics", [])
        }
        for key, known in (
            ("spanIds", known_span_ids),
            ("eventNames", known_event_names),
            ("metricNames", known_metric_names),
        ):
            unknown = set(use_case.get(key, [])) - known
            if unknown:
                failures.append(f"{path}.{key}: unknown ids {sorted(unknown)}")
        for join_index, join in enumerate(use_case.get("joins", [])):
            _require(
                join,
                ("from", "to", "type", "carrier", "reason"),
                f"{path}.joins[{join_index}]",
                failures,
            )

    contracts = contract.get("contracts")
    if _require(
        contracts,
        ("singleInit", "spaRoutes", "crossCutting", "attribution", "joins", "collector", "cardinality"),
        "contract.contracts",
        failures,
    ):
        _substantive(contracts.get("singleInit"), "contract.contracts.singleInit", failures)
        spa = contracts.get("spaRoutes")
        _require(spa, ("owner", "classifier", "navigationSpan", "code"), "contract.contracts.spaRoutes", failures)
        cross = contracts.get("crossCutting")
        if _require(
            cross,
            ("attributes", "providerBootstrap", "spanProcessor", "identityWrite", "backendPropagator", "messagePropagation"),
            "contract.contracts.crossCutting",
            failures,
        ):
            _list(cross.get("attributes"), "contract.contracts.crossCutting.attributes", failures, 3)
            for key in ("providerBootstrap", "spanProcessor", "identityWrite", "backendPropagator", "messagePropagation"):
                _substantive(cross.get(key), f"contract.contracts.crossCutting.{key}", failures)
            for index, attribute in enumerate(cross.get("attributes", [])):
                _require(
                    attribute,
                    (
                        "name", "type", "source", "setAt", "cardinalityClass",
                        "dimensionEligible", "propagation", "consumers",
                    ),
                    f"contract.contracts.crossCutting.attributes[{index}]",
                    failures,
                )
        attribution = contracts.get("attribution")
        _require(
            attribution,
            ("trigger", "event", "firstTouch", "lastTouch", "baggageKeys", "code"),
            "contract.contracts.attribution",
            failures,
        )
        for index, join in enumerate(contracts.get("joins", [])):
            _require(
                join,
                ("from", "to", "type", "carrier", "reason"),
                f"contract.contracts.joins[{index}]",
                failures,
            )
        collector = contracts.get("collector")
        if _require(collector, ("placement", "processorOrder", "ottl", "redactions"), "contract.contracts.collector", failures):
            order = collector.get("processorOrder", [])
            lower = [str(item).lower() for item in order]
            transform_positions = [i for i, item in enumerate(lower) if "transform" in item]
            redact_positions = [i for i, item in enumerate(lower) if "redact" in item or "attribute" in item]
            metric_positions = [i for i, item in enumerate(lower) if "spanmetric" in item]
            batch_positions = [i for i, item in enumerate(lower) if "batch" in item]
            if not transform_positions or not redact_positions or not metric_positions or not batch_positions:
                failures.append("contract.contracts.collector.processorOrder: requires transform, redaction, spanmetrics, and batch")
            elif not (
                max(transform_positions) < min(metric_positions)
                and max(redact_positions) < min(metric_positions)
                and max(metric_positions) < min(batch_positions)
            ):
                failures.append("contract.contracts.collector.processorOrder: derive and redact before spanmetrics, then batch")
            for index, redaction in enumerate(collector.get("redactions", [])):
                _require(
                    redaction,
                    ("field", "action", "reason"),
                    f"contract.contracts.collector.redactions[{index}]",
                    failures,
                )
        cardinality = contracts.get("cardinality")
        if _require(
            cardinality,
            ("entitlement", "inUse", "reserved", "proposedCost", "headroomAfter", "dimensionEligible", "attributeOnly"),
            "contract.contracts.cardinality",
            failures,
        ):
            numbers = (
                cardinality.get("entitlement"),
                cardinality.get("inUse"),
                cardinality.get("reserved"),
                cardinality.get("proposedCost"),
                cardinality.get("headroomAfter"),
            )
            if all(isinstance(value, int) for value in numbers):
                expected = numbers[0] - numbers[1] - numbers[2] - numbers[3]
                if numbers[4] != expected:
                    failures.append(
                        "contract.contracts.cardinality.headroomAfter: "
                        f"expected entitlement - inUse - reserved - proposedCost = {expected}"
                    )
            dimension_eligible = set(cardinality.get("dimensionEligible", []))
            attribute_only = set(cardinality.get("attributeOnly", []))
            overlap = dimension_eligible & attribute_only
            if overlap:
                failures.append(
                    "contract.contracts.cardinality: keys cannot be both dimension-eligible "
                    f"and attribute-only: {sorted(overlap)}"
                )
            for workflow_index, workflow in enumerate(workflows):
                for metric_index, metric in enumerate(workflow.get("metrics", [])):
                    unapproved = set(metric.get("dimensions", [])) - dimension_eligible
                    if unapproved:
                        failures.append(
                            f"contract.workflows[{workflow_index}].metrics[{metric_index}]."
                            f"dimensions: not dimension-eligible {sorted(unapproved)}"
                        )
            for detector_index, detector in enumerate(
                operations.get("detectors", []) if isinstance(operations, dict) else []
            ):
                unapproved = set(detector.get("groupBy", [])) - dimension_eligible
                if unapproved:
                    failures.append(
                        f"contract.operations.detectors[{detector_index}].groupBy: "
                        f"not dimension-eligible {sorted(unapproved)}"
                    )

    reference = contract.get("reference")
    if _require(reference, ("evidence", "sources", "priorArtifacts", "unknowns"), "contract.reference", failures):
        _list(reference.get("evidence"), "contract.reference.evidence", failures)
        known_evidence = _unique_ids(
            reference.get("evidence", []),
            "contract.reference.evidence",
            failures,
        )
        for index, evidence in enumerate(reference.get("evidence", [])):
            _require(
                evidence,
                ("id", "label", "provenance"),
                f"contract.reference.evidence[{index}]",
                failures,
            )
        unknown_evidence = _collect_evidence_refs(contract) - known_evidence
        if unknown_evidence:
            failures.append(
                f"contract: evidenceIds missing from reference register {sorted(unknown_evidence)}"
            )

    _scan_join_types(contract, "contract", failures)
    _scan_placeholders(contract, "contract", failures)
    return sorted(set(failures))
