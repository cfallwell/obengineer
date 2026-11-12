#!/usr/bin/env python3
"""Secure schema-v4 obconfig loading, repair, hashing, and authorization."""

from __future__ import annotations

import copy
import contextlib
import hashlib
import ipaddress
import json
import math
import os
import re
import stat
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

import yaml

SCHEMA_VERSION = 4
CONFIG_NAME = "obconfig.yaml"
TEMPLATE_NAME = "obconfig.yaml.template"
STATE_DIRECTORY = ".obengineer"
TREE_ALGORITHM = "ob-artifact-tree-v1"
MAX_CONFIG_BYTES = 1024 * 1024
SAFE_ACTIVE_MAX_REQUESTS = 100
SAFE_ACTIVE_REQUESTS_PER_SECOND = 1
SAFE_ACTIVE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
SAFE_ACTIVE_PATHS = ("/robots.txt", "/.well-known/security.txt")
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas/obconfig.schema.json"
try:
    _SCHEMA_METADATA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    SECRET_PATHS = frozenset(_SCHEMA_METADATA["x-obengineer-secret-paths"])
    RETIRED = dict(_SCHEMA_METADATA["x-obengineer-retired-keys"])
except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
    raise RuntimeError("obconfig machine schema metadata is unavailable") from exc
SENSITIVE_PATHS = SECRET_PATHS | {"analysis_access.dummy_login.login_id"}
SECRET_KEY = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|credential)",
    re.IGNORECASE,
)
CREDENTIAL_SHAPE = re.compile(
    r"(?:"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+"
    r"|\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[A-Z0-9]{12,}"
    r"|\bgh[posur]_[A-Za-z0-9]{20,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?i:bearer)\s+[A-Za-z0-9._~+/=-]{8,}"
    r")"
)
HIGH_ENTROPY_CANDIDATE = re.compile(r"[A-Za-z0-9_~+/=-]{24,}")
REALM = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
INDEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
KNOWN: dict[str, set[str]] = {
    "engagement": {
        "application", "customer", "scope", "date", "document_version",
        "deployment_environment",
    },
    "initial_scope": {"authorized", "repositories", "parent_folders", "branches"},
    "artifacts": {"directory"},
    "cloud_diagrams": {"generate", "notes"},
    "surfaces": {
        "production_urls", "no_browser_reason", "host_and_remotes", "edge_cdn",
    },
    "security_assessment": {"mode", "authorized_origins"},
    "analysis_access": {"dummy_login"},
    "splunk": {"observability", "platform"},
    "backends": {
        "languages", "deploy_targets", "buses", "cloud_accounts", "gateway",
    },
    "tenancy": {
        "o11y_org_id", "thousandeyes_account_group", "tokens_held_by",
    },
    "standards": {
        "percentile", "workflow_naming", "baggage_header_budget_bytes",
        "baggage_value_ceiling_bytes", "unknown_dimension_threshold_pct",
    },
    "constraints": {
        "privacy_regimes", "data_residency", "consent_platform",
        "pii_deny_list_additions", "competing_eum_agents", "change_windows",
        "who_deploys_front_end", "who_deploys_collector",
    },
    "outcomes": {"first_journey", "audiences"},
    "traffic_baseline": {"rum", "apm", "logs", "infra_integrations"},
    "business_context": {
        "incident_experience", "operating_cost", "revenue_context",
        "business_information",
    },
    "public_evidence": {
        "allowed", "window_months", "brand_terms", "status_page_urls",
        "exclude_domains", "competitors",
    },
    "developer_tools": {"named", "matched"},
}
REQUIRED_SECTIONS = tuple(KNOWN)


@dataclass(frozen=True)
class ConfigIssue:
    line: int
    column: int
    path: str
    reason: str

    def __str__(self) -> str:
        location = f"line {self.line}, column {self.column}"
        path = f"{self.path}: " if self.path else ""
        return f"{location}: {path}{self.reason}"


class ObconfigError(RuntimeError):
    """An error safe to show after centralized redaction."""

    def __init__(self, issue: ConfigIssue):
        self.issue = issue
        super().__init__(str(issue))


class DuplicateKeyError(yaml.MarkedYAMLError):
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: UniqueLoader, node: yaml.MappingNode, deep=False):
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DuplicateKeyError(
                problem=f"duplicate key {key!r}",
                problem_mark=key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _walk_nodes(node: yaml.Node, path: str, marks: dict[str, tuple[int, int]]) -> None:
    marks[path] = (node.start_mark.line + 1, node.start_mark.column + 1)
    if isinstance(node, yaml.MappingNode):
        for key, value in node.value:
            key_name = str(getattr(key, "value", ""))
            child = f"{path}.{key_name}" if path else key_name
            marks[child] = (key.start_mark.line + 1, key.start_mark.column + 1)
            _walk_nodes(value, child, marks)
    elif isinstance(node, yaml.SequenceNode):
        for index, child_node in enumerate(node.value):
            _walk_nodes(child_node, f"{path}[{index}]", marks)


def parse_yaml(raw: bytes) -> tuple[dict[str, Any], dict[str, tuple[int, int]]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ObconfigError(
            ConfigIssue(exc.start + 1, 1, "", "configuration must be UTF-8")
        ) from None
    try:
        data = yaml.load(text, Loader=UniqueLoader)
        node = yaml.compose(text, Loader=UniqueLoader)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        reason = exc.problem or "invalid YAML syntax"
        # Parser messages can contain source-derived values. Preserve only a catalog.
        if isinstance(exc, DuplicateKeyError):
            reason = "duplicate mapping key"
        elif "tab" in reason.casefold():
            reason = "tab characters are not allowed for YAML indentation"
        elif "expected" in reason.casefold():
            reason = "invalid YAML structure"
        else:
            reason = "invalid YAML syntax"
        raise ObconfigError(
            ConfigIssue(
                (mark.line + 1) if mark else 1,
                (mark.column + 1) if mark else 1,
                "",
                reason,
            )
        ) from None
    if not isinstance(data, dict) or node is None:
        raise ObconfigError(ConfigIssue(1, 1, "", "top level must be a mapping"))
    marks: dict[str, tuple[int, int]] = {}
    _walk_nodes(node, "", marks)
    return data, marks


class Redactor:
    """One redaction path for terminal, errors, state, and generated metadata."""

    def __init__(self, config: Mapping[str, Any] | None = None):
        self._values: set[str] = set()
        if config:
            for path in SENSITIVE_PATHS:
                value = get_path(config, path)
                if isinstance(value, str) and value:
                    self._values.add(value)

    def text(self, value: object) -> str:
        result = str(value).replace("\r", " ").replace("\n", " ")
        for secret in sorted(self._values, key=len, reverse=True):
            result = result.replace(secret, "[REDACTED]")
        result = CREDENTIAL_SHAPE.sub("[REDACTED]", result)
        result = HIGH_ENTROPY_CANDIDATE.sub(_redact_high_entropy, result)
        return result

    def value(self, value: Any, path: str = "") -> Any:
        key = path.rsplit(".", 1)[-1]
        if path in SENSITIVE_PATHS or SECRET_KEY.search(key):
            return "configured" if value not in ("", None, [], {}) else "not configured"
        if isinstance(value, dict):
            return {
                str(k): self.value(v, f"{path}.{k}" if path else str(k))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self.value(item, path) for item in value]
        return self.text(value) if isinstance(value, str) else value


def _redact_high_entropy(match: re.Match[str]) -> str:
    candidate = match.group(0)
    counts = {character: candidate.count(character) for character in set(candidate)}
    entropy = -sum(
        (count / len(candidate)) * math.log2(count / len(candidate))
        for count in counts.values()
    )
    classes = sum(
        any(character in alphabet for character in candidate)
        for alphabet in (
            "abcdefghijklmnopqrstuvwxyz",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "0123456789",
            "_~+/=-",
        )
    )
    return "[REDACTED]" if entropy > 4.0 and classes >= 3 else candidate


def get_path(data: Mapping[str, Any], dotted: str, default: Any = None) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return default
        value = value[part]
    return value


def _mark(marks: Mapping[str, tuple[int, int]], path: str) -> tuple[int, int]:
    while path:
        if path in marks:
            return marks[path]
        path = path.rsplit(".", 1)[0] if "." in path else ""
    return (1, 1)


def _issue(
    marks: Mapping[str, tuple[int, int]], path: str, reason: str
) -> ConfigIssue:
    line, column = _mark(marks, path)
    return ConfigIssue(line, column, path, reason)


def _schema_accepts_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
    }.get(expected, False)


def _validate_schema_node(
    value: Any,
    schema: Mapping[str, Any],
    marks: Mapping[str, tuple[int, int]],
    path: str,
) -> None:
    if "oneOf" in schema:
        matches = 0
        for candidate in schema["oneOf"]:
            try:
                _validate_schema_node(value, candidate, marks, path)
                matches += 1
            except ObconfigError:
                pass
        if matches != 1:
            raise ObconfigError(_issue(marks, path, "does not match the field contract"))
        return
    if "const" in schema and value != schema["const"]:
        raise ObconfigError(_issue(marks, path, "must equal the fixed schema value"))
    expected = schema.get("type")
    if expected and not _schema_accepts_type(value, expected):
        raise ObconfigError(_issue(marks, path, f"must be {expected}"))
    if "enum" in schema and value not in schema["enum"]:
        raise ObconfigError(_issue(marks, path, "must be one of the allowed values"))
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        raise ObconfigError(_issue(marks, path, "must not be empty"))
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and "minimum" in schema
        and value < schema["minimum"]
    ):
        raise ObconfigError(
            _issue(marks, path, f"must be at least {schema['minimum']}")
        )
    if isinstance(value, Mapping):
        properties = schema.get("properties", {})
        for required in schema.get("required", []):
            if required not in value:
                missing = f"{path}.{required}" if path else required
                raise ObconfigError(_issue(marks, path, f"missing required key {missing}"))
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    unknown = f"{path}.{key}" if path else str(key)
                    raise ObconfigError(_issue(marks, unknown, "unknown key is not allowed"))
        for key, item in value.items():
            if key in properties:
                child = f"{path}.{key}" if path else str(key)
                _validate_schema_node(item, properties[key], marks, child)
    if isinstance(value, list):
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            _validate_schema_node(item, item_schema, marks, f"{path}[{index}]")
        if schema.get("uniqueItems") and len({repr(item) for item in value}) != len(value):
            raise ObconfigError(_issue(marks, path, "must contain unique values"))


def _mapping(
    data: Mapping[str, Any],
    marks: Mapping[str, tuple[int, int]],
    path: str,
) -> Mapping[str, Any]:
    value = get_path(data, path)
    if not isinstance(value, Mapping):
        raise ObconfigError(_issue(marks, path, "must be a mapping"))
    return value


def _string(
    data: Mapping[str, Any],
    marks: Mapping[str, tuple[int, int]],
    path: str,
    *,
    nonempty: bool = False,
) -> str:
    value = get_path(data, path)
    if not isinstance(value, str) or (nonempty and not value.strip()):
        reason = "must be a nonempty scalar" if nonempty else "must be a string"
        raise ObconfigError(_issue(marks, path, reason))
    return value


def _string_list(
    data: Mapping[str, Any],
    marks: Mapping[str, tuple[int, int]],
    path: str,
) -> list[str]:
    value = get_path(data, path)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ObconfigError(_issue(marks, path, "must be a list of strings"))
    return value


def _boolean(
    data: Mapping[str, Any],
    marks: Mapping[str, tuple[int, int]],
    path: str,
) -> bool:
    value = get_path(data, path)
    if not isinstance(value, bool):
        raise ObconfigError(_issue(marks, path, "must be a boolean"))
    return value


def _integer(
    data: Mapping[str, Any],
    marks: Mapping[str, tuple[int, int]],
    path: str,
    *,
    minimum: int | None = None,
) -> int:
    value = get_path(data, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ObconfigError(_issue(marks, path, "must be an integer"))
    if minimum is not None and value < minimum:
        raise ObconfigError(_issue(marks, path, f"must be at least {minimum}"))
    return value


def _number_or_unknown(
    data: Mapping[str, Any],
    marks: Mapping[str, tuple[int, int]],
    path: str,
) -> None:
    value = get_path(data, path)
    if value == "unknown":
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ObconfigError(
            _issue(marks, path, "must be a nonnegative number or unknown")
        )


def _mapping_list(
    data: Mapping[str, Any],
    marks: Mapping[str, tuple[int, int]],
    path: str,
) -> list[Mapping[str, Any]]:
    value = get_path(data, path)
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in value
    ):
        raise ObconfigError(_issue(marks, path, "must be a list of mappings"))
    return value


def normalize_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("must be an exact HTTPS origin") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("must be an exact HTTPS origin without path or credentials")
    host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    if "*" in host:
        raise ValueError("wildcard origins are not allowed")
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        if host == "localhost" or "." not in host:
            raise ValueError("origin host must be a public fully qualified name") from None
    else:
        if not address.is_global:
            raise ValueError("loopback, private, link-local, and unspecified origins are not allowed")
        host = f"[{host}]" if address.version == 6 else host
    return f"https://{host}{f':{port}' if port not in (None, 443) else ''}"


def validate_platform_host(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("platform host must be an exact HTTPS host") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("platform host must be HTTPS without path, userinfo, query, or fragment")
    host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    host = f"[{host}]" if ":" in host else host
    return f"https://{host}{f':{port}' if port not in (None, 443) else ''}"


def safe_active_requests(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the complete fixed active plan; passive/none always return no requests."""
    security = config["security_assessment"]
    if security["mode"] != "safe-active":
        return []
    requests: list[dict[str, Any]] = []
    for value in security["authorized_origins"]:
        origin = normalize_origin(value)
        for path in SAFE_ACTIVE_PATHS:
            requests.append(
                {
                    "method": "HEAD",
                    "url": origin + path,
                    "follow_redirects": False,
                    "max_requests": SAFE_ACTIVE_MAX_REQUESTS,
                    "requests_per_second": SAFE_ACTIVE_REQUESTS_PER_SECOND,
                }
            )
    if len(requests) > SAFE_ACTIVE_MAX_REQUESTS:
        raise ObconfigError(
            ConfigIssue(1, 1, "security_assessment.authorized_origins", "fixed safe-active request ceiling exceeded")
        )
    return requests


def validate_config(
    data: Mapping[str, Any],
    marks: Mapping[str, tuple[int, int]],
) -> list[str]:
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ObconfigError(
            _issue(marks, "schema_version", "must be integer 4")
        )
    for retired, reason in RETIRED.items():
        if get_path(data, retired, object()) is not object() and _has_path(data, retired):
            raise ObconfigError(_issue(marks, retired, reason))
    for section in REQUIRED_SECTIONS:
        if section not in data:
            raise ObconfigError(_issue(marks, "", f"missing required section {section}"))
        _mapping(data, marks, section)

    _string(data, marks, "engagement.application", nonempty=True)
    for path in (
        "engagement.customer",
        "engagement.scope",
        "engagement.date",
    ):
        _string(data, marks, path)
    _integer(data, marks, "engagement.document_version", minimum=1)
    _string(data, marks, "engagement.deployment_environment", nonempty=True)

    authorized = get_path(data, "initial_scope.authorized")
    if authorized not in {"unknown", "full", "repositories", "parent_folders"}:
        raise ObconfigError(
            _issue(
                marks,
                "initial_scope.authorized",
                "must be unknown, full, repositories, or parent_folders",
            )
        )
    _string_list(data, marks, "initial_scope.repositories")
    for index, item in enumerate(
        _mapping_list(data, marks, "initial_scope.parent_folders")
    ):
        if not all(isinstance(item.get(key), str) for key in ("repository", "path")):
            raise ObconfigError(
                _issue(
                    marks,
                    f"initial_scope.parent_folders[{index}]",
                    "repository and path must be strings",
                )
            )
    for index, item in enumerate(_mapping_list(data, marks, "initial_scope.branches")):
        if not all(
            isinstance(item.get(key), str) for key in ("repository", "branch")
        ):
            raise ObconfigError(
                _issue(
                    marks,
                    f"initial_scope.branches[{index}]",
                    "repository and branch must be strings",
                )
            )

    _string(data, marks, "artifacts.directory", nonempty=True)
    _boolean(data, marks, "cloud_diagrams.generate")
    _string(data, marks, "cloud_diagrams.notes")

    urls = _string_list(data, marks, "surfaces.production_urls")
    no_browser = _string(data, marks, "surfaces.no_browser_reason")
    _string(data, marks, "surfaces.host_and_remotes")
    _string(data, marks, "surfaces.edge_cdn")
    if bool(urls) == bool(no_browser.strip()):
        raise ObconfigError(
            _issue(
                marks,
                "surfaces.production_urls",
                "provide production_urls or no_browser_reason, but not both",
            )
        )
    for index, url in enumerate(urls):
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ObconfigError(
                _issue(marks, f"surfaces.production_urls[{index}]", "must be an absolute HTTP(S) URL")
            )

    security = _mapping(data, marks, "security_assessment")
    mode = security.get("mode")
    if mode not in {"passive", "safe-active", "none"}:
        raise ObconfigError(
            _issue(marks, "security_assessment.mode", "must be passive, safe-active, or none")
        )
    origins = _string_list(data, marks, "security_assessment.authorized_origins")
    if len(origins) * len(SAFE_ACTIVE_PATHS) > SAFE_ACTIVE_MAX_REQUESTS:
        raise ObconfigError(
            _issue(
                marks,
                "security_assessment.authorized_origins",
                "fixed safe-active request ceiling exceeded",
            )
        )
    if (mode == "safe-active") != bool(origins):
        raise ObconfigError(
            _issue(
                marks,
                "security_assessment.authorized_origins",
                "must be nonempty only for safe-active mode",
            )
        )
    normalized_origins: set[str] = set()
    for index, origin in enumerate(origins):
        try:
            normalized = normalize_origin(origin)
        except ValueError as exc:
            raise ObconfigError(
                _issue(marks, f"security_assessment.authorized_origins[{index}]", str(exc))
            ) from None
        if origin != normalized:
            raise ObconfigError(
                _issue(
                    marks,
                    f"security_assessment.authorized_origins[{index}]",
                    "must already be a normalized exact HTTPS origin",
                )
            )
        if normalized in normalized_origins:
            raise ObconfigError(
                _issue(marks, f"security_assessment.authorized_origins[{index}]", "duplicate normalized origin")
            )
        normalized_origins.add(normalized)

    login = _mapping(data, marks, "analysis_access.dummy_login")
    login_id, password = login.get("login_id"), login.get("password")
    if not isinstance(login_id, str) or not isinstance(password, str):
        raise ObconfigError(
            _issue(marks, "analysis_access.dummy_login", "login_id and password must be strings")
        )
    if bool(login_id) != bool(password):
        raise ObconfigError(
            _issue(marks, "analysis_access.dummy_login", "login_id and password must be supplied together")
        )

    o11y = _mapping(data, marks, "splunk.observability")
    realm, o11y_token = o11y.get("realm"), o11y.get("read_token")
    if not isinstance(realm, str) or not isinstance(o11y_token, str):
        raise ObconfigError(_issue(marks, "splunk.observability", "realm and read_token must be strings"))
    if bool(realm) != bool(o11y_token):
        raise ObconfigError(_issue(marks, "splunk.observability", "realm and read_token must be supplied together"))
    if realm and not REALM.fullmatch(realm):
        raise ObconfigError(_issue(marks, "splunk.observability.realm", "invalid realm"))

    platform = _mapping(data, marks, "splunk.platform")
    host, platform_token = platform.get("host"), platform.get("read_token")
    indexes = platform.get("index_allowlist")
    if not isinstance(host, str) or not isinstance(platform_token, str):
        raise ObconfigError(_issue(marks, "splunk.platform", "host and read_token must be strings"))
    if not isinstance(indexes, list) or any(not isinstance(item, str) for item in indexes):
        raise ObconfigError(_issue(marks, "splunk.platform.index_allowlist", "must be a list of strings"))
    configured = [bool(host), bool(platform_token), bool(indexes)]
    if any(configured) and not all(configured):
        raise ObconfigError(
            _issue(marks, "splunk.platform", "host, read_token, and nonempty index_allowlist must be supplied together")
        )
    if host:
        try:
            validate_platform_host(host)
        except ValueError as exc:
            raise ObconfigError(_issue(marks, "splunk.platform.host", str(exc))) from None
    seen: set[str] = set()
    for index, name in enumerate(indexes):
        if name in seen or name in {"*", "_all"} or "*" in name or not INDEX.fullmatch(name):
            raise ObconfigError(
                _issue(marks, f"splunk.platform.index_allowlist[{index}]", "invalid, wildcard, or duplicate index")
            )
        seen.add(name)

    for path in (
        "backends.languages",
        "backends.deploy_targets",
        "backends.buses",
        "backends.cloud_accounts",
        "constraints.privacy_regimes",
        "constraints.pii_deny_list_additions",
        "constraints.competing_eum_agents",
        "outcomes.audiences",
        "business_context.operating_cost.observability_tools_in_use",
        "public_evidence.brand_terms",
        "public_evidence.status_page_urls",
        "public_evidence.exclude_domains",
        "public_evidence.competitors",
        "developer_tools.named",
    ):
        _string_list(data, marks, path)
    for path in (
        "backends.gateway",
        "tenancy.o11y_org_id",
        "tenancy.thousandeyes_account_group",
        "tenancy.tokens_held_by",
        "standards.workflow_naming",
        "constraints.data_residency",
        "constraints.consent_platform",
        "constraints.change_windows",
        "constraints.who_deploys_front_end",
        "constraints.who_deploys_collector",
        "outcomes.first_journey",
        "business_context.operating_cost.opex_challenges",
        "business_context.revenue_context.revenue_challenges",
        "business_context.business_information.business_model",
        "business_context.business_information.seasonality",
        "business_context.business_information.growth_or_margin_pressure",
        "business_context.business_information.regulatory_exposure",
    ):
        _string(data, marks, path)
    percentile = get_path(data, "standards.percentile")
    if not isinstance(percentile, (str, int, float)) or isinstance(percentile, bool):
        raise ObconfigError(
            _issue(marks, "standards.percentile", "must be a scalar percentile")
        )
    _integer(data, marks, "standards.baggage_header_budget_bytes", minimum=1)
    _integer(data, marks, "standards.baggage_value_ceiling_bytes", minimum=1)
    threshold = get_path(data, "standards.unknown_dimension_threshold_pct")
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or threshold < 0
    ):
        raise ObconfigError(
            _issue(
                marks,
                "standards.unknown_dimension_threshold_pct",
                "must be a nonnegative number",
            )
        )

    for section, fields in {
        "traffic_baseline.rum": (
            "sessions_per_day_avg",
            "sessions_per_day_peak",
            "page_views_per_session",
        ),
        "traffic_baseline.apm": (
            "requests_per_minute_avg",
            "requests_per_minute_peak",
            "spans_per_trace",
        ),
        "traffic_baseline.logs": ("gb_per_hour_avg", "gb_per_hour_peak"),
        "business_context.incident_experience": (
            "mttd_minutes",
            "mtta_minutes",
            "mttr_minutes",
            "mtti_minutes",
            "incidents_per_month",
            "sev1_per_quarter",
            "responders_per_incident",
            "war_room_hours_per_month",
            "pct_incidents_found_by_customers",
        ),
        "business_context.operating_cost": (
            "annual_tooling_spend",
            "duplicate_agents_on_page",
            "engineering_hours_per_month_on_triage",
            "fully_loaded_hourly_cost",
        ),
        "business_context.revenue_context": (
            "revenue_per_hour_online",
            "orders_per_day",
            "average_order_value",
            "conversion_rate_pct",
            "cart_abandonment_pct",
        ),
    }.items():
        _mapping(data, marks, section)
        for field in fields:
            _number_or_unknown(data, marks, f"{section}.{field}")
    _mapping_list(data, marks, "traffic_baseline.infra_integrations")
    peak_events = get_path(data, "business_context.revenue_context.peak_events")
    if not isinstance(peak_events, list):
        raise ObconfigError(
            _issue(
                marks,
                "business_context.revenue_context.peak_events",
                "must be a list",
            )
        )
    _string_list(
        data, marks, "business_context.business_information.strategic_initiatives"
    )
    _boolean(data, marks, "public_evidence.allowed")
    _integer(data, marks, "public_evidence.window_months", minimum=1)
    for index, match in enumerate(
        _mapping_list(data, marks, "developer_tools.matched")
    ):
        if not all(
            isinstance(match.get(key), str) for key in ("tool", "via", "key")
        ):
            raise ObconfigError(
                _issue(
                    marks,
                    f"developer_tools.matched[{index}]",
                    "tool, via, and key must be strings",
                )
            )

    _validate_schema_node(data, _SCHEMA_METADATA, marks, "")
    warnings: list[str] = []
    for section, fields in KNOWN.items():
        value = data.get(section)
        if isinstance(value, Mapping):
            warnings.extend(
                f"unknown key {section}.{key} is ignored by runtime consumers"
                for key in value if key not in fields
            )
    return warnings


def _has_path(data: Mapping[str, Any], dotted: str) -> bool:
    sentinel = object()
    value: Any = data
    for part in dotted.split("."):
        if not isinstance(value, Mapping):
            return False
        value = value.get(part, sentinel)
        if value is sentinel:
            return False
    return True


def _regular_no_symlink(path: Path, label: str) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ObconfigError(ConfigIssue(1, 1, "", f"cannot stat {label}: {exc.strerror}")) from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ObconfigError(ConfigIssue(1, 1, "", f"{label} must be a regular file, not a symlink"))
    return info


def _read_regular_bytes(
    path: Path,
    label: str,
    *,
    limit: int = 64 * 1024 * 1024,
    required_mode: int | None = 0o600,
) -> bytes:
    parent_info = path.parent.lstat()
    if stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode):
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"{label} parent must be a regular directory")
        )
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    parent_descriptor = os.open(path.parent, directory_flags)
    descriptor: int | None = None
    try:
        opened_parent = os.fstat(parent_descriptor)
        if (opened_parent.st_dev, opened_parent.st_ino) != (
            parent_info.st_dev,
            parent_info.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{label} parent changed during secure open")
            )
        info = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{label} must be a regular file, not a symlink")
            )
        if info.st_size > limit:
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{label} exceeds the fixed size limit")
            )
        if (
            os.name == "posix"
            and required_mode is not None
            and stat.S_IMODE(info.st_mode) != required_mode
        ):
            raise ObconfigError(
                ConfigIssue(
                    1, 1, "", f"{label} mode must be {required_mode:04o}"
                )
            )
        descriptor = os.open(
            path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_descriptor,
        )
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{label} changed during secure open")
            )
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > limit:
                raise ObconfigError(
                    ConfigIssue(1, 1, "", f"{label} exceeds the fixed size limit")
                )
        after = os.fstat(descriptor)
        current = os.stat(
            path.name, dir_fd=parent_descriptor, follow_symlinks=False
        )
        if (
            (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
            or size != opened.st_size
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{label} changed while being read")
            )
        return b"".join(chunks)
    except FileNotFoundError:
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"{label} does not exist")
        ) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_descriptor)


def read_project_file(
    project_root: Path,
    relative: str | Path,
    label: str,
    *,
    limit: int = 64 * 1024 * 1024,
    required_mode: int | None = None,
) -> bytes:
    candidate = PurePosixPath(str(relative).replace("\\", "/"))
    if (
        candidate.is_absolute()
        or not candidate.parts
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise ObconfigError(ConfigIssue(1, 1, "", f"{label} path is unsafe"))
    root = project_root.resolve()
    root_info = root.lstat()
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directory = os.open(root, directory_flags)
    try:
        opened_root = os.fstat(directory)
        if (opened_root.st_dev, opened_root.st_ino) != (
            root_info.st_dev,
            root_info.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{label} root changed during secure open")
            )
        for part in candidate.parts[:-1]:
            try:
                child = os.open(part, directory_flags, dir_fd=directory)
            except OSError:
                raise ObconfigError(
                    ConfigIssue(1, 1, "", f"{label} parent is unsafe")
                ) from None
            os.close(directory)
            directory = child
        name = candidate.parts[-1]
        try:
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except OSError as exc:
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"cannot stat {label}: {exc.strerror}")
            ) from None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{label} must be a regular file")
            )
        if (
            os.name == "posix"
            and required_mode is not None
            and stat.S_IMODE(info.st_mode) != required_mode
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{label} mode must be {required_mode:04o}")
            )
        if info.st_size > limit:
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{label} exceeds the fixed size limit")
            )
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory,
        )
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise ObconfigError(
                    ConfigIssue(1, 1, "", f"{label} changed during secure open")
                )
            data = bytearray()
            while len(data) <= limit:
                chunk = os.read(descriptor, min(1024 * 1024, limit + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            after = os.fstat(descriptor)
            current = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if (
                len(data) > limit
                or (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or (current.st_dev, current.st_ino)
                != (opened.st_dev, opened.st_ino)
            ):
                raise ObconfigError(
                    ConfigIssue(1, 1, "", f"{label} changed while being read")
                )
            return bytes(data)
        finally:
            os.close(descriptor)
    finally:
        os.close(directory)


def _git_check(project_root: Path, config: Path) -> None:
    relative = config.relative_to(project_root).as_posix()
    tracked = subprocess.run(
        ["git", "-C", str(project_root), "ls-files", "--error-unmatch", "--", relative],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if tracked.returncode == 0:
        raise ObconfigError(ConfigIssue(1, 1, "", "obconfig.yaml is tracked by git; remove it from the index before continuing"))
    ignored = subprocess.run(
        ["git", "-C", str(project_root), "check-ignore", "-q", "--", relative],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ignored.returncode != 0:
        raise ObconfigError(ConfigIssue(1, 1, "", "obconfig.yaml is not ignored; add exact /obconfig.yaml to the root .gitignore"))


def preflight_config_creation(project_root: Path) -> None:
    root = project_root.resolve()
    local = root / STATE_DIRECTORY
    if local.is_symlink():
        raise ObconfigError(
            ConfigIssue(1, 1, "", ".obengineer must not be a symlink")
        )
    ignore = root / ".gitignore"
    raw = _read_regular_bytes(
        ignore,
        ".gitignore",
        limit=1024 * 1024,
        required_mode=None,
    )
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        raise ObconfigError(
            ConfigIssue(1, 1, "", ".gitignore must be UTF-8")
        ) from None
    if "/obconfig.yaml" not in lines:
        raise ObconfigError(
            ConfigIssue(
                1,
                1,
                "",
                "root .gitignore must contain exact /obconfig.yaml before creation",
            )
        )
    tracked = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "--error-unmatch",
            "--",
            CONFIG_NAME,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if tracked.returncode == 0:
        raise ObconfigError(
            ConfigIssue(
                1, 1, "", "obconfig.yaml is tracked by git; creation is refused"
            )
        )
    ignored = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "-q", "--", CONFIG_NAME],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ignored.returncode != 0:
        raise ObconfigError(
            ConfigIssue(1, 1, "", "git does not ignore root obconfig.yaml")
        )


def read_config_bytes(
    project_root: Path,
    *,
    enforce_git: bool = True,
    enforce_mode: bool = True,
) -> bytes:
    root = project_root.resolve()
    path = root / CONFIG_NAME
    info = _regular_no_symlink(path, CONFIG_NAME)
    if info.st_size > MAX_CONFIG_BYTES:
        raise ObconfigError(ConfigIssue(1, 1, "", "obconfig.yaml exceeds the 1 MiB limit"))
    if os.name == "posix" and enforce_mode and stat.S_IMODE(info.st_mode) != 0o600:
        raise ObconfigError(ConfigIssue(1, 1, "", "obconfig.yaml mode must be 0600; explicit repair can tighten it"))
    if enforce_git:
        _git_check(root, path)
    return _read_regular_bytes(
        path,
        CONFIG_NAME,
        limit=MAX_CONFIG_BYTES,
        required_mode=0o600 if enforce_mode else None,
    )


def load_config(
    project_root: Path,
    *,
    enforce_git: bool = True,
    enforce_mode: bool = True,
) -> tuple[dict[str, Any], dict[str, tuple[int, int]], bytes, list[str]]:
    raw = read_config_bytes(
        project_root, enforce_git=enforce_git, enforce_mode=enforce_mode
    )
    data, marks = parse_yaml(raw)
    warnings = validate_config(data, marks)
    return data, marks, raw, warnings


def config_digest(raw: bytes) -> str:
    return hashlib.sha256(b"obconfig-v4\0" + raw).hexdigest()


def resolve_artifact_directory(project_root: Path, value: str) -> Path:
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if (
        not normalized
        or "\x00" in normalized
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise ObconfigError(ConfigIssue(1, 1, "artifacts.directory", "must be one project-relative directory without traversal"))
    root = project_root.resolve()
    current = root
    for part in pure.parts:
        current = current / part
        try:
            info = current.lstat()
        except OSError as exc:
            raise ObconfigError(ConfigIssue(1, 1, "artifacts.directory", f"cannot stat artifact path: {exc.strerror}")) from None
        if stat.S_ISLNK(info.st_mode):
            raise ObconfigError(ConfigIssue(1, 1, "artifacts.directory", "symlinks are not allowed in artifact paths"))
    if not current.is_dir():
        raise ObconfigError(ConfigIssue(1, 1, "artifacts.directory", "must name a directory"))
    if root not in current.resolve().parents:
        raise ObconfigError(ConfigIssue(1, 1, "artifacts.directory", "resolves outside the project"))
    return current


def _manifest_path(project_root: Path) -> Path:
    return project_root / STATE_DIRECTORY / "artifact-manifest.json"


def _safe_local_directory(project_root: Path) -> Path:
    root = project_root.resolve()
    root_info = root.lstat()
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(root, flags)
    child: int | None = None
    try:
        opened_root = os.fstat(descriptor)
        if (opened_root.st_dev, opened_root.st_ino) != (
            root_info.st_dev,
            root_info.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "project root changed during secure open")
            )
        try:
            info = os.stat(
                STATE_DIRECTORY, dir_fd=descriptor, follow_symlinks=False
            )
        except FileNotFoundError:
            try:
                os.mkdir(STATE_DIRECTORY, 0o700, dir_fd=descriptor)
            except FileExistsError:
                pass
            info = os.stat(
                STATE_DIRECTORY, dir_fd=descriptor, follow_symlinks=False
            )
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ObconfigError(
                ConfigIssue(1, 1, "", ".obengineer must be a regular directory")
            )
        child = os.open(STATE_DIRECTORY, flags, dir_fd=descriptor)
        opened = os.fstat(child)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ObconfigError(
                ConfigIssue(1, 1, "", ".obengineer changed during secure open")
            )
        if os.name == "posix":
            os.fchmod(child, 0o700)
        os.fsync(descriptor)
    finally:
        if child is not None:
            os.close(child)
        os.close(descriptor)
    return root / STATE_DIRECTORY


def _safe_state_subdirectory(project_root: Path, name: str) -> Path:
    if "/" in name or name in {"", ".", ".."}:
        raise ValueError("invalid state directory name")
    local = _safe_local_directory(project_root)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(local, flags)
    child: int | None = None
    try:
        try:
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        except FileNotFoundError:
            try:
                os.mkdir(name, 0o700, dir_fd=descriptor)
            except FileExistsError:
                pass
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{name} must be a regular directory")
            )
        child = os.open(name, flags, dir_fd=descriptor)
        opened = os.fstat(child)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{name} changed during secure open")
            )
        if os.name == "posix":
            os.fchmod(child, 0o700)
        os.fsync(descriptor)
    finally:
        if child is not None:
            os.close(child)
        os.close(descriptor)
    return local / name


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists() and not path.is_symlink():
        return {}
    try:
        value = json.loads(
            _read_regular_bytes(path, "artifact manifest").decode("utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def hash_artifact_tree(
    project_root: Path,
    directory: str,
    *,
    write_manifest: bool = False,
) -> dict[str, Any]:
    root = resolve_artifact_directory(project_root, directory)
    records: list[tuple[bytes, int, str]] = []
    total = 0
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    root_info = root.lstat()
    root_descriptor = os.open(root, directory_flags)

    def walk(descriptor: int, prefix: tuple[str, ...]) -> None:
        nonlocal total
        for name in sorted(os.listdir(descriptor), key=lambda item: item.encode("utf-8")):
            relative = "/".join((*prefix, name))
            try:
                info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except OSError as exc:
                raise ObconfigError(
                    ConfigIssue(
                        1,
                        1,
                        "artifacts.directory",
                        f"cannot stat artifact {redact_path(relative)}: {exc.strerror}",
                    )
                ) from None
            if stat.S_ISDIR(info.st_mode):
                try:
                    child = os.open(name, directory_flags, dir_fd=descriptor)
                except OSError:
                    raise ObconfigError(
                        ConfigIssue(
                            1,
                            1,
                            "artifacts.directory",
                            f"artifact directory changed during open: {redact_path(relative)}",
                        )
                    ) from None
                try:
                    opened = os.fstat(child)
                    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                        raise ObconfigError(
                            ConfigIssue(
                                1,
                                1,
                                "artifacts.directory",
                                f"artifact directory changed during open: {redact_path(relative)}",
                            )
                        )
                    walk(child, (*prefix, name))
                    after_directory = os.fstat(child)
                    current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    if (
                        (
                            opened.st_dev,
                            opened.st_ino,
                            opened.st_mtime_ns,
                            opened.st_ctime_ns,
                        )
                        != (
                            after_directory.st_dev,
                            after_directory.st_ino,
                            after_directory.st_mtime_ns,
                            after_directory.st_ctime_ns,
                        )
                        or (current.st_dev, current.st_ino)
                        != (opened.st_dev, opened.st_ino)
                    ):
                        raise ObconfigError(
                            ConfigIssue(
                                1,
                                1,
                                "artifacts.directory",
                                f"artifact directory changed while read: {redact_path(relative)}",
                            )
                        )
                finally:
                    os.close(child)
                continue
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise ObconfigError(
                    ConfigIssue(
                        1,
                        1,
                        "artifacts.directory",
                        f"unsupported artifact entry {redact_path(relative)}",
                    )
                )
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                file_descriptor = os.open(name, flags, dir_fd=descriptor)
            except OSError:
                raise ObconfigError(
                    ConfigIssue(
                        1,
                        1,
                        "artifacts.directory",
                        f"artifact changed during open: {redact_path(relative)}",
                    )
                ) from None
            digest = hashlib.sha256()
            size = 0
            try:
                opened = os.fstat(file_descriptor)
                if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise ObconfigError(
                        ConfigIssue(
                            1,
                            1,
                            "artifacts.directory",
                            f"artifact changed during open: {redact_path(relative)}",
                        )
                    )
                while True:
                    chunk = os.read(file_descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    size += len(chunk)
                after = os.fstat(file_descriptor)
                current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if (
                    (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    or (current.st_dev, current.st_ino)
                    != (opened.st_dev, opened.st_ino)
                    or size != opened.st_size
                ):
                    raise ObconfigError(
                        ConfigIssue(
                            1,
                            1,
                            "artifacts.directory",
                            f"artifact changed while read: {redact_path(relative)}",
                        )
                    )
            finally:
                os.close(file_descriptor)
            records.append((relative.encode("utf-8"), size, digest.hexdigest()))
            total += size

    try:
        opened_root = os.fstat(root_descriptor)
        if (opened_root.st_dev, opened_root.st_ino) != (
            root_info.st_dev,
            root_info.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(
                    1, 1, "artifacts.directory", "artifact directory changed during open"
                )
            )
        walk(root_descriptor, ())
        after_root = os.fstat(root_descriptor)
        current_root = root.lstat()
        if (
            (
                opened_root.st_dev,
                opened_root.st_ino,
                opened_root.st_mtime_ns,
                opened_root.st_ctime_ns,
            )
            != (
                after_root.st_dev,
                after_root.st_ino,
                after_root.st_mtime_ns,
                after_root.st_ctime_ns,
            )
            or (current_root.st_dev, current_root.st_ino)
            != (opened_root.st_dev, opened_root.st_ino)
        ):
            raise ObconfigError(
                ConfigIssue(
                    1, 1, "artifacts.directory", "artifact directory changed while read"
                )
            )
    finally:
        os.close(root_descriptor)
    records.sort(key=lambda record: record[0])

    tree = hashlib.sha256()
    tree.update(TREE_ALGORITHM.encode() + b"\0")
    files: dict[str, dict[str, Any]] = {}
    for path_bytes, size, digest in records:
        digest_bytes = bytes.fromhex(digest)
        tree.update(struct.pack("!Q", len(path_bytes)))
        tree.update(path_bytes)
        tree.update(struct.pack("!Q", size))
        tree.update(digest_bytes)
        relative = path_bytes.decode("utf-8")
        files[relative] = {"bytes": size, "sha256": digest}

    previous = _read_manifest(_manifest_path(project_root)).get("files", {})
    previous = previous if isinstance(previous, dict) else {}
    added = sorted(set(files) - set(previous))
    deleted = sorted(set(previous) - set(files))
    changed = sorted(
        name for name in set(files) & set(previous) if files[name] != previous[name]
    )
    manifest = {
        "schema_version": 1,
        "algorithm": TREE_ALGORITHM,
        "tree_sha256": tree.hexdigest(),
        "file_count": len(files),
        "total_bytes": total,
        "files": files,
    }
    if write_manifest:
        atomic_write_json(_manifest_path(project_root), manifest, 0o600)
    return {
        **{key: value for key, value in manifest.items() if key != "files"},
        "added": [redact_path(path) for path in added],
        "changed": [redact_path(path) for path in changed],
        "deleted": [redact_path(path) for path in deleted],
        "reread": [redact_path(path) for path in sorted(added + changed)],
        "files": files,
    }


def redact_path(path: str) -> str:
    parts = path.split("/")
    return "/".join("[REDACTED]" if SECRET_KEY.search(part) else part for part in parts)


def atomic_write(
    path: Path,
    data: bytes,
    mode: int = 0o600,
    *,
    expect_absent: bool = False,
) -> None:
    parent = path.parent
    if parent.name == STATE_DIRECTORY:
        _safe_local_directory(parent.parent)
    parent_info = parent.lstat()
    if stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode):
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"{path.name} parent must be a regular directory")
        )
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    parent_descriptor = os.open(parent, directory_flags)
    descriptor: int | None = None
    temporary_name = f".{path.name}.{os.getpid()}.{time.time_ns()}"
    try:
        opened_parent = os.fstat(parent_descriptor)
        if (opened_parent.st_dev, opened_parent.st_ino) != (
            parent_info.st_dev,
            parent_info.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} parent changed during secure open")
            )
        try:
            existing = os.stat(
                path.name, dir_fd=parent_descriptor, follow_symlinks=False
            )
        except FileNotFoundError:
            existing = None
        if existing is not None and (
            stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode)
        ):
            raise ObconfigError(
                ConfigIssue(
                    1, 1, "", f"{path.name} must be a regular file, not a symlink"
                )
            )
        if expect_absent and existing is not None:
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} appeared during secure creation")
            )
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            mode,
            dir_fd=parent_descriptor,
        )
        os.fchmod(descriptor, mode)
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        try:
            current = os.stat(
                path.name, dir_fd=parent_descriptor, follow_symlinks=False
            )
        except FileNotFoundError:
            current = None
        if (existing is None) != (current is None) or (
            existing is not None
            and current is not None
            and (existing.st_dev, existing.st_ino)
            != (current.st_dev, current.st_ino)
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} changed before atomic replace")
            )
        if existing is None:
            try:
                os.link(
                    temporary_name,
                    path.name,
                    src_dir_fd=parent_descriptor,
                    dst_dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
            except FileExistsError:
                raise ObconfigError(
                    ConfigIssue(
                        1, 1, "", f"{path.name} appeared before atomic creation"
                    )
                ) from None
            os.unlink(temporary_name, dir_fd=parent_descriptor)
        else:
            os.replace(
                temporary_name,
                path.name,
                src_dir_fd=parent_descriptor,
                dst_dir_fd=parent_descriptor,
            )
        os.fsync(parent_descriptor)
        final = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        if os.name == "posix" and stat.S_IMODE(final.st_mode) != mode:
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} mode was not preserved")
            )
    except BaseException:
        try:
            if descriptor is not None:
                os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name, dir_fd=parent_descriptor)
        except OSError:
            pass
        raise
    finally:
        os.close(parent_descriptor)


def atomic_write_json(path: Path, value: Mapping[str, Any], mode: int = 0o600) -> None:
    atomic_write(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(),
        mode,
    )


def secure_unlink(
    path: Path,
    *,
    expected_identity: tuple[int, int] | None = None,
    allow_symlink: bool = False,
) -> None:
    parent_info = path.parent.lstat()
    if stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode):
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"{path.name} parent is unsafe")
        )
    descriptor = os.open(
        path.parent,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        try:
            info = os.stat(path.name, dir_fd=descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return
        if (
            (stat.S_ISLNK(info.st_mode) and not allow_symlink)
            or (not stat.S_ISLNK(info.st_mode) and not stat.S_ISREG(info.st_mode))
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} is not a regular file")
            )
        if expected_identity is not None and (info.st_dev, info.st_ino) != expected_identity:
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} changed before secure removal")
            )
        os.unlink(path.name, dir_fd=descriptor)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def prepare_local_state(project_root: Path) -> Path:
    return _safe_local_directory(project_root)


def initialize(project_root: Path, template: Path) -> bool:
    destination = project_root / CONFIG_NAME
    if destination.exists() or destination.is_symlink():
        return False
    preflight_config_creation(project_root)
    _safe_local_directory(project_root)
    raw = _read_regular_bytes(
        template, TEMPLATE_NAME, limit=MAX_CONFIG_BYTES, required_mode=None
    )
    try:
        atomic_write(destination, raw, 0o600, expect_absent=True)
    except BaseException:
        try:
            appeared = destination.lstat()
        except FileNotFoundError:
            pass
        else:
            secure_unlink(
                destination,
                expected_identity=(appeared.st_dev, appeared.st_ino),
                allow_symlink=True,
            )
        raise
    return True


def _catalog_repair(raw: bytes) -> tuple[bytes, list[str]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw, []
    changed: list[str] = []
    repaired = text
    # Enumerated lossless repairs preserve every unrelated byte/comment.
    repaired, count = re.subn(
        r"(?m)^schema_version:\s*[\"']4[\"']\s*$",
        "schema_version: 4",
        repaired,
        count=1,
    )
    if count:
        changed.append("schema_version")
    repaired, count = re.subn(
        r"(?m)^(\s*deployment_environment:)\s*\[\s*([^,\]\n]+)\s*\]\s*$",
        r"\1 \2",
        repaired,
        count=1,
    )
    if count:
        changed.append("engagement.deployment_environment")
    return repaired.encode(), changed


def repair(project_root: Path, *, allow_mode_fix: bool = True) -> list[str]:
    path = project_root / CONFIG_NAME
    info = _regular_no_symlink(path, CONFIG_NAME)
    raw = read_config_bytes(
        project_root, enforce_git=False, enforce_mode=False
    )
    repaired, changes = _catalog_repair(raw)
    if allow_mode_fix and os.name == "posix" and stat.S_IMODE(info.st_mode) != 0o600:
        changes.append("file.mode")
    if not changes:
        raise ObconfigError(ConfigIssue(1, 1, "", "no safe catalogued repair exists"))

    backup_dir = _safe_state_subdirectory(project_root, "backups")
    backup = backup_dir / f"obconfig-{time.time_ns()}.yaml"
    atomic_write(backup, raw, 0o600)
    try:
        data, marks = parse_yaml(repaired)
        validate_config(data, marks)
        atomic_write(path, repaired, 0o600)
        load_config(project_root, enforce_git=False)
    except ObconfigError:
        atomic_write(path, raw, stat.S_IMODE(info.st_mode))
        raise ObconfigError(
            ConfigIssue(1, 1, "", "no safe catalogued repair exists")
        ) from None
    except BaseException:
        atomic_write(path, raw, stat.S_IMODE(info.st_mode))
        raise
    return changes


def summary(data: Mapping[str, Any], tree: Mapping[str, Any]) -> str:
    surfaces = data["surfaces"]
    o11y = data["splunk"]["observability"]
    platform = data["splunk"]["platform"]
    constraints = data["constraints"]
    journey = data["outcomes"].get("first_journey") or "evidence-ranked"
    lines = [
        "Configuration summary (redacted)",
        f"Application: {data['engagement']['application']}",
        f"Deployment environment: {data['engagement']['deployment_environment']}",
        (
            f"Production URLs: {len(surfaces['production_urls'])}"
            if surfaces["production_urls"]
            else "Production URLs: no-browser reason configured"
        ),
        (
            f"Artifacts: {data['artifacts']['directory']} — {tree['file_count']} files, "
            f"tree {tree['tree_sha256'][:12]}, delta +{len(tree['added'])} "
            f"~{len(tree['changed'])} -{len(tree['deleted'])}"
        ),
        (
            f"Security: {data['security_assessment']['mode']}; "
            f"{len(data['security_assessment']['authorized_origins'])} authorized origins"
        ),
        (
            f"Observability Cloud: realm {o11y['realm'] or 'not configured'}; token "
            f"{'configured' if o11y['read_token'] else 'not configured'}"
        ),
        (
            f"Splunk Platform: host {platform['host'] or 'not configured'}; token "
            f"{'configured' if platform['read_token'] else 'not configured'}; "
            f"{len(platform['index_allowlist'])} indexes"
        ),
        (
            "Dummy login: configured"
            if data["analysis_access"]["dummy_login"]["password"]
            else "Dummy login: not configured"
        ),
        (
            "Constraints: "
            f"{len(constraints['privacy_regimes'])} privacy, "
            f"{len(constraints['pii_deny_list_additions'])} PII additions, "
            f"{len(constraints['competing_eum_agents'])} competing agents"
        ),
        f"Percentile: {data['standards']['percentile']}",
        f"First journey: {journey}",
        (
            "Direct APIs: Observability "
            f"{'available' if o11y['read_token'] else 'not configured'}, Platform "
            f"{'available' if platform['read_token'] else 'not configured'}"
        ),
    ]
    return "\n".join(Redactor(data).text(line) for line in lines)


def _authorization_path(project_root: Path) -> Path:
    return project_root / STATE_DIRECTORY / "authorization.json"


def _claim_path(project_root: Path) -> Path:
    return project_root / STATE_DIRECTORY / "analysis-claim.json"


def _last_binding_path(project_root: Path) -> Path:
    return project_root / STATE_DIRECTORY / "last-analysis-binding.json"


def binding(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
    enforce_git: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    data, _, raw, _ = load_config(project_root, enforce_git=enforce_git)
    tree = hash_artifact_tree(project_root, data["artifacts"]["directory"])
    manifest = {
        key: tree[key]
        for key in (
            "schema_version",
            "algorithm",
            "tree_sha256",
            "file_count",
            "total_bytes",
            "files",
        )
    }
    delta = {
        key: tree[key]
        for key in ("added", "changed", "deleted", "reread")
    }
    state = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "intended_version": intended_version,
        "config_sha256": config_digest(raw),
        "artifact_tree_sha256": tree["tree_sha256"],
        "artifact_manifest": manifest,
        "artifact_delta": delta,
    }
    return state, data, tree


def authorize(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
    enforce_git: bool = True,
) -> dict[str, Any]:
    with _gate_lock(project_root):
        if _claim_path(project_root).exists() or _claim_path(project_root).is_symlink():
            raise ObconfigError(
                ConfigIssue(1, 1, "", "an analysis claim already exists")
            )
        state, _, _ = binding(
            project_root,
            command=command,
            intended_version=intended_version,
            enforce_git=enforce_git,
        )
        atomic_write_json(_authorization_path(project_root), state)
        # Recheck immediately after persistence; changed input invalidates the gate.
        validate_authorization(
            project_root,
            command=command,
            intended_version=intended_version,
            enforce_git=enforce_git,
        )
        return state


def _load_bound_state(path: Path, label: str) -> dict[str, Any]:
    try:
        saved = json.loads(_read_regular_bytes(path, label).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"{label} is invalid")
        ) from None
    if not isinstance(saved, dict):
        raise ObconfigError(ConfigIssue(1, 1, "", f"{label} is invalid"))
    return saved


@contextlib.contextmanager
def _gate_lock(project_root: Path):
    local = _safe_local_directory(project_root)
    descriptor = os.open(
        local,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    lock_descriptor: int | None = None
    try:
        try:
            lock_descriptor = os.open(
                "analysis-gate.lock",
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=descriptor,
            )
        except FileExistsError:
            raise ObconfigError(
                ConfigIssue(1, 1, "", "analysis gate operation is already in progress")
            ) from None
        if os.name == "posix" and stat.S_IMODE(os.fstat(lock_descriptor).st_mode) != 0o600:
            raise ObconfigError(
                ConfigIssue(1, 1, "", "analysis gate lock mode must be 0600")
            )
        os.fsync(lock_descriptor)
        os.fsync(descriptor)
        yield
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
            try:
                os.unlink("analysis-gate.lock", dir_fd=descriptor)
                os.fsync(descriptor)
            except FileNotFoundError:
                pass
        os.close(descriptor)


def _validate_bound_state(
    saved: Mapping[str, Any],
    project_root: Path,
    *,
    command: str,
    intended_version: str,
    enforce_git: bool,
    label: str,
) -> dict[str, Any]:
    current, _, _ = binding(
        project_root,
        command=command,
        intended_version=intended_version,
        enforce_git=enforce_git,
    )
    if any(
        saved.get(key) != current[key]
        for key in (
            "schema_version",
            "command",
            "intended_version",
            "config_sha256",
            "artifact_tree_sha256",
            "artifact_manifest",
            "artifact_delta",
        )
    ):
        raise ObconfigError(
            ConfigIssue(
                1,
                1,
                "",
                f"{label} no longer matches current configuration and artifacts",
            )
        )
    return dict(saved)


def validate_authorization(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
    enforce_git: bool = True,
) -> dict[str, Any]:
    path = _authorization_path(project_root)
    saved = _load_bound_state(path, "authorization state")
    return _validate_bound_state(
        saved,
        project_root,
        command=command,
        intended_version=intended_version,
        enforce_git=enforce_git,
        label="authorization",
    )


def claim_authorization(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
    enforce_git: bool = True,
) -> dict[str, Any]:
    with _gate_lock(project_root):
        validate_authorization(
            project_root,
            command=command,
            intended_version=intended_version,
            enforce_git=enforce_git,
        )
        local = _safe_local_directory(project_root)
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(local, directory_flags)
        try:
            try:
                os.link(
                    "authorization.json",
                    "analysis-claim.json",
                    src_dir_fd=descriptor,
                    dst_dir_fd=descriptor,
                    follow_symlinks=False,
                )
            except FileExistsError:
                raise ObconfigError(
                    ConfigIssue(1, 1, "", "analysis authorization was already claimed")
                ) from None
            except FileNotFoundError:
                raise ObconfigError(
                    ConfigIssue(1, 1, "", "analysis authorization is unavailable")
                ) from None
            os.unlink("authorization.json", dir_fd=descriptor)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    try:
        return validate_claim(
            project_root,
            command=command,
            intended_version=intended_version,
            enforce_git=enforce_git,
        )
    except BaseException:
        _unlink_local_state(project_root, "analysis-claim.json")
        raise


def validate_claim(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
    enforce_git: bool = True,
) -> dict[str, Any]:
    saved = _load_bound_state(_claim_path(project_root), "analysis claim")
    return _validate_bound_state(
        saved,
        project_root,
        command=command,
        intended_version=intended_version,
        enforce_git=enforce_git,
        label="analysis claim",
    )


def _unlink_local_state(project_root: Path, name: str) -> None:
    local = _safe_local_directory(project_root)
    descriptor = os.open(
        local,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        try:
            os.unlink(name, dir_fd=descriptor)
        except FileNotFoundError:
            return
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def consume_claim(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
    enforce_git: bool = True,
) -> None:
    with _gate_lock(project_root):
        _consume_claim_locked(
            project_root,
            command=command,
            intended_version=intended_version,
            enforce_git=enforce_git,
        )


def _consume_claim_locked(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
    enforce_git: bool,
) -> None:
    state = validate_claim(
        project_root,
        command=command,
        intended_version=intended_version,
        enforce_git=enforce_git,
    )
    history = {
        key: state[key]
        for key in (
            "schema_version", "command", "intended_version",
            "config_sha256", "artifact_tree_sha256",
        )
    }
    manifest = state.get("artifact_manifest")
    if not isinstance(manifest, Mapping):
        raise ObconfigError(
            ConfigIssue(1, 1, "", "analysis claim has no artifact manifest")
        )
    baseline_path = _manifest_path(project_root)
    history_path = _last_binding_path(project_root)
    old_baseline = (
        _read_regular_bytes(baseline_path, "artifact manifest")
        if baseline_path.exists()
        else None
    )
    old_history = (
        _read_regular_bytes(history_path, "last analysis binding")
        if history_path.exists()
        else None
    )
    try:
        atomic_write_json(baseline_path, manifest)
        atomic_write_json(history_path, history)
    except BaseException:
        if old_baseline is None:
            _unlink_local_state(project_root, baseline_path.name)
        else:
            atomic_write(baseline_path, old_baseline)
        if old_history is None:
            _unlink_local_state(project_root, history_path.name)
        else:
            atomic_write(history_path, old_history)
        raise
    _unlink_local_state(project_root, "analysis-claim.json")


def config_changed_since_authorization(project_root: Path) -> bool:
    path = _last_binding_path(project_root)
    if not path.exists() or path.is_symlink():
        return True
    try:
        state = json.loads(
            _read_regular_bytes(path, "last analysis binding").decode("utf-8")
        )
        raw = read_config_bytes(project_root)
        data, marks = parse_yaml(raw)
        validate_config(data, marks)
        tree = hash_artifact_tree(project_root, data["artifacts"]["directory"])
    except (ObconfigError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return True
    return (
        state.get("config_sha256") != config_digest(raw)
        or state.get("artifact_tree_sha256") != tree["tree_sha256"]
    )


def find_template(script: Path) -> Path:
    for parent in [script.resolve().parent, *script.resolve().parents]:
        for candidate in (
            parent / TEMPLATE_NAME,
            parent / "obengineer" / TEMPLATE_NAME,
        ):
            if candidate.is_file() and not candidate.is_symlink():
                return candidate
    raise ObconfigError(ConfigIssue(1, 1, "", "cannot locate canonical obconfig.yaml.template"))


def redacted_issue(exc: BaseException, redactor: Redactor | None = None) -> str:
    active = redactor or Redactor()
    if isinstance(exc, ObconfigError):
        return active.text(exc.issue)
    return active.text("operation failed without exposing configuration values")
