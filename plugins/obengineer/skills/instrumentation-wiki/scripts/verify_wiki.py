#!/usr/bin/env python3
"""Prove an agent wiki is retrievable, resolvable, and safe to load into context.

    python3 verify_wiki.py "wiki/apps/<app>/services/<service>"

The document has verify_render.py; without an equivalent the wiki's rules are
enforced by whoever remembers them. Checks, all mechanical:

  layout       the notes every wiki must have, whatever the target
  frontmatter  type, status, and updated on every note, from the allowed sets
  links        every [[wikilink]] resolves, and no bare name is ambiguous
  index        a map rather than a summary: short, and its counts match the tree
  promotion    a promoted note carries more than its name
  versions     a row per component with a provenance column
  value        the value model labels its figures, and cited sources carry read dates
  pointers     the host files exist, point at the index, and stay pointers
  secrets      no credential-shaped value reached a note

Specification: skills/references/agent-wiki.md. When the two disagree, the
specification wins and this script is what needs fixing.

Exit code 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
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
    # The value model exists on every run. With no business inputs it holds the
    # arithmetic with its coefficients visibly unfilled, which is what makes the
    # next run a coefficient update rather than a fresh research exercise.
    "business/value-model.md",
]

# Every figure in the value model carries its provenance. An unlabelled number
# is indistinguishable from an invented one, and invented business numbers are
# the fastest way to lose an executive audience.
VALUE_LABELS = ("stated", "measured", "public", "derived")

NOTE_TYPES = {"index", "reference", "bt", "workflow", "use-case", "finding",
              "detector", "sli", "work-order"}
NOTE_STATUS = {"proposed", "designed", "implemented", "verified", "retired"}
FINDING_STATUS = {"open", "fixed", "regressed", "risk-accepted"}
WORK_ORDER_STATUS = {
    "proposed", "accepted", "in-progress", "blocked", "implemented", "verified", "retired"
}

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


def wiki_root_of(service: Path) -> Path | None:
    """The `wiki/` directory that holds `apps/<app>/services/<service>/`."""
    resolved = service.resolve()
    for parent in (resolved, *resolved.parents):
        if parent.name == "wiki":
            return parent
    return None


def repo_root_of(service: Path) -> Path:
    """Host pointers live in the repository that contains `wiki/`."""
    wiki = wiki_root_of(service)
    if wiki is not None and wiki.parent != wiki:
        return wiki.parent
    resolved = service.resolve()
    # wiki/apps/<app>/services/<service> — five levels up is the repository root.
    return resolved.parents[4] if len(resolved.parents) >= 5 else Path(".")


def note_outside_service(target: str, note: Path, service: Path) -> Path | None:
    """Resolve a path wikilink that leaves this service, including a shared service.

    A shared service is recorded under each app. The join is a path such as
    `apps/<other-app>/services/<service>/index`, resolved from `wiki/`.
    """
    wiki = wiki_root_of(service)
    if wiki is None or "/" not in target:
        return None
    prospects: list[Path] = []
    if target.startswith("apps/"):
        prospects.append(wiki / target)
    joined = (note.parent / target).resolve()
    try:
        joined.relative_to(wiki)
    except ValueError:
        pass
    else:
        prospects.append(joined)
    for prospect in prospects:
        md = prospect if prospect.suffix == ".md" else Path(str(prospect) + ".md")
        if md.is_file():
            return md
    return None


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


def acceptance_verifier():
    path = Path(__file__).with_name("verify_analysis_acceptance.py")
    spec = importlib.util.spec_from_file_location("verify_analysis_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.verify


def check(app: Path, repo_root: Path, index_max_lines: int) -> list[str]:
    failures: list[str] = []
    app_root = app.parents[1]  # wiki/apps/<app>/services/<service> -> wiki/apps/<app>
    app_work_orders = list((app_root / "implementation" / "work-orders").glob("*.md"))
    notes = sorted(set(app.rglob("*.md")) | set(app_work_orders))
    rel = {
        p: str(p.relative_to(repo_root)) if p.is_relative_to(repo_root) else str(p)
        for p in notes
    }

    # ---- layout ----------------------------------------------------------
    for required in REQUIRED:
        if not (app / required).is_file():
            failures.append(f"missing required note: {required}")

    acceptance_name = re.compile(
        rf"analysis-{re.escape(app_root.name)}-\d{{4}}-\d{{2}}-\d{{2}}"
        r"\.acceptance\.yaml$"
    )
    acceptances = sorted(
        path for path in (repo_root / "docs" / "observability").glob(
            "analysis-*.acceptance.yaml"
        )
        if acceptance_name.fullmatch(path.name)
    )
    if not acceptances:
        failures.append("missing exact-commit analysis acceptance record")
    else:
        acceptance_path = acceptances[-1]
        acceptance = acceptance_path.read_text()
        accepted = {
            match.group(1): match.group(2).strip()
            for match in re.finditer(
                r"^([a-z_]+):\s*([^#\n]+?)\s*$", acceptance, re.M
            )
        }
        required_fields = (
            "status", "analysis", "analysis_commit", "analysis_pr",
            "accepted_by", "accepted_at", "provenance_seal_digest",
        )
        for field in required_fields:
            if not accepted.get(field):
                failures.append(
                    f"acceptance record {acceptance_path.name} is missing {field}"
                )
        if accepted.get("status") != "accepted":
            failures.append(
                f"acceptance record {acceptance_path.name} status is not accepted"
            )
        accepted_analysis = re.compile(
            rf"docs/observability/analysis-{re.escape(app_root.name)}-"
            r"\d{4}-\d{2}-\d{2}\.md$"
        )
        if not accepted_analysis.fullmatch(accepted.get("analysis", "")):
            failures.append(
                f"acceptance record {acceptance_path.name} targets another application"
            )
        if accepted.get("analysis") and accepted.get("analysis_commit"):
            for failure in acceptance_verifier()(
                repo_root, Path(accepted["analysis"]), accepted["analysis_commit"]
            ):
                failures.append(f"acceptance record {acceptance_path.name}: {failure}")
        ledger_path = repo_root / "docs" / "observability" / "provenance-ledger.json"
        if ledger_path.is_file() and accepted.get("provenance_seal_digest"):
            try:
                actual = json.loads(ledger_path.read_text()).get(
                    "seals", {}
                ).get("analysis", {}).get("digest")
            except (json.JSONDecodeError, AttributeError):
                actual = None
            if actual != accepted["provenance_seal_digest"]:
                failures.append(
                    f"acceptance record {acceptance_path.name}: provenance seal mismatch"
                )

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
        allowed = (
            FINDING_STATUS if kind == "finding"
            else WORK_ORDER_STATUS if kind == "work-order"
            else NOTE_STATUS
        )
        status = fm.get("status", "")
        if status and status not in allowed:
            failures.append(
                f"{rel[p]}: status {status!r} is not one of {sorted(allowed)} for type {kind!r}")
        updated = fm.get("updated", "")
        if updated and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
            failures.append(f"{rel[p]}: updated {updated!r} is not an ISO date")

    # ---- unified work orders ---------------------------------------------
    for p in app_work_orders:
        content = body(p.read_text()).lower()
        for heading in (
            "## target selectors",
            "## repository legs",
            "## acceptance evidence",
            "## coordination",
        ):
            if heading not in content:
                failures.append(f"{rel[p]}: work order is missing {heading}")
        if "## jira issues" not in content and "## manual issue text" not in content:
            failures.append(
                f"{rel[p]}: work order needs Jira issues or manual issue text"
            )

    implementation_map = repo_root / "docs" / "observability" / "implementation-map.json"
    if implementation_map.is_file():
        try:
            mapped_orders = {
                target.get("work_order")
                for target in json.loads(implementation_map.read_text()).get("targets", [])
                if isinstance(target, dict)
            }
        except json.JSONDecodeError:
            mapped_orders = set()
        available_orders = {path.stem for path in app_work_orders}
        for order in sorted(mapped_orders - available_orders):
            failures.append(f"implementation map has no app-level work order: {order}")

    # ---- links -----------------------------------------------------------
    # Obsidian resolves a bare name by shortest path, a slashed name by path.
    # Both are legal here; an ambiguous bare name is not, because the tool and
    # the agent may pick different notes.
    by_path = {
        str(p.relative_to(app).with_suffix("")): p
        for p in notes if p.is_relative_to(app)
    }
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
            if note_outside_service(target, p, app) is not None:
                continue
            # A slash is a path. A missing path is broken even when the last
            # segment matches some other note's stem.
            if "/" in target:
                broken.append(f"{rel[p]} -> [[{target}]]")
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
            counted_root = (
                app_root / "implementation" / "work-orders"
                if directory == "implementation/work-orders"
                else app / directory
            )
            actual = len(list(counted_root.glob("*.md"))) if counted_root.is_dir() else 0
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

    # ---- value model -----------------------------------------------------
    # The value case is only as good as the provenance of its inputs, so the
    # note that holds the arithmetic has to say where each number came from.
    model = app / "business" / "value-model.md"
    if model.is_file():
        text = model.read_text()
        if not any(label in text.lower() for label in VALUE_LABELS):
            failures.append(
                "business/value-model.md labels no figure "
                f"{VALUE_LABELS}; an unlabelled number reads as an invented one")

    evidence = app / "business" / "public-evidence.md"
    if evidence.is_file():
        text = evidence.read_text()
        urls = re.findall(r"https?://\S+", text)
        if urls and not re.search(r"\bread\b", text, re.I):
            failures.append(
                "business/public-evidence.md cites sources but records no read date; "
                "a citation with no read date points at a page that may have changed")

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
    security_files = list(app.rglob("*"))
    security_files += list((app_root / "implementation" / "work-orders").glob("*.md"))
    for p in sorted(set(security_files)):
        if not p.is_file() or p.suffix not in (".md", ".json", ".yaml", ".yml"):
            continue
        text = p.read_text(errors="replace")
        for label, pattern in SECRET_PATTERNS:
            hits = pattern.findall(text)
            if hits:
                failures.append(
                    f"possible {label} in "
                    f"{p.relative_to(repo_root) if p.is_relative_to(repo_root) else p} "
                    f"({len(hits)} match(es))")

    return failures


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("app", type=Path, help="wiki/apps/<app>/services/<service>")
    ap.add_argument("--repo-root", type=Path,
                    help="where the host pointers live (default: the wiki's parent repo)")
    ap.add_argument("--index-max-lines", type=int, default=200)
    args = ap.parse_args(argv)

    app = args.app
    if not app.is_dir():
        sys.exit(f"not a directory: {app}")

    repo_root = args.repo_root
    if repo_root is None:
        repo_root = repo_root_of(app)

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
