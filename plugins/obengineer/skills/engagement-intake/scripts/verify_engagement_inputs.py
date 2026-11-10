#!/usr/bin/env python3
"""Validate engagement-input schema v3 or migrate deterministic v2 fields."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install PyYAML==6.0.3")

REQUIRED = (
    "schema_version: 3",
    "custom_mts_entitled:",
    "custom_mts_in_use:",
    "custom_mts_system_limit:",
    "mms_cardinality_entitled:",
    "mms_cardinality_in_use:",
    "provenance_fact_ids:",
)
RETIRED = ("custom_mts_included:", "mms_slots_remaining:")
SECRET = re.compile(
    r"(\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+"
    r"|\b(?:AKIA|ASIA)[A-Z0-9]{12,}\b"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\bgh[posur]_[A-Za-z0-9]{20,}\b)"
)


def migrate_v2(text: str) -> str:
    if not re.search(r"^schema_version:\s*2\s*$", text, re.M):
        return text
    text = re.sub(
        r"^schema_version:\s*2\s*$", "schema_version: 3", text, flags=re.M
    )
    text = text.replace("custom_mts_included:", "custom_mts_entitled:")
    text = re.sub(
        r"^(\s*)mms_slots_remaining:\s*([^\n]+)$",
        r"\1mms_cardinality_entitled: unknown\n"
        r"\1mms_cardinality_in_use: unknown",
        text,
        flags=re.M,
    )
    if "custom_mts_system_limit:" not in text:
        text = re.sub(
            r"^(\s*custom_mts_in_use:[^\n]*\n)",
            r"\1    custom_mts_system_limit: unknown\n",
            text,
            count=1,
            flags=re.M,
        )
    if "provenance_fact_ids:" not in text:
        text = re.sub(
            r"^(\s*fit_to_entitlement:[^\n]*\n)",
            r"\1  provenance_fact_ids: {}\n",
            text,
            count=1,
            flags=re.M,
        )
    if "migration_notes:" not in text:
        text = re.sub(
            r"^(\s*provenance_fact_ids:[^\n]*\n)",
            r"\1  migration_notes:\n"
            r"    - mms_slots_remaining was retired; obtain MMS cardinality "
            r"entitled and in-use values.\n",
            text,
            count=1,
            flags=re.M,
        )
    return text


def verify_text(text: str) -> list[str]:
    failures: list[str] = []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"engagement inputs are not valid YAML: {exc}"]
    if not isinstance(data, dict):
        return ["engagement inputs top level must be an object"]
    if data.get("schema_version") != 3:
        failures.append("schema_version must be 3")
    entitlement = data.get("entitlement")
    if not isinstance(entitlement, dict):
        failures.append("entitlement must be an object")
        entitlement = {}
    observability = entitlement.get("observability_cloud")
    if not isinstance(observability, dict):
        failures.append("entitlement.observability_cloud must be an object")
        observability = {}
    for field in (
        "custom_mts_entitled", "custom_mts_in_use", "custom_mts_system_limit",
        "mms_cardinality_entitled", "mms_cardinality_in_use",
    ):
        if field not in observability:
            failures.append(
                f"entitlement.observability_cloud is missing {field}"
            )
    if not isinstance(entitlement.get("provenance_fact_ids"), dict):
        failures.append("entitlement.provenance_fact_ids must be an object")
    failures.extend([
        f"missing required schema-v3 field: {field}"
        for field in REQUIRED if field not in text
    ])
    failures.extend(
        f"retired schema-v2 field remains: {field}"
        for field in RETIRED if field in text
    )
    if SECRET.search(text):
        failures.append("credential-shaped value in engagement inputs")
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args(argv)
    try:
        text = args.inputs.read_text()
    except OSError as exc:
        print(f"FAIL — cannot read engagement inputs: {exc}")
        return 1
    if args.migrate:
        migrated = migrate_v2(text)
        if migrated != text:
            args.inputs.write_text(migrated)
            text = migrated
            print("migrated engagement inputs from schema v2 to v3")
    failures = verify_text(text)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print("PASS — engagement inputs use schema v3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
