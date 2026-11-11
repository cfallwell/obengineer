from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / (
    "prefill_engagement_inputs.py"
)
spec = importlib.util.spec_from_file_location("prefill_engagement_inputs", SCRIPT)
prefill = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = prefill
spec.loader.exec_module(prefill)


def test_prefill_maps_allowlisted_values_and_never_copies_token(tmp_path):
    output = tmp_path / "docs/observability/engagement-inputs.yaml"
    raw_token = "not-a-real-token-value"
    changed = prefill.prefill(
        tmp_path,
        output,
        supplied={
            "APPLICATION": "checkout",
            "PRODUCTION_URL": "https://example.invalid",
            "WHAT_HURTS": "Incidents take too long to isolate",
            "ARTIFACTS_DIR": "artifacts",
            "ARTIFACT_DIAGRAMS": "artifacts/context.drawio,artifacts/flow.png",
            "ARTIFACT_NARRATIVE": "artifacts/architecture.md",
            "PRIOR_CONTRACT": "artifacts/prior-guide.pdf",
            "PRIOR_SCHEMA": "artifacts/attribute-schema.json",
            "PRIOR_SCANS": "artifacts/scan-a.json,artifacts/scan-b.json",
            "HOUSE_STYLE_DOCX": "artifacts/house-style.docx",
            "TEST_LOGIN_ID": "dummy-user",
            "PASSWORD_REF": "${DUMMY_TEST_PASSWORD}",
            "SPLUNK_TOKEN": raw_token,
            "PRIVACY_REGIMES": "gdpr,pci",
            "PUBLIC_RESEARCH_ALLOWED": "false",
        },
    )
    data = yaml.safe_load(output.read_text())
    assert data["engagement"]["application"] == "checkout"
    assert data["surfaces"]["production_urls"] == ["https://example.invalid"]
    assert data["business_context"]["commentary"].startswith("Incidents")
    assert data["artifacts"]["location"] == "artifacts"
    assert data["artifacts"]["diagrams"] == [
        "artifacts/context.drawio",
        "artifacts/flow.png",
    ]
    assert data["artifacts"]["narrative"] == "artifacts/architecture.md"
    assert data["artifacts"]["prior_contract"] == "artifacts/prior-guide.pdf"
    assert data["artifacts"]["prior_schema"] == "artifacts/attribute-schema.json"
    assert data["artifacts"]["prior_scans"] == [
        "artifacts/scan-a.json",
        "artifacts/scan-b.json",
    ]
    assert data["artifacts"]["house_style_docx"] == "artifacts/house-style.docx"
    assert data["analysis_access"]["login_id"] == "dummy-user"
    assert data["analysis_access"]["password_ref"] == "${DUMMY_TEST_PASSWORD}"
    assert data["analysis_access"]["token_ref"] == "${SPLUNK_TOKEN}"
    assert data["analysis_access"]["rotate_on_completion"] is True
    assert data["constraints"]["privacy_regimes"] == ["gdpr", "pci"]
    assert data["public_evidence"]["allowed"] is False
    assert raw_token not in output.read_text()
    assert "analysis_access.token_ref" in changed


def test_prefill_rejects_raw_password_and_inconsistent_login(tmp_path):
    output = tmp_path / "inputs.yaml"
    with pytest.raises(prefill.PrefillError, match=r"PASSWORD_REF"):
        prefill.prefill(
            tmp_path,
            output,
            supplied={
                "TEST_LOGIN_ID": "dummy-user",
                "PASSWORD_REF": "raw-password",
            },
        )
    assert not output.exists()

    with pytest.raises(prefill.PrefillError, match="supplied together"):
        prefill.prefill(
            tmp_path,
            output,
            supplied={"TEST_LOGIN_ID": "dummy-user"},
        )


def test_prefill_preserves_existing_human_values(tmp_path):
    output = tmp_path / "inputs.yaml"
    output.write_text(prefill.DEFAULT_TEMPLATE.read_text())
    data = yaml.safe_load(output.read_text())
    data["engagement"]["application"] = "existing-app"
    prefill.atomic_dump_yaml(output, data)

    prefill.prefill(
        tmp_path,
        output,
        supplied={
            "APPLICATION": "replacement",
            "PRODUCTION_URL": "https://example.invalid",
            "WHAT_HURTS": "Slow recovery",
        },
    )
    result = yaml.safe_load(output.read_text())
    assert result["engagement"]["application"] == "existing-app"


def test_prefill_replaces_template_defaults_and_explicit_edit_replaces_existing(tmp_path):
    output = tmp_path / "inputs.yaml"
    output.write_text(prefill.DEFAULT_TEMPLATE.read_text())

    prefill.prefill(
        tmp_path,
        output,
        supplied={
            "SECURITY_ASSESSMENT_MODE": "none",
            "PUBLIC_RESEARCH_ALLOWED": "true",
            "ANALYSIS_PERCENTILE": "p99",
        },
    )
    result = yaml.safe_load(output.read_text())
    assert result["security_assessment"]["mode"] == "none"
    assert result["public_evidence"]["allowed"] is True
    assert result["standards"]["percentile"] == "p99"

    prefill.prefill(
        tmp_path,
        output,
        supplied={"ANALYSIS_PERCENTILE": "p95"},
        overwrite_existing=True,
    )
    result = yaml.safe_load(output.read_text())
    assert result["standards"]["percentile"] == "p95"


def test_start_tracks_explicit_defaults_and_restart_preserves_them(tmp_path):
    output = tmp_path / "inputs.yaml"
    prefill.prefill(
        tmp_path,
        output,
        supplied={
            "SECURITY_ASSESSMENT_MODE": "passive",
            "FIT_TO_ENTITLEMENT": "false",
            "PUBLIC_RESEARCH_ALLOWED": "true",
            "ANALYSIS_PERCENTILE": "p90",
        },
    )
    data = yaml.safe_load(output.read_text())
    assert data["input_provenance"]["supplied_paths"] == [
        "entitlement.fit_to_entitlement",
        "public_evidence.allowed",
        "security_assessment.mode",
        "standards.percentile",
    ]

    # A later start can see different local defaults, but explicit human values win.
    prefill.prefill(
        tmp_path,
        output,
        supplied={
            "SECURITY_ASSESSMENT_MODE": "none",
            "FIT_TO_ENTITLEMENT": "true",
            "PUBLIC_RESEARCH_ALLOWED": "false",
            "ANALYSIS_PERCENTILE": "p99",
        },
    )
    restarted = yaml.safe_load(output.read_text())
    assert restarted["security_assessment"]["mode"] == "passive"
    assert restarted["entitlement"]["fit_to_entitlement"] is False
    assert restarted["public_evidence"]["allowed"] is True
    assert restarted["standards"]["percentile"] == "p90"


def test_edit_clear_restores_template_value_and_removes_provenance(tmp_path):
    output = tmp_path / "inputs.yaml"
    prefill.prefill(
        tmp_path,
        output,
        supplied={
            "SECURITY_ASSESSMENT_MODE": "safe-active",
            "ANALYSIS_PERCENTILE": "p99",
        },
    )
    prefill.prefill(
        tmp_path,
        output,
        supplied={
            "SECURITY_ASSESSMENT_MODE": "clear",
            "ANALYSIS_PERCENTILE": "clear",
        },
        overwrite_existing=True,
    )
    data = yaml.safe_load(output.read_text())
    assert data["security_assessment"]["mode"] == "passive"
    assert data["standards"]["percentile"] == "p90"
    assert data["input_provenance"]["supplied_paths"] == []
    assert "clear" not in output.read_text().lower()

    with pytest.raises(prefill.PrefillError, match="--overwrite-existing"):
        prefill.prefill(
            tmp_path,
            output,
            supplied={"ANALYSIS_PERCENTILE": "clear"},
        )


def test_prefill_rejects_conflicting_production_surface_and_unknown_names(tmp_path):
    with pytest.raises(prefill.PrefillError, match="not both"):
        prefill.prefill(
            tmp_path,
            tmp_path / "inputs.yaml",
            supplied={
                "PRODUCTION_URL": "https://example.invalid",
                "NO_BROWSER_REASON": "batch only",
            },
        )
    with pytest.raises(prefill.PrefillError, match="outside the prefill allowlist"):
        prefill.prefill(
            tmp_path,
            tmp_path / "inputs.yaml",
            supplied={"RAW_PASSWORD": "must-not-be-accepted"},
        )
