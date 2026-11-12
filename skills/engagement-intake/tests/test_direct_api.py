from __future__ import annotations

import importlib.util
import secrets
import sys
import urllib.error
from pathlib import Path
from urllib.parse import parse_qs

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
for name in ("obconfig", "direct_api"):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

import direct_api


def measured_body(source):
    if source == "splunk-observability-direct":
        metric = direct_api.SF_ORG_METRICS[0]
        return (
            '{"type":"metadata","message":{"tsId":"one","properties":'
            f'{{"sf_metric":"{metric}"}}}}}}\n'
            '{"type":"data","message":{"data":[{"tsId":"one","value":12}]}}\n'
        ).encode()
    return b'{"result":{"index":"redacted","events":"7","bytes":"99"}}\n'


def configured():
    tokens = [secrets.token_urlsafe(33), secrets.token_urlsafe(33)]
    config = {
        "splunk": {
            "observability": {"realm": "us1", "read_token": tokens[0]},
            "platform": {
                "host": "https://splunk.example.test:8089",
                "read_token": tokens[1],
                "index_allowlist": ["app_main", "app_audit"],
            },
        }
    }
    return config, tokens


def test_both_phases_mandate_direct_requests_and_tokens_are_headers_only():
    config, tokens = configured()
    captured = []

    def transport(request):
        captured.append(request)
        return direct_api.Response(200, measured_body(request.source))

    for phase in ("analysis", "verification"):
        results = direct_api.collect_direct_evidence(
            config, phase=phase, transport=transport
        )
        assert [row["disposition"] for row in results] == [
            "succeeded", "succeeded"
        ]
        assert all(row["measured"] for row in results)

    assert len(captured) == 4
    for request in captured:
        joined = request.url + (request.body or b"").decode(errors="ignore")
        assert all(token not in joined for token in tokens)
        assert request.method == "POST"
        assert request.url.startswith("https://")
    assert captured[0].headers["X-SF-TOKEN"] == tokens[0]
    assert captured[1].headers["Authorization"] == f"Splunk {tokens[1]}"
    assert all(metric in captured[0].body.decode() for metric in direct_api.SF_ORG_METRICS)
    search = parse_qs(captured[1].body.decode())["search"][0]
    assert 'index="app_main"' in search
    assert "index=*" not in search


def test_mcp_cannot_replace_not_configured_direct_attempt():
    config = {
        "splunk": {
            "observability": {"realm": "", "read_token": ""},
            "platform": {"host": "", "read_token": "", "index_allowlist": []},
        }
    }
    results = direct_api.collect_direct_evidence(config, phase="analysis")
    assert all(row["disposition"] == "not-configured" for row in results)
    assert all(row["attempted"] is False and row["measured"] is False for row in results)


def test_failures_are_explicit_and_response_body_is_never_returned():
    config, tokens = configured()

    def denied(request):
        return direct_api.Response(403, b"sensitive response")

    results = direct_api.collect_direct_evidence(
        config, phase="verification", transport=denied
    )
    assert all(row["disposition"] == "access-denied" for row in results)
    rendered = repr(results)
    assert "sensitive response" not in rendered
    assert all(token not in rendered for token in tokens)


def test_cross_origin_redirect_is_not_followed():
    assert direct_api.NoRedirect().redirect_request(
        None, None, 302, "redirect", {}, "https://other.example.test/"
    ) is None


def test_request_builders_reject_unvalidated_realms_and_indexes():
    token = secrets.token_urlsafe(33)
    with pytest.raises(ValueError):
        direct_api.observability_request("us1.example.test/path", token)
    with pytest.raises(ValueError):
        direct_api.platform_request(
            "https://splunk.example.test:8089", token, ["*"]
        )


def test_transient_read_failures_retry_only_to_fixed_bound():
    request = direct_api.observability_request("us1", secrets.token_urlsafe(33))
    statuses = iter((503, 429, 200))
    calls = []

    def transient(spec):
        calls.append(spec)
        status = next(statuses)
        return direct_api.Response(status, measured_body(spec.source))

    result = direct_api.execute(request, transport=transient)
    assert result["disposition"] == "succeeded"
    assert result["attempts"] == direct_api.MAX_READ_ATTEMPTS
    assert len(calls) == direct_api.MAX_READ_ATTEMPTS

    def unavailable(spec):
        calls.append(spec)
        raise urllib.error.URLError("redacted network failure")

    result = direct_api.execute(request, transport=unavailable)
    assert result == {
        "source": "splunk-observability-direct",
        "attempted": True,
        "attempts": direct_api.MAX_READ_ATTEMPTS,
        "disposition": "unavailable",
        "reason": "TLS, timeout, or network failure",
        "measured": False,
    }


def test_mock_transport_cannot_bypass_response_size_limit():
    request = direct_api.observability_request("us1", secrets.token_urlsafe(33))

    result = direct_api.execute(
        request,
        transport=lambda spec: direct_api.Response(
            200, b"x" * (spec.response_limit_bytes + 1)
        ),
    )

    assert result["disposition"] == "unavailable"
    assert result["attempts"] == 1
    assert result["measured"] is False


def test_unrecognized_success_body_is_not_labeled_measured():
    request = direct_api.platform_request(
        "https://splunk.example.test:8089",
        secrets.token_urlsafe(33),
        ["app_main"],
    )

    result = direct_api.execute(
        request,
        transport=lambda spec: direct_api.Response(200, b'{"ok":true}'),
    )

    assert result["disposition"] == "unavailable"
    assert result["measured"] is False
    assert "ok" not in repr(result)
