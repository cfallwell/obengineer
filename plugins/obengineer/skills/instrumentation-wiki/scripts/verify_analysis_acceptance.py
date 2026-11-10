#!/usr/bin/env python3
"""Verify that analysis artifacts exactly match one reviewed git commit."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
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


def implementation_map_verifier():
    path = Path(__file__).with_name("verify_implementation_map.py")
    spec = importlib.util.spec_from_file_location("verify_implementation_map", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.verify


def _load_verifier(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.verify


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


def read_record(path: Path) -> tuple[Path | None, str | None, list[str]]:
    try:
        text = path.read_text()
    except OSError as exc:
        return None, None, [f"cannot read acceptance record: {exc}"]
    fields = {
        match.group(1): match.group(2).strip()
        for match in re.finditer(r"^([a-z_]+):\s*([^#\n]+?)\s*$", text, re.M)
    }
    failures: list[str] = []
    if fields.get("status") != "accepted":
        failures.append("acceptance record status must be accepted")
    for field in (
        "analysis", "analysis_commit", "analysis_pr", "accepted_by", "accepted_at",
        "provenance_seal_digest",
    ):
        if not fields.get(field):
            failures.append(f"acceptance record has no {field}")
    for field in ("qualifications", "rejected_decisions"):
        if not re.search(rf"^{field}:\s*(?:.*)?$", text, re.M):
            failures.append(f"acceptance record has no {field}")
    if fields.get("accepted_at") and not RFC3339.fullmatch(fields["accepted_at"]):
        failures.append("acceptance record accepted_at must be RFC3339")
    if fields.get("provenance_seal_digest") and not re.fullmatch(
        r"[0-9a-f]{64}", fields["provenance_seal_digest"]
    ):
        failures.append("acceptance record provenance_seal_digest must be SHA-256")
    analysis = Path(fields["analysis"]) if fields.get("analysis") else None
    return analysis, fields.get("analysis_commit"), failures


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


def verify(repo: Path, analysis: Path, commit: str) -> list[str]:
    failures: list[str] = []
    if not FULL_SHA.fullmatch(commit):
        return ["analysis commit must be a full 40-character lowercase SHA"]

    repo = repo.resolve()
    candidate = analysis if analysis.is_absolute() else repo / analysis
    candidate = candidate.resolve()
    try:
        relative = candidate.relative_to(repo)
    except ValueError:
        return ["analysis path must be inside the repository"]

    try:
        resolved = git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    except ValueError as exc:
        return [f"analysis commit is not available: {exc}"]
    if resolved != commit:
        failures.append("analysis commit did not resolve to the supplied full SHA")

    paths = [relative, *(relative.parent / name for name in COMPANIONS)]
    for path in paths:
        current = repo / path
        if not current.is_file():
            failures.append(f"missing current artifact: {path}")
            continue
        try:
            committed = git(repo, "show", f"{commit}:{path.as_posix()}")
        except ValueError:
            failures.append(f"artifact absent from accepted commit: {path}")
            continue
        if current.read_bytes() != committed:
            failures.append(f"artifact differs from accepted commit: {path}")
    implementation_map = repo / relative.parent / COMPANIONS[1]
    if implementation_map.is_file():
        failures.extend(
            f"implementation map: {failure}"
            for failure in implementation_map_verifier()(implementation_map)
        )
    ledger = repo / relative.parent / COMPANIONS[2]
    if ledger.is_file():
        failures.extend(
            f"provenance ledger: {failure}"
            for failure in provenance_ledger_verifier()(ledger)
        )
    if implementation_map.is_file() and ledger.is_file():
        try:
            map_data = json.loads(implementation_map.read_text())
            ledger_data = json.loads(ledger.read_text())
            ledger_ids = {
                item.get("id")
                for collection in (
                    "sources", "facts", "runs", "checks", "artifacts",
                    "decisions", "unresolved",
                )
                for item in ledger_data.get(collection, [])
                if isinstance(item, dict)
            }
            evidence_ids = {
                evidence
                for target in map_data.get("targets", [])
                if isinstance(target, dict)
                for evidence in target.get("evidence", [])
            }
            unknown = evidence_ids - ledger_ids
            if unknown:
                failures.append(
                    f"implementation map evidence missing from ledger: {sorted(unknown)}"
                )
        except (json.JSONDecodeError, AttributeError):
            pass
    plan = repo / relative.parent / COMPANIONS[3]
    if plan.is_file():
        failures.extend(
            f"verification plan: {failure}"
            for failure in verification_plan_verifier()(plan)
        )
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path, nargs="?")
    parser.add_argument("commit", nargs="?")
    parser.add_argument("--record", type=Path)
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    failures: list[str] = []
    analysis, commit = args.analysis, args.commit
    if args.record:
        if analysis or commit:
            parser.error("--record cannot be combined with analysis and commit")
        analysis, commit, failures = read_record(args.record)
    if analysis is None or commit is None:
        parser.error("provide analysis and commit, or --record <acceptance.yaml>")
    failures.extend(verify(args.repo, analysis, commit))
    if args.record and analysis is not None:
        record_text = args.record.read_text()
        match = re.search(
            r"^provenance_seal_digest:\s*([0-9a-f]{64})\s*$",
            record_text, re.M,
        )
        ledger = args.repo / analysis.parent / "provenance-ledger.json"
        if match and ledger.is_file():
            actual = json.loads(ledger.read_text()).get("seals", {}).get(
                "analysis", {}
            ).get("digest")
            if actual != match.group(1):
                failures.append(
                    "acceptance provenance_seal_digest does not match ledger"
                )
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print("PASS — analysis, schema, and implementation map match the accepted commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
