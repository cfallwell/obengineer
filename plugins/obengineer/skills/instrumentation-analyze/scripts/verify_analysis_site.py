#!/usr/bin/env python3
"""Validate a versioned linked analysis site without a browser or preview server."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from analysis_contract import PLACEHOLDER, load_json, validate_contract

VERSION = re.compile(r"^V[1-9][0-9]*$")
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
VERSION_LINK = re.compile(r"\[V[1-9][0-9]*\]")
FORBIDDEN = (
    re.compile(r"https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?", re.I),
    re.compile(r"\bpython(?:3)?\s+-m\s+http\.server\b"),
)
REQUIRED_HEADINGS = (
    "Status",
    "Next steps",
    "Changes in this version",
    "Table of contents and section summaries",
    "Architecture summary",
    "Priority review map",
    "Side-panel navigation",
)
CONTENTS_ROWS = (
    "Architecture",
    "Technology",
    "Current telemetry",
    "Findings",
    "Instrumentation strategy",
    "Implementation path",
    "Work orders",
    "Use cases",
    "Workflows",
    "Business transactions",
    "Shared signal contracts",
    "Operations and verification",
    "Reference",
)
REQUIRED_INDEXES = (
    "overview/index.md",
    "technology/index.md",
    "telemetry/index.md",
    "findings/index.md",
    "strategy/index.md",
    "implementation/index.md",
    "work-orders/index.md",
    "use-cases/index.md",
    "workflows/index.md",
    "business-transactions/index.md",
    "contracts/index.md",
    "operations/index.md",
    "reference/index.md",
)
EMPTY_HEADING = re.compile(
    r"^#{1,6}\s+.+?\s*$\n(?:\s*\n)*(?=#{1,6}\s|\Z)",
    re.MULTILINE,
)


def lexical_quality(text: str, minimum_unique: int = 5) -> bool:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.-]*", text.casefold())
    if len(set(tokens)) < minimum_unique:
        return False
    if tokens and max(tokens.count(token) for token in set(tokens)) / len(tokens) > 0.6:
        return False
    return re.search(r"(.)\1{11,}", text, re.S) is None


def resolve_link(source: Path, raw: str) -> Path | None:
    target = raw.strip().split("#", 1)[0]
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return None
    candidate = (source.parent / target).resolve()
    if candidate.is_dir():
        candidate = candidate / "index.md"
    return candidate


def check(
    version_dir: Path,
    repo_root: Path | None = None,
    contract_path: Path | None = None,
) -> list[str]:
    failures: list[str] = []
    version_dir = version_dir.resolve()
    if not VERSION.fullmatch(version_dir.name):
        failures.append("analysis version directory must be uppercase V<N>")
    index = version_dir / "index.md"
    if not index.is_file():
        return failures + ["missing version index.md"]
    markdown = sorted(version_dir.rglob("*.md"))
    if not markdown:
        return failures + ["analysis version contains no Markdown"]
    for relative in REQUIRED_INDEXES:
        if not (version_dir / relative).is_file():
            failures.append(f"missing canonical detail index: {relative}")

    index_text = index.read_text()
    if not VERSION_LINK.search(index_text):
        failures.append("index.md has no [V<N>] version selector")
    for heading in REQUIRED_HEADINGS:
        if not re.search(rf"^##+\s+.*{re.escape(heading)}", index_text, re.M | re.I):
            failures.append(f"index.md is missing heading: {heading}")
    architecture = re.search(
        r"^##\s+Architecture summary\s*$\n(?P<body>.*?)(?=^##\s|\Z)",
        index_text,
        re.M | re.S | re.I,
    )
    if (
        not architecture
        or len(architecture.group("body").strip()) < 160
        or not lexical_quality(architecture.group("body"))
    ):
        failures.append("index.md Architecture summary must be substantive and visible")
    if not re.search(
        r"\|\s*Priority findings\s*\|\s*Primary use cases\s*\|",
        index_text,
        re.I,
    ):
        failures.append("index.md has no findings/use-cases review map")
    positions = []
    for row in CONTENTS_ROWS:
        match = re.search(
            rf"^\|\s*{re.escape(row)}\s*\|.*$",
            index_text,
            re.M | re.I,
        )
        if not match:
            failures.append(f"index.md table of contents is missing row: {row}")
        else:
            positions.append(match.start())
            if not LINK.search(match.group()):
                failures.append(f"index.md table-of-contents row has no Open link: {row}")
            cells = [cell.strip() for cell in match.group().strip().strip("|").split("|")]
            if len(cells) < 3 or len(cells[1]) < 80:
                failures.append(f"index.md table-of-contents row has no substantive summary: {row}")
    if positions != sorted(positions):
        failures.append("index.md table-of-contents rows are out of approved order")

    repo_root = (repo_root or next(
        (parent for parent in version_dir.parents if (parent / ".git").exists()),
        version_dir.parents[-1],
    )).resolve()

    for path in markdown:
        text = path.read_text()
        relative = path.relative_to(version_dir)
        if path != index and "[Analysis](" not in text:
            failures.append(f"{relative}: no Analysis breadcrumb")
        if PLACEHOLDER.search(text):
            failures.append(f"{relative}: unresolved placeholder or empty-subject marker")
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        prose = re.sub(r"\[[^\]]+\]\([^)]+\)", "", prose)
        condensed = re.sub(r"[#*|`\-\s]", "", prose)
        if len(condensed) < 120 or not lexical_quality(prose):
            failures.append(f"{relative}: page has insufficient substantive content")
        if EMPTY_HEADING.search(text):
            failures.append(f"{relative}: contains an empty heading")
        for pattern in FORBIDDEN:
            if pattern.search(text):
                failures.append(f"{relative}: browser/localhost preview is forbidden")
        for raw in LINK.findall(text):
            target = resolve_link(path, raw)
            if target is None:
                continue
            try:
                target.relative_to(repo_root)
            except ValueError:
                failures.append(f"{relative}: link leaves repository: {raw}")
                continue
            if not target.is_file():
                failures.append(f"{relative}: broken relative link: {raw}")
            if "wiki/apps/" in target.as_posix():
                parts = target.parts
                try:
                    linked_version = parts[parts.index("versions") + 1]
                except (ValueError, IndexError):
                    failures.append(
                        f"{relative}: wiki link is not versioned: {raw}"
                    )
                else:
                    if linked_version != version_dir.name:
                        failures.append(
                            f"{relative}: {version_dir.name} links wiki {linked_version}: {raw}"
                        )
    if contract_path is not None:
        if not contract_path.is_file():
            failures.append(f"missing canonical analysis contract: {contract_path}")
        else:
            failures.extend(validate_contract(load_json(contract_path)))
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version_dir", type=Path)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--contract", type=Path)
    args = parser.parse_args(argv)
    failures = check(args.version_dir, args.repo_root, args.contract)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    count = len(list(args.version_dir.rglob("*.md")))
    print(f"PASS — {args.version_dir.name}: {count} linked Markdown pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
