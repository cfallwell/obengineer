#!/usr/bin/env python3
"""Manage local obconfig lifecycle without exposing configuration values."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

from direct_api import collect_direct_evidence
from obconfig import (
    CONFIG_NAME,
    ConfigIssue,
    ObconfigError,
    Redactor,
    UniqueLoader,
    atomic_write,
    atomic_write_json,
    authorize,
    binding,
    config_changed_since_authorization,
    consume_authorization,
    find_template,
    hash_artifact_tree,
    initialize,
    load_config,
    parse_yaml,
    redacted_issue,
    repair,
    summary,
    validate_authorization,
    validate_config,
)

LEGACY_YAML = Path("docs/observability/engagement-inputs.yaml")
LEGACY_ENV = Path(".env")
LEGACY_TEMPLATE = Path(".env.template")
ENV_MAPPING = {
    "SPLUNK_REALM": "splunk.observability.realm",
    "SPLUNK_ACCESS_TOKEN": "splunk.observability.read_token",
    "SPLUNK_HOST": "splunk.platform.host",
    "SPLUNK_TOKEN": "splunk.platform.read_token",
    "SPLUNK_ENTERPRISE_INDEXES": "splunk.platform.index_allowlist",
    "TEST_LOGIN_ID": "analysis_access.dummy_login.login_id",
    "RAW_PASSWORD": "analysis_access.dummy_login.password",
}
RETIRED_LEGACY = {
    "entitlement",
    "input_provenance",
    "outcomes.known_pain",
    "business_context.commentary",
}
RETIRED_TOP_LEVEL = {"entitlement", "input_provenance"}
RETIRED_SECTION_KEYS = {
    "artifacts": {
        "location", "diagrams", "narrative", "prior_contract", "prior_schema", "prior_scans",
        "house_style_docx", "front_end_scan_notes",
    },
    "cloud_diagrams": {"environments"},
    "surfaces": {"non_production_urls"},
    "security_assessment": {
        "excluded_paths", "max_requests", "max_requests_per_second", "notes",
    },
    "analysis_access": {
        "login_id", "token_ref", "api_key_ref", "password_ref", "rotate_on_completion",
    },
    "tenancy": {"o11y_realm", "splunk_platform_host", "environments"},
    "outcomes": {"known_pain"},
    "business_context": {"commentary"},
}


def _set_path(data: dict[str, Any], dotted: str, value: Any) -> None:
    target = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        current = target.get(part)
        if not isinstance(current, dict):
            current = {}
            target[part] = current
        target = current
    target[parts[-1]] = value


def _get_path(data: Mapping[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _supplied(value: Any) -> bool:
    return value not in (None, "", "unknown", [], {})


def _merge_value(
    target: dict[str, Any],
    destination: str,
    value: Any,
    changed: list[str],
) -> None:
    if not _supplied(value):
        return
    existing = _get_path(target, destination)
    if _supplied(existing) and existing != value:
        raise ValueError(f"redacted conflict for {destination}")
    _set_path(target, destination, copy.deepcopy(value))
    changed.append(destination)


def _read_legacy_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file():
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"{path.name} must be a regular file")
        )
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in ENV_MAPPING:
            result[key] = value.strip().strip("\"'")
    return result


def _merge_retained(
    target: dict[str, Any],
    legacy: Mapping[str, Any],
    project_root: Path,
) -> list[str]:
    changed: list[str] = []
    direct_sections = (
        "engagement", "initial_scope", "backends", "standards", "constraints",
        "outcomes", "traffic_baseline", "business_context", "public_evidence",
        "developer_tools",
    )
    for section in direct_sections:
        current = target.get(section)
        source = legacy.get(section)
        if not isinstance(current, dict) or not isinstance(source, Mapping):
            continue
        for key in current:
            dotted = f"{section}.{key}"
            if dotted in RETIRED_LEGACY or not _supplied(source.get(key)):
                continue
            current[key] = copy.deepcopy(source[key])
            changed.append(dotted)

    old_tenancy = legacy.get("tenancy", {})
    if isinstance(old_tenancy, Mapping):
        mapping = {
            "o11y_org_id": "tenancy.o11y_org_id",
            "thousandeyes_account_group": "tenancy.thousandeyes_account_group",
            "tokens_held_by": "tenancy.tokens_held_by",
            "o11y_realm": "splunk.observability.realm",
            "splunk_platform_host": "splunk.platform.host",
        }
        for source, destination in mapping.items():
            _merge_value(target, destination, old_tenancy.get(source), changed)
        environments = old_tenancy.get("environments")
        if _supplied(environments):
            if not isinstance(environments, list) or len(environments) != 1:
                raise ValueError(
                    "tenancy.environments has multiple values; choose one in engagement.deployment_environment"
                )
            target["engagement"]["deployment_environment"] = environments[0]
            changed.append("engagement.deployment_environment")

    artifacts = legacy.get("artifacts", {})
    if isinstance(artifacts, Mapping):
        location = artifacts.get("location")
        if _supplied(location):
            target["artifacts"]["directory"] = location
            changed.append("artifacts.directory")
        directory = PurePosixPath(str(target["artifacts"]["directory"]).replace("\\", "/"))
        outside: list[str] = []
        for key in (
            "diagrams", "narrative", "prior_contract", "prior_schema",
            "prior_scans", "house_style_docx", "front_end_scan_notes",
        ):
            supplied = artifacts.get(key)
            if not _supplied(supplied):
                continue
            if (
                key == "front_end_scan_notes"
                and isinstance(supplied, str)
                and supplied.lower().startswith("no browser:")
            ):
                continue
            values = supplied if isinstance(supplied, list) else [supplied]
            for value in values:
                candidate = PurePosixPath(str(value).replace("\\", "/"))
                contained = (
                    not candidate.is_absolute()
                    and ".." not in candidate.parts
                    and candidate.parts[: len(directory.parts)] == directory.parts
                )
                path = project_root.joinpath(*candidate.parts) if contained else None
                if (
                    not contained
                    or path is None
                    or path.is_symlink()
                    or not path.is_file()
                ):
                    outside.append(f"artifacts.{key}")
                    break
        if outside:
            raise ValueError(
                "legacy individual artifact paths require manual placement under artifacts.directory: "
                + ", ".join(outside)
            )

    surfaces = legacy.get("surfaces", {})
    if isinstance(surfaces, Mapping):
        for key in ("production_urls", "host_and_remotes", "edge_cdn"):
            if _supplied(surfaces.get(key)):
                target["surfaces"][key] = copy.deepcopy(surfaces[key])
                changed.append(f"surfaces.{key}")
    scan_notes = (
        artifacts.get("front_end_scan_notes")
        if isinstance(artifacts, Mapping) else None
    )
    if isinstance(scan_notes, str) and scan_notes.lower().startswith("no browser:"):
        target["surfaces"]["no_browser_reason"] = scan_notes.split(":", 1)[1].strip()
        changed.append("surfaces.no_browser_reason")

    security = legacy.get("security_assessment", {})
    if isinstance(security, Mapping):
        for key in ("mode", "authorized_origins"):
            if _supplied(security.get(key)):
                target["security_assessment"][key] = copy.deepcopy(security[key])
                changed.append(f"security_assessment.{key}")

    access = legacy.get("analysis_access", {})
    if isinstance(access, Mapping) and _supplied(access.get("login_id")):
        _merge_value(
            target,
            "analysis_access.dummy_login.login_id",
            access["login_id"],
            changed,
        )
    if isinstance(access, Mapping) and isinstance(access.get("dummy_login"), Mapping):
        dummy = access["dummy_login"]
        _merge_value(
            target,
            "analysis_access.dummy_login.login_id",
            dummy.get("login_id"),
            changed,
        )
        _merge_value(
            target,
            "analysis_access.dummy_login.password",
            dummy.get("password"),
            changed,
        )

    splunk = legacy.get("splunk", {})
    if isinstance(splunk, Mapping):
        observability = splunk.get("observability", {})
        if isinstance(observability, Mapping):
            _merge_value(
                target,
                "splunk.observability.realm",
                observability.get("realm"),
                changed,
            )
            _merge_value(
                target,
                "splunk.observability.read_token",
                observability.get("read_token"),
                changed,
            )
        platform = splunk.get("platform", {})
        if isinstance(platform, Mapping):
            for key in ("host", "read_token", "index_allowlist"):
                _merge_value(
                    target,
                    f"splunk.platform.{key}",
                    platform.get(key),
                    changed,
                )

    known_top_level = set(target) | RETIRED_TOP_LEVEL
    unknown: dict[str, Any] = {
        str(key): copy.deepcopy(value)
        for key, value in legacy.items()
        if key not in known_top_level
    }
    for section, target_value in target.items():
        source_value = legacy.get(section)
        if not isinstance(target_value, Mapping) or not isinstance(source_value, Mapping):
            continue
        retired = RETIRED_SECTION_KEYS.get(section, set())
        extra = {
            str(key): copy.deepcopy(value)
            for key, value in source_value.items()
            if key not in target_value and key not in retired
        }
        if extra:
            unknown[section] = extra
    if unknown:
        target.setdefault("extensions", {})["legacy"] = unknown
        changed.append("extensions.legacy")
    return changed


def migrate_legacy(project_root: Path, template: Path) -> list[str]:
    destination = project_root / CONFIG_NAME
    if destination.exists() or destination.is_symlink():
        raise ValueError("obconfig.yaml already exists; legacy values were not merged")
    template_data, _ = parse_yaml(template.read_bytes())
    target = copy.deepcopy(template_data)
    changed: list[str] = []
    legacy: Mapping[str, Any] = {}
    legacy_path = project_root / LEGACY_YAML
    if legacy_path.exists():
        if legacy_path.is_symlink() or not legacy_path.is_file():
            raise ValueError(f"{LEGACY_YAML} must be a regular file")
        legacy = yaml.load(legacy_path.read_text(encoding="utf-8"), Loader=UniqueLoader)
        if not isinstance(legacy, Mapping):
            raise ValueError(f"{LEGACY_YAML} top level must be a mapping")
        changed.extend(_merge_retained(target, legacy, project_root))

    env = _read_legacy_env(project_root / LEGACY_ENV)
    for name, destination_path in ENV_MAPPING.items():
        value = env.get(name)
        if not _supplied(value):
            continue
        if isinstance(value, str) and re.fullmatch(r"\$\{[^}]+\}", value):
            if destination_path.endswith(("read_token", "password")):
                raise ValueError(f"{name} is an unresolved legacy reference")
        converted: Any = value
        if name == "SPLUNK_ENTERPRISE_INDEXES":
            converted = [item.strip() for item in value.split(",") if item.strip()]
        existing = _get_path(target, destination_path)
        if (
            name in {"SPLUNK_REALM", "SPLUNK_HOST", "TEST_LOGIN_ID"}
            and _supplied(existing)
        ):
            # Legacy YAML is authoritative for the same non-secret fact.
            continue
        if _supplied(existing) and existing != converted:
            raise ValueError(f"redacted conflict for {destination_path}")
        _set_path(target, destination_path, converted)
        changed.append(destination_path)

    # v3 dummy access may have a reference only; never resolve process environment.
    access = legacy.get("analysis_access", {})
    if isinstance(access, Mapping) and _supplied(access.get("login_id")):
        password_ref = access.get("password_ref")
        if _supplied(password_ref) and not (
            _supplied(_get_path(target, "analysis_access.dummy_login.password"))
            or (
                password_ref == "${RAW_PASSWORD}"
                and _supplied(env.get("RAW_PASSWORD"))
            )
        ):
            raise ValueError(
                "analysis_access.password_ref is unresolved; place the dummy password directly in local obconfig.yaml"
            )

    # Validation is intentionally deferred until after the local file is edited when
    # required application/surface fields were not present in legacy input.
    text = yaml.safe_dump(target, sort_keys=False, allow_unicode=True).encode()
    atomic_write(destination, text, 0o600)
    changed_paths = sorted(set(changed))
    sources = [
        str(relative)
        for relative in (LEGACY_YAML, LEGACY_ENV, LEGACY_TEMPLATE)
        if (project_root / relative).exists()
        or (project_root / relative).is_symlink()
    ]
    atomic_write_json(
        project_root / ".obengineer/migration.json",
        {
            "schema_version": 1,
            "sources_preserved": sources,
            "changed_key_paths": changed_paths,
        },
        0o600,
    )
    return changed_paths


def _project(value: str) -> Path:
    return Path(value).resolve()


def _print_error(exc: BaseException, data: Mapping[str, Any] | None = None) -> int:
    print(f"FAIL — {redacted_issue(exc, Redactor(data))}", file=sys.stderr)
    return 1


def main(
    argv: list[str] | None = None,
    *,
    direct_transport: Any | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("init")
    sub.add_parser("validate")
    repair_parser = sub.add_parser("repair")
    repair_parser.add_argument("--answer", required=True)
    sub.add_parser("summary")
    sub.add_parser("changed")
    authorize_parser = sub.add_parser("authorize")
    authorize_parser.add_argument("--answer", required=True)
    authorize_parser.add_argument("--command", required=True)
    authorize_parser.add_argument("--intended-version", required=True)
    show_parser = sub.add_parser("show")
    show_parser.add_argument("--command", required=True)
    show_parser.add_argument("--intended-version", required=True)
    consume_parser = sub.add_parser("consume")
    consume_parser.add_argument("--command", required=True)
    consume_parser.add_argument("--intended-version", required=True)
    direct_parser = sub.add_parser("direct-api")
    direct_parser.add_argument(
        "--phase", required=True, choices=("analysis", "verification")
    )
    sub.add_parser("migrate-legacy")
    args = parser.parse_args(argv)
    root = _project(args.project_root)
    enforce_git = True
    data: Mapping[str, Any] | None = None
    try:
        if args.operation == "init":
            template = find_template(Path(__file__))
            legacy_sources = [
                str(relative)
                for relative in (LEGACY_ENV, LEGACY_TEMPLATE, LEGACY_YAML)
                if (root / relative).exists() or (root / relative).is_symlink()
            ]
            if legacy_sources and not (root / CONFIG_NAME).exists():
                print("Legacy configuration detected: " + ", ".join(legacy_sources))
                print(
                    "Candidate destination key paths: engagement.*, artifacts.directory, "
                    "surfaces.*, security_assessment.*, splunk.*, analysis_access.dummy_login.*, "
                    "backends.*, tenancy.*, standards.*, constraints.*, outcomes.*, "
                    "traffic_baseline.*, business_context.*, public_evidence.*, developer_tools.*"
                )
                print("Migrate these legacy files now? (yes/no)")
                return 4
            if initialize(root, template):
                print("Created local obconfig.yaml. Edit it and rerun /ob-start.")
                return 0
            print("obconfig.yaml already exists.")
            return 0
        if args.operation == "migrate-legacy":
            template = find_template(Path(__file__))
            changed = migrate_legacy(root, template)
            print("Migrated legacy files into local obconfig.yaml.")
            print("Changed key paths: " + (", ".join(changed) if changed else "none"))
            print("Legacy files were preserved. Edit obconfig.yaml and rerun /ob-start.")
            return 0
        if args.operation == "repair":
            if args.answer != "yes":
                print("Repair stopped; obconfig.yaml was not changed.")
                return 2
            changed = repair(root)
            print("Safe repair complete. Changed key paths: " + ", ".join(changed))
            return 0

        if args.operation == "direct-api":
            config_path = root / CONFIG_NAME
            if not config_path.exists() and not config_path.is_symlink():
                data = {
                    "splunk": {
                        "observability": {"realm": "", "read_token": ""},
                        "platform": {
                            "host": "",
                            "read_token": "",
                            "index_allowlist": [],
                        },
                    }
                }
            else:
                data, _, _, _ = load_config(root, enforce_git=enforce_git)
            if direct_transport is None:
                direct_results = collect_direct_evidence(data, phase=args.phase)
            else:
                direct_results = collect_direct_evidence(
                    data,
                    phase=args.phase,
                    transport=direct_transport,
                )
            payload = Redactor(data).value(
                {
                    "schema_version": 1,
                    "phase": args.phase,
                    "direct_api": direct_results,
                }
            )
            print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            return 0

        data, _, _, warnings = load_config(root, enforce_git=enforce_git)
        if args.operation == "validate":
            for warning in warnings:
                print(f"WARNING — {Redactor(data).text(warning)}")
            print("PASS — obconfig.yaml uses schema v4")
            return 0
        if args.operation == "summary":
            tree = hash_artifact_tree(root, data["artifacts"]["directory"])
            print(summary(data, tree))
            print("Proceed with analysis using this configuration? (yes/no)")
            return 0
        if args.operation == "changed":
            if config_changed_since_authorization(root):
                print("Configuration changed since the last analysis.")
                return 0
            print("Edit obconfig.yaml, then rerun this command.")
            return 3
        if args.operation == "authorize":
            if args.answer != "yes":
                print("Analysis stopped; no authorization was written.")
                return 2
            authorize(
                root,
                command=args.command,
                intended_version=args.intended_version,
                enforce_git=enforce_git,
            )
            print("Analysis authorized for the current configuration and artifact tree.")
            return 0
        if args.operation == "show":
            validate_authorization(
                root,
                command=args.command,
                intended_version=args.intended_version,
                enforce_git=enforce_git,
            )
            print("PASS — one-shot analysis authorization matches current inputs")
            return 0
        if args.operation == "consume":
            consume_authorization(
                root,
                command=args.command,
                intended_version=args.intended_version,
                enforce_git=enforce_git,
            )
            print("Consumed one-shot analysis authorization.")
            return 0
    except (ObconfigError, OSError, ValueError, yaml.YAMLError) as exc:
        if isinstance(exc, ObconfigError) and args.operation in {"validate", "summary"}:
            issue = exc.issue
            detail = f"{issue.path}: {issue.reason}" if issue.path else issue.reason
            print(
                f"obconfig.yaml is invalid at line {issue.line}, column {issue.column}: "
                f"{Redactor(data).text(detail)}. Repair it now? (yes/no)"
            )
            return 1
        return _print_error(exc, data)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
