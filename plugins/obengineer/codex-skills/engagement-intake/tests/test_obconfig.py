from __future__ import annotations

import importlib.util
import os
import secrets
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parents[1]
SCRIPT = SKILL / "scripts/obconfig.py"
spec = importlib.util.spec_from_file_location("obconfig", SCRIPT)
obconfig = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = obconfig
spec.loader.exec_module(obconfig)
direct_spec = importlib.util.spec_from_file_location(
    "direct_api", SKILL / "scripts/direct_api.py"
)
direct_api = importlib.util.module_from_spec(direct_spec)
sys.modules[direct_spec.name] = direct_api
direct_spec.loader.exec_module(direct_api)
manage_spec = importlib.util.spec_from_file_location(
    "manage_obconfig", SKILL / "scripts/manage_obconfig.py"
)
manage_obconfig = importlib.util.module_from_spec(manage_spec)
sys.modules[manage_spec.name] = manage_obconfig
manage_spec.loader.exec_module(manage_obconfig)
TEMPLATE = ROOT / "obconfig.yaml.template"


def project(tmp_path: Path) -> Path:
    (tmp_path / "artifacts").mkdir(parents=True)
    text = TEMPLATE.read_text()
    text = text.replace('application: ""', 'application: "fixture-app"', 1)
    text = text.replace(
        'no_browser_reason: ""',
        'no_browser_reason: "fixture runs without a browser"',
        1,
    )
    config = tmp_path / "obconfig.yaml"
    config.write_text(text)
    config.chmod(0o600)
    return tmp_path


def load_data(root: Path) -> dict:
    return yaml.safe_load((root / "obconfig.yaml").read_text())


def write_data(root: Path, data: dict) -> None:
    path = root / "obconfig.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    path.chmod(0o600)


def test_template_has_schema_v4_and_complete_secret_registry():
    data, marks = obconfig.parse_yaml(TEMPLATE.read_bytes())
    assert data["schema_version"] == 4
    assert set(obconfig.SECRET_PATHS) == {
        "splunk.observability.read_token",
        "splunk.platform.read_token",
        "analysis_access.dummy_login.password",
    }
    assert "entitlement" not in data
    assert "deployment_environment" in data["engagement"]
    assert marks["engagement.deployment_environment"][0] > 1


def test_duplicate_key_reports_exact_redacted_location(tmp_path):
    root = project(tmp_path)
    path = root / "obconfig.yaml"
    text = path.read_text() + "\nschema_version: 4\n"
    path.write_text(text)
    with pytest.raises(obconfig.ObconfigError) as raised:
        obconfig.load_config(root, enforce_git=False)
    assert raised.value.issue.line == len(text.splitlines())
    assert raised.value.issue.column == 1
    assert raised.value.issue.reason == "duplicate mapping key"
    assert "fixture-app" not in str(raised.value)


@pytest.mark.parametrize(
    ("mutation", "path", "reason"),
    [
        (
            lambda data: data.__setitem__("entitlement", {}),
            "entitlement",
            "remove entitlement input",
        ),
        (
            lambda data: data["engagement"].__setitem__(
                "deployment_environment", ["production"]
            ),
            "engagement.deployment_environment",
            "nonempty scalar",
        ),
        (
            lambda data: data["tenancy"].__setitem__("environments", ["production"]),
            "tenancy.environments",
            "singular",
        ),
        (
            lambda data: data["business_context"].__setitem__(
                "commentary", "retired"
            ),
            "business_context.commentary",
            "what-hurts",
        ),
    ],
)
def test_retired_and_plural_fields_fail_at_field_line(
    tmp_path, mutation, path, reason
):
    root = project(tmp_path)
    data = load_data(root)
    mutation(data)
    write_data(root, data)
    with pytest.raises(obconfig.ObconfigError) as raised:
        obconfig.load_config(root, enforce_git=False)
    assert raised.value.issue.path == path
    assert reason in raised.value.issue.reason
    assert raised.value.issue.line > 1


def test_semantic_type_error_reports_exact_field_path_and_line(tmp_path):
    root = project(tmp_path)
    data = load_data(root)
    data["constraints"]["privacy_regimes"] = "not-a-list"
    write_data(root, data)

    with pytest.raises(obconfig.ObconfigError) as raised:
        obconfig.load_config(root, enforce_git=False)

    assert raised.value.issue.path == "constraints.privacy_regimes"
    assert raised.value.issue.line > 1
    assert raised.value.issue.reason == "must be a list of strings"


def test_plaintext_local_credentials_load_and_never_enter_summary(tmp_path):
    root = project(tmp_path)
    data = load_data(root)
    values = [secrets.token_urlsafe(33) for _ in range(3)]
    data["splunk"]["observability"] = {"realm": "us1", "read_token": values[0]}
    data["splunk"]["platform"] = {
        "host": "https://splunk.example.test:8089",
        "read_token": values[1],
        "index_allowlist": ["application_logs"],
    }
    data["analysis_access"]["dummy_login"] = {
        "login_id": "dummy-user",
        "password": values[2],
    }
    write_data(root, data)
    loaded, _, _, _ = obconfig.load_config(root, enforce_git=False)
    tree = obconfig.hash_artifact_tree(root, "artifacts")
    rendered = obconfig.summary(loaded, tree)
    assert all(value not in rendered for value in values)
    assert "dummy-user" not in rendered
    assert "token configured" in rendered
    assert "Dummy login: configured" in rendered


def test_unknown_extension_high_entropy_value_uses_central_redaction():
    value = secrets.token_urlsafe(33)
    redacted = obconfig.Redactor().value(
        {"extensions": {"opaque_vendor_value": value}}
    )
    assert value not in repr(redacted)
    assert redacted["extensions"]["opaque_vendor_value"] == "[REDACTED]"


def test_git_ignore_and_mode_are_mandatory(tmp_path):
    root = project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    with pytest.raises(obconfig.ObconfigError, match="not ignored"):
        obconfig.load_config(root)
    (root / ".gitignore").write_text("/obconfig.yaml\n/.obengineer/\n")
    obconfig.load_config(root)
    (root / "obconfig.yaml").chmod(0o644)
    with pytest.raises(obconfig.ObconfigError, match="0600"):
        obconfig.load_config(root)


def test_catalogued_repair_requires_mutation_and_writes_0600_backup(tmp_path):
    root = project(tmp_path)
    config = root / "obconfig.yaml"
    config.chmod(0o644)
    changes = obconfig.repair(root)
    assert changes == ["file.mode"]
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    backups = list((root / ".obengineer/backups").glob("obconfig-*.yaml"))
    assert len(backups) == 1
    assert stat.S_IMODE(backups[0].stat().st_mode) == 0o600
    assert backups[0].read_bytes() == config.read_bytes()
    with pytest.raises(obconfig.ObconfigError, match="no safe catalogued repair"):
        obconfig.repair(root)


def test_ambiguous_repair_restores_exact_bytes_and_mode(tmp_path):
    root = project(tmp_path)
    config = root / "obconfig.yaml"
    original = b"schema_version: 4\ninvalid: [\n"
    config.write_bytes(original)
    config.chmod(0o640)

    with pytest.raises(obconfig.ObconfigError, match="no safe catalogued repair"):
        obconfig.repair(root)

    assert config.read_bytes() == original
    assert stat.S_IMODE(config.stat().st_mode) == 0o640
    backup = next((root / ".obengineer/backups").glob("obconfig-*.yaml"))
    assert backup.read_bytes() == original
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600


def test_tree_hash_is_metadata_independent_and_delta_is_exact(tmp_path):
    first = project(tmp_path / "first")
    second = project(tmp_path / "second")
    for root in (first, second):
        (root / "artifacts/a").mkdir()
    (first / "artifacts/z.txt").write_bytes(b"z")
    (first / "artifacts/a/x.txt").write_bytes(b"x")
    (second / "artifacts/a/x.txt").write_bytes(b"x")
    (second / "artifacts/z.txt").write_bytes(b"z")
    os.chmod(second / "artifacts/z.txt", 0o600)
    os.utime(second / "artifacts/a/x.txt", (1, 1))
    left = obconfig.hash_artifact_tree(first, "artifacts")
    right = obconfig.hash_artifact_tree(second, "artifacts")
    assert left["tree_sha256"] == right["tree_sha256"]
    (first / "artifacts/a/x.txt").write_bytes(b"changed")
    (first / "artifacts/z.txt").unlink()
    (first / "artifacts/new.txt").write_bytes(b"new")
    delta = obconfig.hash_artifact_tree(first, "artifacts")
    assert delta["added"] == ["new.txt"]
    assert delta["changed"] == ["a/x.txt"]
    assert delta["deleted"] == ["z.txt"]
    assert delta["reread"] == ["a/x.txt", "new.txt"]


def test_tree_rejects_symlink_and_special_entry(tmp_path):
    root = project(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text("outside")
    (root / "artifacts/link").symlink_to(outside)
    with pytest.raises(obconfig.ObconfigError, match="unsupported artifact entry"):
        obconfig.hash_artifact_tree(root, "artifacts")


def test_tree_rejects_file_substitution_race_without_manifest(tmp_path, monkeypatch):
    root = project(tmp_path)
    candidate = root / "artifacts/race.txt"
    candidate.write_text("safe")
    external = tmp_path / "external"
    external.write_text("must not be read")
    original_open = os.open
    substituted = False

    def racing_open(path, flags, *args, **kwargs):
        nonlocal substituted
        if path == "race.txt" and kwargs.get("dir_fd") is not None and not substituted:
            substituted = True
            candidate.unlink()
            candidate.symlink_to(external)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", racing_open)
    with pytest.raises(obconfig.ObconfigError, match="changed during open"):
        obconfig.hash_artifact_tree(root, "artifacts")
    assert not (root / ".obengineer/artifact-manifest.json").exists()
    assert external.read_text() == "must not be read"


def test_authorization_is_one_shot_and_bound_to_both_digests(tmp_path):
    root = project(tmp_path)
    (root / "artifacts/input.txt").write_text("one")
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    obconfig.validate_authorization(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    (root / "artifacts/input.txt").write_text("two")
    with pytest.raises(obconfig.ObconfigError, match="no longer matches"):
        obconfig.validate_authorization(
            root, command="ob-start", intended_version="V1", enforce_git=False
        )
    assert not (root / ".obengineer/authorization.json").exists()

    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    data = load_data(root)
    data["engagement"]["scope"] = "changed"
    write_data(root, data)
    with pytest.raises(obconfig.ObconfigError, match="no longer matches"):
        obconfig.consume_authorization(
            root, command="ob-start", intended_version="V1", enforce_git=False
        )


def test_authorization_state_symlink_substitution_is_rejected(tmp_path):
    root = project(tmp_path)
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    state = root / ".obengineer/authorization.json"
    state.unlink()
    external = tmp_path / "external-state.json"
    external.write_text("{}")
    state.symlink_to(external)

    with pytest.raises(obconfig.ObconfigError, match="regular file"):
        obconfig.validate_authorization(
            root, command="ob-start", intended_version="V1", enforce_git=False
        )
    assert external.read_text() == "{}"


def test_unknown_extensions_and_comments_survive_mode_repair(tmp_path):
    root = project(tmp_path)
    config = root / "obconfig.yaml"
    marker = "\nextensions:\n  # preserve this comment\n  custom_vendor:\n    opaque: value\n"
    config.write_text(config.read_text() + marker)
    config.chmod(0o644)
    obconfig.repair(root)
    assert marker in config.read_text()


def test_passive_is_zero_request_and_safe_active_is_fixed_exact_origin(tmp_path):
    root = project(tmp_path)
    data = load_data(root)
    assert obconfig.safe_active_requests(data) == []
    data["security_assessment"] = {
        "mode": "safe-active",
        "authorized_origins": ["https://app.example.test"],
    }
    write_data(root, data)
    loaded, _, _, _ = obconfig.load_config(root, enforce_git=False)
    requests = obconfig.safe_active_requests(loaded)
    assert requests
    assert {row["method"] for row in requests} <= obconfig.SAFE_ACTIVE_METHODS
    assert all(row["url"].startswith("https://app.example.test/") for row in requests)
    assert all(row["follow_redirects"] is False for row in requests)
    assert all(
        row["max_requests"] == 100 and row["requests_per_second"] == 1
        for row in requests
    )


@pytest.mark.parametrize(
    "origin",
    [
        "http://app.example.test",
        "https://*.example.test",
        "https://app.example.test/path",
        "https://127.0.0.1",
        "https://user@app.example.test",
        "https://APP.example.test",
        "https://app.example.test/",
    ],
)
def test_safe_active_rejects_malformed_origins_at_item_line(tmp_path, origin):
    root = project(tmp_path)
    data = load_data(root)
    data["security_assessment"] = {
        "mode": "safe-active",
        "authorized_origins": [origin],
    }
    write_data(root, data)
    with pytest.raises(obconfig.ObconfigError) as raised:
        obconfig.load_config(root, enforce_git=False)
    assert raised.value.issue.path == "security_assessment.authorized_origins[0]"
    assert raised.value.issue.line > 1


def test_legacy_yaml_and_env_migrate_with_precedence_and_preservation(tmp_path):
    artifact = tmp_path / "artifacts"
    artifact.mkdir()
    legacy_path = tmp_path / "docs/observability/engagement-inputs.yaml"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "engagement": {"application": "legacy-app"},
                "artifacts": {
                    "location": "artifacts",
                    "front_end_scan_notes": "no browser: service has no browser",
                },
                "tenancy": {
                    "o11y_realm": "us1",
                    "environments": ["production"],
                },
                "analysis_access": {
                    "login_id": "local-dummy",
                    "password_ref": "${RAW_PASSWORD}",
                },
                "vendor_extension": {"opaque_setting": "preserve"},
                "entitlement": {"custom": "retire"},
                "outcomes": {"known_pain": "retire"},
            },
            sort_keys=False,
        )
    )
    o11y_token, platform_token, password = (
        secrets.token_urlsafe(33) for _ in range(3)
    )
    legacy_env = tmp_path / ".env"
    legacy_env.write_text(
        "\n".join(
            (
                "SPLUNK_REALM=us9",
                f"SPLUNK_ACCESS_TOKEN={o11y_token}",
                "SPLUNK_HOST=https://splunk.example.test:8089",
                f"SPLUNK_TOKEN={platform_token}",
                "SPLUNK_ENTERPRISE_INDEXES=app_main,app_audit",
                f"RAW_PASSWORD={password}",
            )
        )
        + "\n"
    )

    changed = manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)

    actual = tmp_path / "obconfig.yaml"
    assert actual.is_file() and stat.S_IMODE(actual.stat().st_mode) == 0o600
    migrated = yaml.safe_load(actual.read_text())
    assert migrated["splunk"]["observability"] == {
        "realm": "us1",
        "read_token": o11y_token,
    }
    assert migrated["splunk"]["platform"]["read_token"] == platform_token
    assert migrated["analysis_access"]["dummy_login"]["password"] == password
    assert migrated["engagement"]["deployment_environment"] == "production"
    assert migrated["extensions"]["legacy"] == {
        "vendor_extension": {"opaque_setting": "preserve"}
    }
    assert "entitlement" not in migrated
    assert "known_pain" not in migrated["outcomes"]
    assert "extensions.legacy" in changed
    assert legacy_path.is_file() and legacy_env.is_file()
    migration_state = tmp_path / ".obengineer/migration.json"
    assert stat.S_IMODE(migration_state.stat().st_mode) == 0o600
    state_text = migration_state.read_text()
    assert o11y_token not in state_text
    assert platform_token not in state_text
    assert password not in state_text


def test_legacy_migration_blocks_unresolved_plural_and_redacted_conflict(tmp_path):
    legacy_path = tmp_path / "docs/observability/engagement-inputs.yaml"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "tenancy": {"environments": ["production", "staging"]},
            }
        )
    )
    with pytest.raises(ValueError, match="multiple values"):
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    assert not (tmp_path / "obconfig.yaml").exists()

    legacy_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "analysis_access": {
                    "login_id": "dummy",
                    "password_ref": "${UNAVAILABLE_PASSWORD}",
                },
            }
        )
    )
    with pytest.raises(ValueError, match="password_ref is unresolved"):
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    assert not (tmp_path / "obconfig.yaml").exists()

    first, second = secrets.token_urlsafe(33), secrets.token_urlsafe(33)
    legacy_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "splunk": {
                    "observability": {"realm": "us1", "read_token": first}
                },
            }
        )
    )
    (tmp_path / ".env").write_text(
        f"SPLUNK_REALM=us1\nSPLUNK_ACCESS_TOKEN={second}\n"
    )
    with pytest.raises(ValueError) as raised:
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    message = str(raised.value)
    assert message == "redacted conflict for splunk.observability.read_token"
    assert first not in message and second not in message
    assert not (tmp_path / "obconfig.yaml").exists()
