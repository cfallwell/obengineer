#!/usr/bin/env python3
"""Validate provenance-ledger structure, references, safety, and analysis seal."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

COLLECTIONS = (
    "sources", "facts", "runs", "checks", "artifacts", "decisions", "unresolved"
)
PROVENANCE = {"measured", "stated", "public", "derived"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SECRET = re.compile(
    r"(?:\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+"
    r"|\b(?:AKIA|ASIA)[A-Z0-9]{12,}\b"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\bgh[posur]_[A-Za-z0-9]{20,}\b)"
)


def _entries(data: dict) -> list[dict]:
    return [
        entry
        for name in COLLECTIONS
        for entry in data.get(name, [])
        if isinstance(entry, dict)
    ]


def verify(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"provenance ledger is not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return ["provenance ledger top level must be an object"]

    failures: list[str] = []
    if data.get("schema_version") != 1:
        failures.append("schema_version must be 1")
    for field in (
        "engagement", "contract", "context_profile", "seals", *COLLECTIONS
    ):
        expected = list if field in COLLECTIONS else dict
        if not isinstance(data.get(field), expected):
            failures.append(f"{field} must be a {expected.__name__}")

    contract = data.get("contract", {})
    if isinstance(contract, dict):
        if not isinstance(contract.get("sealed_ids"), list):
            failures.append("contract.sealed_ids must be a list")

    for name in COLLECTIONS:
        if isinstance(data.get(name), list):
            for index, entry in enumerate(data[name]):
                if not isinstance(entry, dict):
                    failures.append(f"{name}[{index}] must be an object")
    entries = _entries(data)
    by_id: dict[str, dict] = {}
    for entry in entries:
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            failures.append("every ledger entry requires an id")
            continue
        if entry_id in by_id:
            failures.append(f"duplicate ledger id: {entry_id}")
        by_id[entry_id] = entry

    for fact in data.get("facts", []) if isinstance(data.get("facts"), list) else []:
        if not isinstance(fact, dict):
            failures.append("facts entries must be objects")
            continue
        provenance = fact.get("provenance")
        if provenance not in PROVENANCE:
            failures.append(f"{fact.get('id', 'fact')}: invalid provenance")
            continue
        if provenance == "measured":
            for field in (
                "collected_at", "tool", "method", "scope",
                "observation_window", "limitations",
            ):
                if field not in fact:
                    failures.append(f"{fact.get('id')}: measured fact missing {field}")
        elif provenance == "stated":
            for field in ("source_role", "stated_at"):
                if not fact.get(field):
                    failures.append(f"{fact.get('id')}: stated fact missing {field}")
        elif provenance == "public":
            for field in ("url", "publication", "published_at", "read_at"):
                if not fact.get(field):
                    failures.append(f"{fact.get('id')}: public fact missing {field}")
        elif provenance == "derived":
            if not fact.get("source_fact_ids") or not fact.get("formula"):
                failures.append(
                    f"{fact.get('id')}: derived fact needs source_fact_ids and formula"
                )

    for artifact in (
        data.get("artifacts", []) if isinstance(data.get("artifacts"), list) else []
    ):
        if not isinstance(artifact, dict):
            failures.append("artifacts entries must be objects")
            continue
        for field in ("path", "sha256", "stage", "run_id", "git_commit"):
            if not artifact.get(field):
                failures.append(f"{artifact.get('id')}: artifact missing {field}")
        if artifact.get("sha256") and not HEX64.fullmatch(artifact["sha256"]):
            failures.append(f"{artifact.get('id')}: artifact sha256 is invalid")

    for unresolved in (
        data.get("unresolved", []) if isinstance(data.get("unresolved"), list) else []
    ):
        if not isinstance(unresolved, dict):
            continue
        if unresolved.get("status") == "not_in_evidence":
            for field in (
                "attempted_source", "failure_reason", "fallback_question", "owner"
            ):
                if not unresolved.get(field):
                    failures.append(
                        f"{unresolved.get('id')}: not_in_evidence missing {field}"
                    )

    reference_fields = ("source_fact_ids", "evidence_refs", "source_ids")
    for entry in entries:
        for field in reference_fields:
            for target in entry.get(field, []) if isinstance(entry.get(field), list) else []:
                if target not in by_id:
                    failures.append(
                        f"{entry.get('id')}: {field} references unknown id {target}"
                    )

    context = data.get("context_profile", {})
    if isinstance(context, dict):
        predicates = context.get("predicates", {})
        loaded = context.get("loaded_references", [])
        if isinstance(predicates, dict) and isinstance(loaded, list):
            for item in loaded:
                if not isinstance(item, dict):
                    failures.append("loaded_references entries must be objects")
                    continue
                predicate = item.get("predicate")
                ref_path = item.get("path", "")
                if predicate not in predicates:
                    failures.append(
                        f"loaded reference has unknown predicate: {predicate}"
                    )
                elif predicates[predicate] is False:
                    failures.append(
                        f"loaded reference violates false predicate: {predicate}"
                    )
                expected: set[str] | None = None
                if ref_path == "platform/browser.md":
                    expected = {"browser"}
                elif ref_path.startswith("platform/languages/"):
                    stem = Path(ref_path).stem
                    expected = {
                        "node": {
                            "language:node", "language:javascript",
                            "language:typescript",
                        },
                    }.get(stem, {f"language:{stem}"})
                elif ref_path.startswith("platform/buses/"):
                    stem = Path(ref_path).stem
                    expected = {
                        "kafka": {"bus:kafka", "bus:msk"},
                        "aws-messaging": {
                            "bus:sqs", "bus:sns", "bus:eventbridge",
                        },
                    }.get(stem, {f"bus:{stem}"})
                elif ref_path.startswith("platform/routers/"):
                    expected = {f"router:{Path(ref_path).stem}"}
                elif ref_path == "platform/clouds.md":
                    expected = {"cloud"}
                elif ref_path == "platform/thousandeyes.md":
                    expected = {"thousandeyes"}
                elif ref_path == "platform/splunk-platform.md":
                    expected = {"splunk-platform"}
                if expected and predicate not in expected:
                    failures.append(
                        f"loaded reference {ref_path} requires one of "
                        f"{sorted(expected)}"
                    )

    analysis_seal = (
        data.get("seals", {}).get("analysis")
        if isinstance(data.get("seals"), dict) else None
    )
    if analysis_seal:
        ids = analysis_seal.get("ids", [])
        if contract.get("sealed_ids") != ids:
            failures.append("contract.sealed_ids does not match analysis seal ids")
        selected = [by_id[item] for item in sorted(ids) if item in by_id]
        unknown = set(ids) - by_id.keys()
        if unknown:
            failures.append(f"analysis seal references unknown ids: {sorted(unknown)}")
        digest = hashlib.sha256(
            json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if analysis_seal.get("digest") != digest:
            failures.append("analysis seal digest does not match sealed entries")

    text = path.read_text(errors="replace")
    if SECRET.search(text):
        failures.append("credential-shaped value in provenance ledger")
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args(argv)
    failures = verify(args.ledger)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print("PASS — provenance ledger is structurally valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
