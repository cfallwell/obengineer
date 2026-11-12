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


@pytest.mark.parametrize(
    ("host", "origin"),
    (
        (
            "https://[2606:4700:4700::1111]",
            "https://[2606:4700:4700::1111]",
        ),
        (
            "https://[2606:4700:4700::1111]:8089",
            "https://[2606:4700:4700::1111]:8089",
        ),
    ),
)
def test_platform_ipv6_url_and_transport_origin_are_bracketed(
    monkeypatch, host, origin
):
    request = direct_api.platform_request(
        host, secrets.token_urlsafe(33), ["app_main"]
    )
    assert request.url == origin + "/services/search/v2/jobs/export"
    validated = []
    original_validate = direct_api.validate_platform_host

    def capture_origin(value):
        validated.append(value)
        return original_validate(value)

    class FakeResponse:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return b'{"result":{"events":"1","bytes":"2"}}'

    class FakeOpener:
        def open(self, outgoing, timeout):
            assert outgoing.full_url == request.url
            return FakeResponse()

    monkeypatch.setattr(
        direct_api, "validate_platform_host", capture_origin
    )
    monkeypatch.setattr(
        direct_api.urllib.request,
        "build_opener",
        lambda *handlers: FakeOpener(),
    )
    response = direct_api.urllib_transport(request)
    assert response.status == 200
    assert validated == [origin]


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


def test_signalflow_batches_apply_logical_timestamp_to_each_point():
    metric = direct_api.SF_ORG_METRICS[0]
    body = (
        "event: metadata\n"
        'data: {"message":{"tsId":"one","properties":'
        f'{{"sf_metric":"{metric}"}}}}}}\n\n'
        "event: data\n"
        'data: {"message":{"logicalTimestampMs":1000,'
        '"data":[{"tsId":"one","value":1}]}}\n\n'
        "event: data\n"
        'data: {"message":{"logicalTimestampMs":2000,'
        '"data":[{"tsId":"one","value":2}]}}\n\n'
    ).encode()
    measured = direct_api._observability_measurements(body)
    assert measured["measurements"][metric] == 2
    assert measured["aggregates"][metric] == {
        "samples": 2,
        "first_timestamp": 1000,
        "last_timestamp": 2000,
        "minimum": 1,
        "maximum": 2,
        "latest": 2,
    }


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


@pytest.mark.parametrize(
    ("url", "address", "family", "expected_authority", "expected_port"),
    (
        (
            "https://www.example.com/robots.txt",
            "8.8.8.8",
            socket.AF_INET,
            "www.example.com",
            443,
        ),
        (
            "https://www.example.com:8443/robots.txt",
            "8.8.8.8",
            socket.AF_INET,
            "www.example.com:8443",
            8443,
        ),
        (
            "https://[2606:4700:4700::1111]/robots.txt",
            "2606:4700:4700::1111",
            socket.AF_INET6,
            "[2606:4700:4700::1111]",
            443,
        ),
    ),
)
def test_safe_active_host_header_preserves_exact_authority(
    monkeypatch, url, address, family, expected_authority, expected_port
):
    class FakeSocket:
        def __init__(self):
            self.sent = b""

        def getpeername(self):
            return (address, expected_port)

        def sendall(self, value):
            self.sent += value

        def recv(self, size):
            return b"HTTP/1.1 204 No Content\r\n\r\n"

        def close(self):
            pass

    fake = FakeSocket()

    class FakeContext:
        def wrap_socket(self, raw, server_hostname):
            return raw

    monkeypatch.setattr(
        direct_api.ssl, "create_default_context", lambda: FakeContext()
    )

    def connection(target, timeout):
        assert target == (address, expected_port)
        return fake

    result = direct_api.safe_active_https_probe(
        {"method": "HEAD", "url": url},
        resolver=lambda *args, **kwargs: [
            (
                family,
                socket.SOCK_STREAM,
                6,
                "",
                (address, expected_port),
            )
        ],
        connection_factory=connection,
    )
    assert result["status"] == 204
    assert f"\r\nHost: {expected_authority}\r\n".encode() in fake.sent


def test_safe_active_status_line_read_is_bounded(monkeypatch):
    class FakeSocket:
        def getpeername(self):
            return ("8.8.8.8", 443)

        def sendall(self, value):
            pass

        def recv(self, size):
            return b"X" * size

        def close(self):
            pass

    class FakeContext:
        def wrap_socket(self, raw, server_hostname):
            return raw

    monkeypatch.setattr(
        direct_api.ssl, "create_default_context", lambda: FakeContext()
    )
    with pytest.raises(ValueError, match="exceeded limit"):
        direct_api.safe_active_https_probe(
            {
                "method": "HEAD",
                "url": "https://www.example.com/robots.txt",
            },
            resolver=lambda *args, **kwargs: [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    6,
                    "",
                    ("8.8.8.8", 443),
                )
            ],
            connection_factory=lambda *args, **kwargs: FakeSocket(),
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


def test_supported_abort_cli_releases_mutated_claim_without_baseline(
    tmp_path, capsys
):
    configured_project(tmp_path)
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    (tmp_path / "obconfig.yaml").write_text("invalid: [\n")
    (tmp_path / "obconfig.yaml").chmod(0o600)
    argv = [
        "--project-root",
        str(tmp_path),
        "abort",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
    ]
    assert manage_obconfig.main(argv) == 0
    terminal = capsys.readouterr()
    assert "without advancing the baseline" in terminal.out
    assert not (tmp_path / ".obengineer/analysis-claim.json").exists()
    assert not (tmp_path / ".obengineer/artifact-manifest.json").exists()
    assert not (tmp_path / ".obengineer/last-analysis-binding.json").exists()


def test_config_projection_exposes_targets_and_constraints_without_secrets(
    tmp_path, capsys
):
    canaries = configured_project(tmp_path)
    data = yaml.safe_load((tmp_path / "obconfig.yaml").read_text())
    production_url = "https://shop.example.test"
    index_canary = "idx_" + secrets.token_hex(20)
    extension_canary = secrets.token_urlsafe(36)
    data["surfaces"]["production_urls"] = [production_url]
    data["surfaces"]["no_browser_reason"] = ""
    data["constraints"]["privacy_regimes"] = ["gdpr", "pci"]
    data["constraints"]["data_residency"] = "eu-only"
    data["engagement"]["deployment_environment"] = "production"
    data["initial_scope"]["repositories"] = ["storefront"]
    data["outcomes"]["first_journey"] = "checkout"
    data["splunk"]["platform"]["index_allowlist"] = [index_canary]
    data["extensions"] = {
        "private_customer_context": extension_canary,
    }
    path = tmp_path / "obconfig.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    path.chmod(0o600)
    (tmp_path / "artifacts/input.txt").write_text("evidence\n")
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    argv = [
        "--project-root",
        str(tmp_path),
        "config-projection",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
    ]
    assert manage_obconfig.main(argv) == 0
    terminal = capsys.readouterr()
    projection = json.loads(terminal.out)
    assert projection["surfaces"]["production_urls"] == [production_url]
    assert projection["constraints"]["privacy_regimes"] == ["gdpr", "pci"]
    assert projection["constraints"]["data_residency"] == "eu-only"
    assert projection["engagement"]["deployment_environment"] == "production"
    assert projection["initial_scope"]["repositories"] == ["storefront"]
    assert projection["outcomes"]["first_journey"] == "checkout"
    assert projection["artifacts"]["file_count"] == 1
    assert projection["artifacts"]["delta"]["added"] == ["input.txt"]
    assert projection["splunk"]["observability"]["realm"] == "us1"
    assert projection["splunk"]["observability"]["configured"] is True
    assert projection["splunk"]["platform"]["host"] == (
        "https://splunk.example.test:8089"
    )
    assert projection["splunk"]["platform"]["index_count"] == 1
    assert projection["availability"]["dummy_login"] == "configured"
    assert "extensions" not in projection
    combined = terminal.out + terminal.err + json.dumps(projection)
    for canary in [*canaries, index_canary, extension_canary]:
        assert canary not in combined
    assert "login_id" not in combined
    assert "read_token" not in combined
    assert "index_allowlist" not in combined
    assert "password" not in combined


def test_config_projection_emits_nothing_when_artifacts_change_mid_projection(
    tmp_path, capsys, monkeypatch
):
    canaries = configured_project(tmp_path)
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    original = manage_obconfig.analysis_config_projection

    def mutate_after_projection(data, claim):
        payload = original(data, claim)
        (tmp_path / "artifacts/raced.txt").write_text("changed\n")
        return payload

    monkeypatch.setattr(
        manage_obconfig,
        "analysis_config_projection",
        mutate_after_projection,
    )
    assert manage_obconfig.main([
        "--project-root",
        str(tmp_path),
        "config-projection",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
    ]) == 1
    terminal = capsys.readouterr()
    assert terminal.out == ""
    for canary in canaries:
        assert canary not in terminal.err


@pytest.mark.parametrize("with_password", (False, True))
def test_production_url_userinfo_fails_at_exact_line_without_projection_leak(
    tmp_path, capsys, with_password
):
    config_canaries = configured_project(tmp_path)
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    username = "user_" + secrets.token_urlsafe(33)
    password = "pass_" + secrets.token_urlsafe(33)
    authority = username + (f":{password}" if with_password else "")
    credential_url = f"https://{authority}@shop.example.test/checkout"
    data = yaml.safe_load((tmp_path / "obconfig.yaml").read_text())
    data["surfaces"]["production_urls"] = [
        "https://safe.example.test",
        credential_url,
    ]
    data["surfaces"]["no_browser_reason"] = ""
    path = tmp_path / "obconfig.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    path.chmod(0o600)
    expected_line = next(
        index
        for index, line in enumerate(path.read_text().splitlines(), 1)
        if credential_url in line
    )

    with pytest.raises(obconfig.ObconfigError) as raised:
        obconfig.load_config(tmp_path)
    issue = raised.value.issue
    assert issue.path == "surfaces.production_urls[1]"
    assert issue.line == expected_line
    assert issue.reason == "must not include userinfo credentials"
    assert username not in str(raised.value)
    assert password not in str(raised.value)

    assert manage_obconfig.main([
        "--project-root",
        str(tmp_path),
        "config-projection",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
    ]) == 1
    terminal = capsys.readouterr()
    assert terminal.out == ""
    combined = terminal.err
    for canary in [*config_canaries, username, password, credential_url]:
        assert canary not in combined


def test_finalize_cli_binds_runtime_outputs_before_dispatch_and_consume(
    tmp_path, capsys
):
    configured_project(tmp_path)
    output = tmp_path / "docs/observability/analysis/app/V1"
    output.mkdir(parents=True)
    (output / "index.md").write_text("generated analysis\n")
    artifact = tmp_path / "artifacts/input.txt"
    artifact.write_text("authorized input")
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    claim = obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    subprocess.run(
        ["git", "add", "docs/observability/analysis/app/V1"],
        cwd=tmp_path,
        check=True,
    )
    dispatched = []
    finalize_argv = [
        "--project-root",
        str(tmp_path),
        "finalize",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
        "--output",
        "docs/observability/analysis/app/V1",
    ]
    assert manage_obconfig.main(finalize_argv) == 0
    payload = json.loads(capsys.readouterr().out)
    assert dispatched == []
    assert payload["finalized"] is True
    assert payload["output_count"] == 1

    # A worktree edit after staging does not alter the exact finalized index tree.
    (output / "index.md").write_text("next-run generated analysis\n")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Obengineer Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-q",
            "-m",
            "analysis V1",
        ],
        cwd=tmp_path,
        check=True,
    )
    dispatch_argv = [
        "--project-root",
        str(tmp_path),
        "dispatch",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
    ]
    assert (
        manage_obconfig.main(
            dispatch_argv, dispatch_callback=dispatched.append
        )
        == 0
    )
    dispatch_payload = json.loads(capsys.readouterr().out)
    assert dispatched == [dispatch_payload]
    assert dispatch_payload["dispatch_verified"] is True
    verify_argv = dispatch_argv.copy()
    verify_argv[2] = "verify-dispatch"
    assert manage_obconfig.main(verify_argv) == 0
    capsys.readouterr()

    # Inputs after finalization belong to the next run and do not alter the
    # finalized/published baseline committed by consume.
    artifact.write_text("next-run input")
    obconfig.consume_claim(
        tmp_path, command="ob-start", intended_version="V1"
    )
    baseline = json.loads(
        (tmp_path / ".obengineer/artifact-manifest.json").read_text()
    )
    history = json.loads(
        (tmp_path / ".obengineer/last-analysis-binding.json").read_text()
    )
    assert baseline["tree_sha256"] == claim["artifact_tree_sha256"]
    assert history["generated_output_sha256"] == payload[
        "generated_output_sha256"
    ]
    assert history["dispatched_commit_sha"] == dispatch_payload["commit_sha"]


def test_finalize_mutation_blocks_dispatch_callback(tmp_path, capsys):
    configured_project(tmp_path)
    output = tmp_path / "generated"
    output.mkdir()
    (output / "result.md").write_text("generated\n")
    artifact = tmp_path / "artifacts/input.txt"
    artifact.write_text("before")
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    subprocess.run(["git", "add", "generated"], cwd=tmp_path, check=True)
    artifact.write_text("mutated before finalize")
    dispatched = []
    argv = [
        "--project-root",
        str(tmp_path),
        "finalize",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
        "--output",
        "generated",
    ]
    assert manage_obconfig.main(argv, dispatch_callback=dispatched.append) == 1
    terminal = capsys.readouterr()
    assert terminal.out == ""
    assert dispatched == []
    assert "no longer matches" in terminal.err


def test_finalize_rejects_output_omitted_from_git_index(tmp_path, capsys):
    configured_project(tmp_path)
    output = tmp_path / "generated"
    output.mkdir()
    (output / "result.md").write_text("not staged\n")
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    argv = [
        "--project-root",
        str(tmp_path),
        "finalize",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
        "--output",
        "generated",
    ]
    assert manage_obconfig.main(argv) == 1
    terminal = capsys.readouterr()
    assert terminal.out == ""
    assert "omitted from the Git tree" in terminal.err


def test_dispatch_and_consume_reject_nonfinalized_commit_tree(
    tmp_path, capsys
):
    configured_project(tmp_path)
    output = tmp_path / "generated"
    output.mkdir()
    result = output / "result.md"
    result.write_text("finalized bytes\n")
    subprocess.run(["git", "add", "generated"], cwd=tmp_path, check=True)
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    obconfig.finalize_claim(
        tmp_path,
        command="ob-start",
        intended_version="V1",
        generated_outputs=["generated"],
    )
    result.write_text("different committed bytes\n")
    subprocess.run(["git", "add", "generated"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Obengineer Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-q",
            "-m",
            "wrong tree",
        ],
        cwd=tmp_path,
        check=True,
    )
    dispatch_argv = [
        "--project-root",
        str(tmp_path),
        "dispatch",
        "--command",
        "ob-start",
        "--intended-version",
        "V1",
    ]
    assert manage_obconfig.main(dispatch_argv) == 1
    assert "exact finalized Git index tree" in capsys.readouterr().err
    assert not (tmp_path / ".obengineer/analysis-dispatch.json").exists()
    with pytest.raises(obconfig.ObconfigError, match="analysis dispatch"):
        obconfig.consume_claim(
            tmp_path, command="ob-start", intended_version="V1"
        )


def test_verify_dispatch_and_consume_reject_head_after_dispatch(tmp_path):
    configured_project(tmp_path)
    output = tmp_path / "generated"
    output.mkdir()
    (output / "result.md").write_text("finalized\n")
    subprocess.run(["git", "add", "generated"], cwd=tmp_path, check=True)
    obconfig.authorize(tmp_path, command="ob-start", intended_version="V1")
    obconfig.claim_authorization(
        tmp_path, command="ob-start", intended_version="V1"
    )
    obconfig.finalize_claim(
        tmp_path,
        command="ob-start",
        intended_version="V1",
        generated_outputs=["generated"],
    )
    commit = [
        "git",
        "-c",
        "user.name=Obengineer Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-q",
    ]
    subprocess.run([*commit, "-m", "analysis V1"], cwd=tmp_path, check=True)
    obconfig.record_dispatch(
        tmp_path, command="ob-start", intended_version="V1"
    )
    (tmp_path / "unrelated.txt").write_text("not dispatched\n")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=tmp_path, check=True)
    subprocess.run([*commit, "-m", "later commit"], cwd=tmp_path, check=True)
    with pytest.raises(obconfig.ObconfigError, match="HEAD no longer matches"):
        obconfig.verify_dispatch(
            tmp_path, command="ob-start", intended_version="V1"
        )
    with pytest.raises(obconfig.ObconfigError, match="HEAD no longer matches"):
        obconfig.consume_claim(
            tmp_path, command="ob-start", intended_version="V1"
        )


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


@pytest.mark.parametrize("change", ("mutate", "replace", "mode"))
def test_verification_discards_evidence_when_config_changes_during_request(
    tmp_path, capsys, change
):
    canaries = configured_project(tmp_path)
    changed = False

    def transport(request):
        nonlocal changed
        if not changed:
            changed = True
            path = tmp_path / "obconfig.yaml"
            if change == "mutate":
                data = yaml.safe_load(path.read_text())
                data["engagement"]["scope"] = "changed during verification"
                path.write_text(yaml.safe_dump(data, sort_keys=False))
                path.chmod(0o600)
            else:
                if change == "replace":
                    replacement = tmp_path / "replacement.yaml"
                    replacement.write_bytes(path.read_bytes())
                    replacement.chmod(0o600)
                    replacement.replace(path)
                else:
                    path.chmod(0o640)
        return direct_api.Response(200, measured_body(request.source))

    argv = [
        "--project-root",
        str(tmp_path),
        "direct-api",
        "--phase",
        "verification",
    ]
    assert manage_obconfig.main(argv, direct_transport=transport) == 1
    terminal = capsys.readouterr()
    rendered = terminal.out + terminal.err + repr(argv)
    assert terminal.out == ""
    assert "changed" in terminal.err or "mode must be 0600" in terminal.err
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
