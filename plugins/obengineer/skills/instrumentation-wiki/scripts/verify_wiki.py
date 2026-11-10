#!/usr/bin/env python3
"""Prove an agent wiki is retrievable, resolvable, and safe to load into context.

    python3 verify_wiki.py "wiki/apps/<app>/versions/V<N>"

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
from datetime import date
from pathlib import Path, PurePosixPath

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install PyYAML==6.0.3")

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

VERSION_REQUIRED = [
    "index.md",
    "meta/versions.md",
    "meta/run-log.md",
    "meta/decisions.md",
    "implementation/work-orders/index.md",
]
SERVICE_REQUIRED = [
    "index.md",
    "contract/cross-cutting.md",
    # The value model exists on every run. With no business inputs it holds the
    # arithmetic with its coefficients visibly unfilled, which is what makes the
    # next run a coefficient update rather than a fresh research exercise.
    "business/value-model.md",
]

# Every figure in the value model carries its provenance. An unlabelled number
# is indistinguishable from an invented one, and invented business numbers are
# the fastest way to lose an executive audience.
VALUE_LABELS = ("stated", "measured", "public", "derived")

NOTE_TYPES = {
    "architecture", "business-transaction", "bt", "catalog", "contract",
    "dashboard", "decision", "detector", "finding", "index", "metric",
    "objective", "operation", "reference", "run-log", "service", "sli",
    "slo", "use-case", "workflow", "work-order",
}
NOTE_STATUS = {
    "accepted", "active", "blocked", "changed", "deferred", "designed",
    "implemented", "not-applicable", "observed", "proposed", "ready",
    "resolved", "retained", "superseded", "retired", "verified",
}
FINDING_STATUS = {
    "deferred", "false-positive", "fixed", "open", "regressed",
    "risk-accepted",
}
WORK_ORDER_STATUS = {
    "proposed", "ready", "in-progress", "blocked", "retained", "changed",
    "superseded", "implemented", "verified", "retired",
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
    ("the retrieval rule", re.compile(r"do not load (?:every version or )?the whole wiki", re.I)),
    ("the same-commit update rule", re.compile(r"same commit", re.I)),
]

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
WIKILINK = re.compile(r"\[\[([^\]|#]+)")
WORK_ORDER_ID = re.compile(r"^WO-[0-9]{3,}$")
SELECTOR = re.compile(
    r"^(?:work-order:WO-[0-9]{3,}|"
    r"(?:business-transaction|workflow|use-case|detector|objective|config):"
    r"[a-z0-9][a-z0-9._-]*)$"
)
WORK_ORDER_SECTIONS = (
    "findings",
    "use cases",
    "workflows and business transactions",
    "target selectors",
    "repository legs",
    "dependencies",
    "acceptance evidence",
    "verification criteria",
    "coordination",
)


def markdown_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.M))
    return {
        match.group(1).strip().lower(): text[
            match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)
        ].strip()
        for index, match in enumerate(matches)
    }


def meaningful(text: object) -> bool:
    if not isinstance(text, str):
        return False
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9._-]*", text)
    return len(tokens) >= 4 and len(set(token.casefold() for token in tokens)) >= 3


def authorized_relative_path(value: object, authorized: list[str]) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        return False
    normalized = path.as_posix().rstrip("/") + "/"
    for parent in authorized:
        if not isinstance(parent, str) or not parent:
            continue
        parent_path = PurePosixPath(parent)
        if parent_path.is_absolute() or ".." in parent_path.parts:
            continue
        parent_value = parent_path.as_posix().rstrip("/")
        if parent_value in {"", "."} or normalized.startswith(parent_value + "/"):
            return True
    return False


def wiki_root_of(service: Path) -> Path | None:
    """The `wiki/` directory that holds `apps/<app>/versions/V<N>/`."""
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
    # Fall back for callers outside the expected versioned wiki tree.
    return resolved.parents[4] if len(resolved.parents) >= 5 else Path(".")


def note_outside_service(target: str, note: Path, service: Path) -> Path | None:
    """Resolve a path wikilink that leaves this service, including a shared service.

    A shared service is recorded under each app. The join is a versioned path
    resolved from `wiki/`.
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


def frontmatter(text: str) -> dict | None:
    m = FRONTMATTER.match(text)
    if not m:
        return None
    try:
        fields = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return fields if isinstance(fields, dict) else None


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


def check(target: Path, repo_root: Path, index_max_lines: int) -> list[str]:
    failures: list[str] = []
    # New invocations pass wiki/apps/<app>/versions/V<N>. Accepting a service
    # path remains a CLI migration aid, but validation always covers every
    # service in that version.
    if target.parent.name == "services":
        version_root = target.parents[1]
    else:
        version_root = target
    if version_root.parent.name != "versions" or not re.fullmatch(
        r"V[1-9][0-9]*", version_root.name
    ):
        return [
            "wiki path must be wiki/apps/<app>/versions/V<N>"
        ]
    app_root = version_root.parents[1]
    version = version_root.name
    services_root = version_root / "services"
    services = sorted(
        path for path in services_root.iterdir() if path.is_dir()
    ) if services_root.is_dir() else []
    if not services:
        failures.append("version has no services/<service> directories")
    app_work_orders = sorted(
        (version_root / "implementation" / "work-orders").glob("*.md")
    )
    notes = sorted(version_root.rglob("*.md"))
    rel = {
        p: str(p.relative_to(repo_root)) if p.is_relative_to(repo_root) else str(p)
        for p in notes
    }

    # ---- layout ----------------------------------------------------------
    for required in VERSION_REQUIRED:
        if not (version_root / required).is_file():
            failures.append(f"missing required note: {required}")
    for service in services:
        for required in SERVICE_REQUIRED:
            if not (service / required).is_file():
                failures.append(
                    f"{service.relative_to(version_root)}: "
                    f"missing required note: {required}"
                )

    acceptance_path = (
        repo_root / "docs" / "observability" / "analysis" / app_root.name /
        version / "acceptance.yaml"
    )
    is_accepted = False
    # Proposed analysis versions must pass before acceptance. When an acceptance
    # record exists, verify its content digest and version binding.
    if acceptance_path.is_file():
        module_path = Path(__file__).with_name("verify_analysis_acceptance.py")
        spec = importlib.util.spec_from_file_location(
            "verify_analysis_acceptance_record", module_path
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        accepted, acceptance_failures = module.parse_record(acceptance_path)
        record_failures = [
            f"acceptance record: {failure}" for failure in acceptance_failures
        ]
        failures.extend(record_failures)
        if not acceptance_failures:
            verification_failures = [
                f"acceptance record: {failure}"
                for failure in module.verify(
                    repo_root,
                    Path(accepted["analysis"]),
                    accepted["version"],
                    accepted.get("analysis_content_digest"),
                    accepted["analysis_content_commit"],
                    accepted["schema_version"],
                )
            ]
            failures.extend(verification_failures)
            is_accepted = not verification_failures

    # ---- frontmatter -----------------------------------------------------
    fields: dict[Path, dict] = {}
    for p in notes:
        fm = frontmatter(p.read_text())
        if fm is None:
            failures.append(f"{rel[p]}: no YAML frontmatter")
            continue
        fields[p] = fm
        for key in (
            "title", "type", "app", "version", "status", "updated",
            "sources", "work_orders",
        ):
            if not fm.get(key):
                if key in ("sources", "work_orders") and fm.get(key) == []:
                    continue
                failures.append(f"{rel[p]}: frontmatter has no {key}")
        if fm.get("app") and fm["app"] != app_root.name:
            failures.append(
                f"{rel[p]}: app {fm['app']!r} does not match {app_root.name!r}"
            )
        if fm.get("version") and fm["version"] != version:
            failures.append(
                f"{rel[p]}: version {fm['version']!r} does not match {version}"
            )
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
        for key in ("sources", "work_orders"):
            if key in fm and not isinstance(fm[key], list):
                failures.append(f"{rel[p]}: {key} must be a list")
            elif isinstance(fm.get(key), list) and not all(
                isinstance(item, str) and item for item in fm[key]
            ):
                failures.append(f"{rel[p]}: {key} entries must be non-empty strings")
        updated = fm.get("updated", "")
        if isinstance(updated, date):
            updated = updated.isoformat()
        if updated and (
            not isinstance(updated, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated)
        ):
            failures.append(f"{rel[p]}: updated {updated!r} is not an ISO date")
        if "[Analysis](" not in body(p.read_text()):
            failures.append(f"{rel[p]}: no Analysis breadcrumb")

    implementation_map = repo_root / "docs" / "observability" / "implementation-map.json"
    map_data: dict = {}
    repositories: dict[str, list[str]] = {}
    mapped_targets: dict[str, str] = {}
    mapped_repositories: dict[str, set[str]] = {}
    if implementation_map.is_file():
        try:
            map_data = json.loads(implementation_map.read_text())
            repositories = {
                repository.get("id"): repository.get("authorized_paths", [])
                for repository in map_data.get("repositories", [])
                if isinstance(repository, dict)
                and isinstance(repository.get("id"), str)
                and isinstance(repository.get("authorized_paths"), list)
            }
            mapped_targets = {
                target.get("selector"): target.get("work_order")
                for target in map_data.get("targets", [])
                if isinstance(target, dict)
            }
            for target in map_data.get("targets", []):
                if (
                    isinstance(target, dict)
                    and isinstance(target.get("work_order"), str)
                    and isinstance(target.get("repositories"), list)
                ):
                    mapped_repositories.setdefault(
                        target["work_order"], set()
                    ).update(
                        value for value in target["repositories"]
                        if isinstance(value, str)
                    )
        except json.JSONDecodeError:
            failures.append("implementation map is not valid JSON")
        mapped_orders = set(mapped_targets.values())
        available_orders = {path.stem for path in app_work_orders}
        for order in sorted(mapped_orders - available_orders):
            failures.append(f"implementation map has no app-level work order: {order}")
    else:
        failures.append("missing docs/observability/implementation-map.json")

    # ---- unified work orders ---------------------------------------------
    work_order_fields: dict[str, dict] = {}
    work_order_bodies: dict[str, str] = {}
    for p in app_work_orders:
        if p.name == "index.md":
            continue
        fm = fields.get(p, {})
        order_id = fm.get("work_order_id")
        if not isinstance(order_id, str) or not WORK_ORDER_ID.fullmatch(order_id):
            failures.append(f"{rel[p]}: frontmatter has invalid work_order_id")
            order_id = p.stem
        elif order_id != p.stem:
            failures.append(f"{rel[p]}: work_order_id does not match filename")
        work_order_fields[order_id] = fm
        content = body(p.read_text())
        work_order_bodies[order_id] = content
        sections = markdown_sections(content)
        for heading in WORK_ORDER_SECTIONS:
            if heading not in sections:
                failures.append(f"{rel[p]}: work order is missing ## {heading}")
            elif heading != "dependencies" and not meaningful(sections[heading]):
                failures.append(f"{rel[p]}: ## {heading} is not meaningful")
        if "jira issues" not in sections and "manual issue text" not in sections:
            failures.append(f"{rel[p]}: work order needs Jira issues or manual issue text")

        selectors = fm.get("selectors")
        if not isinstance(selectors, list) or not selectors:
            failures.append(f"{rel[p]}: selectors must be a non-empty YAML list")
            selectors = []
        for selector in selectors:
            if not isinstance(selector, str) or not SELECTOR.fullmatch(selector):
                failures.append(f"{rel[p]}: invalid target selector {selector!r}")
            elif mapped_targets.get(selector) != order_id:
                failures.append(
                    f"{rel[p]}: selector {selector!r} is not mapped to {order_id}"
                )
            elif selector not in sections.get("target selectors", ""):
                failures.append(
                    f"{rel[p]}: ## target selectors does not name {selector!r}"
                )

        dependencies = fm.get("depends_on")
        if not isinstance(dependencies, list) or not all(
            isinstance(value, str) and WORK_ORDER_ID.fullmatch(value)
            for value in dependencies
        ):
            failures.append(f"{rel[p]}: depends_on must contain work-order IDs")

        legs = fm.get("repository_legs")
        if not isinstance(legs, list) or not legs:
            failures.append(f"{rel[p]}: repository_legs must be a non-empty YAML list")
            legs = []
        for index, leg in enumerate(legs):
            leg_path = f"{rel[p]}: repository_legs[{index}]"
            if not isinstance(leg, dict):
                failures.append(f"{leg_path} must be an object")
                continue
            repository = leg.get("repository")
            if not isinstance(repository, str) or not repository:
                failures.append(f"{leg_path}.repository is required")
                authorized = []
            elif repository not in repositories:
                failures.append(f"{leg_path} references unknown repository {repository!r}")
                authorized = []
            else:
                authorized = repositories[repository]
            paths = leg.get("paths")
            if not isinstance(paths, list) or not paths or not all(
                authorized_relative_path(value, authorized) for value in paths
            ):
                failures.append(f"{leg_path}.paths must be authorized relative paths")
            for key in ("changes", "tests"):
                values = leg.get(key)
                if not isinstance(values, list) or not values or not all(
                    meaningful(value) for value in values
                ):
                    failures.append(f"{leg_path}.{key} is not meaningful")
        actual_repositories = {
            repository
            for leg in legs
            if isinstance(leg, dict)
            for repository in (leg.get("repository"),)
            if isinstance(repository, str)
        }
        if actual_repositories != mapped_repositories.get(order_id, set()):
            failures.append(
                f"{rel[p]}: repository legs {sorted(actual_repositories)} do not "
                f"match mapped repositories {sorted(mapped_repositories.get(order_id, set()))}"
            )
        repository_section = sections.get("repository legs", "")
        for repository in actual_repositories:
            if isinstance(repository, str) and repository not in repository_section:
                failures.append(
                    f"{rel[p]}: ## repository legs does not name {repository!r}"
                )

        status = fm.get("status")
        dependencies = dependencies if isinstance(dependencies, list) else []
        dependency_section = sections.get("dependencies", "")
        if dependencies:
            for dependency in dependencies:
                if dependency not in dependency_section:
                    failures.append(
                        f"{rel[p]}: ## dependencies does not name {dependency}"
                    )
        elif not re.search(r"\bnone\b", dependency_section, re.I):
            failures.append(f"{rel[p]}: ## dependencies must explicitly say none")
        if is_accepted and status == "proposed":
            failures.append(
                f"{rel[p]}: accepted versions cannot leave work orders proposed"
            )
        if is_accepted and status == "blocked" and not dependencies:
            failures.append(
                f"{rel[p]}: accepted dependency-free work order must be ready"
            )
        if not is_accepted and status == "ready":
            failures.append(f"{rel[p]}: work orders cannot be ready before acceptance")
        if not is_accepted:
            expected = "blocked" if dependencies else "proposed"
            if status != expected:
                failures.append(
                    f"{rel[p]}: before acceptance status must be {expected}"
                )

    order_ids = set(work_order_fields)
    graph: dict[str, list[str]] = {}
    for order_id, fm in work_order_fields.items():
        dependencies = fm.get("depends_on", [])
        dependencies = dependencies if isinstance(dependencies, list) else []
        graph[order_id] = dependencies
        unknown = set(dependencies) - order_ids
        if unknown:
            failures.append(
                f"{order_id}: dependencies do not exist: {sorted(unknown)}"
            )
        if fm.get("status") == "ready":
            incomplete = {
                dependency
                for dependency in dependencies
                if work_order_fields.get(dependency, {}).get("status")
                not in {"implemented", "verified", "retired"}
            }
            if incomplete:
                failures.append(
                    f"{order_id}: ready work order has incomplete dependencies "
                    f"{sorted(incomplete)}"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(order_id: str, trail: list[str]) -> None:
        if order_id in visiting:
            failures.append(
                "work-order dependency cycle: " + " -> ".join([*trail, order_id])
            )
            return
        if order_id in visited:
            return
        visiting.add(order_id)
        for dependency in graph.get(order_id, []):
            if dependency in graph:
                visit(dependency, [*trail, order_id])
        visiting.remove(order_id)
        visited.add(order_id)

    for order_id in sorted(graph):
        visit(order_id, [])

    # ---- links -----------------------------------------------------------
    # Obsidian resolves a bare name by shortest path, a slashed name by path.
    # Both are legal here; an ambiguous bare name is not, because the tool and
    # the agent may pick different notes.
    by_path = {
        str(p.relative_to(version_root).with_suffix("")): p
        for p in notes if p.is_relative_to(version_root)
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
                str((p.parent / target).resolve().relative_to(version_root.resolve()))
                if (p.parent / target).resolve().is_relative_to(version_root.resolve())
                else target,
            }
            if candidates & set(by_path):
                continue
            if note_outside_service(target, p, version_root) is not None:
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

    # Every object-to-order edge must be reciprocal. The work order links the
    # canonical note path; the note declares the same ID in frontmatter.
    for note, fm in fields.items():
        if fm.get("type") == "work-order":
            continue
        for order_id in fm.get("work_orders", []) if isinstance(fm.get("work_orders"), list) else []:
            if order_id not in work_order_bodies:
                failures.append(f"{rel[note]}: references missing work order {order_id}")
                continue
            note_key = str(note.relative_to(version_root).with_suffix(""))
            linked = {
                match.group(1).strip().rstrip("/")
                for match in WIKILINK.finditer(work_order_bodies[order_id])
            }
            if note_key not in linked:
                failures.append(
                    f"{order_id}: missing reverse link to [[{note_key}]]"
                )
    for order_id, content in work_order_bodies.items():
        sections = markdown_sections(content)
        for heading in ("findings", "use cases", "workflows and business transactions"):
            for match in WIKILINK.finditer(sections.get(heading, "")):
                target = match.group(1).strip().rstrip("/")
                note = by_path.get(target)
                if note is not None and order_id not in fields.get(note, {}).get("work_orders", []):
                    failures.append(
                        f"{order_id}: reverse-linked note [[{target}]] does not declare the work order"
                    )

    # ---- index: a map, not a summary -------------------------------------
    indexes = [version_root / "index.md", *[service / "index.md" for service in services]]
    for index in indexes:
        if not index.is_file():
            continue
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
                version_root / "implementation" / "work-orders"
                if directory == "implementation/work-orders"
                else index.parent / directory
            )
            actual = (
                len([path for path in counted_root.glob("*.md") if path.name != "index.md"])
                if counted_root.is_dir() else 0
            )
            if int(claimed.group()) != actual:
                failures.append(
                    f"index.md claims {claimed.group()} for {label!r}; "
                    f"{directory}/ holds {actual}")

    # ---- promotion: a note earns its file --------------------------------
    for service in services:
        for directory in ("workflows", "detectors"):
            root = service / directory
            for p in root.glob("*.md") if root.is_dir() else []:
                content = [
                    line for line in body(p.read_text()).split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
                if len(content) < 3:
                    failures.append(
                        f"{rel[p]}: promoted note carries {len(content)} line(s) "
                        "of content. A note earns its file — fold it back into "
                        "its catalogue note."
                    )

    # ---- versions --------------------------------------------------------
    versions = version_root / "meta" / "versions.md"
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
    for service in services:
        model = service / "business" / "value-model.md"
        if model.is_file():
            text = model.read_text()
            if not any(label in text.lower() for label in VALUE_LABELS):
                failures.append(
                    f"{service.name}/business/value-model.md labels no figure "
                    f"{VALUE_LABELS}; an unlabelled number reads as an invented one"
                )

        evidence = service / "business" / "public-evidence.md"
        if evidence.is_file():
            text = evidence.read_text()
            urls = re.findall(r"https?://\S+", text)
            if urls and not re.search(r"\bread\b", text, re.I):
                failures.append(
                    f"{service.name}/business/public-evidence.md cites sources "
                    "but records no read date; a citation with no read date points "
                    "at a page that may have changed"
                )

    # ---- host pointers ---------------------------------------------------
    app_index = app_root / "index.md"
    index_path = str(app_index.relative_to(repo_root)) if app_index.is_file() and \
        app_index.resolve().is_relative_to(repo_root.resolve()) else "index.md"
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
    security_files = list(version_root.rglob("*"))
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
    ap.add_argument("wiki", type=Path, help="wiki/apps/<app>/versions/V<N>")
    ap.add_argument("--repo-root", type=Path,
                    help="where the host pointers live (default: the wiki's parent repo)")
    ap.add_argument("--index-max-lines", type=int, default=200)
    args = ap.parse_args(argv)

    wiki = args.wiki
    if not wiki.is_dir():
        sys.exit(f"not a directory: {wiki}")

    repo_root = args.repo_root
    if repo_root is None:
        repo_root = repo_root_of(wiki)

    failures = check(wiki, repo_root, args.index_max_lines)
    version = wiki.parents[1] if wiki.parent.name == "services" else wiki
    notes = len(list(version.rglob("*.md")))
    if failures:
        print(f"FAIL — {len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASS — {version.name} wiki: {notes} notes, every link resolves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
