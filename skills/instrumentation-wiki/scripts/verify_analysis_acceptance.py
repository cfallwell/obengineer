#!/usr/bin/env python3
"""Verify that analysis artifacts exactly match one reviewed git commit."""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
COMPANIONS = ("attribute-schema.json", "implementation-map.json")


def implementation_map_verifier():
    path = Path(__file__).with_name("verify_implementation_map.py")
    spec = importlib.util.spec_from_file_location("verify_implementation_map", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.verify


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
    if not fields.get("analysis"):
        failures.append("acceptance record has no analysis path")
    if not fields.get("analysis_commit"):
        failures.append("acceptance record has no analysis_commit")
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

    paths = [relative, relative.parent / COMPANIONS[0], relative.parent / COMPANIONS[1]]
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
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print("PASS — analysis, schema, and implementation map match the accepted commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
