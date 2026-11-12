from __future__ import annotations

import importlib.util
import json
import secrets
import subprocess
import sys
import socket
import urllib.error
from pathlib import Path
from urllib.parse import parse_qs

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
for name in ("obconfig", "direct_api"):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

import direct_api
import obconfig

manage_spec = importlib.util.spec_from_file_location(
    "manage_obconfig", SCRIPTS / "manage_obconfig.py"
)
manage_obconfig = importlib.util.module_from_spec(manage_spec)
sys.modules[manage_spec.name] = manage_obconfig
manage_spec.loader.exec_module(manage_obconfig)
TEMPLATE = SCRIPTS.parents[2] / "obconfig.yaml.template"


def measured_body(source):
    if source == "splunk-observability-direct":
        metric = direct_api.SF_ORG_METRICS[0]
        return (
            "event: metadata\n"
            'data: {"type":"metadata","message":{"tsId":"one","properties":'
            f'{{"sf_metric":"{metric}"}}}}}}\n\n'
            "event: data\n"
            'data: {"type":"data","message":{"data":'
            '[{"tsId":"one","timestamp":1000,"value":10},'
            '{"tsId":"one","timestamp":2000,"value":12}]}}\n\n'
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


def configured_project(root: Path):
    (root / "artifacts").mkdir()
    data = yaml.safe_load(TEMPLATE.read_text())
    canaries = [secrets.token_urlsafe(33) for _ in range(3)]
    data["engagement"]["application"] = "direct-cli-fixture"
    data["surfaces"]["no_browser_reason"] = "service has no browser"
    data["splunk"]["observability"] = {
        "realm": "us1",
        "read_token": canaries[0],
    }
    data["splunk"]["platform"] = {
        "host": "https://splunk.example.test:8089",
        "read_token": canaries[1],
        "index_allowlist": ["app_main"],
    }
    data["analysis_access"]["dummy_login"] = {
        "login_id": "disposable-user",
        "password": canaries[2],
    }
    config = root / "obconfig.yaml"
    config.write_text(yaml.safe_dump(data, sort_keys=False))
    config.chmod(0o600)
    (root / ".gitignore").write_text("/obconfig.yaml\n/.obengineer/\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return canaries


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
        assert results[0]["measurements"][direct_api.SF_ORG_METRICS[0]] == 12
        aggregate = results[0]["aggregates"][direct_api.SF_ORG_METRICS[0]]
        assert aggregate == {
            "samples": 2,
            "first_timestamp": 1000,
            "last_timestamp": 2000,
            "minimum": 10,
            "maximum": 12,
            "latest": 12,
        }

    assert len(captured) == 4
    for request in captured:
        joined = request.url + (request.body or b"").decode(errors="ignore")
        assert all(token not in joined for token in tokens)
        assert request.method == "POST"
        assert request.url.startswith("https://")
    assert captured[0].url == (
        "https://api.us1.observability.splunkcloud.com/v2/signalflow/execute"
    )
    assert captured[0].headers["X-SF-TOKEN"] == tokens[0]
    assert captured[1].headers["Authorization"] == f"Splunk {tokens[1]}"
    assert all(metric in captured[0].body.decode() for metric in direct_api.SF_ORG_METRICS)
    search = parse_qs(captured[1].body.decode())["search"][0]
    assert 'index="app_main"' in search
    assert "index=*" not in search
    platform_body = parse_qs(captured[1].body.decode())
    assert platform_body["earliest_time"] == ["-5m"]
    assert platform_body["latest_time"] == ["now"]
    assert platform_body["max_time"] == ["30"]
    assert platform_body["max_count"] == ["10000"]


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

    delays = []
    result = direct_api.execute(request, transport=transient, sleep=delays.append)
    assert result["disposition"] == "succeeded"
    assert result["attempts"] == direct_api.MAX_READ_ATTEMPTS
    assert len(calls) == direct_api.MAX_READ_ATTEMPTS
    assert delays == [0.25, 0.5]

    def unavailable(spec):
        calls.append(spec)
        raise urllib.error.URLError("redacted network failure")

    result = direct_api.execute(
        request, transport=unavailable, sleep=lambda _: None
    )
    assert result == {
        "source": "splunk-observability-direct",
        "attempted": True,
        "attempts": direct_api.MAX_READ_ATTEMPTS,
        "disposition": "unavailable",
        "reason": "TLS, timeout, or network failure",
        "measured": False,
    }

    statuses = iter((429, 200))
    delays = []
    result = direct_api.execute(
        request,
        transport=lambda spec: direct_api.Response(
            next(statuses), measured_body(spec.source), {"Retry-After": "10"}
        ),
        sleep=delays.append,
    )
    assert result["disposition"] == "succeeded"
    assert delays == [2.0]


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


def test_sse_parser_is_bounded():
    line = b"data: " + b"x" * direct_api.MAX_SSE_LINE_BYTES + b"\n\n"
    with pytest.raises(ValueError, match="size limit"):
        direct_api._sse_json_events(line)
    body = b"".join(b"data: {}\n\n" for _ in range(direct_api.MAX_SSE_EVENTS + 1))
    with pytest.raises(ValueError, match="event count"):
        direct_api._sse_json_events(body)


def test_safe_active_plan_zero_calls_and_fixed_capture():
    passive = {"security_assessment": {"mode": "passive", "authorized_origins": []}}
    calls = []
    assert direct_api.execute_safe_active(passive, executor=calls.append) == []
    assert calls == []

    active = {
        "security_assessment": {
            "mode": "safe-active",
            "authorized_origins": ["https://www.example.com"],
        }
    }

    def capture(request):
        calls.append(request)
        return {"status": 204}

    results = direct_api.execute_safe_active(
        active, executor=capture, sleep=lambda _: None
    )
    assert [(row["method"], row["path"]) for row in results] == [
        ("HEAD", "/robots.txt"),
        ("HEAD", "/.well-known/security.txt"),
    ]
    assert all(request["follow_redirects"] is False for request in calls)
    assert all(request["max_requests"] == 100 for request in calls)
    assert all(request["requests_per_second"] == 1 for request in calls)


def test_safe_active_rejects_any_private_dns_answer_and_peer_swap():
    def mixed(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
        ]

    with pytest.raises(ValueError, match="non-global"):
        direct_api._global_addresses("www.example.com", 443, resolver=mixed)

    class SwappedSocket:
        def getpeername(self):
            return ("10.0.0.1", 443)

        def close(self):
            pass

    with pytest.raises(ValueError, match="peer"):
        direct_api.safe_active_https_probe(
            {"method": "HEAD", "url": "https://www.example.com/robots.txt"},
            resolver=lambda *args, **kwargs: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
            ],
            connection_factory=lambda *args, **kwargs: SwappedSocket(),
        )


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


@pytest.mark.parametrize("phase", ("analysis", "verification"))
def test_supported_cli_invokes_mock_transport_without_leaking_canaries(
    tmp_path, monkeypatch, capsys, phase
):
    canaries = configured_project(tmp_path)
    if phase == "analysis":
        obconfig.authorize(
            tmp_path, command="ob-start", intended_version="V1"
        )
        obconfig.claim_authorization(
            tmp_path, command="ob-start", intended_version="V1"
        )
    captured = []

    def transport(request):
        captured.append(request)
        return direct_api.Response(200, measured_body(request.source))

    argv = [
        str(SCRIPTS / "manage_obconfig.py"),
        "--project-root",
        str(tmp_path),
        "direct-api",
        "--phase",
        phase,
    ]
    if phase == "analysis":
        argv.extend(["--command", "ob-start", "--intended-version", "V1"])
    monkeypatch.setattr(sys, "argv", argv)

    assert manage_obconfig.main(direct_transport=transport) == 0
    terminal = capsys.readouterr()
    payload = json.loads(terminal.out)
    rendered = terminal.out + terminal.err + repr(payload) + repr(sys.argv)

    assert terminal.err == ""
    assert payload["phase"] == phase
    assert [row["disposition"] for row in payload["direct_api"]] == [
        "succeeded",
        "succeeded",
    ]
    assert all(row["measured"] for row in payload["direct_api"])
    assert all(canary not in rendered for canary in canaries)
    assert len(captured) == 2
    for request in captured:
        combined_target = request.url + (request.body or b"").decode()
        assert all(canary not in combined_target for canary in canaries)
    assert captured[0].headers["X-SF-TOKEN"] == canaries[0]
    assert captured[1].headers["Authorization"] == f"Splunk {canaries[1]}"


def test_supported_safe_active_cli_is_claim_bound_and_redacted(
    tmp_path, capsys
):
    canaries = configured_project(tmp_path)
    path = tmp_path / "obconfig.yaml"
    data = yaml.safe_load(path.read_text())
    data["security_assessment"] = {
        "mode": "safe-active",
        "authorized_origins": ["https://www.example.com"],
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    path.chmod(0o600)
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    captured = []

    def executor(request):
        captured.append(request)
        return {"status": 200}

    argv = [
        "--project-root",
        str(tmp_path),
        "safe-active",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
    ]
    assert manage_obconfig.main(argv, safe_active_executor=executor) == 0
    terminal = capsys.readouterr()
    payload = json.loads(terminal.out)
    rendered = terminal.out + terminal.err + repr(payload) + repr(argv)
    assert len(captured) == 2
    assert all(row["disposition"] == "succeeded" for row in payload["safe_active"])
    assert all(canary not in rendered for canary in canaries)


def test_direct_api_discards_result_when_config_swaps_during_transport(
    tmp_path, capsys
):
    canaries = configured_project(tmp_path)
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    swapped = False

    def transport(request):
        nonlocal swapped
        if not swapped:
            swapped = True
            path = tmp_path / "obconfig.yaml"
            data = yaml.safe_load(path.read_text())
            data["engagement"]["scope"] = "changed during request"
            path.write_text(yaml.safe_dump(data, sort_keys=False))
            path.chmod(0o600)
        return direct_api.Response(200, measured_body(request.source))

    argv = [
        "--project-root",
        str(tmp_path),
        "direct-api",
        "--phase",
        "analysis",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
    ]
    assert manage_obconfig.main(argv, direct_transport=transport) == 1
    terminal = capsys.readouterr()
    rendered = terminal.out + terminal.err + repr(argv)
    assert terminal.out == ""
    assert "no longer matches" in terminal.err
    assert all(canary not in rendered for canary in canaries)


def test_supported_cli_missing_config_ignores_environment_and_reports_not_configured(
    tmp_path, monkeypatch, capsys
):
    environment_canaries = [secrets.token_urlsafe(33) for _ in range(3)]
    monkeypatch.setenv("SPLUNK_ACCESS_TOKEN", environment_canaries[0])
    monkeypatch.setenv("SPLUNK_TOKEN", environment_canaries[1])
    monkeypatch.setenv("RAW_PASSWORD", environment_canaries[2])

    def no_network(request):
        raise AssertionError("missing config must not invoke a transport")

    argv = [
        str(SCRIPTS / "manage_obconfig.py"),
        "--project-root",
        str(tmp_path),
        "direct-api",
        "--phase",
        "verification",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    assert manage_obconfig.main(direct_transport=no_network) == 0
    terminal = capsys.readouterr()
    payload = json.loads(terminal.out)
    rendered = terminal.out + terminal.err + repr(payload) + repr(sys.argv)

    assert terminal.err == ""
    assert [row["disposition"] for row in payload["direct_api"]] == [
        "not-configured",
        "not-configured",
    ]
    assert all(row["attempted"] is False for row in payload["direct_api"])
    assert all(canary not in rendered for canary in environment_canaries)


def test_supported_cli_refuses_permissive_config_without_leaking(
    tmp_path, capsys
):
    canaries = configured_project(tmp_path)
    (tmp_path / "obconfig.yaml").chmod(0o644)
    argv = [
        "--project-root",
        str(tmp_path),
        "direct-api",
        "--phase",
        "verification",
    ]

    assert manage_obconfig.main(argv, direct_transport=lambda request: None) == 1
    terminal = capsys.readouterr()
    rendered = terminal.out + terminal.err + repr(argv)

    assert terminal.out == ""
    assert "mode must be 0600" in terminal.err
    assert all(canary not in rendered for canary in canaries)
