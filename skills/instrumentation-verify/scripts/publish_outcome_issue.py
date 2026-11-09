#!/usr/bin/env python3
"""Preview and optionally publish an anonymized obengineer outcome issue."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = "cfallwell/obengineer"
ALLOWED = {
    "canonical_reference", "spec_commit", "outcome_class", "defect_class",
    "numerator", "denominator", "coverage", "consequence_code",
    "proposed_change", "deny_terms",
}
FORBIDDEN_KEY = re.compile(
    r"(customer|tenant|account|org_id|url|credential|token|taxonomy|artifact|query)",
    re.I,
)
SENSITIVE_VALUE = re.compile(
    r"(https?://|\b(?:AKIA|ASIA)[A-Z0-9]{12,}\b"
    r"|\bgh[posur]_[A-Za-z0-9]{20,}\b"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def build(payload: dict) -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        raise ValueError("outcome payload must be an object")
    unknown = set(payload) - ALLOWED
    if unknown or any(FORBIDDEN_KEY.search(key) for key in payload):
        raise ValueError(f"outcome payload has forbidden fields: {sorted(unknown)}")
    required = ALLOWED - {"coverage"}
    missing = [key for key in sorted(required) if payload.get(key) in ("", None)]
    if missing:
        raise ValueError(f"outcome payload missing fields: {missing}")
    deny_terms = payload.get("deny_terms")
    if not isinstance(deny_terms, list) or not deny_terms or not all(
        isinstance(term, str) and term.strip() for term in deny_terms
    ):
        raise ValueError("deny_terms must contain engagement-derived identifiers")
    rendered_values = "\n".join(
        str(value) for key, value in payload.items() if key != "deny_terms"
    )
    if SENSITIVE_VALUE.search(rendered_values):
        raise ValueError("outcome payload contains a URL or credential-shaped value")
    lowered = rendered_values.casefold()
    leaked = [term for term in deny_terms if term.casefold() in lowered]
    if leaked:
        raise ValueError("outcome payload contains engagement-derived deny terms")
    if not FULL_SHA.fullmatch(str(payload["spec_commit"])):
        raise ValueError("spec_commit must be a full lowercase SHA")
    for field in ("numerator", "denominator"):
        if not isinstance(payload[field], int) or payload[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    coverage = payload.get("coverage")
    if coverage is not None and (
        not isinstance(coverage, (int, float)) or not 0 <= coverage <= 1
    ):
        raise ValueError("coverage must be between 0 and 1")
    marker_source = "|".join(str(payload[key]) for key in (
        "canonical_reference", "outcome_class", "defect_class"
    ))
    marker = hashlib.sha256(marker_source.encode()).hexdigest()
    title = (
        f"[outcome] {payload['canonical_reference']}: "
        f"{payload['defect_class']}"
    )
    body = "\n".join([
        f"<!-- obengineer-outcome:{marker} -->",
        f"- Specification commit: `{payload['spec_commit']}`",
        f"- Outcome class: `{payload['outcome_class']}`",
        f"- Defect class: `{payload['defect_class']}`",
        f"- Numerator: {payload['numerator']}",
        f"- Denominator: {payload['denominator']}",
        f"- Measurement coverage: {payload.get('coverage', 'unknown')}",
        f"- Consequence: `{payload['consequence_code']}`",
        "",
        "## Proposed canonical change",
        str(payload["proposed_change"]),
        "",
        "_Anonymized aggregate: no engagement or customer identifiers._",
    ])
    return title, body, marker


def preview_hash(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\n{body}".encode()).hexdigest()


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def publish(title: str, body: str, marker: str, *, spec_commit: str | None = None,
            execute=run) -> tuple[int, str]:
    if shutil.which("gh") is None:
        return 2, (
            "GitHub CLI is unavailable. Install it, then authenticate at "
            "https://github.com/login/device or run "
            "`gh auth login --web --hostname github.com`."
        )
    auth = execute(["gh", "auth", "status", "--hostname", "github.com"])
    if auth.returncode:
        return 2, (
            "GitHub authentication is required even for a public repository. Run "
            "`gh auth login --web --hostname github.com` or open "
            "https://github.com/login/device, then rerun this command."
        )
    if spec_commit:
        commit = execute([
            "gh", "api", f"repos/{REPO}/commits/{spec_commit}",
            "--silent",
        ])
        if commit.returncode:
            return 1, "spec_commit does not belong to cfallwell/obengineer"
    listed = execute([
        "gh", "issue", "list", "--repo", REPO, "--state", "all",
        "--search", f"obengineer-outcome:{marker}", "--json", "number,body",
    ])
    if listed.returncode:
        return 1, listed.stderr.strip() or "failed to search outcome issues"
    matches = json.loads(listed.stdout or "[]")
    if matches:
        result = execute([
            "gh", "issue", "edit", str(matches[0]["number"]), "--repo", REPO,
            "--title", title, "--body", body,
        ])
    else:
        result = execute([
            "gh", "issue", "create", "--repo", REPO,
            "--title", title, "--body", body,
        ])
    return result.returncode, (result.stdout or result.stderr).strip()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--approved-preview")
    args = parser.parse_args(argv)
    try:
        title, body, marker = build(json.loads(args.payload.read_text()))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL — {exc}")
        return 1
    digest = preview_hash(title, body)
    print(f"TITLE\n{title}\n\nBODY\n{body}\n\nPREVIEW SHA256\n{digest}")
    if not args.publish:
        print(
            "\nPREVIEW ONLY — after human review rerun with "
            f"--publish --approved-preview {digest}"
        )
        return 0
    if args.approved_preview != digest:
        print("FAIL — --publish requires the exact approved preview hash")
        return 1
    payload_data = json.loads(args.payload.read_text())
    code, message = publish(
        title, body, marker, spec_commit=payload_data["spec_commit"]
    )
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
