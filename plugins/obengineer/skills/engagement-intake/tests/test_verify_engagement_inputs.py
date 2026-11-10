from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / (
    "verify_engagement_inputs.py"
)
spec = importlib.util.spec_from_file_location("verify_engagement_inputs", SCRIPT)
verifier = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verifier
spec.loader.exec_module(verifier)


def v2() -> str:
    return """schema_version: 2
engagement:
  application: checkout
artifacts:
  front_end_scan_notes: ""
surfaces:
  production_urls:
    - https://example.invalid
analysis_access:
  token_ref: unknown
  api_key_ref: unknown
  login_id: unknown
  password_ref: unknown
  rotate_on_completion: unknown
business_context:
  commentary: Slow incident triage
entitlement:
  fit_to_entitlement: false
  observability_cloud:
    custom_mts_included: unknown
    custom_mts_in_use: unknown
    mms_slots_remaining: unknown
"""


def test_v2_migrates_to_valid_v3():
    migrated = verifier.migrate_v2(v2())
    assert verifier.verify_text(migrated) == []
    assert "custom_mts_entitled:" in migrated
    assert "custom_mts_system_limit:" in migrated
    assert "mms_cardinality_entitled:" in migrated
    assert "mms_cardinality_in_use:" in migrated
    assert "mms_cardinality_entitled: unknown" in migrated
    assert "mms_slots_remaining was retired" in migrated
    assert "provenance_fact_ids:" in migrated


def test_v2_is_rejected_without_migration():
    failures = verifier.verify_text(v2())
    assert any("schema-v3" in failure for failure in failures)
    assert any("retired schema-v2" in failure for failure in failures)


def test_credential_shape_is_rejected():
    migrated = verifier.migrate_v2(v2())
    migrated += "\nunsafe: ghp_" + ("a" * 30) + "\n"
    assert "credential-shaped value in engagement inputs" in verifier.verify_text(
        migrated
    )


def test_malformed_yaml_and_comment_only_fields_are_rejected():
    malformed = "schema_version: 3\nentitlement: [\n# custom_mts_entitled:\n"
    assert any(
        "not valid YAML" in failure
        for failure in verifier.verify_text(malformed)
    )


def test_required_application_and_production_surface_are_validated():
    migrated = verifier.migrate_v2(v2())
    missing_application = migrated.replace(
        "  application: checkout", '  application: ""'
    )
    assert "engagement.application is required" in verifier.verify_text(
        missing_application
    )
    missing_surface = migrated.replace(
        "  production_urls:\n    - https://example.invalid",
        "  production_urls: []",
    )
    assert any(
        "provide production_urls" in failure
        for failure in verifier.verify_text(missing_surface)
    )


def test_no_browser_reason_satisfies_production_surface_requirement():
    migrated = verifier.migrate_v2(v2())
    no_browser = migrated.replace(
        '  front_end_scan_notes: ""',
        "  front_end_scan_notes: 'no browser: batch-only service'",
    ).replace(
        "  production_urls:\n    - https://example.invalid",
        "  production_urls: []",
    )
    assert verifier.verify_text(no_browser) == []


def test_login_requires_password_reference_and_rotation():
    migrated = verifier.migrate_v2(v2()).replace(
        "  login_id: unknown\n  password_ref: unknown\n"
        "  rotate_on_completion: unknown",
        "  login_id: dummy-user\n  password_ref: plain-text\n"
        "  rotate_on_completion: false",
    )
    failures = verifier.verify_text(migrated)
    assert any("password_ref must be a ${VAR}" in failure for failure in failures)
    assert any("rotate_on_completion must be true" in failure for failure in failures)

    valid = migrated.replace("password_ref: plain-text", "password_ref: ${TEST_PASSWORD}")
    valid = valid.replace("rotate_on_completion: false", "rotate_on_completion: true")
    assert verifier.verify_text(valid) == []


def test_login_and_password_reference_must_be_supplied_together():
    migrated = verifier.migrate_v2(v2()).replace(
        "  login_id: unknown", "  login_id: dummy-user"
    )
    assert any(
        "must be supplied together" in failure
        for failure in verifier.verify_text(migrated)
    )
