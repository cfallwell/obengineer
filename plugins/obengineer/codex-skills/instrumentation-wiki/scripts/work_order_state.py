#!/usr/bin/env python3
"""Manage the mutable work-order state ledger and revision chain for an accepted analysis version.

The ledger lives outside the acceptance digest:
  wiki/apps/<app>/implementation/V<N>/state.yaml
  wiki/apps/<app>/implementation/V<N>/revisions/<WO-id>/R<k>.md   (k >= 2)
R1 is the accepted wiki note under wiki/apps/<app>/versions/V<N>/implementation/work-orders/.

A version whose notes carry no `kind` (accepted under contract v3) gets a `mode: legacy`
ledger: no foundation gate, readiness from note status and depends_on, and no revisions.
As on the v3 platform, a `blocked` legacy order with dependencies becomes runnable once
every dependency is complete, unless its repository mapping is unresolved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

WORK_ORDER_ID = re.compile(r"^WO-[A-Za-z0-9._-]+$")
VERSION = re.compile(r"^V[1-9][0-9]*$")
APP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
NAME = re.compile(r"^[a-z][a-z0-9_.]*$")
REVISION_FILE = re.compile(r"^R([1-9][0-9]*)\.md$")

SUBORDINATE_KINDS = (
    "workflow",
    "business-transaction",
    "detector",
    "alert-condition",
    "dashboard",
    "custom-code",
)
KINDS = {"foundation", "use-case", *SUBORDINATE_KINDS}
STATUSES = {
    "proposed", "ready", "blocked", "in-progress", "implemented", "verified", "changed",
}
LEGACY_STATUSES = STATUSES | {"retained", "superseded", "retired"}
SETTABLE_STATUSES = ("in-progress", "implemented", "verified")
COMPLETE = {"implemented", "verified"}
LEGACY_RUNNABLE = {"ready", "in-progress"}
LEGACY_DEPENDENCY_DONE = COMPLETE | {"retired"}
REIMPLEMENT_REQUIRED = {"implemented", "verified", "changed"}
ROLES = {"sre", "engineering", "other"}
CHANGE_KEYS = {"attributes", "spans", "names", "notes"}
HIERARCHY = "hierarchy"
LEGACY = "legacy"


class StateError(Exception):
    pass


def version_dir(repo: Path, app: str, version: str) -> Path:
    return repo / "wiki" / "apps" / app / "versions" / version


def state_dir(repo: Path, app: str, version: str) -> Path:
    return repo / "wiki" / "apps" / app / "implementation" / version


def ledger_path(repo: Path, app: str, version: str) -> Path:
    return state_dir(repo, app, version) / "state.yaml"


def accepted_note(repo: Path, app: str, version: str, order_id: str) -> Path:
    return (
        version_dir(repo, app, version)
        / "implementation" / "work-orders" / f"{order_id}.md"
    )


def revision_path(repo: Path, app: str, version: str, order_id: str, revision: int) -> Path:
    if revision == 1:
        return accepted_note(repo, app, version, order_id)
    return state_dir(repo, app, version) / "revisions" / order_id / f"R{revision}.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---\n"):
        raise StateError(f"{path}: missing YAML frontmatter")
    end = text.find("\n---", 4)
    if end == -1:
        raise StateError(f"{path}: unterminated YAML frontmatter")
    try:
        data = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        raise StateError(f"{path}: frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise StateError(f"{path}: frontmatter must be a mapping")
    return data


def id_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(
        isinstance(item, str) and WORK_ORDER_ID.fullmatch(item) for item in value
    ):
        raise StateError("expected a list of work-order IDs")
    return list(value)


def read_notes(repo: Path, app: str, version: str) -> tuple[str, dict[str, dict]]:
    directory = version_dir(repo, app, version) / "implementation" / "work-orders"
    paths = sorted(directory.glob("WO-*.md"))
    if not paths:
        raise StateError(f"no accepted work-order notes under {directory}")
    parsed = [(path, frontmatter(path)) for path in paths]
    with_kind = [path.name for path, fm in parsed if "kind" in fm]
    if with_kind and len(with_kind) != len(parsed):
        without = [path.name for path, fm in parsed if "kind" not in fm]
        raise StateError(
            f"work-order notes mix v4 kind and legacy notes: with kind {with_kind}, "
            f"without kind {without}"
        )
    mode = HIERARCHY if with_kind else LEGACY
    notes: dict[str, dict] = {}
    for path, fm in parsed:
        order_id = fm.get("work_order_id")
        if order_id != path.stem or not WORK_ORDER_ID.fullmatch(str(order_id)):
            raise StateError(f"{path}: work_order_id does not match filename")
        kind = fm.get("kind")
        if mode == HIERARCHY and kind not in KINDS:
            raise StateError(f"{path}: kind must be one of {sorted(KINDS)}")
        try:
            notes[order_id] = {
                "kind": kind,
                "depends_on": id_list(fm.get("depends_on")),
                "parents": id_list(fm.get("parents")),
                "subordinates": id_list(fm.get("subordinates")),
                "status": fm.get("status"),
                "repository_mapping": fm.get("repository_mapping"),
            }
        except StateError as exc:
            raise StateError(f"{path}: {exc}") from exc
    return mode, notes


def load_ledger(repo: Path, app: str, version: str) -> dict:
    path = ledger_path(repo, app, version)
    try:
        data = yaml.safe_load(path.read_text())
    except OSError as exc:
        raise StateError(f"state ledger not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise StateError(f"state ledger is not valid YAML: {exc}") from exc
    failures = ledger_failures(data, app, version)
    if failures:
        raise StateError("; ".join(failures))
    return data


def ledger_failures(data: object, app: str, version: str) -> list[str]:
    if not isinstance(data, dict):
        return ["state ledger top level must be a mapping"]
    failures: list[str] = []
    if data.get("schema_version") != 1:
        failures.append("schema_version must be 1")
    if data.get("app") != app:
        failures.append("app does not match --app")
    if data.get("analysis_version") != version:
        failures.append("analysis_version does not match --version")
    mode = ledger_mode(data)
    if mode not in (HIERARCHY, LEGACY):
        failures.append(f"mode must be {HIERARCHY} or {LEGACY}")
    statuses = LEGACY_STATUSES if mode == LEGACY else STATUSES
    orders = data.get("work_orders")
    if not isinstance(orders, dict) or not orders:
        return failures + ["work_orders must be a non-empty mapping"]
    for order_id, entry in orders.items():
        if not isinstance(order_id, str) or not WORK_ORDER_ID.fullmatch(order_id):
            failures.append(f"invalid work-order id: {order_id!r}")
            continue
        if not isinstance(entry, dict):
            failures.append(f"{order_id}: entry must be a mapping")
            continue
        if mode == LEGACY:
            if "kind" in entry:
                failures.append(f"{order_id}: legacy ledger entries carry no kind")
        elif entry.get("kind") not in KINDS:
            failures.append(f"{order_id}: kind is invalid")
        if entry.get("status") not in statuses:
            failures.append(f"{order_id}: status is invalid")
        revision = entry.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            failures.append(f"{order_id}: revision must be a positive integer")
            revision = None
        implemented = entry.get("implemented_revision")
        if implemented is not None and (
            not isinstance(implemented, int)
            or isinstance(implemented, bool)
            or implemented < 1
            or (revision is not None and implemented > revision)
        ):
            failures.append(f"{order_id}: implemented_revision is invalid")
        if entry.get("status") in COMPLETE | {"changed"} and implemented is None:
            failures.append(f"{order_id}: {entry.get('status')} requires implemented_revision")
        prs = entry.get("pull_requests")
        if not isinstance(prs, list) or not all(isinstance(p, str) and p for p in prs):
            failures.append(f"{order_id}: pull_requests must be a list of URLs")
        try:
            id_list(entry.get("depends_on"))
        except StateError:
            failures.append(f"{order_id}: depends_on must contain work-order IDs")
        try:
            id_list(entry.get("subordinates"))
        except StateError:
            failures.append(f"{order_id}: subordinates must contain work-order IDs")
    return failures


def ledger_mode(data: dict) -> object:
    return data.get("mode", HIERARCHY)


def is_complete(entry: dict) -> bool:
    return (
        entry.get("status") in COMPLETE
        and entry.get("implemented_revision") == entry.get("revision")
    )


def write_ledger(repo: Path, app: str, version: str, data: dict) -> None:
    path = ledger_path(repo, app, version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def cmd_init(args) -> int:
    path = ledger_path(args.repo, args.app, args.version)
    if path.exists():
        raise StateError(f"state ledger already exists: {path}")
    mode, notes = read_notes(args.repo, args.app, args.version)
    orders = {}
    for order_id, note in notes.items():
        if mode == LEGACY:
            orders[order_id] = legacy_entry(note)
            continue
        status = note["status"] if note["status"] in STATUSES else "proposed"
        if status in COMPLETE | {"changed", "in-progress"}:
            status = "proposed"
        orders[order_id] = {
            "kind": note["kind"],
            "status": status,
            "revision": 1,
            "implemented_revision": None,
            "pull_requests": [],
            "depends_on": note["depends_on"],
            "parents": note["parents"],
            "subordinates": note["subordinates"],
        }
    write_ledger(args.repo, args.app, args.version, {
        "schema_version": 1,
        "mode": mode,
        "app": args.app,
        "analysis_version": args.version,
        "work_orders": orders,
    })
    print(f"PASS — initialized {mode} ledger {path} with {len(orders)} work orders")
    return 0


def legacy_entry(note: dict) -> dict:
    """Carry a v3 note's recorded status forward; v3 notes were the status record."""
    status = note["status"] if note["status"] in LEGACY_STATUSES else "proposed"
    implemented = 1 if status in COMPLETE | {"changed"} else None
    return {
        "status": status,
        "revision": 1,
        "implemented_revision": implemented,
        "pull_requests": [],
        "depends_on": note["depends_on"],
        "subordinates": [],
        "repository_mapping": note["repository_mapping"],
    }


def get_order(ledger: dict, order_id: str) -> dict:
    entry = ledger["work_orders"].get(order_id)
    if entry is None:
        raise StateError(f"unknown work order: {order_id}")
    return entry


def next_subordinate(ledger: dict, entry: dict) -> str | None:
    orders = ledger["work_orders"]
    rank = {kind: index for index, kind in enumerate(SUBORDINATE_KINDS)}
    candidates = [
        sub for sub in entry.get("subordinates") or []
        if sub in orders and not is_complete(orders[sub])
    ]
    candidates.sort(key=lambda sub: (rank.get(orders[sub].get("kind"), len(rank)), sub))
    return candidates[0] if candidates else None


def relative(repo: Path, path: Path) -> str:
    return str(path.relative_to(repo))


def revision_paths(args, entry: dict) -> list[str]:
    return [
        relative(args.repo, revision_path(args.repo, args.app, args.version, args.work_order, k))
        for k in range(2, entry["revision"] + 1)
    ]


def gate(args, ledger: dict) -> dict:
    orders = ledger["work_orders"]
    entry = get_order(ledger, args.work_order)
    revision = entry["revision"]
    result = {
        "work_order": args.work_order,
        "mode": ledger_mode(ledger),
        "runnable": False,
        "reason": "",
        "revision": revision,
        "revision_path": relative(
            args.repo,
            revision_path(args.repo, args.app, args.version, args.work_order, revision),
        ),
        "accepted_note": relative(
            args.repo, accepted_note(args.repo, args.app, args.version, args.work_order)
        ),
        "revision_paths": revision_paths(args, entry),
        "next_subordinate": None,
    }
    if ledger_mode(ledger) == LEGACY:
        return legacy_gate(args, orders, entry, result)
    if entry["kind"] == "foundation":
        pending = [
            dep for dep in entry.get("depends_on") or []
            if orders.get(dep, {}).get("status") not in COMPLETE
        ]
        if pending:
            result["reason"] = f"foundation dependencies incomplete: {pending}"
            return result
    else:
        pending = sorted(
            order_id for order_id, other in orders.items()
            if other["kind"] == "foundation" and other["status"] not in COMPLETE
        )
        if pending:
            result["reason"] = f"foundation work orders incomplete: {pending}"
            return result
    if entry["kind"] == "use-case":
        result["next_subordinate"] = next_subordinate(ledger, entry)
    if entry["status"] in REIMPLEMENT_REQUIRED and not args.reimplement:
        result["reason"] = f"work order is {entry['status']}; pass --reimplement to run it again"
        return result
    result["runnable"] = True
    result["reason"] = (
        "reimplementation override" if entry["status"] in REIMPLEMENT_REQUIRED
        else "all prerequisites complete"
    )
    return result


def legacy_gate(args, orders: dict, entry: dict, result: dict) -> dict:
    status = entry["status"]
    depends = entry.get("depends_on") or []
    if status == "blocked":
        if entry.get("repository_mapping") == "unresolved":
            result["reason"] = "legacy work order is blocked; its repository mapping is unresolved"
            return result
        if not depends:
            result["reason"] = "legacy work order is blocked and has no dependencies to complete"
            return result
    elif status not in LEGACY_RUNNABLE | REIMPLEMENT_REQUIRED:
        result["reason"] = f"legacy work order is {status}; only ready or in-progress orders run"
        return result
    pending = [
        dep for dep in depends
        if orders.get(dep, {}).get("status") not in LEGACY_DEPENDENCY_DONE
    ]
    if pending:
        result["reason"] = f"dependencies incomplete: {pending}"
        return result
    if status in REIMPLEMENT_REQUIRED and not args.reimplement:
        result["reason"] = f"work order is {status}; pass --reimplement to run it again"
        return result
    result["runnable"] = True
    result["reason"] = (
        "reimplementation override" if status in REIMPLEMENT_REQUIRED
        else "all legacy dependencies complete"
    )
    return result


def cmd_gate(args) -> int:
    ledger = load_ledger(args.repo, args.app, args.version)
    result = gate(args, ledger)
    print(json.dumps(result, indent=2))
    return 0 if result["runnable"] else 1


def cmd_set_status(args) -> int:
    ledger = load_ledger(args.repo, args.app, args.version)
    entry = get_order(ledger, args.work_order)
    if args.status == "verified" and entry.get("implemented_revision") != entry["revision"]:
        raise StateError(
            f"{args.work_order}: cannot verify; current revision R{entry['revision']} is not "
            f"implemented (implemented revision: {entry.get('implemented_revision')})"
        )
    entry["status"] = args.status
    if args.status == "implemented":
        entry["implemented_revision"] = entry["revision"]
    if args.pr and args.pr not in entry["pull_requests"]:
        entry["pull_requests"].append(args.pr)
    write_ledger(args.repo, args.app, args.version, ledger)
    print(f"PASS — {args.work_order} status {args.status} at revision {entry['revision']}")
    return 0


def deny_list(repo: Path) -> set[str]:
    path = repo / "docs" / "observability" / "attribute-schema.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise StateError(f"attribute-schema.json is not valid JSON: {exc}") from exc
    deny = data.get("deny") if isinstance(data, dict) else None
    names: set[str] = set()
    if isinstance(deny, dict):
        deny = deny.get("keys", deny.get("attributes", list(deny)))
    for item in deny if isinstance(deny, list) else []:
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict):
            for key in ("key", "name", "attribute"):
                if isinstance(item.get(key), str):
                    names.add(item[key])
    return names


def validate_names(section: str, value: object, denied: set[str]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, dict) or set(value) - {"add", "remove", "rename"}:
        raise StateError(f"changes.{section} allows only add, remove, rename")
    names: list[str] = []
    for op in ("add", "remove"):
        items = value.get(op, [])
        if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
            raise StateError(f"changes.{section}.{op} must be a list of names")
        names.extend(items)
    renames = value.get("rename", [])
    if not isinstance(renames, list) or not all(
        isinstance(r, dict) and set(r) == {"from", "to"}
        and isinstance(r["from"], str) and isinstance(r["to"], str)
        for r in renames
    ):
        raise StateError(f"changes.{section}.rename must be a list of {{from, to}}")
    for rename in renames:
        names.extend((rename["from"], rename["to"]))
    for name in names:
        if not NAME.fullmatch(name):
            raise StateError(f"changes.{section}: name {name!r} must match {NAME.pattern}")
    if section == "attributes":
        added = list(value.get("add", [])) + [r["to"] for r in renames]
        blocked = sorted(n for n in added if n in denied)
        if blocked:
            raise StateError(f"changes.attributes uses deny-listed keys: {blocked}")
    return names


def read_change(path: Path, denied: set[str]) -> dict:
    try:
        change = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise StateError(f"change file is not readable YAML: {exc}") from exc
    return validate_change(change, denied)


def validate_change(change: object, denied: set[str]) -> dict:
    if not isinstance(change, dict):
        raise StateError("change file must be a mapping")
    reason = change.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise StateError("reason is required")
    if change.get("requested_by_role") not in ROLES:
        raise StateError(f"requested_by_role must be one of {sorted(ROLES)}")
    changes = change.get("changes")
    if not isinstance(changes, dict) or not changes:
        raise StateError("changes must be a non-empty mapping")
    unknown = set(changes) - CHANGE_KEYS
    if unknown:
        raise StateError(f"changes has unknown keys: {sorted(unknown)}")
    validate_names("attributes", changes.get("attributes"), denied)
    validate_names("spans", changes.get("spans"), denied)
    names = changes.get("names")
    if names is not None:
        if not isinstance(names, dict) or set(names) - {"rename"}:
            raise StateError("changes.names allows only rename")
        validate_names("names", names, denied)
    notes = changes.get("notes")
    if notes is not None and (
        not isinstance(notes, list)
        or not all(isinstance(n, str) and n.strip() for n in notes)
    ):
        raise StateError("changes.notes must be a list of non-empty strings")
    return {
        "reason": reason.strip(),
        "requested_by_role": change["requested_by_role"],
        "changes": changes,
    }


def cmd_revise(args) -> int:
    ledger = load_ledger(args.repo, args.app, args.version)
    entry = get_order(ledger, args.work_order)
    if ledger_mode(ledger) == LEGACY:
        raise StateError(
            f"{args.work_order} belongs to a legacy (contract v3) analysis version; revisions "
            "need the v4 work-order hierarchy. Create a new analysis version with "
            "/ob-edit-inputs to change it."
        )
    if entry["kind"] not in SUBORDINATE_KINDS:
        raise StateError(
            f"{args.work_order} is a {entry['kind']} work order; only subordinate kinds can be revised"
        )
    change = read_change(args.file, deny_list(args.repo))
    previous = entry["revision"]
    previous_file = revision_path(args.repo, args.app, args.version, args.work_order, previous)
    if not previous_file.exists():
        raise StateError(f"previous revision missing: {previous_file}")
    revision = previous + 1
    meta = {
        "work_order_id": args.work_order,
        "analysis_version": args.version,
        "revision": revision,
        "previous_revision": previous,
        "previous_digest": sha256(previous_file),
        **change,
    }
    body = (
        f"# {args.work_order} revision R{revision}\n\n"
        f"Revises R{previous} of {args.work_order} in accepted analysis {args.version} "
        f"without creating a new analysis version.\n\n"
        f"Reason: {change['reason']}\n"
    )
    target = revision_path(args.repo, args.app, args.version, args.work_order, revision)
    if target.exists():
        raise StateError(f"revision already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n\n" + body)
    entry["revision"] = revision
    if entry["status"] in COMPLETE:
        entry["status"] = "changed"
    write_ledger(args.repo, args.app, args.version, ledger)
    print(f"PASS — wrote {target.relative_to(args.repo)}")
    return 0


def verify(repo: Path, app: str, version: str) -> list[str]:
    try:
        ledger = load_ledger(repo, app, version)
    except StateError as exc:
        return [str(exc)]
    failures: list[str] = []
    revisions_root = state_dir(repo, app, version) / "revisions"
    if revisions_root.exists():
        for directory in sorted(revisions_root.iterdir()):
            if directory.name not in ledger["work_orders"]:
                failures.append(f"revisions for unknown work order: {directory.name}")
    for order_id, entry in ledger["work_orders"].items():
        if entry["status"] in COMPLETE and not is_complete(entry):
            failures.append(
                f"{order_id}: {entry['status']} but implemented revision "
                f"{entry.get('implemented_revision')} is not current revision {entry['revision']}"
            )
        if not accepted_note(repo, app, version, order_id).exists():
            failures.append(f"{order_id}: accepted wiki note is missing")
            continue
        directory = revisions_root / order_id
        found = sorted(
            int(m.group(1)) for p in (directory.glob("*") if directory.exists() else [])
            if (m := REVISION_FILE.fullmatch(p.name))
        )
        expected = list(range(2, entry["revision"] + 1))
        if found != expected:
            failures.append(
                f"{order_id}: revision files {found} do not match ledger revision "
                f"{entry['revision']} (expected {expected})"
            )
            continue
        if expected and entry.get("kind") not in SUBORDINATE_KINDS:
            failures.append(
                f"{order_id}: {entry.get('kind', 'legacy')} work orders cannot have revisions"
            )
        for revision in expected:
            path = revision_path(repo, app, version, order_id, revision)
            previous = revision_path(repo, app, version, order_id, revision - 1)
            try:
                fm = frontmatter(path)
            except StateError as exc:
                failures.append(str(exc))
                continue
            if (
                fm.get("work_order_id") != order_id
                or fm.get("analysis_version") != version
                or fm.get("revision") != revision
                or fm.get("previous_revision") != revision - 1
            ):
                failures.append(f"{order_id}: R{revision} frontmatter identity is inconsistent")
            if fm.get("previous_digest") != sha256(previous):
                failures.append(f"{order_id}: R{revision} previous_digest does not match R{revision - 1}")
            if fm.get("requested_by_role") not in ROLES or not str(fm.get("reason", "")).strip():
                failures.append(f"{order_id}: R{revision} needs reason and requested_by_role")
    return failures


def cmd_verify(args) -> int:
    failures = verify(args.repo, args.app, args.version)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print("PASS — work-order state ledger and revision chain are intact")
    return 0


class NameDelta:
    """Net add/remove/rename of names relative to the accepted note (R1)."""

    def __init__(self) -> None:
        self.added: list[str] = []
        self.removed: list[str] = []
        self.renamed: dict[str, str] = {}

    def original_of(self, current: str) -> str | None:
        return next((o for o, n in self.renamed.items() if n == current), None)

    def apply(self, ops: dict) -> None:
        for rename in ops.get("rename", []):
            source, target = rename["from"], rename["to"]
            if source in self.added:
                self.added[self.added.index(source)] = target
            elif (original := self.original_of(source)) is not None:
                self.renamed[original] = target
            else:
                self.renamed[source] = target
        for name in ops.get("remove", []):
            if name in self.added:
                self.added.remove(name)
                continue
            original = self.original_of(name)
            if original is not None:
                del self.renamed[original]
                name = original
            if name not in self.removed:
                self.removed.append(name)
        for name in ops.get("add", []):
            if name in self.removed:
                self.removed.remove(name)
            elif name not in self.added:
                self.added.append(name)

    def result(self, operations: tuple[str, ...]) -> dict:
        out = {
            "add": self.added,
            "remove": self.removed,
            "rename": [{"from": o, "to": n} for o, n in self.renamed.items() if o != n],
        }
        return {op: out[op] for op in operations}


def cumulative(
    repo: Path, app: str, version: str, order_id: str, entry: dict,
) -> tuple[dict, list[dict]]:
    deltas = {
        "attributes": NameDelta(), "spans": NameDelta(), "names": NameDelta(),
    }
    notes: list[dict] = []
    revisions: list[dict] = []
    for k in range(2, entry["revision"] + 1):
        path = revision_path(repo, app, version, order_id, k)
        change = validate_change(frontmatter(path), set())
        for section, delta in deltas.items():
            if change["changes"].get(section):
                delta.apply(change["changes"][section])
        notes.extend(
            {"revision": k, "note": note} for note in change["changes"].get("notes") or []
        )
        revisions.append({
            "revision": k,
            "path": relative(repo, path),
            "reason": change["reason"],
            "requested_by_role": change["requested_by_role"],
        })
    return {
        "attributes": deltas["attributes"].result(("add", "remove", "rename")),
        "spans": deltas["spans"].result(("add", "remove", "rename")),
        "names": deltas["names"].result(("rename",)),
        "notes": notes,
    }, revisions


def cmd_show(args) -> int:
    ledger = load_ledger(args.repo, args.app, args.version)
    entry = get_order(ledger, args.work_order)
    broken = [
        failure for failure in verify(args.repo, args.app, args.version)
        if failure.startswith(f"{args.work_order}:")
    ]
    if broken:
        raise StateError("; ".join(broken))
    changes, revisions = cumulative(args.repo, args.app, args.version, args.work_order, entry)
    print(json.dumps({
        "work_order": args.work_order,
        "mode": ledger_mode(ledger),
        "status": entry["status"],
        "revision": entry["revision"],
        "implemented_revision": entry.get("implemented_revision"),
        "accepted_note": relative(
            args.repo, accepted_note(args.repo, args.app, args.version, args.work_order)
        ),
        "revision_paths": [item["path"] for item in revisions],
        "revisions": revisions,
        "effective_changes": changes,
    }, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", type=Path, default=Path("."))
    common.add_argument("--app", required=True)
    common.add_argument("--version", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", parents=[common])
    gate_parser = sub.add_parser("gate", parents=[common])
    gate_parser.add_argument("--work-order", required=True)
    gate_parser.add_argument("--reimplement", action="store_true")
    status_parser = sub.add_parser("set-status", parents=[common])
    status_parser.add_argument("--work-order", required=True)
    status_parser.add_argument("--status", required=True, choices=SETTABLE_STATUSES)
    status_parser.add_argument("--pr")
    revise_parser = sub.add_parser("revise", parents=[common])
    revise_parser.add_argument("--work-order", required=True)
    revise_parser.add_argument("--file", type=Path, required=True)
    sub.add_parser("verify", parents=[common])
    show_parser = sub.add_parser("show", parents=[common])
    show_parser.add_argument("--work-order", required=True)
    args = parser.parse_args(argv)
    if not APP.fullmatch(args.app):
        parser.error("--app must be a simple name")
    if not VERSION.fullmatch(args.version):
        parser.error("--version must look like V1")
    if getattr(args, "work_order", None) and not WORK_ORDER_ID.fullmatch(args.work_order):
        parser.error("--work-order must look like WO-001")
    handlers = {
        "init": cmd_init,
        "gate": cmd_gate,
        "set-status": cmd_set_status,
        "revise": cmd_revise,
        "verify": cmd_verify,
        "show": cmd_show,
    }
    try:
        return handlers[args.command](args)
    except StateError as exc:
        print(f"FAIL — {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
