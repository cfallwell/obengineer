#!/usr/bin/env python3
"""Validate an accepted read-only verification plan."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ID = re.compile(r"^VC-[0-9]{3,}$")
ROUTES = {"implementation", "terraform", "contract-amendment", "human-owner"}
SYSTEMS = {
    "splunk-observability", "splunk-platform", "thousandeyes",
    "repository", "terraform",
}
READ_OPERATIONS = {"list", "get", "search", "query", "plan-read", "state-read"}
POST_ENDPOINTS = {
    "signalflow": ("/v2/signalflow/execute",),
    "spl-search": ("/services/search/jobs", "/services/search/v2/jobs/export"),
}
OPERATORS = {"equals", "not-equals", "exists", "not-empty", "gte", "lte", "contains"}
ISO_DURATION = re.compile(
    r"^P(?=\d|T\d)(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+(?:\.\d+)?S)?)?$"
)
LEDGER_ID = re.compile(r"^SRC-[A-Za-z0-9._-]+$")


def load(path: Path) -> tuple[dict | None, list[str]]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"verification plan is not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, ["verification plan top level must be an object"]
    return data, []


def verify(path: Path) -> list[str]:
    data, failures = load(path)
    if data is None:
        return failures
    if data.get("schema_version") != 1:
        failures.append("schema_version must be 1")
    criteria = data.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return failures + ["criteria must be a non-empty list"]
    seen: set[str] = set()
    for index, criterion in enumerate(criteria):
        if not isinstance(criterion, dict):
            failures.append(f"criteria[{index}] must be an object")
            continue
        criterion_id = criterion.get("id")
        if not isinstance(criterion_id, str) or not ID.fullmatch(criterion_id):
            failures.append(f"criteria[{index}].id is invalid")
        elif criterion_id in seen:
            failures.append(f"duplicate criterion id: {criterion_id}")
        else:
            seen.add(criterion_id)
        if criterion.get("system") not in SYSTEMS:
            failures.append(f"{criterion_id}: unsupported system")
        source_section = criterion.get("source_section")
        if not isinstance(source_section, int) or not 1 <= source_section <= 31:
            failures.append(f"{criterion_id}: source_section is invalid")
        query = criterion.get("query")
        if not isinstance(query, dict) or not query.get("kind"):
            failures.append(f"{criterion_id}: query requires kind")
        else:
            operation = query.get("operation", "get")
            method = query.get("method", "GET").upper()
            if operation not in READ_OPERATIONS:
                failures.append(f"{criterion_id}: query operation is not read-only")
            if method not in ("GET", "POST"):
                failures.append(f"{criterion_id}: query method is not read-only")
            if method == "POST":
                allowed = POST_ENDPOINTS.get(query.get("kind"), ())
                endpoint = query.get("endpoint", "")
                if not any(endpoint.endswith(path) for path in allowed):
                    failures.append(
                        f"{criterion_id}: POST endpoint is not an approved read query"
                    )
            if not LEDGER_ID.fullmatch(str(query.get("reference", ""))):
                failures.append(f"{criterion_id}: query reference must be a source ledger id")
        expected = criterion.get("expected")
        if not isinstance(expected, dict) or expected.get("operator") not in OPERATORS:
            failures.append(f"{criterion_id}: expected predicate is required")
        elif expected["operator"] not in {"exists", "not-empty"} and \
                "value" not in expected:
            failures.append(f"{criterion_id}: expected predicate needs value")
        if not ISO_DURATION.fullmatch(str(criterion.get("observation_window", ""))):
            failures.append(f"{criterion_id}: observation_window is required")
        if not criterion.get("owner"):
            failures.append(f"{criterion_id}: owner is required")
        remediation = criterion.get("remediation")
        if not isinstance(remediation, dict):
            failures.append(f"{criterion_id}: remediation is required")
            continue
        if remediation.get("route") not in ROUTES:
            failures.append(f"{criterion_id}: remediation route is invalid")
        if not remediation.get("instructions"):
            failures.append(f"{criterion_id}: remediation instructions are required")
        if remediation.get("route") in {"implementation", "terraform"} and not \
                remediation.get("selector"):
            failures.append(f"{criterion_id}: remediation selector is required")
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args(argv)
    failures = verify(args.plan)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print("PASS — verification plan is actionable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
