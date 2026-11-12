#!/usr/bin/env python3
"""Deterministic, read-only Splunk direct-API request adapters.

The adapters expose request plans for mocked documented endpoints and a bounded urllib
transport. They never put credentials in URLs, query strings, exceptions, or results.
"""

from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from obconfig import INDEX, REALM, Redactor, normalize_origin, validate_platform_host

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
CONNECT_READ_TIMEOUT_SECONDS = 15
MAX_READ_ATTEMPTS = 3
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
SF_ORG_METRICS = (
    "sf.org.numActiveTimeSeries",
    "sf.org.limit.activeTimeSeries",
    "sf.org.numCustomMetrics",
    "sf.org.limit.customMetricMaxLimit",
    "sf.org.limit.customMetricTimeSeries",
    "sf.org.apm.numTracesReceived",
    "sf.org.apm.numSpanBytesReceived",
    "sf.org.apm.numMonitoringMetricSets",
    "sf.org.apm.numTroubleshootingMetricSets",
)


@dataclass(frozen=True)
class RequestSpec:
    source: str
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None
    timeout_seconds: int = CONNECT_READ_TIMEOUT_SECONDS
    response_limit_bytes: int = MAX_RESPONSE_BYTES


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _json_objects(body: bytes) -> list[Mapping[str, Any]]:
    objects: list[Mapping[str, Any]] = []
    for raw_line in body.splitlines() or [body]:
        line = raw_line.strip()
        if line.startswith(b"data:"):
            line = line[5:].strip()
        if not line:
            continue
        value = json.loads(line)
        if isinstance(value, Mapping):
            objects.append(value)
    return objects


def _observability_measurements(body: bytes) -> dict[str, Any] | None:
    metadata: dict[str, str] = {}
    values: dict[str, int | float] = {}
    pending: list[Mapping[str, Any]] = []
    for event in _json_objects(body):
        message = event.get("message", event)
        if not isinstance(message, Mapping):
            continue
        properties = message.get("properties")
        tsid = message.get("tsId")
        if isinstance(properties, Mapping) and isinstance(tsid, str):
            metric = properties.get("sf_metric")
            if isinstance(metric, str) and metric in SF_ORG_METRICS:
                metadata[tsid] = metric
        points = message.get("data")
        if isinstance(points, list):
            pending.extend(point for point in points if isinstance(point, Mapping))
    for point in pending:
        metric = metadata.get(point.get("tsId"))
        value = point.get("value")
        if (
            metric is not None
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            values[metric] = value
    if not values:
        return None
    return {
        "measurements": dict(sorted(values.items())),
        "measurement_count": len(values),
    }


def _platform_measurements(body: bytes) -> dict[str, Any] | None:
    rows: list[Mapping[str, Any]] = []
    for value in _json_objects(body):
        result = value.get("result")
        if isinstance(result, Mapping):
            rows.append(result)
        results = value.get("results")
        if isinstance(results, list):
            rows.extend(item for item in results if isinstance(item, Mapping))
    total_events = 0
    total_bytes = 0
    measured_rows = 0
    for row in rows:
        try:
            events = int(row["events"])
            byte_count = int(row["bytes"])
        except (KeyError, TypeError, ValueError):
            continue
        if events < 0 or byte_count < 0:
            continue
        total_events += events
        total_bytes += byte_count
        measured_rows += 1
    if not measured_rows:
        return None
    return {
        "index_count": measured_rows,
        "events": total_events,
        "bytes": total_bytes,
    }


def _measure_response(source: str, body: bytes) -> dict[str, Any] | None:
    try:
        if source == "splunk-observability-direct":
            return _observability_measurements(body)
        if source == "splunk-platform-direct":
            return _platform_measurements(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return None


def observability_request(realm: str, token: str) -> RequestSpec:
    if not realm or not token or not REALM.fullmatch(realm):
        raise ValueError("Observability Cloud access is not configured")
    host = f"stream.{realm}.observability.splunkcloud.com"
    # SignalFlow program contains only the approved fixed metric registry.
    program = "\n".join(
        f"data({metric!r}).publish(label={('m' + str(index))!r})"
        for index, metric in enumerate(SF_ORG_METRICS)
    )
    body = json.dumps(
        {"program": program, "start": "-5m", "stop": "Now"},
        separators=(",", ":"),
    ).encode()
    return RequestSpec(
        source="splunk-observability-direct",
        method="POST",
        url=f"https://{host}/v2/signalflow/execute",
        headers={
            "X-SF-TOKEN": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        body=body,
    )


def _splunk_index_expression(indexes: list[str]) -> str:
    # Indexes were schema-validated; quoting remains defense in depth.
    return " OR ".join(
        'index="' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        for value in indexes
    )


def platform_request(host: str, token: str, indexes: list[str]) -> RequestSpec:
    normalized = validate_platform_host(host)
    if not token or not indexes:
        raise ValueError("Splunk Platform access is not configured")
    if len(set(indexes)) != len(indexes) or any(
        name in {"*", "_all"} or "*" in name or not INDEX.fullmatch(name)
        for name in indexes
    ):
        raise ValueError("Splunk Platform index allowlist is invalid")
    search = (
        "search (" + _splunk_index_expression(indexes) + ") "
        "| stats count AS events, sum(eval(len(_raw))) AS bytes by index"
    )
    body = urllib.parse.urlencode(
        {"search": search, "output_mode": "json"}
    ).encode()
    return RequestSpec(
        source="splunk-platform-direct",
        method="POST",
        url=normalized + "/services/search/v2/jobs/export",
        headers={
            "Authorization": f"Splunk {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        body=body,
    )


def urllib_transport(request: RequestSpec) -> Response:
    parsed = urllib.parse.urlsplit(request.url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("direct API request requires HTTPS")
    origin_text = f"https://{parsed.hostname}{f':{parsed.port}' if parsed.port else ''}"
    expected_origin = (
        validate_platform_host(origin_text)
        if request.source == "splunk-platform-direct"
        else normalize_origin(origin_text)
    )
    if request.url.split(parsed.path or "/", 1)[0].rstrip("/") != expected_origin:
        raise ValueError("direct API target origin was not normalized")
    opener = urllib.request.build_opener(
        NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    outgoing = urllib.request.Request(
        request.url,
        data=request.body,
        headers=dict(request.headers),
        method=request.method,
    )
    with opener.open(outgoing, timeout=request.timeout_seconds) as response:
        body = response.read(request.response_limit_bytes + 1)
        if len(body) > request.response_limit_bytes:
            raise ValueError("direct API response exceeded the fixed size limit")
        return Response(status=response.status, body=body)


def execute(
    request: RequestSpec,
    *,
    transport: Callable[[RequestSpec], Response] = urllib_transport,
) -> dict[str, Any]:
    for attempt in range(1, MAX_READ_ATTEMPTS + 1):
        try:
            response = transport(request)
            if len(response.body) > request.response_limit_bytes:
                raise ValueError("direct API response exceeded the fixed size limit")
            if response.status in RETRYABLE_STATUS and attempt < MAX_READ_ATTEMPTS:
                continue
            if 200 <= response.status < 300:
                measurements = _measure_response(request.source, response.body)
                if measurements is None:
                    return {
                        "source": request.source,
                        "attempted": True,
                        "attempts": attempt,
                        "disposition": "unavailable",
                        "status": response.status,
                        "reason": "documented aggregate response shape was unavailable",
                        "measured": False,
                    }
                disposition = "succeeded"
            elif response.status in {401, 403}:
                disposition = "access-denied"
            elif response.status in {404, 405, 501}:
                disposition = "unsupported-endpoint"
            else:
                disposition = "http-failure"
            result = {
                "source": request.source,
                "attempted": True,
                "attempts": attempt,
                "disposition": disposition,
                "status": response.status,
                "response_bytes": len(response.body),
                "measured": disposition == "succeeded",
            }
            if disposition == "succeeded":
                result.update(measurements)
            return result
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE_STATUS and attempt < MAX_READ_ATTEMPTS:
                continue
            disposition = (
                "access-denied"
                if exc.code in {401, 403}
                else "unsupported-endpoint"
                if exc.code in {404, 405, 501}
                else "http-failure"
            )
            return {
                "source": request.source,
                "attempted": True,
                "attempts": attempt,
                "disposition": disposition,
                "status": exc.code,
                "measured": False,
            }
        except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError):
            if attempt < MAX_READ_ATTEMPTS:
                continue
            return {
                "source": request.source,
                "attempted": True,
                "attempts": attempt,
                "disposition": "unavailable",
                "reason": "TLS, timeout, or network failure",
                "measured": False,
            }
        except (OSError, ValueError):
            return {
                "source": request.source,
                "attempted": True,
                "attempts": attempt,
                "disposition": "unavailable",
                "reason": "bounded direct adapter rejected the response or target",
                "measured": False,
            }
    raise AssertionError("bounded direct adapter exhausted without a disposition")


def collect_direct_evidence(
    config: Mapping[str, Any],
    *,
    phase: str,
    transport: Callable[[RequestSpec], Response] = urllib_transport,
) -> list[dict[str, Any]]:
    if phase not in {"analysis", "verification"}:
        raise ValueError("phase must be analysis or verification")
    results: list[dict[str, Any]] = []
    observability = config["splunk"]["observability"]
    if observability["read_token"]:
        results.append(
            execute(
                observability_request(
                    observability["realm"], observability["read_token"]
                ),
                transport=transport,
            )
        )
    else:
        results.append(
            {
                "source": "splunk-observability-direct",
                "attempted": False,
                "disposition": "not-configured",
                "measured": False,
            }
        )
    platform = config["splunk"]["platform"]
    if platform["read_token"]:
        results.append(
            execute(
                platform_request(
                    platform["host"],
                    platform["read_token"],
                    platform["index_allowlist"],
                ),
                transport=transport,
            )
        )
    else:
        results.append(
            {
                "source": "splunk-platform-direct",
                "attempted": False,
                "disposition": "not-configured",
                "measured": False,
            }
        )
    # Defense in depth: never return a transport message or response body.
    return Redactor(config).value(results)
