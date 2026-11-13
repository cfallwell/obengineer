from __future__ import annotations

import importlib.util
import os
import secrets
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
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


def prepare_config_creation(root: Path) -> None:
    (root / ".gitignore").write_text("/obconfig.yaml\n/.obengineer/\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)


def finalize_for_test(root: Path, command: str, version: str) -> None:
    if not (root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    output = root / "generated"
    output.mkdir(exist_ok=True)
    (output / "result.md").write_text(f"{command} {version}\n")
    subprocess.run(["git", "add", "generated"], cwd=root, check=True)
    obconfig.finalize_claim(
        root,
        command=command,
        intended_version=version,
        generated_outputs=["generated"],
        enforce_git=False,
    )
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
            f"analysis {version}",
        ],
        cwd=root,
        check=True,
    )
    obconfig.record_dispatch(
        root, command=command, intended_version=version
    )


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
    lines = TEMPLATE.read_text().splitlines()

    def leaf_paths(value, prefix=""):
        if isinstance(value, dict) and value:
            for key, item in value.items():
                child = f"{prefix}.{key}" if prefix else key
                yield from leaf_paths(item, child)
        else:
            yield prefix

    for path in leaf_paths(data):
        line = lines[marks[path][0] - 1]
        assert "#" in line, f"{path} lacks an inline field contract comment"
        assert ";" in line.split("#", 1)[1], f"{path} comment lacks contract clauses"
        schema = obconfig._SCHEMA_METADATA
        for part in path.split("."):
            schema = schema["properties"][part]
        assert schema["x-obengineer-source-line"] == marks[path][0]


def test_schema_runtime_rejects_numeric_schema_version_and_invalid_list_items(
    tmp_path
):
    root = project(tmp_path)
    data = load_data(root)
    data["schema_version"] = 4.0
    write_data(root, data)
    with pytest.raises(obconfig.ObconfigError) as raised:
        obconfig.load_config(root, enforce_git=False)
    assert raised.value.issue.path == "schema_version"

    data = load_data(project(tmp_path / "infra"))
    data["traffic_baseline"]["infra_integrations"] = [
        {"name": "host", "entities": 2, "metrics_per_entity": 10}
    ]
    write_data(tmp_path / "infra", data)
    obconfig.load_config(tmp_path / "infra", enforce_git=False)
    data["traffic_baseline"]["infra_integrations"] = [{"name": "host"}]
    write_data(tmp_path / "infra", data)
    with pytest.raises(obconfig.ObconfigError):
        obconfig.load_config(tmp_path / "infra", enforce_git=False)

    peak_root = project(tmp_path / "peak")
    data = load_data(peak_root)
    data["business_context"]["revenue_context"]["peak_events"] = [
        "holiday",
        {"name": "launch"},
    ]
    write_data(peak_root, data)
    obconfig.load_config(peak_root, enforce_git=False)
    data["business_context"]["revenue_context"]["peak_events"] = [42]
    write_data(peak_root, data)
    with pytest.raises(obconfig.ObconfigError):
        obconfig.load_config(peak_root, enforce_git=False)


@pytest.mark.parametrize("invalid", (float("nan"), float("inf"), float("-inf")))
@pytest.mark.parametrize(
    "path",
    (
        ("standards", "unknown_dimension_threshold_pct"),
        ("standards", "percentile"),
        ("traffic_baseline", "rum", "sessions_per_day_avg"),
    ),
)
def test_numeric_contract_rejects_non_finite_values(tmp_path, path, invalid):
    root = project(tmp_path)
    data = load_data(root)
    target = data
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = invalid
    write_data(root, data)
    with pytest.raises(obconfig.ObconfigError, match="finite|nonnegative"):
        obconfig.load_config(root, enforce_git=False)


def test_threshold_and_percentile_accept_finite_numbers(tmp_path):
    root = project(tmp_path)
    data = load_data(root)
    data["standards"]["unknown_dimension_threshold_pct"] = 0.5
    data["standards"]["percentile"] = 95.5
    write_data(root, data)
    obconfig.load_config(root, enforce_git=False)


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
    left = obconfig.hash_artifact_tree(first, "artifacts", write_manifest=True)
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


def test_tree_rejects_recursive_directory_mutation(tmp_path, monkeypatch):
    root = project(tmp_path)
    nested = root / "artifacts/nested"
    nested.mkdir()
    (nested / "one.txt").write_text("one")
    original_listdir = os.listdir
    calls = 0

    def racing_listdir(target):
        nonlocal calls
        result = original_listdir(target)
        if isinstance(target, int):
            calls += 1
        if calls == 2:
            (nested / "late.txt").write_text("late")
            current = nested.stat()
            os.utime(
                nested,
                ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000_000),
            )
        return result

    monkeypatch.setattr(os, "listdir", racing_listdir)
    with pytest.raises(obconfig.ObconfigError, match="directory changed"):
        obconfig.hash_artifact_tree(root, "artifacts")


def test_authorization_is_one_shot_and_bound_to_both_digests(tmp_path):
    root = project(tmp_path)
    (root / "artifacts/input.txt").write_text("one")
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    claim = obconfig.claim_authorization(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    assert claim["artifact_delta"]["added"] == ["input.txt"]
    with pytest.raises(obconfig.ObconfigError):
        obconfig.claim_authorization(
            root, command="ob-start", intended_version="V1", enforce_git=False
        )
    (root / "artifacts/input.txt").write_text("two")
    with pytest.raises(obconfig.ObconfigError, match="no longer matches"):
        obconfig.validate_claim(
            root, command="ob-start", intended_version="V1", enforce_git=False
        )
    with pytest.raises(obconfig.ObconfigError, match="finalized"):
        obconfig.consume_claim(
            root, command="ob-start", intended_version="V1", enforce_git=False
        )


def test_direct_ob_analyze_authorization_is_bound_to_its_own_command(tmp_path):
    root = project(tmp_path)
    prepare_config_creation(root)
    (root / "artifacts/input.txt").write_text("one")
    for argv in (
        ["authorize", "--answer", "yes"],
        ["claim"],
    ):
        assert manage_obconfig.main(
            ["--project-root", str(root), *argv, "--command", "ob-analyze",
             "--intended-version", "V1"]
        ) == 0
    obconfig.abort_claim(root, command="ob-analyze", intended_version="V1")

    obconfig.authorize(
        root, command="ob-analyze", intended_version="V2", enforce_git=False
    )
    with pytest.raises(obconfig.ObconfigError, match="no longer matches"):
        obconfig.claim_authorization(
            root, command="ob-start", intended_version="V2", enforce_git=False
        )
    claim = obconfig.claim_authorization(
        root, command="ob-analyze", intended_version="V2", enforce_git=False
    )
    assert claim["command"] == "ob-analyze"
    finalize_for_test(root, "ob-analyze", "V2")
    obconfig.consume_claim(
        root, command="ob-analyze", intended_version="V2", enforce_git=False
    )
    assert not (root / ".obengineer/analysis-claim.json").exists()


def test_concurrent_claim_has_exactly_one_winner(tmp_path):
    root = project(tmp_path)
    (root / "artifacts/input.txt").write_text("one")
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )

    def attempt():
        try:
            obconfig.claim_authorization(
                root, command="ob-start", intended_version="V1", enforce_git=False
            )
            return "claimed"
        except obconfig.ObconfigError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))

    assert sorted(outcomes) == ["claimed", "rejected"]
    assert not (root / ".obengineer/authorization.json").exists()
    assert (root / ".obengineer/analysis-claim.json").is_file()


def test_baseline_updates_only_after_successful_claim_consume(tmp_path):
    root = project(tmp_path)
    artifact = root / "artifacts/input.txt"
    artifact.write_text("one")

    first = obconfig.hash_artifact_tree(root, "artifacts")
    assert first["added"] == ["input.txt"]
    retry = obconfig.hash_artifact_tree(root, "artifacts")
    assert retry["added"] == ["input.txt"]
    assert not (root / ".obengineer/artifact-manifest.json").exists()

    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    claim = obconfig.claim_authorization(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    assert claim["artifact_delta"]["added"] == ["input.txt"]
    finalize_for_test(root, "ob-start", "V1")
    obconfig.consume_claim(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )

    unchanged = obconfig.hash_artifact_tree(root, "artifacts")
    assert unchanged["added"] == []
    artifact.write_text("two")
    (root / "artifacts/new.txt").write_text("new")
    delta = obconfig.hash_artifact_tree(root, "artifacts")
    assert delta["changed"] == ["input.txt"]
    assert delta["added"] == ["new.txt"]
    artifact.unlink()
    deletion = obconfig.hash_artifact_tree(root, "artifacts")
    assert deletion["deleted"] == ["input.txt"]


def test_claim_abort_preserves_baseline_and_allows_reauthorization(tmp_path):
    root = project(tmp_path)
    (root / "artifacts/input.txt").write_text("one")
    baseline = root / ".obengineer/artifact-manifest.json"
    history = root / ".obengineer/last-analysis-binding.json"
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    obconfig.claim_authorization(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    obconfig.abort_claim(
        root, command="ob-start", intended_version="V1"
    )
    assert not baseline.exists()
    assert not history.exists()
    assert not (root / ".obengineer/analysis-claim.json").exists()
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    obconfig.claim_authorization(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )


def test_mutated_claim_can_abort_without_advancing_baseline(tmp_path):
    root = project(tmp_path)
    artifact = root / "artifacts/input.txt"
    artifact.write_text("one")
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    obconfig.claim_authorization(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    artifact.write_text("mutated")
    obconfig.abort_claim(root, command="ob-start", intended_version="V1")
    assert not (root / ".obengineer/artifact-manifest.json").exists()
    assert not (root / ".obengineer/last-analysis-binding.json").exists()


def test_abort_preserves_claim_replacement_raced_after_validation(
    tmp_path, monkeypatch
):
    root = project(tmp_path)
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    obconfig.claim_authorization(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    claim = root / ".obengineer/analysis-claim.json"
    replacement_raw = claim.read_bytes()
    original_rename = os.rename
    substituted = False

    def racing_rename(source, destination, *args, **kwargs):
        nonlocal substituted
        if source == "analysis-claim.json" and not substituted:
            substituted = True
            source_dir = kwargs["src_dir_fd"]
            original_rename(
                source,
                "validated-original.json",
                src_dir_fd=source_dir,
                dst_dir_fd=source_dir,
            )
            descriptor = os.open(
                source,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=source_dir,
            )
            try:
                os.write(descriptor, replacement_raw)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "rename", racing_rename)
    with pytest.raises(obconfig.ObconfigError, match="changed before removal"):
        obconfig.abort_claim(root, command="ob-start", intended_version="V1")
    assert claim.read_bytes() == replacement_raw
    assert (root / ".obengineer/validated-original.json").is_file()
    assert not (root / ".obengineer/artifact-manifest.json").exists()


def test_state_directory_rename_during_abort_fails_without_deleting_claim(
    tmp_path, monkeypatch
):
    root = project(tmp_path)
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    obconfig.claim_authorization(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    original_rename = os.rename
    moved = root / ".obengineer-moved"
    substituted = False

    def racing_rename(source, destination, *args, **kwargs):
        nonlocal substituted
        if source == "analysis-claim.json" and not substituted:
            substituted = True
            original_rename(root / ".obengineer", moved)
            (root / ".obengineer").mkdir(mode=0o700)
        return original_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "rename", racing_rename)
    with pytest.raises(obconfig.ObconfigError, match="state directory changed"):
        obconfig.abort_claim(root, command="ob-start", intended_version="V1")
    assert (moved / "analysis-claim.json").is_file()
    assert not (root / ".obengineer/analysis-claim.json").exists()


def test_consume_journal_recovers_after_write_and_unlink_interruptions(
    tmp_path, monkeypatch
):
    root = project(tmp_path)
    (root / "artifacts/input.txt").write_text("one")
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    obconfig.claim_authorization(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    finalize_for_test(root, "ob-start", "V1")
    original_write = obconfig.atomic_write_json
    failed = False

    def interrupt_write(path, value, mode=0o600, **kwargs):
        nonlocal failed
        if path.name == "last-analysis-binding.json" and not failed:
            failed = True
            raise OSError("injected consume write interruption")
        return original_write(path, value, mode, **kwargs)

    monkeypatch.setattr(obconfig, "atomic_write_json", interrupt_write)
    with pytest.raises(OSError, match="injected"):
        obconfig.consume_claim(
            root, command="ob-start", intended_version="V1", enforce_git=False
        )
    assert (root / ".obengineer/consume-journal.json").is_file()
    assert stat.S_IMODE(
        (root / ".obengineer/consume-journal.json").stat().st_mode
    ) == 0o600
    monkeypatch.setattr(obconfig, "atomic_write_json", original_write)
    with pytest.raises(obconfig.ObconfigError, match="recovery request"):
        obconfig.consume_claim(
            root,
            command="ob-edit-inputs",
            intended_version="V9",
            enforce_git=False,
        )
    assert (root / ".obengineer/consume-journal.json").exists()
    obconfig.consume_claim(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    assert not (root / ".obengineer/consume-journal.json").exists()
    assert not (root / ".obengineer/analysis-claim.json").exists()
    assert (root / ".obengineer/artifact-manifest.json").is_file()
    assert (root / ".obengineer/last-analysis-binding.json").is_file()

    # A second transaction interrupted at claim removal converges the same way.
    (root / "artifacts/input.txt").write_text("two")
    obconfig.authorize(
        root, command="ob-edit-inputs", intended_version="V2", enforce_git=False
    )
    obconfig.claim_authorization(
        root, command="ob-edit-inputs", intended_version="V2", enforce_git=False
    )
    finalize_for_test(root, "ob-edit-inputs", "V2")
    original_unlink = obconfig._quarantine_remove_state
    failed = False

    def interrupt_unlink(project_root, name, expected):
        nonlocal failed
        if name == "analysis-claim.json" and not failed:
            failed = True
            raise OSError("injected consume unlink interruption")
        return original_unlink(project_root, name, expected)

    monkeypatch.setattr(obconfig, "_quarantine_remove_state", interrupt_unlink)
    with pytest.raises(OSError, match="unlink"):
        obconfig.consume_claim(
            root,
            command="ob-edit-inputs",
            intended_version="V2",
            enforce_git=False,
        )
    monkeypatch.setattr(obconfig, "_quarantine_remove_state", original_unlink)
    obconfig.consume_claim(
        root,
        command="ob-edit-inputs",
        intended_version="V2",
        enforce_git=False,
    )
    assert not (root / ".obengineer/consume-journal.json").exists()


def test_abort_and_consume_are_serialized(tmp_path):
    root = project(tmp_path)
    (root / "artifacts/input.txt").write_text("one")
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    obconfig.claim_authorization(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    finalize_for_test(root, "ob-start", "V1")

    def abort():
        try:
            obconfig.abort_claim(
                root, command="ob-start", intended_version="V1"
            )
            return "abort"
        except obconfig.ObconfigError:
            return "abort-rejected"

    def consume():
        try:
            obconfig.consume_claim(
                root, command="ob-start", intended_version="V1", enforce_git=False
            )
            return "consume"
        except obconfig.ObconfigError:
            return "consume-rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda operation: operation(), (abort, consume)))
    assert sum(value in {"abort", "consume"} for value in outcomes) == 1
    consumed = "consume" in outcomes
    assert (root / ".obengineer/artifact-manifest.json").exists() is consumed
    assert (root / ".obengineer/last-analysis-binding.json").exists() is consumed


def test_stale_gate_lock_file_does_not_block(tmp_path):
    root = project(tmp_path)
    local = root / ".obengineer"
    local.mkdir(mode=0o700)
    lock = local / "analysis-gate.lock"
    lock.write_text("stale")
    lock.chmod(0o600)
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    assert lock.exists()


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


def test_local_claim_state_requires_0600(tmp_path):
    root = project(tmp_path)
    obconfig.authorize(
        root, command="ob-start", intended_version="V1", enforce_git=False
    )
    state = root / ".obengineer/authorization.json"
    assert stat.S_IMODE(state.stat().st_mode) == 0o600
    state.chmod(0o644)
    with pytest.raises(obconfig.ObconfigError, match="0600"):
        obconfig.claim_authorization(
            root, command="ob-start", intended_version="V1", enforce_git=False
        )


def test_schema_contract_rejects_every_removed_template_leaf(tmp_path):
    root = project(tmp_path)
    valid = load_data(root)

    def leaves(value, prefix=()):
        if isinstance(value, dict) and value:
            for key, item in value.items():
                yield from leaves(item, (*prefix, key))
        else:
            yield prefix

    for path in leaves(valid):
        mutated = yaml.safe_load(yaml.safe_dump(valid))
        target = mutated
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]
        write_data(root, mutated)
        with pytest.raises(obconfig.ObconfigError):
            obconfig.load_config(root, enforce_git=False)


def test_schema_contract_rejects_unknown_nested_key_at_mark(tmp_path):
    root = project(tmp_path)
    data = load_data(root)
    data["splunk"]["observability"]["retired_nested"] = "invalid"
    write_data(root, data)
    with pytest.raises(obconfig.ObconfigError) as raised:
        obconfig.load_config(root, enforce_git=False)
    assert raised.value.issue.path == "splunk.observability.retired_nested"
    assert raised.value.issue.line > 1


def test_safe_active_origin_ceiling_fails_at_field_mark(tmp_path):
    root = project(tmp_path)
    data = load_data(root)
    data["security_assessment"] = {
        "mode": "safe-active",
        "authorized_origins": [
            f"https://host-{index}.example.com" for index in range(51)
        ],
    }
    write_data(root, data)
    with pytest.raises(obconfig.ObconfigError) as raised:
        obconfig.load_config(root, enforce_git=False)
    assert raised.value.issue.path == "security_assessment.authorized_origins"
    assert raised.value.issue.line > 1
    assert "ceiling" in raised.value.issue.reason


def test_unknown_extensions_and_comments_survive_mode_repair(tmp_path):
    root = project(tmp_path)
    config = root / "obconfig.yaml"
    marker = "extensions:\n  # preserve this comment\n  custom_vendor:\n    opaque: value\n"
    config.write_text(
        config.read_text().replace(
            "extensions: {}  # mapping; required namespace, default empty; never place credentials here\n",
            marker,
        )
    )
    config.chmod(0o644)
    obconfig.repair(root)
    assert marker in config.read_text()


def test_repair_refuses_substitution_after_backup(tmp_path, monkeypatch):
    root = project(tmp_path)
    config = root / "obconfig.yaml"
    config.chmod(0o644)
    concurrent = b"concurrent content\n"
    original_write = obconfig.atomic_write

    def substitute_after_backup(path, data, mode=0o600, **kwargs):
        result = original_write(path, data, mode, **kwargs)
        if path.parent.name == "backups":
            replacement = root / "replacement"
            replacement.write_bytes(concurrent)
            replacement.chmod(0o600)
            replacement.replace(config)
        return result

    monkeypatch.setattr(obconfig, "atomic_write", substitute_after_backup)
    with pytest.raises(obconfig.ObconfigError, match="changed after repair backup"):
        obconfig.repair(root)
    assert config.read_bytes() == concurrent


def test_repair_commit_refuses_inode_substitution(tmp_path, monkeypatch):
    root = project(tmp_path)
    config = root / "obconfig.yaml"
    config.chmod(0o644)
    concurrent = b"concurrent commit content\n"
    original_exchange = obconfig._rename_exchange
    substituted = False

    def substitute_before_exchange(directory, left, right):
        nonlocal substituted
        if not substituted:
            substituted = True
            replacement = root / "replacement"
            replacement.write_bytes(concurrent)
            replacement.chmod(0o600)
            replacement.replace(config)
        return original_exchange(directory, left, right)

    monkeypatch.setattr(obconfig, "_rename_exchange", substitute_before_exchange)
    with pytest.raises(obconfig.ObconfigError, match="concurrent config"):
        obconfig.repair(root)
    assert config.read_bytes() == concurrent


def test_repair_fails_closed_when_atomic_exchange_is_unsupported(
    tmp_path, monkeypatch
):
    root = project(tmp_path)
    config = root / "obconfig.yaml"
    config.chmod(0o644)
    original = config.read_bytes()

    def unsupported(*args, **kwargs):
        raise obconfig.ObconfigError(
            obconfig.ConfigIssue(
                1, 1, "", "atomic repair exchange is unsupported"
            )
        )

    monkeypatch.setattr(obconfig, "_rename_exchange", unsupported)
    with pytest.raises(obconfig.ObconfigError, match="unsupported"):
        obconfig.repair(root)
    assert config.read_bytes() == original


def test_repair_rollback_never_overwrites_concurrent_replacement(
    tmp_path, monkeypatch
):
    root = project(tmp_path)
    config = root / "obconfig.yaml"
    config.chmod(0o644)
    concurrent = b"concurrent rollback content\n"

    def fail_post_validation(*args, **kwargs):
        replacement = root / "replacement"
        replacement.write_bytes(concurrent)
        replacement.chmod(0o600)
        replacement.replace(config)
        raise obconfig.ObconfigError(
            obconfig.ConfigIssue(1, 1, "", "injected post-commit failure")
        )

    monkeypatch.setattr(obconfig, "load_config", fail_post_validation)
    with pytest.raises(obconfig.ObconfigError, match="rollback refused"):
        obconfig.repair(root)
    assert config.read_bytes() == concurrent


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
    prepare_config_creation(tmp_path)
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
    legacy_env.chmod(0o600)

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
    prepare_config_creation(tmp_path)
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
    (tmp_path / ".env").chmod(0o600)
    with pytest.raises(ValueError) as raised:
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    message = str(raised.value)
    assert message == "redacted conflict for splunk.observability.read_token"
    assert first not in message and second not in message
    assert not (tmp_path / "obconfig.yaml").exists()


def test_legacy_migration_rolls_back_config_and_state_on_commit_failure(
    tmp_path, monkeypatch
):
    prepare_config_creation(tmp_path)
    legacy = tmp_path / "docs/observability/engagement-inputs.yaml"
    legacy.parent.mkdir(parents=True)
    canary = secrets.token_urlsafe(33)
    legacy.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "engagement": {"application": "rollback-fixture"},
                "artifacts": {
                    "location": "artifacts",
                    "front_end_scan_notes": "no browser: migration fixture",
                },
                "splunk": {
                    "observability": {"realm": "us1", "read_token": canary}
                },
            }
        )
    )
    (tmp_path / "artifacts").mkdir()

    def fail_state(*args, **kwargs):
        raise OSError("injected state commit failure")

    monkeypatch.setattr(manage_obconfig, "atomic_write_json", fail_state)
    with pytest.raises(OSError, match="injected"):
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    assert not (tmp_path / "obconfig.yaml").exists()
    assert not (tmp_path / ".obengineer/migration.json").exists()
    assert canary not in repr(list((tmp_path / ".obengineer").glob("*")))


def test_migration_rollback_final_exchange_preserves_replacement(
    tmp_path, monkeypatch
):
    prepare_config_creation(tmp_path)
    (tmp_path / "artifacts").mkdir()
    legacy = tmp_path / "docs/observability/engagement-inputs.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "engagement": {"application": "rollback-exchange-fixture"},
                "artifacts": {
                    "location": "artifacts",
                    "front_end_scan_notes": "no browser: rollback exchange",
                },
            }
        )
    )

    def fail_state(*args, **kwargs):
        raise OSError("injected state commit failure")

    original_exchange = obconfig._rename_exchange
    replacement = b"concurrent rollback replacement\n"
    substituted = False

    def substitute_at_unlink(directory, left, right):
        nonlocal substituted
        if right == "obconfig.yaml" and not substituted:
            substituted = True
            os.unlink(right, dir_fd=directory)
            descriptor = os.open(
                right,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=directory,
            )
            os.write(descriptor, replacement)
            os.close(descriptor)
        return original_exchange(directory, left, right)

    monkeypatch.setattr(manage_obconfig, "atomic_write_json", fail_state)
    monkeypatch.setattr(
        obconfig, "_rename_exchange", substitute_at_unlink
    )
    with pytest.raises(
        obconfig.ObconfigError, match="replacement was preserved"
    ):
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    assert (tmp_path / "obconfig.yaml").read_bytes() == replacement


def test_migration_json_final_exchange_preserves_replacement(
    tmp_path, monkeypatch
):
    prepare_config_creation(tmp_path)
    (tmp_path / "artifacts").mkdir()
    legacy = tmp_path / "docs/observability/engagement-inputs.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "engagement": {"application": "state-exchange-fixture"},
                "artifacts": {
                    "location": "artifacts",
                    "front_end_scan_notes": "no browser: state exchange",
                },
            }
        )
    )
    state = tmp_path / ".obengineer"
    state.mkdir(mode=0o700)
    migration = state / "migration.json"
    migration.write_bytes(b'{"previous":true}\n')
    migration.chmod(0o600)
    replacement = b"concurrent migration state replacement\n"
    original_exchange = obconfig._rename_exchange
    substituted = False

    def substitute_state_at_exchange(directory, left, right):
        nonlocal substituted
        if right == "migration.json" and not substituted:
            substituted = True
            os.unlink(right, dir_fd=directory)
            descriptor = os.open(
                right,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=directory,
            )
            os.write(descriptor, replacement)
            os.close(descriptor)
        return original_exchange(directory, left, right)

    monkeypatch.setattr(
        obconfig, "_rename_exchange", substitute_state_at_exchange
    )
    with pytest.raises(
        obconfig.ObconfigError,
        match="replacement was preserved|atomic exchange",
    ):
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    assert migration.read_bytes() == replacement
    assert not (tmp_path / "obconfig.yaml").exists()


def test_init_and_migration_reject_local_state_symlink_before_secrets(tmp_path):
    prepare_config_creation(tmp_path)
    external = tmp_path / "external-state"
    external.mkdir()
    (tmp_path / ".obengineer").symlink_to(external, target_is_directory=True)
    with pytest.raises(obconfig.ObconfigError, match="must not be a symlink"):
        obconfig.initialize(tmp_path, TEMPLATE)
    assert not (tmp_path / "obconfig.yaml").exists()

    canary = secrets.token_urlsafe(33)
    legacy = tmp_path / ".env"
    legacy.write_text(f"SPLUNK_ACCESS_TOKEN={canary}\n")
    legacy.chmod(0o600)
    with pytest.raises(obconfig.ObconfigError, match="must not be a symlink"):
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    assert not (tmp_path / "obconfig.yaml").exists()
    assert list(external.iterdir()) == []


def test_init_preserves_config_symlink_substitution_without_writing_secret(
    tmp_path, monkeypatch
):
    prepare_config_creation(tmp_path)
    external = tmp_path / "external-config"
    external.write_text("unchanged")
    original = obconfig.atomic_write

    def substitute(path, data, mode=0o600, **kwargs):
        (tmp_path / "obconfig.yaml").symlink_to(external)
        return original(path, data, mode, **kwargs)

    monkeypatch.setattr(obconfig, "atomic_write", substitute)
    with pytest.raises(obconfig.ObconfigError, match="symlink"):
        obconfig.initialize(tmp_path, TEMPLATE)
    assert external.read_text() == "unchanged"
    assert (tmp_path / "obconfig.yaml").is_symlink()
    assert (tmp_path / "obconfig.yaml").resolve() == external


def test_migration_preserves_unowned_config_symlink_substitution(
    tmp_path, monkeypatch
):
    prepare_config_creation(tmp_path)
    (tmp_path / "artifacts").mkdir()
    legacy = tmp_path / "docs/observability/engagement-inputs.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "engagement": {"application": "swap-fixture"},
                "artifacts": {
                    "location": "artifacts",
                    "front_end_scan_notes": "no browser: swap fixture",
                },
            }
        )
    )
    external = tmp_path / "external-config"
    external.write_text("unchanged")
    original = manage_obconfig.atomic_write

    def substitute(path, data, mode=0o600, **kwargs):
        if path.name == "obconfig.yaml":
            path.symlink_to(external)
        return original(path, data, mode, **kwargs)

    monkeypatch.setattr(manage_obconfig, "atomic_write", substitute)
    with pytest.raises(obconfig.ObconfigError, match="symlink"):
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    assert external.read_text() == "unchanged"
    assert (tmp_path / "obconfig.yaml").is_symlink()
    assert (tmp_path / "obconfig.yaml").resolve() == external
    assert not (tmp_path / ".obengineer/migration.json").exists()


@pytest.mark.parametrize("operation", ("init", "migration"))
@pytest.mark.parametrize("replacement_type", ("file", "symlink", "directory"))
def test_atomic_creation_preserves_replacement_after_link(
    tmp_path, monkeypatch, operation, replacement_type
):
    prepare_config_creation(tmp_path)
    if operation == "migration":
        (tmp_path / "artifacts").mkdir()
        legacy = tmp_path / "docs/observability/engagement-inputs.yaml"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 3,
                    "engagement": {"application": "atomic-race-fixture"},
                    "artifacts": {
                        "location": "artifacts",
                        "front_end_scan_notes": "no browser: atomic race",
                    },
                }
            )
        )
    original_link = os.link
    replacement = b"concurrent replacement bytes\n"
    substituted = False

    def replace_after_link(source, destination, *args, **kwargs):
        nonlocal substituted
        result = original_link(source, destination, *args, **kwargs)
        if destination == "obconfig.yaml" and not substituted:
            substituted = True
            directory = kwargs["dst_dir_fd"]
            os.unlink(destination, dir_fd=directory)
            if replacement_type == "file":
                descriptor = os.open(
                    destination,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=directory,
                )
                os.write(descriptor, replacement)
                os.close(descriptor)
            elif replacement_type == "symlink":
                external = tmp_path / "concurrent-target"
                external.write_bytes(replacement)
                os.symlink(
                    external.name,
                    destination,
                    dir_fd=directory,
                )
            else:
                os.mkdir(destination, 0o700, dir_fd=directory)
                (tmp_path / "obconfig.yaml/marker").write_bytes(replacement)
        return result

    monkeypatch.setattr(os, "link", replace_after_link)
    with pytest.raises(obconfig.ObconfigError, match="changed after atomic creation"):
        if operation == "init":
            obconfig.initialize(tmp_path, TEMPLATE)
        else:
            manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    config = tmp_path / "obconfig.yaml"
    if replacement_type == "file":
        assert config.read_bytes() == replacement
    elif replacement_type == "symlink":
        assert config.is_symlink()
        assert config.resolve().read_bytes() == replacement
    else:
        assert config.is_dir()
        assert (config / "marker").read_bytes() == replacement
    assert not (tmp_path / ".obengineer/migration.json").exists()


@pytest.mark.parametrize("operation", ("update", "unlink"))
@pytest.mark.parametrize("replacement_type", ("file", "symlink", "directory"))
def test_identity_bound_final_exchange_preserves_replacement(
    tmp_path, monkeypatch, operation, replacement_type
):
    root = project(tmp_path)
    state = root / ".obengineer"
    state.mkdir(mode=0o700)
    target = state / "migration.json"
    target.write_bytes(b'{"before":true}\n')
    target.chmod(0o600)
    _, version = obconfig._capture_regular_version(
        target, "migration state", required_mode=0o600
    )
    replacement = b"concurrent final-syscall replacement\n"
    original_exchange = obconfig._rename_exchange
    substituted = False

    def substitute_at_exchange(directory, left, right):
        nonlocal substituted
        if right == "migration.json" and not substituted:
            substituted = True
            os.unlink(right, dir_fd=directory)
            if replacement_type == "file":
                descriptor = os.open(
                    right,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=directory,
                )
                os.write(descriptor, replacement)
                os.close(descriptor)
            elif replacement_type == "symlink":
                external = root / "concurrent-state-target"
                external.write_bytes(replacement)
                os.symlink(
                    os.path.relpath(external, state),
                    right,
                    dir_fd=directory,
                )
            else:
                os.mkdir(right, 0o700, dir_fd=directory)
                (target / "marker").write_bytes(replacement)
        return original_exchange(directory, left, right)

    monkeypatch.setattr(obconfig, "_rename_exchange", substitute_at_exchange)
    with pytest.raises(obconfig.ObconfigError, match="atomic exchange|atomic removal"):
        if operation == "update":
            obconfig.atomic_write(
                target,
                b'{"after":true}\n',
                expected_identity=(version.device, version.inode),
                expected_digest=version.digest,
                expected_mode=version.mode,
            )
        else:
            obconfig.secure_unlink(
                target,
                expected_identity=(version.device, version.inode),
                expected_digest=version.digest,
                expected_mode=version.mode,
            )
    if replacement_type == "file":
        assert target.read_bytes() == replacement
    elif replacement_type == "symlink":
        assert target.is_symlink()
        assert target.resolve().read_bytes() == replacement
    else:
        assert target.is_dir()
        assert (target / "marker").read_bytes() == replacement


@pytest.mark.parametrize("operation", ("update", "unlink"))
def test_identity_bound_mutation_fails_closed_without_exchange_support(
    tmp_path, monkeypatch, operation
):
    root = project(tmp_path)
    state = root / ".obengineer"
    state.mkdir(mode=0o700)
    target = state / "migration.json"
    original = b'{"preserve":true}\n'
    target.write_bytes(original)
    target.chmod(0o600)
    _, version = obconfig._capture_regular_version(
        target, "migration state", required_mode=0o600
    )

    def unsupported(*args, **kwargs):
        raise obconfig.ObconfigError(
            obconfig.ConfigIssue(
                1, 1, "", "atomic rename exchange is unsupported"
            )
        )

    monkeypatch.setattr(obconfig, "_rename_exchange", unsupported)
    with pytest.raises(obconfig.ObconfigError, match="unsupported"):
        if operation == "update":
            obconfig.atomic_write(
                target,
                b'{"changed":true}\n',
                expected_identity=(version.device, version.inode),
                expected_digest=version.digest,
                expected_mode=version.mode,
            )
        else:
            obconfig.secure_unlink(
                target,
                expected_identity=(version.device, version.inode),
                expected_digest=version.digest,
                expected_mode=version.mode,
            )
    assert target.read_bytes() == original


@pytest.mark.parametrize("replacement_type", ("file", "symlink", "directory"))
def test_secure_unlink_final_noreplace_preserves_raced_path(
    tmp_path, monkeypatch, replacement_type
):
    root = project(tmp_path)
    state = root / ".obengineer"
    state.mkdir(mode=0o700)
    target = state / "migration.json"
    target.write_bytes(b'{"owned":true}\n')
    target.chmod(0o600)
    _, version = obconfig._capture_regular_version(
        target, "migration state", required_mode=0o600
    )
    replacement = b"replacement at final no-replace\n"
    original_noreplace = obconfig._rename_noreplace
    substituted = False

    def substitute_at_final_rename(directory, left, right):
        nonlocal substituted
        if left == "migration.json" and not substituted:
            substituted = True
            os.unlink(left, dir_fd=directory)
            if replacement_type == "file":
                descriptor = os.open(
                    left,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=directory,
                )
                os.write(descriptor, replacement)
                os.close(descriptor)
            elif replacement_type == "symlink":
                external = root / "final-unlink-target"
                external.write_bytes(replacement)
                os.symlink(
                    os.path.relpath(external, state),
                    left,
                    dir_fd=directory,
                )
            else:
                os.mkdir(left, 0o700, dir_fd=directory)
                (target / "marker").write_bytes(replacement)
        return original_noreplace(directory, left, right)

    monkeypatch.setattr(
        obconfig, "_rename_noreplace", substitute_at_final_rename
    )
    with pytest.raises(obconfig.ObconfigError, match="final removal"):
        obconfig.secure_unlink(
            target,
            expected_identity=(version.device, version.inode),
            expected_digest=version.digest,
            expected_mode=version.mode,
        )
    if replacement_type == "file":
        assert target.read_bytes() == replacement
    elif replacement_type == "symlink":
        assert target.is_symlink()
        assert target.resolve().read_bytes() == replacement
    else:
        assert target.is_dir()
        assert (target / "marker").read_bytes() == replacement


def test_atomic_update_rollback_exchange_preserves_final_race(
    tmp_path, monkeypatch
):
    root = project(tmp_path)
    state = root / ".obengineer"
    state.mkdir(mode=0o700)
    target = state / "migration.json"
    target.write_bytes(b'{"before":true}\n')
    target.chmod(0o600)
    _, version = obconfig._capture_regular_version(
        target, "migration state", required_mode=0o600
    )
    replacement = b"rollback final exchange replacement\n"
    original_lstat = Path.lstat
    parent_stats = 0

    def fail_post_exchange_parent_check(self):
        nonlocal parent_stats
        if self == state:
            parent_stats += 1
            if parent_stats == 2:
                raise OSError("injected post-exchange validation failure")
        return original_lstat(self)

    original_exchange = obconfig._rename_exchange
    exchanges = 0

    def substitute_at_rollback(directory, left, right):
        nonlocal exchanges
        exchanges += 1
        if exchanges == 2:
            os.unlink(right, dir_fd=directory)
            descriptor = os.open(
                right,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=directory,
            )
            os.write(descriptor, replacement)
            os.close(descriptor)
        return original_exchange(directory, left, right)

    monkeypatch.setattr(Path, "lstat", fail_post_exchange_parent_check)
    monkeypatch.setattr(
        obconfig, "_rename_exchange", substitute_at_rollback
    )
    with pytest.raises(OSError, match="post-exchange"):
        obconfig.atomic_write(
            target,
            b'{"after":true}\n',
            expected_identity=(version.device, version.inode),
            expected_digest=version.digest,
            expected_mode=version.mode,
        )
    assert target.read_bytes() == replacement


@pytest.mark.parametrize("race", ("ignore", "index"))
def test_init_rolls_back_when_git_safety_changes_after_commit(
    tmp_path, monkeypatch, race
):
    prepare_config_creation(tmp_path)
    original = obconfig.preflight_config_creation
    calls = 0

    def racing_preflight(root):
        nonlocal calls
        calls += 1
        if calls == 2:
            if race == "ignore":
                (root / ".gitignore").write_text("/.obengineer/\n")
            else:
                subprocess.run(
                    ["git", "add", "-f", "obconfig.yaml"],
                    cwd=root,
                    check=True,
                )
        return original(root)

    monkeypatch.setattr(obconfig, "preflight_config_creation", racing_preflight)
    with pytest.raises(obconfig.ObconfigError):
        obconfig.initialize(tmp_path, TEMPLATE)
    assert not (tmp_path / "obconfig.yaml").exists()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "obconfig.yaml"],
        cwd=tmp_path,
        capture_output=True,
    )
    assert tracked.returncode != 0


@pytest.mark.parametrize("boundary", (2, 3))
@pytest.mark.parametrize("race", ("ignore", "index"))
def test_migration_rechecks_git_at_each_commit_boundary(
    tmp_path, monkeypatch, boundary, race
):
    prepare_config_creation(tmp_path)
    (tmp_path / "artifacts").mkdir()
    canary = secrets.token_urlsafe(33)
    legacy = tmp_path / "docs/observability/engagement-inputs.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "engagement": {"application": "git-race-fixture"},
                "artifacts": {
                    "location": "artifacts",
                    "front_end_scan_notes": "no browser: git race fixture",
                },
                "splunk": {
                    "observability": {"realm": "us1", "read_token": canary}
                },
            }
        )
    )
    original = manage_obconfig.preflight_config_creation
    calls = 0

    def racing_preflight(root):
        nonlocal calls
        calls += 1
        if calls == boundary:
            if race == "ignore":
                (root / ".gitignore").write_text("/.obengineer/\n")
            else:
                subprocess.run(
                    ["git", "add", "-f", "obconfig.yaml"],
                    cwd=root,
                    check=True,
                )
        return original(root)

    monkeypatch.setattr(
        manage_obconfig, "preflight_config_creation", racing_preflight
    )
    with pytest.raises(obconfig.ObconfigError):
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    assert not (tmp_path / "obconfig.yaml").exists()
    assert not (tmp_path / ".obengineer/migration.json").exists()
    assert subprocess.run(
        ["git", "ls-files", "--error-unmatch", "obconfig.yaml"],
        cwd=tmp_path,
        capture_output=True,
    ).returncode != 0
    for path in (tmp_path / ".obengineer").glob("*"):
        if path.is_file():
            assert canary not in path.read_text(errors="ignore")


@pytest.mark.parametrize(
    "boundary", ("after-config", "after-state", "during-final-read")
)
def test_migration_revalidates_secret_source_through_final_commit(
    tmp_path, monkeypatch, boundary
):
    prepare_config_creation(tmp_path)
    (tmp_path / "artifacts").mkdir()
    legacy = tmp_path / "docs/observability/engagement-inputs.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "engagement": {"application": "source-race-fixture"},
                "artifacts": {
                    "location": "artifacts",
                    "front_end_scan_notes": "no browser: source race",
                },
            }
        )
    )
    original_secret = secrets.token_urlsafe(33)
    replacement_secret = secrets.token_urlsafe(33)
    env = tmp_path / ".env"
    env.write_text(
        f"SPLUNK_REALM=us1\nSPLUNK_ACCESS_TOKEN={original_secret}\n"
    )
    env.chmod(0o600)

    def replace_source():
        replacement = tmp_path / ".env.replacement"
        replacement.write_text(
            f"SPLUNK_REALM=us1\nSPLUNK_ACCESS_TOKEN={replacement_secret}\n"
        )
        replacement.chmod(0o600)
        replacement.replace(env)

    if boundary == "after-config":
        original_write = manage_obconfig.atomic_write

        def write_then_replace(path, data, mode=0o600, **kwargs):
            result = original_write(path, data, mode, **kwargs)
            if path.name == "obconfig.yaml":
                replace_source()
            return result

        monkeypatch.setattr(manage_obconfig, "atomic_write", write_then_replace)
    elif boundary == "after-state":
        original_json = manage_obconfig.atomic_write_json

        def state_then_replace(path, value, mode=0o600, **kwargs):
            result = original_json(path, value, mode, **kwargs)
            if path.name == "migration.json":
                replace_source()
            return result

        monkeypatch.setattr(
            manage_obconfig, "atomic_write_json", state_then_replace
        )
    else:
        original_read = manage_obconfig.read_project_file_version
        env_reads = 0

        def replace_during_final(root, relative, label, **kwargs):
            nonlocal env_reads
            if Path(relative) == Path(".env"):
                env_reads += 1
                if env_reads == 2:
                    replace_source()
            return original_read(root, relative, label, **kwargs)

        monkeypatch.setattr(
            manage_obconfig,
            "read_project_file_version",
            replace_during_final,
        )

    with pytest.raises(obconfig.ObconfigError, match="changed before migration commit"):
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    assert not (tmp_path / "obconfig.yaml").exists()
    assert not (tmp_path / ".obengineer/migration.json").exists()
    assert replacement_secret in env.read_text()


@pytest.mark.parametrize("destination", ("config", "state"))
def test_migration_preserves_hostile_destination_replacement(
    tmp_path, monkeypatch, destination
):
    prepare_config_creation(tmp_path)
    (tmp_path / "artifacts").mkdir()
    legacy = tmp_path / "docs/observability/engagement-inputs.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        yaml.safe_dump(
            {
                "schema_version": 3,
                "engagement": {"application": "destination-race-fixture"},
                "artifacts": {
                    "location": "artifacts",
                    "front_end_scan_notes": "no browser: destination race",
                },
            }
        )
    )
    hostile = b"hostile same-user replacement\n"
    original_preflight = manage_obconfig.preflight_config_creation
    calls = 0

    def replace_at_boundary(root):
        nonlocal calls
        calls += 1
        result = original_preflight(root)
        target_call = 2 if destination == "config" else 3
        if calls == target_call:
            target = (
                root / "obconfig.yaml"
                if destination == "config"
                else root / ".obengineer/migration.json"
            )
            replacement = root / f".{destination}.replacement"
            replacement.write_bytes(hostile)
            replacement.chmod(0o600)
            replacement.replace(target)
        return result

    monkeypatch.setattr(
        manage_obconfig, "preflight_config_creation", replace_at_boundary
    )
    with pytest.raises(
        obconfig.ObconfigError,
        match="replacement was preserved|destination changed",
    ):
        manage_obconfig.migrate_legacy(tmp_path, TEMPLATE)
    target = (
        tmp_path / "obconfig.yaml"
        if destination == "config"
        else tmp_path / ".obengineer/migration.json"
    )
    assert target.read_bytes() == hostile
    if destination == "state":
        assert not (tmp_path / "obconfig.yaml").exists()
