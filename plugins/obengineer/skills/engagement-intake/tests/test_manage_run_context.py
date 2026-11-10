from __future__ import annotations

import importlib.util
import socket
import subprocess
import sys
import time
from pathlib import Path

import yaml

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "manage_run_context.py"
spec = importlib.util.spec_from_file_location("manage_run_context", SCRIPT)
context = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = context
spec.loader.exec_module(context)

TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "inputs"
    / "engagement-inputs.template.yaml"
)


def write_required_inputs(root: Path) -> Path:
    path = root / context.INPUTS_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    data = yaml.safe_load(TEMPLATE.read_text())
    data["engagement"]["application"] = "checkout"
    data["surfaces"]["production_urls"] = ["https://example.invalid"]
    data["business_context"]["commentary"] = "Incidents take too long to isolate"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def test_first_question_is_local_and_available_within_five_seconds(
    tmp_path, monkeypatch
):
    network_attempts = []

    def fail_connect(*args, **kwargs):
        network_attempts.append((args, kwargs))
        raise AssertionError("network attempted before first question")

    monkeypatch.setattr(socket.socket, "connect", fail_connect)
    started = time.monotonic()
    state = context.start(context.new_context())
    context.atomic_write_context(tmp_path / context.CONTEXT_RELATIVE_PATH, state)
    elapsed = time.monotonic() - started

    assert elapsed < 5
    assert network_attempts == []
    assert "What is the application name?" in context.FIRST_QUESTION
    assert "explicit production URL" in context.FIRST_QUESTION
    assert "what hurts today" in context.FIRST_QUESTION
    assert state["state"] == "required"

    started = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "start",
            "--project-root",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert time.monotonic() - started < 5
    assert result.stdout.startswith(
        "Before I inspect source, the network, or connected tools"
    )


def test_state_machine_requires_explicit_no_after_checked_optional_loop(tmp_path):
    inputs = write_required_inputs(tmp_path)
    state = context.start(context.new_context())
    state = context.complete_required(state, inputs)
    assert state["state"] == "optional-review"
    assert all(value == "complete" for value in state["required"].values())

    state = context.review(state, "yes 1 3", [1, 2, 3])
    assert state["state"] == "optional-answers"
    assert state["analysis_authorized"] is False
    assert state["optional"]["pending"] == [1, 3]

    state = context.record_answer(state, 1, "answered")
    assert state["state"] == "optional-answers"
    state = context.record_answer(state, 3, "skipped")
    assert state["state"] == "optional-review"
    checklist = context.render_checklist(state)
    assert "[x] 1." in checklist
    assert "[-] 3." in checklist
    assert "[ ] 2." in checklist
    assert state["analysis_authorized"] is False

    state = context.review(state, "no", [2, 4, 5])
    assert state["state"] == "optional-review"
    assert state["analysis_authorized"] is True
    assert state["last_event"] == "review-no"
    assert "pending" not in state["optional"]["items"].values()


def test_start_does_not_reask_inputs_prefilled_from_project_context(tmp_path):
    inputs = write_required_inputs(tmp_path)
    data = yaml.safe_load(inputs.read_text())
    data["analysis_access"]["login_id"] = "qa-user"
    data["analysis_access"]["password_ref"] = "${OBENGINEER_TEST_PASSWORD}"
    data["analysis_access"]["rotate_on_completion"] = True
    data["standards"]["percentile"] = "p95"
    inputs.write_text(yaml.safe_dump(data, sort_keys=False))
    state = context.start(context.new_context(), inputs)
    assert state["state"] == "optional-review"
    assert all(value == "complete" for value in state["required"].values())
    assert state["optional"]["items"]["3"] == "complete"
    assert state["optional"]["items"]["9"] == "complete"
    prompt = context.render_required_prompt(state)
    assert "already complete" in prompt
    assert "What is the application name?" not in prompt


def test_non_explicit_no_and_out_of_order_answers_are_rejected(tmp_path):
    inputs = write_required_inputs(tmp_path)
    state = context.complete_required(context.start(context.new_context()), inputs)
    try:
        context.review(state, "no thanks", [1, 2])
    except context.StateError as exc:
        assert "exactly" in str(exc)
    else:
        raise AssertionError("non-explicit no must be rejected")
    assert state["analysis_authorized"] is False
    assert state["optional"]["offered"] == []

    state = context.review(state, "yes 1 3", [1, 3])
    try:
        context.record_answer(state, 3, "answered")
    except context.StateError as exc:
        assert "item 1 next" in str(exc)
    else:
        raise AssertionError("optional answers must be processed in order")


def test_explicit_no_can_authorize_when_no_optional_items_are_offered(tmp_path):
    inputs = write_required_inputs(tmp_path)
    state = context.complete_required(context.start(context.new_context()), inputs)
    state = context.review(state, "no", [])
    assert state["analysis_authorized"] is True
    assert state["last_event"] == "review-no"


def test_reopen_clears_authorization_and_preserves_completed_inputs(tmp_path):
    inputs = write_required_inputs(tmp_path)
    state = context.start(context.new_context(), inputs)
    state = context.review(state, "yes 1", [1, 2])
    state = context.record_answer(state, 1, "answered")
    state = context.review(state, "no", [2])
    assert state["analysis_authorized"] is True
    assert state["optional"]["items"]["1"] == "complete"
    assert state["optional"]["items"]["2"] == "skipped"

    state = context.reopen(state, inputs)
    assert state["analysis_authorized"] is False
    assert state["last_event"] == "reopen"
    assert state["state"] == "optional-review"
    assert state["optional"]["items"]["1"] == "complete"
    assert state["optional"]["items"]["2"] == "pending"


def test_explicit_template_defaults_render_checked_after_restart(tmp_path):
    inputs = write_required_inputs(tmp_path)
    data = yaml.safe_load(inputs.read_text())
    data["input_provenance"] = {
        "supplied_paths": [
            "security_assessment.mode",
            "entitlement.fit_to_entitlement",
            "public_evidence.allowed",
            "standards.percentile",
        ]
    }
    inputs.write_text(yaml.safe_dump(data, sort_keys=False))

    first = context.start(context.new_context(), inputs)
    assert first["optional"]["items"]["2"] == "complete"
    assert first["optional"]["items"]["5"] == "complete"
    assert first["optional"]["items"]["8"] == "complete"
    assert first["optional"]["items"]["9"] == "complete"

    restarted = context.start(context.new_context(), inputs)
    checklist = context.render_checklist(restarted)
    for number in (2, 5, 8, 9):
        assert f"[x] {number}." in checklist


def test_filtered_add_uses_canonical_numbers_and_reopen_preserves_mapping(tmp_path):
    inputs = write_required_inputs(tmp_path)
    state = context.start(context.new_context(), inputs)

    # A filtered display keeps labels 2 and 9; display position 1 is never
    # reinterpreted as canonical item 2.
    state = context.review(state, "yes 9", [2, 9])
    assert state["optional"]["selected"] == [9]
    state = context.record_answer(state, 9, "answered")
    state = context.review(state, "no", [2])
    reopened = context.reopen(state, inputs)
    assert reopened["optional"]["items"]["9"] == "complete"
    assert reopened["optional"]["items"]["2"] == "pending"
    assert reopened["optional"]["offered"] == []


def test_context_write_is_atomic_and_schema_valid(tmp_path):
    path = tmp_path / context.CONTEXT_RELATIVE_PATH
    state = context.start(context.new_context())
    context.atomic_write_context(path, state)
    loaded = context.load_context(path)
    assert loaded == state
    assert list(path.parent.glob("tmp*")) == []
