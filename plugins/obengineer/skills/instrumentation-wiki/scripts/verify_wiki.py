#!/usr/bin/env python3
"""Prove an agent wiki is retrievable, resolvable, and safe to load into context.

    python3 verify_wiki.py "wiki/<Customer>/<app>"

The document has verify_render.py; without an equivalent the wiki's rules are
enforced by whoever remembers them. Checks, all mechanical:

  layout       the notes every wiki must have, whatever the target
  frontmatter  type, status, and updated on every note, from the allowed sets
  links        every [[wikilink]] resolves, and no bare name is ambiguous
  index        a map rather than a summary: short, and its counts match the tree
  promotion    a promoted note carries more than its name
  versions     a row per component with a provenance column
  pointers     the host files exist, point at the index, and stay pointers
  secrets      no credential-shaped value reached a note

Specification: skills/references/agent-wiki.md. When the two disagree, the
specification wins and this script is what needs fixing.

Exit code 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Identical to verify_render.py's list: a value unsafe in a customer document is
# more dangerous in a wiki, which agent hosts load by default.
SECRET_PATTERNS = [
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+")),
    ("opaque token", re.compile(r"\b[0-9a-f]{32,}\b")),
    ("aws access key", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[A-Z0-9]{12,}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("github token", re.compile(r"\bgh[posur]_[A-Za-z0-9]{20,}\b")),
    ("stripe key", re.compile(r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("basic-auth url", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
]

REQUIRED = [
    "index.md",
    "meta/versions.md",
    "meta/run-log.md",
    "meta/decisions.md",
    "contract/cross-cutting.md",
    "contract/attribute-schema.json",
]

NOTE_TYPES = {"index", "reference", "bt", "workflow", "use-case", "finding",
              "detector", "sli", "work-order"}
NOTE_STATUS = {"proposed", "designed", "implemented", "verified", "retired"}
FINDING_STATUS = {"open", "fixed", "regressed", "accepted"}

# index.md count rows, and the directory each is counted from. A count that
# disagrees with the tree is worse than an absent one: it is read as current.
COUNTED = {
    "open findings": "findings",
    "business transactions": "business-transactions",
    "use cases": "use-cases",
    "work orders": "implementation/work-orders",
}
COUNTED_ALIASES = {"objectives": "slos", "objectives, all `proposed`": "slos"}

# The retrieval discipline the host pointers exist to carry.
POINTER_RULES = [
    ("the retrieval rule", re.compile(r"do not load the whole wiki", re.I)),
    ("the same-commit update rule", re.compile(r"same commit", re.I)),
]

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
WIKILINK = re.compile(r"\[\[([^\]|#]+)")


def frontmatter(text: str) -> dict[str, str] | None:
    m = FRONTMATTER.match(text)
    if not m:
        return None
    fields: dict[str, str] = {}
    for line in m.group(1).split("\n"):
        km = re.match(r"([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km:
            fields[km.group(1)] = km.group(2).strip()
    return fields


def body(text: str) -> str:
    m = FRONTMATTER.match(text)
    return text[m.end():] if m else text


def check(app: Path, repo_root: Path, index_max_lines: int) -> list[str]:
    failures: list[str] = []
    notes = sorted(p for p in app.rglob("*.md"))
    rel = {p: str(p.relative_to(app)) for p in notes}

    # ---- layout ----------------------------------------------------------
    for required in REQUIRED:
        if not (app / required).is_file():
            failures.append(f"missing required note: {required}")

    # ---- frontmatter -----------------------------------------------------
    fields: dict[Path, dict[str, str]] = {}
    for p in notes:
        fm = frontmatter(p.read_text())
        if fm is None:
            failures.append(f"{rel[p]}: no YAML frontmatter")
            continue
        fields[p] = fm
        for key in ("title", "type", "status", "updated"):
            if not fm.get(key):
                failures.append(f"{rel[p]}: frontmatter has no {key}")
        kind = fm.get("type", "")
        if kind and kind not in NOTE_TYPES:
            failures.append(f"{rel[p]}: type {kind!r} is not one of {sorted(NOTE_TYPES)}")
        allowed = FINDING_STATUS if kind == "finding" else NOTE_STATUS
        status = fm.get("status", "")
        if status and status not in allowed:
            failures.append(
                f"{rel[p]}: status {status!r} is not one of {sorted(allowed)} for type {kind!r}")
        updated = fm.get("updated", "")
        if updated and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
            failures.append(f"{rel[p]}: updated {updated!r} is not an ISO date")

    # ---- links -----------------------------------------------------------
    # Obsidian resolves a bare name by shortest path, a slashed name by path.
    # Both are legal here; an ambiguous bare name is not, because the tool and
    # the agent may pick different notes.
    by_path = {str(p.relative_to(app).with_suffix("")): p for p in notes}
    by_stem: dict[str, list[Path]] = {}
    for p in notes:
        by_stem.setdefault(p.stem, []).append(p)

    broken: list[str] = []
    ambiguous: list[str] = []
    for p in notes:
        for m in WIKILINK.finditer(body(p.read_text())):
            target = m.group(1).strip().rstrip("/")
            if not target:
                continue
            candidates = {
                target,
                target.lstrip("./"),
                str((p.parent / target).resolve().relative_to(app.resolve()))
                if (p.parent / target).resolve().is_relative_to(app.resolve()) else target,
            }
            if candidates & set(by_path):
                continue
            hits = by_stem.get(Path(target).name, [])
            if len(hits) > 1:
                ambiguous.append(f"{rel[p]} -> [[{target}]] ({len(hits)} notes share that name)")
            elif not hits:
                broken.append(f"{rel[p]} -> [[{target}]]")
    if broken:
        failures.append(f"{len(broken)} broken wikilink(s): {broken[:5]}")
    if ambiguous:
        failures.append(f"{len(ambiguous)} ambiguous wikilink(s): {ambiguous[:5]}")

    # ---- index: a map, not a summary -------------------------------------
    index = app / "index.md"
    if index.is_file():
        text = index.read_text()
        lines = len(text.strip().split("\n"))
        if lines > index_max_lines:
            failures.append(
                f"index.md is {lines} lines; the one note loaded unconditionally stays "
                f"under {index_max_lines}. Move detail into the notes it links to.")
        if not WIKILINK.search(text):
            failures.append("index.md has no wikilinks — it is a summary, not a map")

        for row in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|", text, re.M):
            label = row.group(1).strip().strip("*").lower()
            directory = COUNTED.get(label) or COUNTED_ALIASES.get(label)
            if not directory:
                continue
            claimed = re.search(r"\d+", row.group(2))
            if not claimed:
                continue
            actual = len(list((app / directory).glob("*.md"))) if (app / directory).is_dir() else 0
            if int(claimed.group()) != actual:
                failures.append(
                    f"index.md claims {claimed.group()} for {label!r}; "
                    f"{directory}/ holds {actual}")

    # ---- promotion: a note earns its file --------------------------------
    for directory in ("workflows", "detectors"):
        for p in (app / directory).glob("*.md") if (app / directory).is_dir() else []:
            content = [ln for ln in body(p.read_text()).split("\n")
                       if ln.strip() and not ln.strip().startswith("#")]
            if len(content) < 3:
                failures.append(
                    f"{rel[p]}: promoted note carries {len(content)} line(s) of content. "
                    "A note earns its file — fold it back into its catalogue note.")

    # ---- versions --------------------------------------------------------
    versions = app / "meta" / "versions.md"
    if versions.is_file():
        text = versions.read_text()
        header = next((ln for ln in text.split("\n")
                       if ln.startswith("|") and "provenance" in ln.lower()), None)
        if header is None:
            failures.append("meta/versions.md has no table column named provenance")
        rows = [ln for ln in text.split("\n")
                if ln.startswith("|") and not re.fullmatch(r"[|\s:-]+", ln)]
        if len(rows) < 2:  # the header, plus at least one component
            failures.append("meta/versions.md records no component versions")

    # ---- host pointers ---------------------------------------------------
    index_path = str(index.relative_to(repo_root)) if index.is_file() and \
        index.resolve().is_relative_to(repo_root.resolve()) else "index.md"
    for pointer in (".cursor/rules/obengineer-wiki.mdc", "CLAUDE.md", "AGENTS.md"):
        path = repo_root / pointer
        if not path.is_file():
            failures.append(f"no host pointer at {pointer}; agents will not find the wiki")
            continue
        text = path.read_text()
        if index_path not in text and "index.md" not in text:
            failures.append(f"{pointer} does not name the wiki index")
        for label, pattern in POINTER_RULES:
            if not pattern.search(text):
                failures.append(f"{pointer} does not carry {label}")

    # ---- secrets ---------------------------------------------------------
    for p in sorted(app.rglob("*")):
        if not p.is_file() or p.suffix not in (".md", ".json", ".yaml", ".yml"):
            continue
        text = p.read_text(errors="replace")
        for label, pattern in SECRET_PATTERNS:
            hits = pattern.findall(text)
            if hits:
                failures.append(
                    f"possible {label} in {p.relative_to(app)} ({len(hits)} match(es))")

    return failures


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("app", type=Path, help="wiki/<Customer>/<app>")
    ap.add_argument("--repo-root", type=Path,
                    help="where the host pointers live (default: the wiki's parent repo)")
    ap.add_argument("--index-max-lines", type=int, default=200)
    args = ap.parse_args(argv)

    app = args.app
    if not app.is_dir():
        sys.exit(f"not a directory: {app}")

    repo_root = args.repo_root
    if repo_root is None:
        # wiki/<Customer>/<app> — three levels up is the repository root.
        repo_root = app.parent.parent.parent if len(app.resolve().parents) >= 3 else Path(".")

    failures = check(app, repo_root, args.index_max_lines)
    notes = len(list(app.rglob("*.md")))
    if failures:
        print(f"FAIL — {len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASS — {app.name} wiki: {notes} notes, every link resolves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
