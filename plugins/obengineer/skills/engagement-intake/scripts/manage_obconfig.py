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

from direct_api import collect_direct_evidence, execute_safe_active
from obconfig import (
    CONFIG_NAME,
    ConfigIssue,
    ObconfigError,
    Redactor,
    RegularFileVersion,
    UniqueLoader,
    atomic_write,
    atomic_write_json,
    abort_claim,
    analysis_config_projection,
    authorize,
    binding,
    capture_config_binding,
    claim_authorization,
    config_digest,
    config_changed_since_authorization,
    consume_claim,
    find_template,
    finalize_claim,
    hash_artifact_tree,
    initialize,
    load_config,
    parse_yaml,
    preflight_config_creation,
    prepare_local_state,
    read_project_file,
    read_project_file_version,
    record_dispatch,
    redacted_issue,
    remove_config_from_index,
    repair,
    secure_unlink,
    summary,
    validate_claim,
    validate_authorization,
    validate_config,
    verify_dispatch,
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


def _read_legacy_env(
    project_root: Path, relative: Path
) -> tuple[dict[str, str], RegularFileVersion | None]:
    path = project_root / relative
    if not path.exists() and not path.is_symlink():
        return {}, None
    raw, version = read_project_file_version(
        project_root,
        relative,
        relative.as_posix(),
        limit=1024 * 1024,
        required_mode=0o600 if relative == LEGACY_ENV else None,
    )
    result: dict[str, str] = {}
    for raw_line in raw.decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in ENV_MAPPING:
            result[key] = value.strip().strip("\"'")
    return result, version


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
    preflight_config_creation(project_root)
    local = prepare_local_state(project_root)
    template_data, _ = parse_yaml(
        read_project_file(
            template.parent,
            template.name,
            "obconfig.yaml.template",
            limit=1024 * 1024,
        )
    )
    target = copy.deepcopy(template_data)
    source_versions: dict[Path, RegularFileVersion] = {}
    changed: list[str] = []
    legacy: Mapping[str, Any] = {}
    legacy_path = project_root / LEGACY_YAML
    if legacy_path.exists() or legacy_path.is_symlink():
        legacy_raw, legacy_version = read_project_file_version(
            project_root,
            LEGACY_YAML,
            LEGACY_YAML.as_posix(),
            limit=1024 * 1024,
        )
        legacy = yaml.load(legacy_raw.decode("utf-8"), Loader=UniqueLoader)
        if not isinstance(legacy, Mapping):
            raise ValueError(f"{LEGACY_YAML} top level must be a mapping")
        source_versions[LEGACY_YAML] = legacy_version
        changed.extend(_merge_retained(target, legacy, project_root))

    env, env_version = _read_legacy_env(project_root, LEGACY_ENV)
    if env_version is not None:
        source_versions[LEGACY_ENV] = env_version
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

    text = yaml.safe_dump(target, sort_keys=False, allow_unicode=True).encode()
    staged_data, staged_marks = parse_yaml(text)
    validate_config(staged_data, staged_marks)
    changed_paths = sorted(set(changed))
    sources = [
        str(relative)
        for relative in (LEGACY_YAML, LEGACY_ENV, LEGACY_TEMPLATE)
        if (project_root / relative).exists()
        or (project_root / relative).is_symlink()
    ]
    migration_path = local / "migration.json"
    previous_migration: bytes | None = None
    previous_migration_version: RegularFileVersion | None = None
    if migration_path.exists() or migration_path.is_symlink():
        previous_migration, previous_migration_version = read_project_file_version(
            project_root,
            Path(".obengineer/migration.json"),
            "migration state",
            limit=1024 * 1024,
            required_mode=0o600,
        )
    config_written = False
    config_identity: tuple[int, int] | None = None
    config_version: RegularFileVersion | None = None
    migration_written = False
    migration_identity: tuple[int, int] | None = None
    migration_version: RegularFileVersion | None = None
    try:
        config_version = atomic_write(
            destination, text, 0o600, expect_absent=True
        )
        config_written = True
        config_identity = (
            config_version.device,
            config_version.inode,
        )
        preflight_config_creation(project_root)
        migration_version = atomic_write_json(
            migration_path,
            {
                "schema_version": 1,
                "sources_preserved": sources,
                "changed_key_paths": changed_paths,
            },
            0o600,
            expect_absent=previous_migration_version is None,
            expected_identity=(
                None
                if previous_migration_version is None
                else (
                    previous_migration_version.device,
                    previous_migration_version.inode,
                )
            ),
            expected_digest=(
                None
                if previous_migration_version is None
                else previous_migration_version.digest
            ),
            expected_mode=(
                None
                if previous_migration_version is None
                else previous_migration_version.mode
            ),
        )
        migration_written = True
        migration_identity = (
            migration_version.device,
            migration_version.inode,
        )
        preflight_config_creation(project_root)
        for source, expected in source_versions.items():
            _, current = read_project_file_version(
                project_root,
                source,
                source.as_posix(),
                limit=1024 * 1024,
                required_mode=0o600 if source == LEGACY_ENV else None,
            )
            if current != expected:
                raise ObconfigError(
                    ConfigIssue(
                        1,
                        1,
                        "",
                        f"{source.as_posix()} changed before migration commit",
                    )
                )
        config_raw, final_config = read_project_file_version(
            project_root,
            Path(CONFIG_NAME),
            CONFIG_NAME,
            limit=1024 * 1024,
            required_mode=0o600,
        )
        state_raw, final_state = read_project_file_version(
            project_root,
            Path(".obengineer/migration.json"),
            "migration state",
            required_mode=0o600,
        )
        if (
            config_raw != text
            or final_config != config_version
            or final_state != migration_version
            or not state_raw
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "migration destination changed before commit")
            )
    except BaseException as original_error:
        remove_config_from_index(project_root)
        rollback_errors: list[BaseException] = []
        try:
            if config_written:
                secure_unlink(
                    destination,
                    expected_identity=config_identity,
                    expected_digest=(
                        config_version.digest
                        if config_version is not None
                        else None
                    ),
                    expected_mode=(
                        config_version.mode
                        if config_version is not None
                        else None
                    ),
                )
        except BaseException as cleanup_error:
            rollback_errors.append(cleanup_error)
        try:
            if migration_written:
                if previous_migration is None:
                    secure_unlink(
                        migration_path,
                        expected_identity=migration_identity,
                        expected_digest=(
                            migration_version.digest
                            if migration_version is not None
                            else None
                        ),
                        expected_mode=(
                            migration_version.mode
                            if migration_version is not None
                            else None
                        ),
                    )
                else:
                    assert migration_version is not None
                    atomic_write(
                        migration_path,
                        previous_migration,
                        0o600,
                        expected_identity=(
                            migration_version.device,
                            migration_version.inode,
                        ),
                        expected_digest=migration_version.digest,
                        expected_mode=migration_version.mode,
                    )
        except BaseException as cleanup_error:
            rollback_errors.append(cleanup_error)
        if rollback_errors:
            raise ObconfigError(
                ConfigIssue(
                    1,
                    1,
                    "",
                    "concurrent replacement was preserved during migration rollback",
                )
            ) from original_error
        raise
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
    safe_active_executor: Any | None = None,
    dispatch_callback: Any | None = None,
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
    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--command", required=True)
    claim_parser.add_argument("--intended-version", required=True)
    projection_parser = sub.add_parser("config-projection")
    projection_parser.add_argument("--command", required=True)
    projection_parser.add_argument("--intended-version", required=True)
    abort_parser = sub.add_parser("abort")
    abort_parser.add_argument("--command", required=True)
    abort_parser.add_argument("--intended-version", required=True)
    finalize_parser = sub.add_parser("finalize")
    finalize_parser.add_argument("--command", required=True)
    finalize_parser.add_argument("--intended-version", required=True)
    finalize_parser.add_argument("--output", action="append", required=True)
    dispatch_parser = sub.add_parser("dispatch")
    dispatch_parser.add_argument("--command", required=True)
    dispatch_parser.add_argument("--intended-version", required=True)
    verify_dispatch_parser = sub.add_parser("verify-dispatch")
    verify_dispatch_parser.add_argument("--command", required=True)
    verify_dispatch_parser.add_argument("--intended-version", required=True)
    consume_parser = sub.add_parser("consume")
    consume_parser.add_argument("--command", required=True)
    consume_parser.add_argument("--intended-version", required=True)
    direct_parser = sub.add_parser("direct-api")
    direct_parser.add_argument(
        "--phase", required=True, choices=("analysis", "verification")
    )
    direct_parser.add_argument("--command")
    direct_parser.add_argument("--intended-version")
    safe_active_parser = sub.add_parser("safe-active")
    safe_active_parser.add_argument("--command", required=True)
    safe_active_parser.add_argument("--intended-version", required=True)
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

        if args.operation in {"direct-api", "safe-active"}:
            config_path = root / CONFIG_NAME
            config_binding = None
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
                data, _, config_raw, _ = load_config(
                    root, enforce_git=enforce_git
                )
                config_binding = capture_config_binding(
                    root,
                    enforce_git=enforce_git,
                    expected_digest=config_digest(config_raw),
                )
            if args.operation == "safe-active" or args.phase == "analysis":
                if not args.command or not args.intended_version:
                    raise ValueError(
                        "analysis direct-api requires --command and --intended-version"
                    )
                validate_claim(
                    root,
                    command=args.command,
                    intended_version=args.intended_version,
                    enforce_git=enforce_git,
                )
            if args.operation == "safe-active":
                if safe_active_executor is None:
                    active_results = execute_safe_active(data)
                else:
                    active_results = execute_safe_active(
                        data,
                        executor=safe_active_executor,
                        sleep=lambda _: None,
                    )
                validate_claim(
                    root,
                    command=args.command,
                    intended_version=args.intended_version,
                    enforce_git=enforce_git,
                )
                payload = Redactor(data).value(
                    {
                        "schema_version": 1,
                        "phase": "analysis",
                        "safe_active": active_results,
                    }
                )
                print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
                return 0
            if direct_transport is None:
                direct_results = collect_direct_evidence(data, phase=args.phase)
            else:
                direct_results = collect_direct_evidence(
                    data,
                    phase=args.phase,
                    transport=direct_transport,
                )
            if args.phase == "analysis":
                validate_claim(
                    root,
                    command=args.command,
                    intended_version=args.intended_version,
                    enforce_git=enforce_git,
                )
            elif config_binding is not None:
                current_binding = capture_config_binding(
                    root,
                    enforce_git=enforce_git,
                    expected_digest=config_binding.digest,
                )
                if current_binding != config_binding:
                    raise ObconfigError(
                        ConfigIssue(
                            1,
                            1,
                            "",
                            "obconfig.yaml identity or mode changed during verification",
                        )
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

        if args.operation == "config-projection":
            claimed_before = validate_claim(
                root,
                command=args.command,
                intended_version=args.intended_version,
                enforce_git=enforce_git,
            )
            data, _, raw, _ = load_config(root, enforce_git=enforce_git)
            if config_digest(raw) != claimed_before.get("config_sha256"):
                raise ObconfigError(
                    ConfigIssue(
                        1,
                        1,
                        "",
                        "configuration projection does not match analysis claim",
                    )
                )
            payload = analysis_config_projection(data, claimed_before)
            claimed_after = validate_claim(
                root,
                command=args.command,
                intended_version=args.intended_version,
                enforce_git=enforce_git,
            )
            if claimed_after != claimed_before:
                raise ObconfigError(
                    ConfigIssue(
                        1,
                        1,
                        "",
                        "analysis claim changed during configuration projection",
                    )
                )
            print(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                )
            )
            return 0

        if args.operation == "abort":
            abort_claim(
                root,
                command=args.command,
                intended_version=args.intended_version,
            )
            print("Aborted one-shot analysis claim without advancing the baseline.")
            return 0
        if args.operation == "finalize":
            finalized = finalize_claim(
                root,
                command=args.command,
                intended_version=args.intended_version,
                generated_outputs=args.output,
                enforce_git=enforce_git,
            )
            payload = {
                "finalized": True,
                "command": args.command,
                "intended_version": args.intended_version,
                "git_index_tree_sha": finalized["git_index_tree_sha"],
                "generated_output_sha256": finalized[
                    "generated_output_sha256"
                ],
                "output_count": finalized[
                    "generated_output_manifest"
                ]["output_count"],
            }
            print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            return 0
        if args.operation in {"dispatch", "verify-dispatch"}:
            dispatched = (
                record_dispatch(
                    root,
                    command=args.command,
                    intended_version=args.intended_version,
                )
                if args.operation == "dispatch"
                else verify_dispatch(
                    root,
                    command=args.command,
                    intended_version=args.intended_version,
                )
            )
            payload = {
                "dispatch_verified": True,
                "command": args.command,
                "intended_version": args.intended_version,
                "commit_sha": dispatched["commit_sha"],
                "tree_sha": dispatched["tree_sha"],
            }
            if dispatch_callback is not None:
                dispatch_callback(dict(payload))
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
        if args.operation == "claim":
            state = claim_authorization(
                root,
                command=args.command,
                intended_version=args.intended_version,
                enforce_git=enforce_git,
            )
            print(
                json.dumps(
                    Redactor(data).value(
                        {
                            "claimed": True,
                            "command": state["command"],
                            "intended_version": state["intended_version"],
                            "artifact_tree_sha256": state[
                                "artifact_tree_sha256"
                            ],
                            "artifact_delta": state["artifact_delta"],
                        }
                    ),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 0
        if args.operation == "consume":
            consume_claim(
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
