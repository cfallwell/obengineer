#!/usr/bin/env python3
"""Validate engagement-input schema v3 or migrate deterministic v2 fields."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

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
PASSWORD_REFERENCE = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")


def supplied(value) -> bool:
    return value not in (None, "", "unknown", [])


def absolute_http_url(value) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def project_relative_path(value) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().replace("\\", "/")
    if (
        not normalized
        or normalized.startswith(("/", "//"))
        or re.match(r"^[A-Za-z]:", normalized)
        or "\x00" in normalized
    ):
        return False
    parts = PurePosixPath(normalized).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def path_is_contained(project_root: Path, value: str) -> bool:
    root = project_root.resolve()
    candidate = (root / value).resolve(strict=False)
    return candidate != root and root in candidate.parents


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


def verify_text(text: str, project_root: Path | None = None) -> list[str]:
    failures: list[str] = []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"engagement inputs are not valid YAML: {exc}"]
    if not isinstance(data, dict):
        return ["engagement inputs top level must be an object"]
    if data.get("schema_version") != 3:
        failures.append("schema_version must be 3")
    engagement = data.get("engagement")
    if not isinstance(engagement, dict) or not supplied(
        engagement.get("application")
    ):
        failures.append("engagement.application is required")
    surfaces = data.get("surfaces")
    if not isinstance(surfaces, dict):
        failures.append("surfaces must be an object")
        surfaces = {}
    production_urls = surfaces.get("production_urls")
    valid_urls = (
        isinstance(production_urls, list)
        and bool(production_urls)
        and all(absolute_http_url(url) for url in production_urls)
    )
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        failures.append("artifacts must be an object")
        artifacts = {}
    no_browser = artifacts.get("front_end_scan_notes")
    valid_no_browser = (
        isinstance(no_browser, str)
        and bool(re.fullmatch(r"no browser:\s*\S.*", no_browser.strip(), re.I))
    )
    if valid_urls == valid_no_browser:
        failures.append(
            "provide production_urls or front_end_scan_notes as "
            "'no browser: <reason>', but not both"
        )
    for field in (
        "location", "narrative", "prior_contract", "prior_schema", "house_style_docx"
    ):
        value = artifacts.get(field)
        if supplied(value) and not project_relative_path(value):
            failures.append(
                f"artifacts.{field} must be a project-relative path without traversal"
            )
        elif (
            supplied(value)
            and project_root is not None
            and not path_is_contained(project_root, value)
        ):
            failures.append(
                f"artifacts.{field} resolves outside the project through a symlink"
            )
    for field in ("diagrams", "prior_scans"):
        values = artifacts.get(field)
        if supplied(values) and (
            not isinstance(values, list)
            or not all(project_relative_path(value) for value in values)
        ):
            failures.append(
                f"artifacts.{field} must contain project-relative paths without traversal"
            )
        elif (
            supplied(values)
            and project_root is not None
            and any(not path_is_contained(project_root, value) for value in values)
        ):
            failures.append(
                f"artifacts.{field} resolves outside the project through a symlink"
            )
    if supplied(no_browser) and not valid_no_browser and not project_relative_path(
        no_browser
    ):
        failures.append(
            "artifacts.front_end_scan_notes must be a project-relative path "
            "or 'no browser: <reason>'"
        )
    elif (
        supplied(no_browser)
        and not valid_no_browser
        and project_root is not None
        and not path_is_contained(project_root, no_browser)
    ):
        failures.append(
            "artifacts.front_end_scan_notes resolves outside the project "
            "through a symlink"
        )
    business_context = data.get("business_context")
    if not isinstance(business_context, dict) or not supplied(
        business_context.get("commentary")
    ):
        failures.append("business_context.commentary (what hurts today) is required")
    access = data.get("analysis_access")
    if not isinstance(access, dict):
        failures.append("analysis_access must be an object")
        access = {}
    login_set = supplied(access.get("login_id"))
    password = access.get("password_ref")
    password_set = supplied(password)
    if login_set != password_set:
        failures.append(
            "analysis_access.login_id and password_ref must be supplied together"
        )
    if password_set and (
        not isinstance(password, str) or not PASSWORD_REFERENCE.fullmatch(password)
    ):
        failures.append(
            "analysis_access.password_ref must be a ${VAR} reference"
        )
    access_supplied = any(
        supplied(access.get(field))
        for field in ("token_ref", "api_key_ref", "login_id", "password_ref")
    )
    if access_supplied and access.get("rotate_on_completion") is not True:
        failures.append(
            "analysis_access.rotate_on_completion must be true when access is supplied"
        )
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
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="workspace root used to contain the input and every artifact path",
    )
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    inputs = args.inputs.resolve()
    if inputs == project_root or project_root not in inputs.parents:
        print("FAIL — engagement inputs resolve outside --project-root")
        return 1
    try:
        text = inputs.read_text()
    except OSError as exc:
        print(f"FAIL — cannot read engagement inputs: {exc}")
        return 1
    if args.migrate:
        migrated = migrate_v2(text)
        if migrated != text:
            inputs.write_text(migrated)
            text = migrated
            print("migrated engagement inputs from schema v2 to v3")
    failures = verify_text(text, project_root)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print("PASS — engagement inputs use schema v3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
