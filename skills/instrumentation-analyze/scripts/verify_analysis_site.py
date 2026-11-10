#!/usr/bin/env python3
"""Validate a versioned linked analysis site without starting a preview server."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VERSION = re.compile(r"^V[1-9][0-9]*$")
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
VERSION_LINK = re.compile(r"\[V[1-9][0-9]*\]")
FORBIDDEN = (
    re.compile(r"https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?", re.I),
    re.compile(r"\bpython(?:3)?\s+-m\s+http\.server\b"),
)
REQUIRED_HEADINGS = (
    "Contents",
    "Analysis summary",
    "Changes in this version",
)
CONTENTS_ROWS = (
    "Architecture",
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


def resolve_link(source: Path, raw: str) -> Path | None:
    target = raw.strip().split("#", 1)[0]
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return None
    candidate = (source.parent / target).resolve()
    if candidate.is_dir():
        candidate = candidate / "index.md"
    return candidate


def check(version_dir: Path, repo_root: Path | None = None) -> list[str]:
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

    index_text = index.read_text()
    if not VERSION_LINK.search(index_text):
        failures.append("index.md has no [V<N>] version selector")
    for heading in REQUIRED_HEADINGS:
        if not re.search(rf"^##+\s+.*{re.escape(heading)}", index_text, re.M | re.I):
            failures.append(f"index.md is missing heading: {heading}")
    h2 = re.findall(r"^##\s+(.+?)\s*$", index_text, re.M)
    allowed_h2 = {heading.lower() for heading in REQUIRED_HEADINGS}
    expanded = [heading for heading in h2 if heading.lower() not in allowed_h2]
    if expanded:
        failures.append(
            "index.md expands detail sections instead of using the approved compact "
            f"index: {expanded}"
        )
    if "Side-panel navigation" not in index_text:
        failures.append("index.md has no Side-panel navigation notice")
    if "Next steps" not in index_text and "implementation can start" not in index_text:
        failures.append("index.md has neither awaiting-acceptance nor accepted next steps")
    if not re.search(
        r"\|\s*Priority findings\s*\|\s*Primary use cases\s*\|",
        index_text,
        re.I,
    ):
        failures.append("index.md has no compact findings/use-cases preview")
    positions = []
    for row in CONTENTS_ROWS:
        match = re.search(
            rf"^\|\s*{re.escape(row)}\s*\|.*$",
            index_text,
            re.M | re.I,
        )
        if not match:
            failures.append(f"index.md Contents is missing row: {row}")
        else:
            positions.append(match.start())
            if not LINK.search(match.group()):
                failures.append(f"index.md Contents row has no Open link: {row}")
    if positions != sorted(positions):
        failures.append("index.md Contents rows are out of approved order")

    repo_root = (repo_root or next(
        (parent for parent in version_dir.parents if (parent / ".git").exists()),
        version_dir.parents[-1],
    )).resolve()

    for path in markdown:
        text = path.read_text()
        relative = path.relative_to(version_dir)
        if path != index and "[Analysis](" not in text:
            failures.append(f"{relative}: no Analysis breadcrumb")
        if "Not in evidence" in text:
            failures.append(
                f"{relative}: empty subjects belong on Suggested additions, not a page"
            )
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
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version_dir", type=Path)
    parser.add_argument("--repo-root", type=Path)
    args = parser.parse_args(argv)
    failures = check(args.version_dir, args.repo_root)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    count = len(list(args.version_dir.rglob("*.md")))
    print(f"PASS — {args.version_dir.name}: {count} linked Markdown pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
