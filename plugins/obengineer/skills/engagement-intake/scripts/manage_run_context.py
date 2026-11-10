#!/usr/bin/env python3
"""Atomically maintain the deterministic guided-intake state machine."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install PyYAML==6.0.3")

CONTEXT_RELATIVE_PATH = Path(".obengineer/run-context.json")
INPUTS_RELATIVE_PATH = Path("docs/observability/engagement-inputs.yaml")
STATES = {"new", "required", "optional-review", "optional-answers"}
STATUSES = {"pending", "complete", "skipped"}
EVENTS = {"initialize", "start", "required", "review-yes", "answer", "review-no"}
MARKERS = {"pending": "[ ]", "complete": "[x]", "skipped": "[-]"}
REQUIRED_LABELS = {
    "application": "Application",
    "production-surface": "Explicit production URL or no-browser reason",
    "what-hurts": "What hurts today",
}
OPTIONAL_LABELS = {
    1: "Diagrams or prior analysis",
    2: "Security assessment authorization",
    3: "Dummy authenticated test access",
    4: "Tenant realm and environments",
    5: "Entitlement and traffic baselines",
    6: "Privacy, residency, consent, and change constraints",
    7: "Business and incident context",
    8: "Bounded public-record research",
    9: "Chart and detector percentile",
    10: "Journey to rank first",
}
FIRST_QUESTION = """Before I inspect source, the network, or connected tools, please provide or confirm:
1. What is the application name?
2. What is the explicit production URL? If no browser applies, answer `no browser: <reason>`.
3. In your own words, what hurts today?"""


class StateError(ValueError):
    """An invalid event or corrupt context."""


def new_context() -> dict:
    return {
        "schema_version": 1,
        "turn": 0,
        "state": "new",
        "analysis_authorized": False,
        "required": {key: "pending" for key in REQUIRED_LABELS},
        "optional": {
            "items": {str(number): "pending" for number in OPTIONAL_LABELS},
            "offered": [],
            "selected": [],
            "pending": [],
        },
        "last_event": "initialize",
    }


def validate_context(context: dict) -> None:
    if not isinstance(context, dict) or context.get("schema_version") != 1:
        raise StateError("run context must use schema version 1")
    if context.get("state") not in STATES:
        raise StateError("run context has an invalid state")
    if not isinstance(context.get("turn"), int) or context["turn"] < 0:
        raise StateError("run context has an invalid turn")
    if not isinstance(context.get("analysis_authorized"), bool):
        raise StateError("run context has an invalid authorization flag")
    if context.get("last_event") not in EVENTS:
        raise StateError("run context has an invalid last event")
    required = context.get("required")
    if not isinstance(required, dict) or set(required) != set(REQUIRED_LABELS):
        raise StateError("run context has invalid required checklist keys")
    if any(status not in STATUSES for status in required.values()):
        raise StateError("run context has an invalid required checklist status")
    optional = context.get("optional")
    if not isinstance(optional, dict):
        raise StateError("run context has invalid optional state")
    items = optional.get("items")
    if (
        not isinstance(items, dict)
        or set(items) != {str(number) for number in OPTIONAL_LABELS}
        or any(status not in STATUSES for status in items.values())
    ):
        raise StateError("run context has invalid optional checklist items")
    for name in ("offered", "selected", "pending"):
        values = optional.get(name)
        if (
            not isinstance(values, list)
            or any(
                type(value) is not int or value not in OPTIONAL_LABELS
                for value in values
            )
            or len(values) != len(set(values))
            or values != sorted(values)
        ):
            raise StateError(f"run context has invalid optional {name}")
    if context["state"] == "optional-answers" and not optional["pending"]:
        raise StateError("optional-answers requires at least one pending answer")
    if context["analysis_authorized"] and (
        context["state"] != "optional-review"
        or context.get("last_event") != "review-no"
    ):
        raise StateError("analysis authorization requires an explicit no review event")


def load_context(path: Path) -> dict:
    if not path.exists():
        return new_context()
    try:
        context = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot load run context: {exc}") from exc
    validate_context(context)
    return context


def atomic_write_context(path: Path, context: dict) -> None:
    validate_context(context)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(context, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, encoding="utf-8"
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _is_set(value: object) -> bool:
    return value not in (None, "", "unknown", [])


def _absolute_production_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def required_statuses(inputs_path: Path) -> dict[str, str]:
    try:
        data = yaml.safe_load(inputs_path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise StateError(f"cannot load engagement inputs: {exc}") from exc
    if not isinstance(data, dict):
        raise StateError("engagement inputs top level must be an object")
    application = (data.get("engagement") or {}).get("application")
    urls = (data.get("surfaces") or {}).get("production_urls") or []
    notes = (data.get("artifacts") or {}).get("front_end_scan_notes")
    commentary = (data.get("business_context") or {}).get("commentary")
    valid_urls = (
        isinstance(urls, list)
        and bool(urls)
        and all(_absolute_production_url(url) for url in urls)
    )
    no_browser = (
        isinstance(notes, str)
        and bool(re.fullmatch(r"no browser:\s*\S.*", notes.strip(), re.I))
    )
    return {
        "application": "complete" if _is_set(application) else "pending",
        "production-surface": "complete" if valid_urls ^ no_browser else "pending",
        "what-hurts": "complete" if _is_set(commentary) else "pending",
    }


def start(context: dict) -> dict:
    if context["analysis_authorized"]:
        raise StateError("analysis is already authorized for this intake")
    if context["state"] == "new":
        context["state"] = "required"
    context["turn"] += 1
    context["last_event"] = "start"
    return context


def complete_required(context: dict, inputs_path: Path) -> dict:
    if context["state"] != "required" or context["analysis_authorized"]:
        raise StateError("required answers are not expected in the current state")
    context["required"] = required_statuses(inputs_path)
    missing = [
        REQUIRED_LABELS[key]
        for key, status in context["required"].items()
        if status != "complete"
    ]
    if missing:
        raise StateError("required answers remain incomplete: " + ", ".join(missing))
    context["state"] = "optional-review"
    context["turn"] += 1
    context["last_event"] = "required"
    return context


def _parse_yes(response: str) -> list[int] | None:
    normalized = " ".join(response.lower().split())
    if not re.fullmatch(r"yes(?: (?:[1-9]|10))+", normalized):
        return None
    selected = [int(part) for part in normalized.split()[1:]]
    if len(selected) != len(set(selected)):
        raise StateError("optional selections must not contain duplicates")
    return sorted(selected)


def review(context: dict, response: str, offered: list[int]) -> dict:
    if context["state"] != "optional-review" or context["analysis_authorized"]:
        raise StateError("optional review is not expected in the current state")
    if (
        not isinstance(response, str)
        or not isinstance(offered, list)
        or any(type(item) is not int or item not in OPTIONAL_LABELS for item in offered)
        or len(offered) != len(set(offered))
    ):
        raise StateError("offered optional items must be unique numbers from 1 to 10")
    offered = sorted(offered)
    normalized = " ".join(response.lower().split())
    if normalized == "no":
        context["optional"]["offered"] = offered
        for item in OPTIONAL_LABELS:
            if context["optional"]["items"][str(item)] == "pending":
                context["optional"]["items"][str(item)] = "skipped"
        context["optional"]["selected"] = []
        context["optional"]["pending"] = []
        context["analysis_authorized"] = True
        context["turn"] += 1
        context["last_event"] = "review-no"
        return context

    selected = _parse_yes(response)
    if selected is None:
        raise StateError("reply exactly `no` or `yes` followed by item numbers")
    if not set(selected) <= set(offered):
        raise StateError("selected items must be present in the offered checklist")
    context["optional"]["offered"] = offered
    context["optional"]["selected"] = selected
    context["optional"]["pending"] = selected.copy()
    context["state"] = "optional-answers"
    context["turn"] += 1
    context["last_event"] = "review-yes"
    return context


def record_answer(context: dict, item: int, status: str) -> dict:
    if context["state"] != "optional-answers" or context["analysis_authorized"]:
        raise StateError("an optional answer is not expected in the current state")
    if type(item) is not int:
        raise StateError("answer item must be a number from 1 to 10")
    pending = context["optional"]["pending"]
    if not pending or item != pending[0]:
        expected = pending[0] if pending else "none"
        raise StateError(f"answer optional item {expected} next")
    if status not in {"answered", "skipped"}:
        raise StateError("answer status must be answered or skipped")
    context["optional"]["items"][str(item)] = (
        "complete" if status == "answered" else "skipped"
    )
    context["optional"]["pending"] = pending[1:]
    if not context["optional"]["pending"]:
        context["state"] = "optional-review"
    context["turn"] += 1
    context["last_event"] = "answer"
    return context


def render_checklist(context: dict) -> str:
    lines = ["Required inputs"]
    for key, label in REQUIRED_LABELS.items():
        lines.append(f"{MARKERS[context['required'][key]]} {label}")
    lines.append("Optional inputs")
    for number, label in OPTIONAL_LABELS.items():
        status = context["optional"]["items"][str(number)]
        lines.append(f"{MARKERS[status]} {number}. {label}")
    lines.append(
        "Analysis authorized: "
        + ("yes (explicit `no` recorded)" if context["analysis_authorized"] else "no")
    )
    return "\n".join(lines)


def read_payload(path: str | None) -> dict:
    if not path:
        return {}
    try:
        text = sys.stdin.read() if path == "-" else Path(path).read_text()
        payload = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot read event payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise StateError("event payload must be a JSON object")
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "event", choices=("start", "required", "review", "answer", "show")
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--payload", metavar="PATH", help="JSON payload; use - for stdin")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    context_path = root / CONTEXT_RELATIVE_PATH
    inputs_path = root / INPUTS_RELATIVE_PATH
    try:
        context = load_context(context_path)
        payload = read_payload(args.payload)
        if args.event == "start":
            context = start(context)
        elif args.event == "required":
            context = complete_required(context, inputs_path)
        elif args.event == "review":
            context = review(
                context,
                payload.get("response", ""),
                payload.get("offered", []),
            )
        elif args.event == "answer":
            context = record_answer(
                context,
                payload.get("item"),
                payload.get("status", ""),
            )
        if args.event != "show":
            atomic_write_context(context_path, context)
    except StateError as exc:
        print(f"FAIL — {exc}")
        return 1
    if args.event == "start":
        print(FIRST_QUESTION)
    print(render_checklist(context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
