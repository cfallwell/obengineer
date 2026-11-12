#!/usr/bin/env python3
"""Secure schema-v4 obconfig loading, repair, hashing, and authorization."""

from __future__ import annotations

import copy
import contextlib
import ctypes
import errno
import hashlib
import ipaddress
import json
import math
import os
import re
import stat
import struct
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

import yaml

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None
try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None

SCHEMA_VERSION = 4
CONFIG_NAME = "obconfig.yaml"
TEMPLATE_NAME = "obconfig.yaml.template"
STATE_DIRECTORY = ".obengineer"
TREE_ALGORITHM = "ob-artifact-tree-v1"
GENERATED_OUTPUT_ALGORITHM = "ob-generated-index-output-v2"
MAX_CONFIG_BYTES = 1024 * 1024
SAFE_ACTIVE_MAX_REQUESTS = 100
SAFE_ACTIVE_REQUESTS_PER_SECOND = 1
SAFE_ACTIVE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
SAFE_ACTIVE_PATHS = ("/robots.txt", "/.well-known/security.txt")
RENAME_EXCHANGE = 2
RENAME_NOREPLACE = 1
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas/obconfig.schema.json"
_FALLBACK_GATE_LOCKS: dict[str, threading.RLock] = {}
_FALLBACK_GATE_LOCKS_GUARD = threading.Lock()
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


@dataclass(frozen=True)
class ConfigFileBinding:
    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int
    ctime_ns: int
    digest: str


@dataclass(frozen=True)
class RegularFileVersion:
    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int
    ctime_ns: int
    digest: str


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
    if (
        schema.get("x-obengineer-finite")
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and not math.isfinite(value)
    ):
        raise ObconfigError(_issue(marks, path, "must be finite"))
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
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
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
    if (
        not isinstance(percentile, (str, int, float))
        or isinstance(percentile, bool)
        or (
            isinstance(percentile, (int, float))
            and not math.isfinite(percentile)
        )
    ):
        raise ObconfigError(
            _issue(
                marks,
                "standards.percentile",
                "must be a string or finite numeric percentile",
            )
        )
    _integer(data, marks, "standards.baggage_header_budget_bytes", minimum=1)
    _integer(data, marks, "standards.baggage_value_ceiling_bytes", minimum=1)
    threshold = get_path(data, "standards.unknown_dimension_threshold_pct")
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(threshold)
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
        current_parent = path.parent.lstat()
        if (current_parent.st_dev, current_parent.st_ino) != (
            opened_parent.st_dev,
            opened_parent.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{label} parent changed while being read")
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


def read_project_file_version(
    project_root: Path,
    relative: str | Path,
    label: str,
    *,
    limit: int = 64 * 1024 * 1024,
    required_mode: int | None = None,
) -> tuple[bytes, RegularFileVersion]:
    raw = read_project_file(
        project_root,
        relative,
        label,
        limit=limit,
        required_mode=required_mode,
    )
    path = project_root.resolve() / Path(relative)
    info = _regular_no_symlink(path, label)
    repeated = read_project_file(
        project_root,
        relative,
        label,
        limit=limit,
        required_mode=required_mode,
    )
    after = _regular_no_symlink(path, label)
    fields = (
        info.st_dev,
        info.st_ino,
        stat.S_IMODE(info.st_mode),
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )
    after_fields = (
        after.st_dev,
        after.st_ino,
        stat.S_IMODE(after.st_mode),
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if raw != repeated or fields != after_fields:
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"{label} changed while capturing identity")
        )
    return raw, RegularFileVersion(
        *fields,
        hashlib.sha256(raw).hexdigest(),
    )


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


def remove_config_from_index(project_root: Path) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(project_root.resolve()),
            "rm",
            "--cached",
            "--force",
            "--ignore-unmatch",
            "--",
            CONFIG_NAME,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
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


def capture_config_binding(
    project_root: Path,
    *,
    enforce_git: bool = True,
    expected_digest: str | None = None,
) -> ConfigFileBinding:
    path = project_root.resolve() / CONFIG_NAME
    before = _regular_no_symlink(path, CONFIG_NAME)
    raw = read_config_bytes(project_root, enforce_git=enforce_git)
    after = _regular_no_symlink(path, CONFIG_NAME)
    before_fields = (
        before.st_dev,
        before.st_ino,
        stat.S_IMODE(before.st_mode),
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_fields = (
        after.st_dev,
        after.st_ino,
        stat.S_IMODE(after.st_mode),
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_fields != after_fields:
        raise ObconfigError(
            ConfigIssue(1, 1, "", "obconfig.yaml changed while binding verification")
        )
    digest = config_digest(raw)
    if expected_digest is not None and digest != expected_digest:
        raise ObconfigError(
            ConfigIssue(1, 1, "", "obconfig.yaml content changed before request")
        )
    return ConfigFileBinding(*after_fields, digest)


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


def _normalized_generated_paths(relative_paths: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in relative_paths:
        candidate = PurePosixPath(value.replace("\\", "/"))
        if (
            candidate.is_absolute()
            or not candidate.parts
            or any(part in {"", ".", ".."} for part in candidate.parts)
            or candidate.parts[0] in {".git", STATE_DIRECTORY}
            or candidate.as_posix() == CONFIG_NAME
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "generated output path is unsafe")
            )
        normalized.append(candidate.as_posix())
    normalized = sorted(set(normalized))
    if not normalized:
        raise ObconfigError(
            ConfigIssue(1, 1, "", "at least one generated output path is required")
        )
    for index, value in enumerate(normalized):
        prefix = value + "/"
        if any(other.startswith(prefix) for other in normalized[index + 1 :]):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "generated output paths must not overlap")
            )
    return normalized


def _git_output(project_root: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=project_root,
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ObconfigError(
            ConfigIssue(1, 1, "", "Git object verification is unavailable")
        ) from None
    if completed.returncode != 0:
        raise ObconfigError(
            ConfigIssue(1, 1, "", "Git object verification failed")
        )
    return completed.stdout


def _require_git_project_root(project_root: Path) -> Path:
    root = project_root.resolve()
    reported = Path(
        _git_output(root, "rev-parse", "--show-toplevel")
        .decode("utf-8", errors="strict")
        .strip()
    ).resolve()
    if reported != root:
        raise ObconfigError(
            ConfigIssue(1, 1, "", "project root must be the Git worktree root")
        )
    return root


def _git_index_entries(
    project_root: Path, paths: list[str]
) -> tuple[str, dict[str, tuple[str, str]]]:
    root = _require_git_project_root(project_root)
    tree_sha = _git_output(root, "write-tree").decode("ascii").strip()
    pathspecs = [f":(literal){path}" for path in paths]
    raw = _git_output(root, "ls-files", "--stage", "-z", "--", *pathspecs)
    entries: dict[str, tuple[str, str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, encoded_path = record.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split(" ")
            path = encoded_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "Git index output entry is invalid")
            ) from None
        if stage != "0" or mode not in {"100644", "100755"}:
            raise ObconfigError(
                ConfigIssue(
                    1,
                    1,
                    "",
                    "generated outputs must be regular stage-zero Git index files",
                )
            )
        entries[path] = (mode, object_id)
    return tree_sha, entries


def _git_commit_entries(
    project_root: Path,
    commit_sha: str,
    paths: list[str],
) -> tuple[str, dict[str, tuple[str, str]]]:
    root = _require_git_project_root(project_root)
    tree_sha = _git_output(
        root, "rev-parse", "--verify", f"{commit_sha}^{{tree}}"
    ).decode("ascii").strip()
    pathspecs = [f":(literal){path}" for path in paths]
    raw = _git_output(
        root,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        commit_sha,
        "--",
        *pathspecs,
    )
    entries: dict[str, tuple[str, str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, encoded_path = record.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split(" ")
            path = encoded_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "Git commit output entry is invalid")
            ) from None
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise ObconfigError(
                ConfigIssue(
                    1, 1, "", "generated commit outputs must be regular files"
                )
            )
        entries[path] = (mode, object_id)
    return tree_sha, entries


def _git_output_manifest(
    project_root: Path,
    paths: list[str],
    entries: Mapping[str, tuple[str, str]],
) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    for value in paths:
        exact = value in entries
        prefix = value + "/"
        children = sorted(path for path in entries if path.startswith(prefix))
        if exact and children:
            raise ObconfigError(
                ConfigIssue(1, 1, "", "generated output path is ambiguous")
            )
        selected = [value] if exact else children
        if not selected:
            raise ObconfigError(
                ConfigIssue(
                    1, 1, "", "generated output is omitted from the Git tree"
                )
            )
        files: list[dict[str, Any]] = []
        for path in selected:
            mode, object_id = entries[path]
            content = _git_output(project_root, "cat-file", "blob", object_id)
            files.append(
                {
                    "path": path,
                    "mode": mode,
                    "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "git_object": object_id,
                }
            )
        output_type = "file" if exact else "directory"
        output_digest = hashlib.sha256(
            json.dumps(
                files, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        outputs.append(
            {
                "path": value,
                "type": output_type,
                "file_count": len(files),
                "sha256": output_digest,
                "files": files,
            }
        )
    projection = {
        "algorithm": GENERATED_OUTPUT_ALGORITHM,
        "paths": paths,
        "outputs": outputs,
    }
    return {
        "schema_version": 2,
        **projection,
        "output_count": len(outputs),
        "sha256": hashlib.sha256(
            json.dumps(
                projection, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest(),
    }


def hash_staged_generated_outputs(
    project_root: Path,
    relative_paths: Iterable[str],
) -> tuple[str, dict[str, Any]]:
    normalized = _normalized_generated_paths(relative_paths)
    tree_sha, entries = _git_index_entries(project_root, normalized)
    return tree_sha, _git_output_manifest(project_root, normalized, entries)


def hash_committed_generated_outputs(
    project_root: Path,
    commit_sha: str,
    relative_paths: Iterable[str],
) -> tuple[str, dict[str, Any]]:
    normalized = _normalized_generated_paths(relative_paths)
    tree_sha, entries = _git_commit_entries(
        project_root, commit_sha, normalized
    )
    return tree_sha, _git_output_manifest(project_root, normalized, entries)


def _descriptor_digest(
    directory: int,
    name: str,
    expected: os.stat_result,
) -> str:
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory,
    )
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{name} changed during identity check")
            )
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        ) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{name} changed during content check")
            )
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _renameat2(
    directory: int, left: str, right: str, flags: int, operation: str
) -> None:
    if os.name != "posix":
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"atomic {operation} is unsupported")
        )
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"atomic {operation} is unsupported")
        )
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        directory,
        os.fsencode(left),
        directory,
        os.fsencode(right),
        flags,
    )
    if result != 0:
        error = ctypes.get_errno()
        if error in {
            errno.ENOSYS,
            errno.EINVAL,
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }:
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"atomic {operation} is unsupported")
            )
        if error == errno.EEXIST and flags == RENAME_NOREPLACE:
            raise FileExistsError(right)
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"atomic {operation} failed")
        )


def _rename_exchange(directory: int, left: str, right: str) -> None:
    _renameat2(directory, left, right, RENAME_EXCHANGE, "rename exchange")


def _rename_noreplace(directory: int, left: str, right: str) -> None:
    _renameat2(directory, left, right, RENAME_NOREPLACE, "rename no-replace")


def _exchange_remove_name(
    directory: int,
    name: str,
    *,
    expected_identity: tuple[int, int],
    expected_digest: str,
    expected_mode: int,
) -> None:
    placeholder = f".{name}.remove.{os.getpid()}.{time.time_ns()}"
    descriptor = os.open(
        placeholder,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory,
    )
    placeholder_info = os.fstat(descriptor)
    os.close(descriptor)
    placeholder_identity = (
        placeholder_info.st_dev,
        placeholder_info.st_ino,
    )
    exchanged = False
    try:
        _rename_exchange(directory, placeholder, name)
        exchanged = True
        removed = os.stat(
            placeholder, dir_fd=directory, follow_symlinks=False
        )
        replacement = os.stat(
            name, dir_fd=directory, follow_symlinks=False
        )
        removed_matches = (
            (removed.st_dev, removed.st_ino) == expected_identity
            and stat.S_IMODE(removed.st_mode) == expected_mode
            and stat.S_ISREG(removed.st_mode)
            and _descriptor_digest(directory, placeholder, removed)
            == expected_digest
        )
        placeholder_matches = (
            replacement.st_dev,
            replacement.st_ino,
        ) == placeholder_identity
        if not removed_matches or not placeholder_matches:
            if placeholder_matches:
                _rename_exchange(directory, placeholder, name)
                exchanged = False
            raise ObconfigError(
                ConfigIssue(
                    1,
                    1,
                    "",
                    f"{name} changed at atomic removal",
                )
            )

        tombstone = f".{name}.tombstone.{os.getpid()}.{time.time_ns()}"
        _rename_noreplace(directory, name, tombstone)
        moved_placeholder = os.stat(
            tombstone, dir_fd=directory, follow_symlinks=False
        )
        if (
            moved_placeholder.st_dev,
            moved_placeholder.st_ino,
        ) != placeholder_identity or not stat.S_ISREG(
            moved_placeholder.st_mode
        ) or stat.S_IMODE(moved_placeholder.st_mode) != 0o600 or (
            _descriptor_digest(directory, tombstone, moved_placeholder)
            != hashlib.sha256(b"").hexdigest()
        ):
            try:
                _rename_noreplace(directory, tombstone, name)
            except (FileExistsError, ObconfigError):
                pass
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{name} changed at final removal")
            )
        os.unlink(tombstone, dir_fd=directory)
        os.unlink(placeholder, dir_fd=directory)
        exchanged = False
        os.fsync(directory)
    finally:
        if exchanged:
            # A matching old target remains under the random placeholder if a
            # concurrent pathname replacement prevented safe completion.
            try:
                os.fsync(directory)
            except OSError:
                pass
        else:
            try:
                current = os.stat(
                    placeholder,
                    dir_fd=directory,
                    follow_symlinks=False,
                )
                if (
                    current.st_dev,
                    current.st_ino,
                ) == placeholder_identity:
                    os.unlink(placeholder, dir_fd=directory)
            except OSError:
                pass


def _restore_exchange(
    directory: int,
    temporary_name: str,
    target_name: str,
    *,
    restored_target_identity: tuple[int, int],
    restored_temporary_identity: tuple[int, int],
    restored_target_mode: int,
    restored_temporary_mode: int,
    restored_target_digest: str | None,
    restored_temporary_digest: str,
) -> bool:
    """Exchange back, then undo that exchange if a final-syscall race won."""
    _rename_exchange(directory, temporary_name, target_name)
    restored_target = os.stat(
        target_name, dir_fd=directory, follow_symlinks=False
    )
    restored_temporary = os.stat(
        temporary_name, dir_fd=directory, follow_symlinks=False
    )
    target_matches = (
        restored_target.st_dev,
        restored_target.st_ino,
    ) == restored_target_identity and stat.S_IMODE(
        restored_target.st_mode
    ) == restored_target_mode
    temporary_matches = (
        restored_temporary.st_dev,
        restored_temporary.st_ino,
    ) == restored_temporary_identity and stat.S_IMODE(
        restored_temporary.st_mode
    ) == restored_temporary_mode and stat.S_ISREG(
        restored_temporary.st_mode
    ) and (
        _descriptor_digest(
            directory, temporary_name, restored_temporary
        )
        == restored_temporary_digest
    )
    if (
        target_matches
        and (
            restored_target_digest is None
            or (
                stat.S_ISREG(restored_target.st_mode)
                and _descriptor_digest(
                    directory, target_name, restored_target
                )
                == restored_target_digest
            )
        )
        and temporary_matches
    ):
        return True
    _rename_exchange(directory, temporary_name, target_name)
    return False


def atomic_write(
    path: Path,
    data: bytes,
    mode: int = 0o600,
    *,
    expect_absent: bool = False,
    expected_identity: tuple[int, int] | None = None,
    expected_digest: str | None = None,
    expected_mode: int | None = None,
) -> RegularFileVersion:
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
    temporary_identity: tuple[int, int] | None = None
    created_path = False
    existing: os.stat_result | None = None
    existing_digest: str | None = None
    exchanged = False
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
        if existing is not None:
            existing_digest = _descriptor_digest(
                parent_descriptor, path.name, existing
            )
        if expect_absent and existing is not None:
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} appeared during secure creation")
            )
        if expected_identity is not None:
            if existing is None or (existing.st_dev, existing.st_ino) != expected_identity:
                raise ObconfigError(
                    ConfigIssue(1, 1, "", f"{path.name} identity changed before write")
                )
            if (
                expected_mode is not None
                and stat.S_IMODE(existing.st_mode) != expected_mode
            ):
                raise ObconfigError(
                    ConfigIssue(1, 1, "", f"{path.name} mode changed before write")
                )
            if (
                expected_digest is not None
                and _descriptor_digest(parent_descriptor, path.name, existing)
                != expected_digest
            ):
                raise ObconfigError(
                    ConfigIssue(1, 1, "", f"{path.name} content changed before write")
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
        temporary_info = os.fstat(descriptor)
        temporary_identity = (
            temporary_info.st_dev,
            temporary_info.st_ino,
        )
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
        if expected_identity is not None and current is not None:
            if (
                expected_mode is not None
                and stat.S_IMODE(current.st_mode) != expected_mode
            ) or (
                expected_digest is not None
                and _descriptor_digest(parent_descriptor, path.name, current)
                != expected_digest
            ):
                raise ObconfigError(
                    ConfigIssue(
                        1, 1, "", f"{path.name} changed before atomic replace"
                    )
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
            created_path = True
        else:
            _rename_exchange(
                parent_descriptor, temporary_name, path.name
            )
            exchanged = True
            exchanged_old = os.stat(
                temporary_name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            exchanged_new = os.stat(
                path.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            exchanged_old_digest = (
                _descriptor_digest(
                    parent_descriptor, temporary_name, exchanged_old
                )
                if stat.S_ISREG(exchanged_old.st_mode)
                else None
            )
            old_matches = (
                exchanged_old.st_dev,
                exchanged_old.st_ino,
            ) == (existing.st_dev, existing.st_ino) and (
                stat.S_IMODE(exchanged_old.st_mode)
                == stat.S_IMODE(existing.st_mode)
            ) and (
                existing_digest is not None
                and _descriptor_digest(
                    parent_descriptor, temporary_name, exchanged_old
                )
                == existing_digest
            )
            new_matches = (
                exchanged_new.st_dev,
                exchanged_new.st_ino,
            ) == temporary_identity
            if not old_matches or not new_matches:
                if new_matches:
                    restored = _restore_exchange(
                        parent_descriptor,
                        temporary_name,
                        path.name,
                        restored_target_identity=(
                            exchanged_old.st_dev,
                            exchanged_old.st_ino,
                        ),
                        restored_temporary_identity=temporary_identity,
                        restored_target_mode=stat.S_IMODE(
                            exchanged_old.st_mode
                        ),
                        restored_temporary_mode=mode,
                        restored_target_digest=exchanged_old_digest,
                        restored_temporary_digest=hashlib.sha256(
                            data
                        ).hexdigest(),
                    )
                    exchanged = not restored
                raise ObconfigError(
                    ConfigIssue(
                        1,
                        1,
                        "",
                        f"{path.name} changed at atomic exchange",
                    )
                )
        os.fsync(parent_descriptor)
        final = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        if (
            temporary_identity is None
            or (final.st_dev, final.st_ino) != temporary_identity
            or (os.name == "posix" and stat.S_IMODE(final.st_mode) != mode)
            or _descriptor_digest(parent_descriptor, path.name, final)
            != hashlib.sha256(data).hexdigest()
        ):
            raise ObconfigError(
                ConfigIssue(
                    1, 1, "", f"{path.name} changed after atomic creation"
                )
            )
        current_parent = parent.lstat()
        if (current_parent.st_dev, current_parent.st_ino) != (
            opened_parent.st_dev,
            opened_parent.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} parent changed during write")
            )
        if exchanged:
            assert existing is not None and existing_digest is not None
            _exchange_remove_name(
                parent_descriptor,
                temporary_name,
                expected_identity=(existing.st_dev, existing.st_ino),
                expected_digest=existing_digest,
                expected_mode=stat.S_IMODE(existing.st_mode),
            )
            exchanged = False
            created_path = True
            os.fsync(parent_descriptor)
        return RegularFileVersion(
            final.st_dev,
            final.st_ino,
            stat.S_IMODE(final.st_mode),
            final.st_size,
            final.st_mtime_ns,
            final.st_ctime_ns,
            hashlib.sha256(data).hexdigest(),
        )
    except BaseException:
        try:
            if descriptor is not None:
                os.close(descriptor)
        except OSError:
            pass
        if exchanged and existing is not None and temporary_identity is not None:
            try:
                current_new = os.stat(
                    path.name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                current_old = os.stat(
                    temporary_name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (
                    current_new.st_dev,
                    current_new.st_ino,
                ) == temporary_identity and (
                    current_old.st_dev,
                    current_old.st_ino,
                ) == (existing.st_dev, existing.st_ino):
                    restored = _restore_exchange(
                        parent_descriptor,
                        temporary_name,
                        path.name,
                        restored_target_identity=(
                            existing.st_dev,
                            existing.st_ino,
                        ),
                        restored_temporary_identity=temporary_identity,
                        restored_target_mode=stat.S_IMODE(
                            existing.st_mode
                        ),
                        restored_temporary_mode=mode,
                        restored_target_digest=existing_digest,
                        restored_temporary_digest=hashlib.sha256(
                            data
                        ).hexdigest(),
                    )
                    exchanged = not restored
            except (OSError, ObconfigError):
                pass
        if not exchanged and temporary_identity is not None:
            try:
                temporary_current = os.stat(
                    temporary_name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (
                    temporary_current.st_dev,
                    temporary_current.st_ino,
                ) == temporary_identity:
                    os.unlink(temporary_name, dir_fd=parent_descriptor)
            except OSError:
                pass
        if created_path and existing is None and temporary_identity is not None:
            try:
                current = os.stat(
                    path.name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (current.st_dev, current.st_ino) == temporary_identity:
                    _exchange_remove_name(
                        parent_descriptor,
                        path.name,
                        expected_identity=temporary_identity,
                        expected_digest=hashlib.sha256(data).hexdigest(),
                        expected_mode=mode,
                    )
            except (FileNotFoundError, OSError):
                pass
        raise
    finally:
        os.close(parent_descriptor)


def atomic_write_json(
    path: Path,
    value: Mapping[str, Any],
    mode: int = 0o600,
    *,
    expect_absent: bool = False,
    expected_identity: tuple[int, int] | None = None,
    expected_digest: str | None = None,
    expected_mode: int | None = None,
) -> RegularFileVersion:
    return atomic_write(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(),
        mode,
        expect_absent=expect_absent,
        expected_identity=expected_identity,
        expected_digest=expected_digest,
        expected_mode=expected_mode,
    )


def secure_unlink(
    path: Path,
    *,
    expected_identity: tuple[int, int] | None = None,
    expected_digest: str | None = None,
    expected_mode: int | None = None,
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
        if stat.S_ISLNK(info.st_mode):
            raise ObconfigError(
                ConfigIssue(
                    1,
                    1,
                    "",
                    f"{path.name} symlink removal is not identity-safe",
                )
            )
        if expected_identity is not None and (info.st_dev, info.st_ino) != expected_identity:
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} changed before secure removal")
            )
        if (
            expected_mode is not None
            and stat.S_IMODE(info.st_mode) != expected_mode
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} mode changed before removal")
            )
        current_digest = _descriptor_digest(descriptor, path.name, info)
        if expected_digest is not None:
            if current_digest != expected_digest:
                raise ObconfigError(
                    ConfigIssue(
                        1, 1, "", f"{path.name} content changed before removal"
                    )
                )
        _exchange_remove_name(
            descriptor,
            path.name,
            expected_identity=(info.st_dev, info.st_ino),
            expected_digest=current_digest,
            expected_mode=stat.S_IMODE(info.st_mode),
        )
        current_parent = path.parent.lstat()
        opened_parent = os.fstat(descriptor)
        if (current_parent.st_dev, current_parent.st_ino) != (
            opened_parent.st_dev,
            opened_parent.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", f"{path.name} parent changed during removal")
            )
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
    written_version: RegularFileVersion | None = None
    try:
        written_version = atomic_write(
            destination, raw, 0o600, expect_absent=True
        )
        preflight_config_creation(project_root)
    except BaseException:
        remove_config_from_index(project_root)
        if written_version is not None:
            secure_unlink(
                destination,
                expected_identity=(
                    written_version.device,
                    written_version.inode,
                ),
                expected_digest=written_version.digest,
                expected_mode=written_version.mode,
            )
        raise
    return True


def _capture_regular_version(
    path: Path,
    label: str,
    *,
    required_mode: int | None = None,
) -> tuple[bytes, RegularFileVersion]:
    before = _regular_no_symlink(path, label)
    raw = _read_regular_bytes(
        path,
        label,
        limit=MAX_CONFIG_BYTES,
        required_mode=required_mode,
    )
    after = _regular_no_symlink(path, label)
    before_fields = (
        before.st_dev,
        before.st_ino,
        stat.S_IMODE(before.st_mode),
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_fields = (
        after.st_dev,
        after.st_ino,
        stat.S_IMODE(after.st_mode),
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_fields != after_fields:
        raise ObconfigError(
            ConfigIssue(1, 1, "", f"{label} changed during secure read")
        )
    return raw, RegularFileVersion(
        *after_fields,
        hashlib.sha256(raw).hexdigest(),
    )


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
    raw, original = _capture_regular_version(
        path,
        CONFIG_NAME,
        required_mode=None,
    )
    repaired, changes = _catalog_repair(raw)
    if allow_mode_fix and os.name == "posix" and original.mode != 0o600:
        changes.append("file.mode")
    if not changes:
        raise ObconfigError(ConfigIssue(1, 1, "", "no safe catalogued repair exists"))

    backup_dir = _safe_state_subdirectory(project_root, "backups")
    backup = backup_dir / f"obconfig-{time.time_ns()}.yaml"
    atomic_write(backup, raw, 0o600, expect_absent=True)
    current_raw, current = _capture_regular_version(
        path, CONFIG_NAME, required_mode=None
    )
    if current != original or current_raw != raw:
        raise ObconfigError(
            ConfigIssue(1, 1, "", "obconfig.yaml changed after repair backup")
        )

    try:
        data, marks = parse_yaml(repaired)
        validate_config(data, marks)
    except ObconfigError:
        raise ObconfigError(
            ConfigIssue(1, 1, "", "no safe catalogued repair exists")
        ) from None
    candidate = path.parent / f".obconfig.repair.{os.getpid()}.{time.time_ns()}"
    atomic_write(candidate, repaired, 0o600, expect_absent=True)
    candidate_raw, candidate_version = _capture_regular_version(
        candidate, "repair candidate", required_mode=0o600
    )
    if candidate_raw != repaired:
        secure_unlink(
            candidate,
            expected_identity=(candidate_version.device, candidate_version.inode),
        )
        raise ObconfigError(
            ConfigIssue(1, 1, "", "repair candidate bytes did not match")
        )

    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directory = os.open(path.parent, directory_flags)
    exchanged = False
    try:
        _rename_exchange(directory, candidate.name, path.name)
        exchanged = True
        exchanged_old = os.stat(
            candidate.name, dir_fd=directory, follow_symlinks=False
        )
        old_matches = (
            exchanged_old.st_dev,
            exchanged_old.st_ino,
            stat.S_IMODE(exchanged_old.st_mode),
        ) == (original.device, original.inode, original.mode) and (
            _descriptor_digest(directory, candidate.name, exchanged_old)
            == original.digest
        )
        if not old_matches:
            _rename_exchange(directory, candidate.name, path.name)
            exchanged = False
            raise ObconfigError(
                ConfigIssue(
                    1,
                    1,
                    "",
                    "repair exchange found concurrent config and restored it",
                )
            )
        committed_raw, committed = _capture_regular_version(
            path, CONFIG_NAME, required_mode=0o600
        )
        if committed_raw != repaired or (
            committed.device,
            committed.inode,
        ) != (candidate_version.device, candidate_version.inode):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "repair exchange identity did not match")
            )
        load_config(project_root, enforce_git=False)
        secure_unlink(
            candidate,
            expected_identity=(original.device, original.inode),
        )
        exchanged = False
    except BaseException:
        if exchanged:
            target_raw, target_version = _capture_regular_version(
                path, CONFIG_NAME, required_mode=None
            )
            old_raw, old_version = _capture_regular_version(
                candidate, "repair exchanged original", required_mode=None
            )
            if (
                target_raw != repaired
                or (
                    target_version.device,
                    target_version.inode,
                )
                != (candidate_version.device, candidate_version.inode)
                or old_raw != raw
                or old_version != original
            ):
                raise ObconfigError(
                    ConfigIssue(
                        1,
                        1,
                        "",
                        "repair rollback refused because exchanged files changed",
                    )
                ) from None
            _rename_exchange(directory, candidate.name, path.name)
            exchanged = False
        if candidate.exists() and not candidate.is_symlink():
            candidate_info = candidate.lstat()
            if (candidate_info.st_dev, candidate_info.st_ino) == (
                candidate_version.device,
                candidate_version.inode,
            ):
                secure_unlink(
                    candidate,
                    expected_identity=(
                        candidate_version.device,
                        candidate_version.inode,
                    ),
                )
        raise
    finally:
        os.close(directory)
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


def _dispatch_path(project_root: Path) -> Path:
    return project_root / STATE_DIRECTORY / "analysis-dispatch.json"


def _consume_journal_path(project_root: Path) -> Path:
    return project_root / STATE_DIRECTORY / "consume-journal.json"


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
    with _gate_lock(
        project_root,
        recovery_command=command,
        recovery_version=intended_version,
    ):
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


def _load_bound_state_version(
    path: Path, label: str
) -> tuple[dict[str, Any], RegularFileVersion]:
    raw, version = _capture_regular_version(
        path,
        label,
        required_mode=0o600,
    )
    try:
        saved = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ObconfigError(ConfigIssue(1, 1, "", f"{label} is invalid")) from None
    if not isinstance(saved, dict):
        raise ObconfigError(ConfigIssue(1, 1, "", f"{label} is invalid"))
    return saved, version


def _quarantine_remove_state(
    project_root: Path,
    name: str,
    expected: RegularFileVersion,
) -> None:
    local = _safe_local_directory(project_root)
    local_info = local.lstat()
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(local, flags)
    quarantine = f".{name}.quarantine.{os.getpid()}.{time.time_ns()}"
    moved = False
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (
            local_info.st_dev,
            local_info.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "state directory changed before quarantine")
            )
        os.rename(
            name,
            quarantine,
            src_dir_fd=descriptor,
            dst_dir_fd=descriptor,
        )
        moved = True
        moved_info = os.stat(
            quarantine, dir_fd=descriptor, follow_symlinks=False
        )
        current_local = local.lstat()
        identity_matches = (
            moved_info.st_dev,
            moved_info.st_ino,
        ) == (expected.device, expected.inode)
        content_matches = (
            stat.S_IMODE(moved_info.st_mode) == expected.mode
            and _descriptor_digest(descriptor, quarantine, moved_info)
            == expected.digest
        )
        state_matches = (
            current_local.st_dev,
            current_local.st_ino,
        ) == (opened.st_dev, opened.st_ino)
        if not identity_matches or not content_matches or not state_matches:
            try:
                os.link(
                    quarantine,
                    name,
                    src_dir_fd=descriptor,
                    dst_dir_fd=descriptor,
                    follow_symlinks=False,
                )
                os.unlink(quarantine, dir_fd=descriptor)
                moved = False
            except FileExistsError:
                pass
            raise ObconfigError(
                ConfigIssue(
                    1,
                    1,
                    "",
                    f"{name} or state directory changed before removal",
                )
            )
        os.unlink(quarantine, dir_fd=descriptor)
        moved = False
        os.fsync(descriptor)
        final_local = local.lstat()
        if (final_local.st_dev, final_local.st_ino) != (
            opened.st_dev,
            opened.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "state directory changed after removal")
            )
    finally:
        # A mismatched replacement is preserved under quarantine if its original
        # pathname was concurrently occupied before it could be restored.
        if moved:
            try:
                os.fsync(descriptor)
            except OSError:
                pass
        os.close(descriptor)


@contextlib.contextmanager
def _gate_lock(
    project_root: Path,
    *,
    recovery_command: str | None = None,
    recovery_version: str | None = None,
):
    root = project_root.resolve()
    root_info = root.lstat()
    root_descriptor = os.open(
        root,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    lock_descriptor: int | None = None
    fallback_lock: threading.RLock | None = None
    try:
        opened_root = os.fstat(root_descriptor)
        if (opened_root.st_dev, opened_root.st_ino) != (
            root_info.st_dev,
            root_info.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "project root changed during gate open")
            )
        if fcntl is not None:
            fcntl.flock(root_descriptor, fcntl.LOCK_EX)
        elif msvcrt is not None:  # pragma: no cover - Windows
            local = _safe_local_directory(project_root)
            lock_descriptor = os.open(
                local / "analysis-gate.lock",
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            if os.fstat(lock_descriptor).st_size == 0:
                os.write(lock_descriptor, b"\0")
                os.fsync(lock_descriptor)
            os.lseek(lock_descriptor, 0, os.SEEK_SET)
            msvcrt.locking(lock_descriptor, msvcrt.LK_LOCK, 1)
        else:  # Last-resort in-process lock without residual-file ownership semantics.
            key = str(root)
            with _FALLBACK_GATE_LOCKS_GUARD:
                fallback_lock = _FALLBACK_GATE_LOCKS.setdefault(
                    key, threading.RLock()
                )
            fallback_lock.acquire()
        current_root = root.lstat()
        if (current_root.st_dev, current_root.st_ino) != (
            opened_root.st_dev,
            opened_root.st_ino,
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "project root changed after gate lock")
            )
        recovered = _recover_consume_locked(
            project_root,
            expected_command=recovery_command,
            expected_version=recovery_version,
        )
        yield recovered
    finally:
        if fallback_lock is not None:
            fallback_lock.release()
        if fcntl is not None:
            fcntl.flock(root_descriptor, fcntl.LOCK_UN)
        elif msvcrt is not None and lock_descriptor is not None:  # pragma: no cover
            os.lseek(lock_descriptor, 0, os.SEEK_SET)
            msvcrt.locking(lock_descriptor, msvcrt.LK_UNLCK, 1)
        if lock_descriptor is not None:
            os.close(lock_descriptor)
        os.close(root_descriptor)


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
    with _gate_lock(
        project_root,
        recovery_command=command,
        recovery_version=intended_version,
    ):
        authorization_path = _authorization_path(project_root)
        saved, authorization_version = _load_bound_state_version(
            authorization_path, "authorization state"
        )
        _validate_bound_state(
            saved,
            project_root,
            command=command,
            intended_version=intended_version,
            enforce_git=enforce_git,
            label="authorization",
        )
        local = _safe_local_directory(project_root)
        local_info = local.lstat()
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(local, directory_flags)
        linked = False
        try:
            opened_local = os.fstat(descriptor)
            if (opened_local.st_dev, opened_local.st_ino) != (
                local_info.st_dev,
                local_info.st_ino,
            ):
                raise ObconfigError(
                    ConfigIssue(1, 1, "", "state directory changed during claim open")
                )
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
            linked = True
            os.unlink("authorization.json", dir_fd=descriptor)
            os.fsync(descriptor)
            current_local = local.lstat()
            if (current_local.st_dev, current_local.st_ino) != (
                opened_local.st_dev,
                opened_local.st_ino,
            ):
                raise ObconfigError(
                    ConfigIssue(1, 1, "", "state directory changed during claim")
                )
        finally:
            os.close(descriptor)
        try:
            claimed, claim_version = _load_bound_state_version(
                _claim_path(project_root), "analysis claim"
            )
            if (
                claimed != saved
                or claim_version.device != authorization_version.device
                or claim_version.inode != authorization_version.inode
                or claim_version.digest != authorization_version.digest
                or claim_version.mode != authorization_version.mode
            ):
                raise ObconfigError(
                    ConfigIssue(1, 1, "", "analysis claim identity changed")
                )
            return _validate_bound_state(
                claimed,
                project_root,
                command=command,
                intended_version=intended_version,
                enforce_git=enforce_git,
                label="analysis claim",
            )
        except BaseException:
            if linked:
                _quarantine_remove_state(
                    project_root,
                    "analysis-claim.json",
                    authorization_version,
                )
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


def finalize_claim(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
    generated_outputs: Iterable[str],
    enforce_git: bool = True,
) -> dict[str, Any]:
    with _gate_lock(
        project_root,
        recovery_command=command,
        recovery_version=intended_version,
    ):
        path = _claim_path(project_root)
        saved, version = _load_bound_state_version(path, "analysis claim")
        if saved.get("finalized") is True:
            raise ObconfigError(
                ConfigIssue(1, 1, "", "analysis claim is already finalized")
            )
        _validate_bound_state(
            saved,
            project_root,
            command=command,
            intended_version=intended_version,
            enforce_git=enforce_git,
            label="analysis claim",
        )
        index_tree_sha, generated = hash_staged_generated_outputs(
            project_root, generated_outputs
        )
        _validate_bound_state(
            saved,
            project_root,
            command=command,
            intended_version=intended_version,
            enforce_git=enforce_git,
            label="analysis claim",
        )
        finalized = dict(saved)
        finalized.update(
            {
                "finalized": True,
                "git_index_tree_sha": index_tree_sha,
                "generated_output_manifest": generated,
                "generated_output_sha256": generated["sha256"],
            }
        )
        encoded = (
            json.dumps(finalized, indent=2, sort_keys=True) + "\n"
        ).encode()
        atomic_write(
            path,
            encoded,
            0o600,
            expected_identity=(version.device, version.inode),
            expected_digest=version.digest,
            expected_mode=version.mode,
        )
        persisted, _ = _load_bound_state_version(path, "analysis claim")
        if persisted != finalized:
            raise ObconfigError(
                ConfigIssue(1, 1, "", "finalized claim did not persist exactly")
            )
        return finalized


def _resolve_head_commit(project_root: Path) -> str:
    commit = _git_output(
        _require_git_project_root(project_root),
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
    ).decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise ObconfigError(
            ConfigIssue(1, 1, "", "Git HEAD commit identity is invalid")
        )
    return commit


def _verify_dispatched_git_objects(
    project_root: Path,
    dispatch: Mapping[str, Any],
    generated_manifest: Mapping[str, Any],
) -> None:
    commit_sha = dispatch.get("commit_sha")
    tree_sha = dispatch.get("tree_sha")
    paths = generated_manifest.get("paths")
    if (
        not isinstance(commit_sha, str)
        or not isinstance(tree_sha, str)
        or not isinstance(paths, list)
        or not all(isinstance(path, str) for path in paths)
    ):
        raise ObconfigError(
            ConfigIssue(1, 1, "", "analysis dispatch record is invalid")
        )
    if _resolve_head_commit(project_root) != commit_sha:
        raise ObconfigError(
            ConfigIssue(1, 1, "", "Git HEAD no longer matches analysis dispatch")
        )
    committed_tree, committed_manifest = hash_committed_generated_outputs(
        project_root, commit_sha, paths
    )
    if (
        committed_tree != tree_sha
        or committed_manifest != dict(generated_manifest)
        or dispatch.get("generated_output_sha256")
        != generated_manifest.get("sha256")
    ):
        raise ObconfigError(
            ConfigIssue(
                1, 1, "", "dispatched Git tree or generated outputs do not match"
            )
        )


def record_dispatch(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
) -> dict[str, Any]:
    with _gate_lock(
        project_root,
        recovery_command=command,
        recovery_version=intended_version,
    ):
        claim, claim_version = _load_bound_state_version(
            _claim_path(project_root), "analysis claim"
        )
        generated = claim.get("generated_output_manifest")
        index_tree = claim.get("git_index_tree_sha")
        if (
            claim.get("schema_version") != SCHEMA_VERSION
            or claim.get("command") != command
            or claim.get("intended_version") != intended_version
            or claim.get("finalized") is not True
            or not isinstance(generated, Mapping)
            or not isinstance(index_tree, str)
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "analysis claim is not dispatchable")
            )
        commit_sha = _resolve_head_commit(project_root)
        committed_tree, committed_manifest = hash_committed_generated_outputs(
            project_root, commit_sha, generated.get("paths", [])
        )
        if committed_tree != index_tree or committed_manifest != dict(generated):
            raise ObconfigError(
                ConfigIssue(
                    1,
                    1,
                    "",
                    "HEAD must commit the exact finalized Git index tree and outputs",
                )
            )
        dispatch = {
            "schema_version": 1,
            "command": command,
            "intended_version": intended_version,
            "claim_sha256": claim_version.digest,
            "commit_sha": commit_sha,
            "tree_sha": committed_tree,
            "generated_output_sha256": generated["sha256"],
        }
        path = _dispatch_path(project_root)
        atomic_write_json(path, dispatch, expect_absent=True)
        persisted, _ = _load_bound_state_version(path, "analysis dispatch")
        if persisted != dispatch:
            raise ObconfigError(
                ConfigIssue(1, 1, "", "analysis dispatch did not persist exactly")
            )
        _verify_dispatched_git_objects(project_root, dispatch, generated)
        return dispatch


def verify_dispatch(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
) -> dict[str, Any]:
    with _gate_lock(
        project_root,
        recovery_command=command,
        recovery_version=intended_version,
    ):
        claim, claim_version = _load_bound_state_version(
            _claim_path(project_root), "analysis claim"
        )
        dispatch = _load_bound_state(
            _dispatch_path(project_root), "analysis dispatch"
        )
        generated = claim.get("generated_output_manifest")
        if (
            claim.get("finalized") is not True
            or claim.get("command") != command
            or claim.get("intended_version") != intended_version
            or not isinstance(generated, Mapping)
            or dispatch.get("command") != command
            or dispatch.get("intended_version") != intended_version
            or dispatch.get("claim_sha256") != claim_version.digest
            or dispatch.get("tree_sha") != claim.get("git_index_tree_sha")
        ):
            raise ObconfigError(
                ConfigIssue(
                    1, 1, "", "analysis dispatch does not match finalized claim"
                )
            )
        _verify_dispatched_git_objects(project_root, dispatch, generated)
        return dict(dispatch)


def abort_claim(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
) -> None:
    """Release an uncommitted claim without touching baseline or history."""
    with _gate_lock(
        project_root,
        recovery_command=command,
        recovery_version=intended_version,
    ):
        path = _claim_path(project_root)
        saved, version = _load_bound_state_version(path, "analysis claim")
        if (
            saved.get("schema_version") != SCHEMA_VERSION
            or saved.get("command") != command
            or saved.get("intended_version") != intended_version
        ):
            raise ObconfigError(
                ConfigIssue(1, 1, "", "analysis claim command or version does not match")
            )
        dispatch_path = _dispatch_path(project_root)
        if dispatch_path.exists() or dispatch_path.is_symlink():
            dispatch, dispatch_version = _load_bound_state_version(
                dispatch_path, "analysis dispatch"
            )
            if (
                dispatch.get("command") != command
                or dispatch.get("intended_version") != intended_version
                or dispatch.get("claim_sha256") != version.digest
            ):
                raise ObconfigError(
                    ConfigIssue(
                        1, 1, "", "analysis dispatch does not match abort claim"
                    )
                )
            _quarantine_remove_state(
                project_root, dispatch_path.name, dispatch_version
            )
        _quarantine_remove_state(
            project_root,
            path.name,
            version,
        )


def recover_pending_consume(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
) -> bool:
    with _gate_lock(
        project_root,
        recovery_command=command,
        recovery_version=intended_version,
    ) as recovered:
        return bool(recovered)


def consume_claim(
    project_root: Path,
    *,
    command: str,
    intended_version: str,
    enforce_git: bool = True,
) -> None:
    with _gate_lock(
        project_root,
        recovery_command=command,
        recovery_version=intended_version,
    ) as recovered:
        if recovered:
            return
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
    state, claim_version = _load_bound_state_version(
        _claim_path(project_root), "analysis claim"
    )
    if (
        state.get("schema_version") != SCHEMA_VERSION
        or state.get("command") != command
        or state.get("intended_version") != intended_version
    ):
        raise ObconfigError(
            ConfigIssue(1, 1, "", "analysis claim command or version does not match")
        )
    generated_manifest = state.get("generated_output_manifest")
    if (
        state.get("finalized") is not True
        or not isinstance(generated_manifest, Mapping)
        or state.get("generated_output_sha256")
        != generated_manifest.get("sha256")
    ):
        raise ObconfigError(
            ConfigIssue(1, 1, "", "analysis claim must be finalized before consume")
        )
    dispatch, dispatch_version = _load_bound_state_version(
        _dispatch_path(project_root), "analysis dispatch"
    )
    if (
        dispatch.get("command") != command
        or dispatch.get("intended_version") != intended_version
        or dispatch.get("claim_sha256") != claim_version.digest
        or dispatch.get("tree_sha") != state.get("git_index_tree_sha")
    ):
        raise ObconfigError(
            ConfigIssue(
                1, 1, "", "analysis dispatch does not match finalized claim"
            )
        )
    _verify_dispatched_git_objects(project_root, dispatch, generated_manifest)
    history = {
        key: state[key]
        for key in (
            "schema_version", "command", "intended_version",
            "config_sha256", "artifact_tree_sha256",
            "generated_output_sha256", "git_index_tree_sha",
        )
    }
    history["dispatched_commit_sha"] = dispatch["commit_sha"]
    history["dispatched_tree_sha"] = dispatch["tree_sha"]
    history["generated_output_manifest"] = dict(generated_manifest)
    manifest = state.get("artifact_manifest")
    if not isinstance(manifest, Mapping):
        raise ObconfigError(
            ConfigIssue(1, 1, "", "analysis claim has no artifact manifest")
        )
    journal = {
        "schema_version": 1,
        "command": command,
        "intended_version": intended_version,
        "claim_sha256": claim_version.digest,
        "dispatch_sha256": dispatch_version.digest,
        "dispatch": dict(dispatch),
        "artifact_manifest": dict(manifest),
        "last_analysis_binding": history,
    }
    atomic_write_json(
        _consume_journal_path(project_root),
        journal,
        expect_absent=True,
    )
    _recover_consume_locked(
        project_root,
        expected_command=command,
        expected_version=intended_version,
    )


def _recover_consume_locked(
    project_root: Path,
    *,
    expected_command: str | None,
    expected_version: str | None,
) -> bool:
    """Finish a consume transaction whose durable journal is its commit point."""
    path = _consume_journal_path(project_root)
    if not path.exists() and not path.is_symlink():
        return False
    journal = _load_bound_state(path, "consume journal")
    manifest = journal.get("artifact_manifest")
    history = journal.get("last_analysis_binding")
    claim_sha256 = journal.get("claim_sha256")
    dispatch_sha256 = journal.get("dispatch_sha256")
    dispatch = journal.get("dispatch")
    if (
        journal.get("schema_version") != 1
        or not isinstance(manifest, Mapping)
        or not isinstance(history, Mapping)
        or not isinstance(claim_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", claim_sha256)
        or not isinstance(dispatch_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", dispatch_sha256)
        or not isinstance(dispatch, Mapping)
    ):
        raise ObconfigError(ConfigIssue(1, 1, "", "consume journal is invalid"))
    if (
        expected_command is None
        or expected_version is None
        or journal.get("command") != expected_command
        or journal.get("intended_version") != expected_version
    ):
        raise ObconfigError(
            ConfigIssue(
                1,
                1,
                "",
                "consume journal command or version does not match recovery request",
            )
        )

    claim_path = _claim_path(project_root)
    claim_exists = claim_path.exists() or claim_path.is_symlink()
    claim_version: RegularFileVersion | None = None
    if claim_exists:
        claim_raw, claim_version = _capture_regular_version(
            claim_path,
            "analysis claim",
            required_mode=0o600,
        )
        if hashlib.sha256(claim_raw).hexdigest() != claim_sha256:
            raise ObconfigError(
                ConfigIssue(1, 1, "", "consume journal does not match analysis claim")
            )

    generated_manifest = history.get("generated_output_manifest")
    if not isinstance(generated_manifest, Mapping):
        raise ObconfigError(
            ConfigIssue(1, 1, "", "consume journal generated outputs are invalid")
        )
    dispatch_path = _dispatch_path(project_root)
    dispatch_exists = dispatch_path.exists() or dispatch_path.is_symlink()
    dispatch_version: RegularFileVersion | None = None
    if dispatch_exists:
        dispatch_raw, dispatch_version = _capture_regular_version(
            dispatch_path,
            "analysis dispatch",
            required_mode=0o600,
        )
        if (
            hashlib.sha256(dispatch_raw).hexdigest() != dispatch_sha256
            or _load_bound_state(dispatch_path, "analysis dispatch")
            != dict(dispatch)
        ):
            raise ObconfigError(
                ConfigIssue(
                    1, 1, "", "consume journal does not match analysis dispatch"
                )
            )
    _verify_dispatched_git_objects(
        project_root, dispatch, generated_manifest
    )

    atomic_write_json(_manifest_path(project_root), manifest)
    atomic_write_json(_last_binding_path(project_root), history)
    saved_manifest = _load_bound_state(
        _manifest_path(project_root), "artifact manifest"
    )
    saved_history = _load_bound_state(
        _last_binding_path(project_root), "last analysis binding"
    )
    if saved_manifest != dict(manifest) or saved_history != dict(history):
        raise ObconfigError(
            ConfigIssue(1, 1, "", "consume transaction did not persist exactly")
        )
    if claim_exists:
        assert claim_version is not None
        _quarantine_remove_state(
            project_root,
            claim_path.name,
            claim_version,
        )
    if dispatch_exists:
        assert dispatch_version is not None
        _quarantine_remove_state(
            project_root,
            dispatch_path.name,
            dispatch_version,
        )
    _, journal_version = _capture_regular_version(
        path,
        "consume journal",
        required_mode=0o600,
    )
    _quarantine_remove_state(project_root, path.name, journal_version)
    return True


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
