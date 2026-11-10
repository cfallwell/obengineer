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
from pathlib import Path

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


def parse_record(path: Path) -> tuple[dict[str, str], list[str]]:
    try:
        text = path.read_text()
    except OSError as exc:
        return {}, [f"cannot read acceptance record: {exc}"]
    fields = {
        match.group(1): match.group(2).strip()
        for match in re.finditer(r"^([a-z_]+):\s*([^#\n]+?)\s*$", text, re.M)
    }
    failures: list[str] = []
    if fields.get("status") != "accepted":
        failures.append("acceptance record status must be accepted")
    required = (
        "version", "analysis", "analysis_content_commit",
        "analysis_content_digest", "analysis_pr", "accepted_via", "accepted_at",
        "provenance_seal_digest",
    )
    for field in required:
        if not fields.get(field):
            failures.append(f"acceptance record has no {field}")
    if fields.get("version") and not VERSION.fullmatch(fields["version"]):
        failures.append("acceptance record version must be uppercase V<N>")
    if fields.get("analysis_content_commit") and not FULL_SHA.fullmatch(
        fields["analysis_content_commit"]
    ):
        failures.append("analysis_content_commit must be a full lowercase SHA")
    if fields.get("analysis_content_digest") and not SHA256.fullmatch(
        fields["analysis_content_digest"]
    ):
        failures.append("analysis_content_digest must be SHA-256")
    if fields.get("accepted_via") != "explicit-human-confirmation":
        failures.append("accepted_via must be explicit-human-confirmation")
    if fields.get("accepted_at") and not RFC3339.fullmatch(fields["accepted_at"]):
        failures.append("accepted_at must be RFC3339")
    if fields.get("provenance_seal_digest") and not SHA256.fullmatch(
        fields["provenance_seal_digest"]
    ):
        failures.append("provenance_seal_digest must be SHA-256")
    for field in ("qualifications", "rejected_decisions"):
        if not re.search(rf"^{field}:\s*(?:.*)?$", text, re.M):
            failures.append(f"acceptance record has no {field}")
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


def artifact_paths(repo: Path, analysis: Path, version: str) -> tuple[list[Path], list[str]]:
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
    for name in COMPANIONS:
        path = docs / name
        if path.is_file():
            paths.append(path)
        else:
            failures.append(f"missing current artifact: {path.relative_to(repo)}")
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


def verify(repo: Path, analysis: Path, version: str, expected_digest: str,
           commit: str | None = None) -> list[str]:
    repo = repo.resolve()
    failures: list[str] = []
    paths, path_failures = artifact_paths(repo, analysis, version)
    failures.extend(path_failures)
    if expected_digest and paths:
        actual = content_digest(repo, paths)
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    fields, failures = parse_record(args.record)
    if not failures:
        failures.extend(
            verify(
                args.repo,
                Path(fields["analysis"]),
                fields["version"],
                fields["analysis_content_digest"],
                fields["analysis_content_commit"],
            )
        )
        ledger = args.repo / "docs" / "observability" / "provenance-ledger.json"
        if ledger.is_file():
            actual = json.loads(ledger.read_text()).get("seals", {}).get(
                "analysis", {}
            ).get("digest")
            if actual != fields["provenance_seal_digest"]:
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
