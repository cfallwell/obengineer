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
