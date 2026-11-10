#!/usr/bin/env python3
"""Verify content-bound acceptance for a versioned analysis and wiki."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install PyYAML==6.0.3")

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^V[1-9][0-9]*$")
RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
COMPANIONS = (
    "attribute-schema.json",
    "implementation-map.json",
    "provenance-ledger.json",
    "verification-plan.json",
)
V2_COMPANIONS = (*COMPANIONS, "analysis-contract.json")


def _load_verifier(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.verify


def implementation_map_verifier():
    return _load_verifier(
        "verify_implementation_map",
        Path(__file__).with_name("verify_implementation_map.py"),
    )


def provenance_ledger_verifier():
    return _load_verifier(
        "verify_provenance_ledger",
        Path(__file__).with_name("verify_provenance_ledger.py"),
    )


def verification_plan_verifier():
    return _load_verifier(
        "verify_plan",
        Path(__file__).parents[2] / "instrumentation-verify" / "scripts" /
        "verify_plan.py",
    )


def parse_record(path: Path) -> tuple[dict, list[str]]:
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        return {}, [f"cannot read acceptance record: {exc}"]
    if not isinstance(data, dict):
        return {}, ["acceptance record top level must be a mapping"]
    fields = dict(data)
    failures: list[str] = []
    accepted_at = fields.get("accepted_at")
    if isinstance(accepted_at, datetime):
        if accepted_at.tzinfo == timezone.utc:
            fields["accepted_at"] = accepted_at.isoformat().replace("+00:00", "Z")
        else:
            fields["accepted_at"] = accepted_at.isoformat()
    schema_version = fields.get("schema_version", 1)
    if schema_version not in (1, 2):
        failures.append("acceptance schema_version must be 1 or 2")
        return fields, failures
    fields["schema_version"] = schema_version
    if fields.get("status") != "accepted":
        failures.append("acceptance record status must be accepted")
    required = ["version", "analysis", "analysis_pr", "accepted_via", "accepted_at"]
    if schema_version == 2:
        required.extend((
            "analysis_content_commit", "analysis_content_digest",
            "provenance_seal_digest",
        ))
        if "analysis_commit" in fields:
            failures.append(
                "acceptance schema_version 2 uses analysis_content_commit, "
                "not analysis_commit"
            )
    else:
        legacy_commit = fields.get("analysis_commit")
        content_commit = fields.get("analysis_content_commit")
        if legacy_commit and content_commit and legacy_commit != content_commit:
            failures.append(
                "legacy acceptance commit fields disagree; migrate to schema_version 2"
            )
        fields["analysis_content_commit"] = content_commit or legacy_commit
        if not fields["analysis_content_commit"]:
            failures.append(
                "legacy acceptance record has no analysis_commit; "
                "migrate to schema_version 2"
            )
    for field in required:
        if not fields.get(field):
            failures.append(f"acceptance record has no {field}")
    if fields.get("version") and (
        not isinstance(fields["version"], str)
        or not VERSION.fullmatch(fields["version"])
    ):
        failures.append("acceptance record version must be uppercase V<N>")
    if fields.get("analysis_content_commit") and (
        not isinstance(fields["analysis_content_commit"], str)
        or not FULL_SHA.fullmatch(fields["analysis_content_commit"])
    ):
        failures.append("analysis_content_commit must be a full lowercase SHA")
    if fields.get("analysis_content_digest") and (
        not isinstance(fields["analysis_content_digest"], str)
        or not SHA256.fullmatch(fields["analysis_content_digest"])
    ):
        failures.append("analysis_content_digest must be SHA-256")
    if fields.get("accepted_via") != "explicit-human-confirmation":
        failures.append("accepted_via must be explicit-human-confirmation")
    if fields.get("accepted_at") and (
        not isinstance(fields["accepted_at"], str)
        or not RFC3339.fullmatch(fields["accepted_at"])
    ):
        failures.append("accepted_at must be RFC3339")
    if fields.get("provenance_seal_digest") and (
        not isinstance(fields["provenance_seal_digest"], str)
        or not SHA256.fullmatch(fields["provenance_seal_digest"])
    ):
        failures.append("provenance_seal_digest must be SHA-256")
    for field in ("qualifications", "rejected_decisions"):
        if field not in fields:
            failures.append(f"acceptance record has no {field}")
        elif not isinstance(fields[field], list):
            failures.append(f"acceptance record {field} must be a list")
    return fields, failures


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        detail = result.stderr.decode(errors="replace").strip()
        raise ValueError(detail or f"git {' '.join(args)} failed")
    return result.stdout


def artifact_paths(repo: Path, analysis: Path, version: str,
                   schema_version: int = 2) -> tuple[list[Path], list[str]]:
    failures: list[str] = []
    candidate = analysis if analysis.is_absolute() else repo / analysis
    candidate = candidate.resolve()
    try:
        relative = candidate.relative_to(repo)
    except ValueError:
        return [], ["analysis path must be inside the repository"]
    if candidate.name != "index.md" or candidate.parent.name != version:
        failures.append("analysis must be the index.md under its V<N> directory")
    try:
        app = candidate.parent.parent.name
        expected_prefix = Path("docs/observability/analysis") / app / version
        relative.relative_to(expected_prefix)
    except ValueError:
        failures.append(
            "analysis path must be docs/observability/analysis/<app>/V<N>/index.md"
        )
        return [], failures

    docs = repo / "docs" / "observability"
    wiki = repo / "wiki" / "apps" / app / "versions" / version
    paths = [
        path for path in candidate.parent.rglob("*")
        if path.is_file() and path.name != "acceptance.yaml"
    ]
    companions = V2_COMPANIONS if schema_version == 2 else COMPANIONS
    for name in companions:
        path = docs / name
        if path.is_file():
            paths.append(path)
        else:
            failures.append(f"missing current artifact: {path.relative_to(repo)}")
    optional_contract = docs / "analysis-contract.json"
    if schema_version == 1 and optional_contract.is_file():
        paths.append(optional_contract)
    if wiki.is_dir():
        paths.extend(path for path in wiki.rglob("*") if path.is_file())
    else:
        failures.append(f"missing versioned wiki: {wiki.relative_to(repo)}")
    return sorted(set(paths), key=lambda path: path.relative_to(repo).as_posix()), failures


def content_digest(repo: Path, paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(repo).as_posix().encode()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def verify(repo: Path, analysis: Path, version: str, expected_digest: str | None,
           commit: str | None = None, schema_version: int = 2) -> list[str]:
    repo = repo.resolve()
    failures: list[str] = []
    paths, path_failures = artifact_paths(
        repo, analysis, version, schema_version=schema_version
    )
    failures.extend(path_failures)
    if expected_digest and paths:
        actual = content_digest(repo, paths)
        # Some schema v1 acceptances predate analysis-contract.json. Once that
        # file appears for a newer run, preserve their original digest while
        # allowing later v1 records that included it to remain verifiable.
        contract = repo / "docs" / "observability" / "analysis-contract.json"
        if actual != expected_digest and schema_version == 1 and contract in paths:
            legacy_paths = [path for path in paths if path != contract]
            if content_digest(repo, legacy_paths) == expected_digest:
                actual = expected_digest
        if actual != expected_digest:
            failures.append(
                f"accepted content digest differs: expected {expected_digest}, got {actual}"
            )
    if commit:
        try:
            resolved = git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
            if resolved != commit:
                failures.append("analysis_content_commit did not resolve exactly")
        except ValueError as exc:
            failures.append(f"analysis content commit is not available: {exc}")

    docs = repo / "docs" / "observability"
    implementation_map = docs / COMPANIONS[1]
    ledger = docs / COMPANIONS[2]
    plan = docs / COMPANIONS[3]
    if implementation_map.is_file():
        failures.extend(
            f"implementation map: {failure}"
            for failure in implementation_map_verifier()(implementation_map)
        )
    if ledger.is_file():
        failures.extend(
            f"provenance ledger: {failure}"
            for failure in provenance_ledger_verifier()(ledger)
        )
    if plan.is_file():
        failures.extend(
            f"verification plan: {failure}"
            for failure in verification_plan_verifier()(plan)
        )
    return failures


def discover_acceptance(repo: Path) -> tuple[Path | None, list[str]]:
    root = repo / "docs" / "observability" / "analysis"
    candidates = sorted(
        path for path in root.glob("*/V*/acceptance.yaml")
        if VERSION.fullmatch(path.parent.name)
    )
    if not candidates:
        return None, [
            "no acceptance record found at "
            "docs/observability/analysis/<app>/V<N>/acceptance.yaml"
        ]
    if len(candidates) > 1:
        rendered = [str(path.relative_to(repo)) for path in candidates]
        return None, [f"acceptance record is ambiguous: {rendered}"]
    return candidates[0], []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    record = args.record
    failures: list[str] = []
    if record is None:
        record, failures = discover_acceptance(args.repo)
    fields: dict = {}
    if record is not None:
        fields, record_failures = parse_record(record)
        failures.extend(record_failures)
    if not failures:
        expected_record = (
            args.repo / Path(fields["analysis"]).parent / "acceptance.yaml"
        ).resolve()
        if record.resolve() != expected_record:
            failures.append(
                "acceptance record must be beside its analysis index at "
                "docs/observability/analysis/<app>/V<N>/acceptance.yaml"
            )
    if not failures:
        failures.extend(
            verify(
                args.repo,
                Path(fields["analysis"]),
                fields["version"],
                fields.get("analysis_content_digest"),
                fields["analysis_content_commit"],
                fields["schema_version"],
            )
        )
        ledger = args.repo / "docs" / "observability" / "provenance-ledger.json"
        if ledger.is_file():
            actual = json.loads(ledger.read_text()).get("seals", {}).get(
                "analysis", {}
            ).get("digest")
            if fields.get("provenance_seal_digest") and \
                    actual != fields["provenance_seal_digest"]:
                failures.append(
                    "acceptance provenance_seal_digest does not match ledger"
                )
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print("PASS — versioned analysis and wiki match the accepted content digest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
