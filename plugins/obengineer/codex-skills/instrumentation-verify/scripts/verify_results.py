#!/usr/bin/env python3
"""Validate verification results, exclusions, remediation, and summary arithmetic."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:\d{2})$"
)
STATUSES = {"met", "unmet", "unmeasurable"}
LEDGER_ID = re.compile(r"^(?:SRC|FACT|CHECK|DEC|UNRES)-[A-Za-z0-9._-]+$")


def plan_verifier():
    path = Path(__file__).with_name("verify_plan.py")
    spec = importlib.util.spec_from_file_location("verify_plan", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.verify


def ledger_verifier():
    path = Path(__file__).parents[2] / "instrumentation-wiki" / "scripts" / (
        "verify_provenance_ledger.py"
    )
    spec = importlib.util.spec_from_file_location("verify_provenance_ledger", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.verify


def acceptance_verifier():
    path = Path(__file__).parents[2] / "instrumentation-wiki" / "scripts" / (
        "verify_analysis_acceptance.py"
    )
    spec = importlib.util.spec_from_file_location("verify_analysis_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read(path: Path, label: str) -> tuple[dict | None, list[str]]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"{label} is not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{label} top level must be an object"]
    return data, []


def content_commit(data: dict, label: str) -> tuple[str, list[str]]:
    schema_version = data.get("schema_version")
    failures: list[str] = []
    if schema_version == 1:
        commit = data.get("analysis_commit", "")
        if "analysis_content_commit" in data:
            failures.append(
                f"{label} schema_version 1 uses analysis_commit, "
                "not analysis_content_commit"
            )
    elif schema_version == 2:
        commit = data.get("analysis_content_commit", "")
        if "analysis_commit" in data:
            failures.append(
                f"{label} schema_version 2 uses analysis_content_commit, "
                "not analysis_commit"
            )
    else:
        return "", [f"{label} schema_version must be 1 or 2"]
    if not isinstance(commit, str) or not FULL_SHA.fullmatch(commit):
        failures.append(f"{label} needs a full accepted content commit SHA")
    return commit, failures


def exclusions(path: Path | None, commit: str, plan_ids: set[str],
               ledger_ids: set[str] | None) -> tuple[set[str], list[str]]:
    if path is None:
        return set(), []
    data, failures = read(path, "verification exclusions")
    if data is None:
        return set(), failures
    exclusion_commit, commit_failures = content_commit(
        data, "verification exclusions"
    )
    failures.extend(commit_failures)
    if exclusion_commit != commit:
        failures.append("verification exclusions must match the full accepted commit")
    result: set[str] = set()
    for item in data.get("exclusions", []):
        if not isinstance(item, dict):
            failures.append("exclusion entries must be objects")
            continue
        criterion_id = item.get("criterion_id")
        if criterion_id not in plan_ids:
            failures.append(f"exclusion references unknown criterion: {criterion_id}")
        if item.get("decision") != "unremediable":
            failures.append(f"{criterion_id}: exclusion decision must be unremediable")
        for field in (
            "reason_code", "rationale", "approved_by", "approved_at",
            "review_at", "evidence_refs",
        ):
            if field not in item or item[field] in ("", None):
                failures.append(f"{criterion_id}: exclusion missing {field}")
        for field in ("approved_at", "review_at"):
            if item.get(field) and not RFC3339.fullmatch(item[field]):
                failures.append(f"{criterion_id}: {field} must be RFC3339")
        if item.get("review_at") and RFC3339.fullmatch(item["review_at"]):
            review_at = datetime.fromisoformat(
                item["review_at"].replace("Z", "+00:00")
            )
            if review_at <= datetime.now(timezone.utc):
                failures.append(f"{criterion_id}: exclusion review_at has expired")
        refs = item.get("evidence_refs")
        if not isinstance(refs, list) or not refs or not all(
            isinstance(ref, str) and LEDGER_ID.fullmatch(ref) for ref in refs
        ):
            failures.append(f"{criterion_id}: exclusion evidence_refs are invalid")
        elif ledger_ids is not None and not set(refs) <= ledger_ids:
            failures.append(f"{criterion_id}: exclusion evidence_refs do not resolve")
        if criterion_id in result:
            failures.append(f"duplicate exclusion: {criterion_id}")
        result.add(criterion_id)
    return result, failures


def verify(plan_path: Path, results_path: Path, exclusions_path: Path | None = None,
           ledger_path: Path | None = None,
           acceptance_path: Path | None = None) -> list[str]:
    plan, failures = read(plan_path, "verification plan")
    failures.extend(f"plan: {item}" for item in plan_verifier()(plan_path))
    results, result_failures = read(results_path, "verification results")
    failures.extend(result_failures)
    if plan is None or results is None:
        return failures
    commit, commit_failures = content_commit(results, "verification results")
    failures.extend(commit_failures)
    if acceptance_path is not None:
        acceptance, acceptance_failures = acceptance_verifier().parse_record(
            acceptance_path
        )
        failures.extend(
            f"acceptance: {failure}" for failure in acceptance_failures
        )
        if not acceptance_failures and \
                acceptance.get("analysis_content_commit") != commit:
            failures.append(
                "verification results commit does not match acceptance record"
            )
    ledger_ids: set[str] | None = None
    if ledger_path is not None:
        failures.extend(
            f"ledger: {item}" for item in ledger_verifier()(ledger_path)
        )
        ledger, ledger_failures = read(ledger_path, "provenance ledger")
        failures.extend(ledger_failures)
        if ledger:
            ledger_ids = {
                item.get("id")
                for collection in (
                    "sources", "facts", "runs", "checks", "artifacts",
                    "decisions", "unresolved",
                )
                for item in ledger.get(collection, [])
                if isinstance(item, dict)
            }
    plan_ids = {
        item.get("id") for item in plan.get("criteria", []) if isinstance(item, dict)
    }
    excluded, excluded_failures = exclusions(
        exclusions_path, commit, plan_ids, ledger_ids
    )
    failures.extend(excluded_failures)
    eligible = plan_ids - excluded

    rows = results.get("results")
    if not isinstance(rows, list):
        return failures + ["results must be a list"]
    seen: set[str] = set()
    counts = {status: 0 for status in STATUSES}
    for row in rows:
        if not isinstance(row, dict):
            failures.append("result rows must be objects")
            continue
        criterion_id = row.get("criterion_id")
        if criterion_id in excluded:
            failures.append(f"excluded criterion appears in results: {criterion_id}")
        if criterion_id not in plan_ids:
            failures.append(f"unknown result criterion: {criterion_id}")
        if criterion_id in seen:
            failures.append(f"duplicate result criterion: {criterion_id}")
        seen.add(criterion_id)
        status = row.get("status")
        if status not in STATUSES:
            failures.append(f"{criterion_id}: invalid result status")
            continue
        counts[status] += 1
        evidence_refs = row.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            failures.append(f"{criterion_id}: result needs ledger evidence_refs")
        elif not all(
            isinstance(item, str) and LEDGER_ID.fullmatch(item)
            for item in evidence_refs
        ):
            failures.append(f"{criterion_id}: invalid ledger evidence_refs")
        elif ledger_ids is not None and not set(evidence_refs) <= ledger_ids:
            failures.append(f"{criterion_id}: evidence_refs do not resolve in ledger")
        if status == "unmet":
            for field in (
                "expected", "observed", "owner", "remediation_route",
                "remediation_instructions", "next_command", "recheck_instructions",
                "human_notification",
            ):
                if field not in row or row[field] in ("", None):
                    failures.append(f"{criterion_id}: unmet result missing {field}")
        if status == "unmeasurable" and not row.get("human_action"):
            failures.append(f"{criterion_id}: unmeasurable result needs human_action")

    missing = eligible - seen
    if missing:
        failures.append(f"eligible criteria missing results: {sorted(missing)}")
    summary = results.get("summary", {})
    expected_summary = {
        "accepted": len(plan_ids),
        "excluded": len(excluded),
        "eligible": len(eligible),
        **counts,
    }
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            failures.append(
                f"summary {key} is {summary.get(key)!r}; recomputed value is {value}"
            )
    if len(eligible) != sum(counts.values()):
        failures.append("eligible count does not equal met + unmet + unmeasurable")
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--exclusions", type=Path)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path)
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    acceptance = args.acceptance
    discovery_failures: list[str] = []
    if acceptance is None:
        acceptance, discovery_failures = acceptance_verifier().discover_acceptance(
            args.repo
        )
    if discovery_failures:
        for failure in discovery_failures:
            print(f"FAIL — {failure}")
        return 1
    failures = verify(
        args.plan, args.results, args.exclusions, args.ledger, acceptance
    )
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print("PASS — verification results are complete and actionable")
    results = json.loads(args.results.read_text())
    return 2 if results.get("summary", {}).get("unmet", 0) else 0


if __name__ == "__main__":
    sys.exit(main())
