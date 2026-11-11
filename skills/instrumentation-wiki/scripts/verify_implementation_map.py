#!/usr/bin/env python3
"""Validate the implementation-map contract emitted by analysis."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SELECTOR = re.compile(
    r"^(work-order|business-transaction|workflow|use-case|detector|objective|config):[^:]+$"
)
MAPPING_STATUS = {"complete", "incomplete"}
LEDGER_ID = re.compile(r"^(?:SRC|FACT|CHECK|DEC|UNRES)-[A-Za-z0-9._-]+$")
REPOSITORY_ID = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?$")
SAFE_PATH = re.compile(
    r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*(?:^|/)\.(?:/|$))[A-Za-z0-9._/-]+$"
)


def safe_authorized_path(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and "\\" not in value
        and SAFE_PATH.fullmatch(value) is not None
    )


def path_stays_in_repository(root: Path, relative: str) -> bool:
    resolved_root = root.resolve()
    resolved = (root / relative).resolve(strict=False)
    return resolved != resolved_root and resolved_root in resolved.parents


def verify(
    path: Path,
    repository_roots: dict[str, Path] | None = None,
) -> list[str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"implementation map is not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return ["implementation map top level must be an object"]

    failures: list[str] = []
    if data.get("schema_version") != 1:
        failures.append("schema_version must be 1")

    repositories = data.get("repositories")
    if not isinstance(repositories, list):
        failures.append("repositories must be a list")
        repositories = []
    repository_ids: set[str] = set()
    for index, repository in enumerate(repositories):
        if not isinstance(repository, dict):
            failures.append(f"repositories[{index}] must be an object")
            continue
        repo_id = repository.get("id")
        if not isinstance(repo_id, str) or not REPOSITORY_ID.fullmatch(repo_id):
            failures.append(f"repositories[{index}].id is required")
        elif repo_id in repository_ids:
            failures.append(f"duplicate repository id: {repo_id}")
        else:
            repository_ids.add(repo_id)
        if not isinstance(repository.get("remote"), str) or not repository["remote"]:
            failures.append(f"repositories[{index}].remote is required")
        paths = repository.get("authorized_paths")
        if not isinstance(paths, list) or not paths or not all(
            safe_authorized_path(item) for item in paths
        ):
            failures.append(
                f"repositories[{index}].authorized_paths must contain safe relative paths"
            )
        elif repository_roots and repo_id in repository_roots:
            for path_index, relative in enumerate(paths):
                if not path_stays_in_repository(
                    repository_roots[repo_id], relative
                ):
                    failures.append(
                        f"repositories[{index}].authorized_paths[{path_index}] "
                        "escapes the repository through a symlink"
                    )

    targets = data.get("targets")
    if not isinstance(targets, list) or not targets:
        failures.append("targets must be a non-empty list")
        targets = []
    selectors: set[str] = set()
    work_orders: set[str] = set()
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            failures.append(f"targets[{index}] must be an object")
            continue
        selector = target.get("selector")
        if not isinstance(selector, str) or not SELECTOR.fullmatch(selector):
            failures.append(f"targets[{index}].selector is invalid")
        elif selector in selectors:
            failures.append(f"duplicate target selector: {selector}")
        else:
            selectors.add(selector)
        work_order = target.get("work_order")
        if not isinstance(work_order, str) or not work_order:
            failures.append(f"targets[{index}].work_order is required")
        else:
            work_orders.add(work_order)
        status = target.get("mapping_status")
        if status not in MAPPING_STATUS:
            failures.append(f"targets[{index}].mapping_status is invalid")
        target_repositories = target.get("repositories")
        if not isinstance(target_repositories, list):
            failures.append(f"targets[{index}].repositories must be a list")
            target_repositories = []
        unknown = set(target_repositories) - repository_ids
        if unknown:
            failures.append(
                f"targets[{index}] references unknown repositories: {sorted(unknown)}"
            )
        if status == "complete" and not target_repositories:
            failures.append(
                f"targets[{index}] is complete but has no repository mapping"
            )
        evidence = target.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            failures.append(f"targets[{index}].evidence is required")
        elif not all(
            isinstance(item, str) and LEDGER_ID.fullmatch(item)
            for item in evidence
        ):
            failures.append(
                f"targets[{index}].evidence must contain provenance-ledger ids"
            )

    if len(work_orders) == 0:
        failures.append("no work-order mappings were defined")
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map", type=Path)
    parser.add_argument(
        "--repository-root",
        action="append",
        default=[],
        metavar="ID=PATH",
        help="resolve authorized paths against a mounted repository root",
    )
    args = parser.parse_args(argv)
    repository_roots: dict[str, Path] = {}
    for mapping in args.repository_root:
        if "=" not in mapping:
            parser.error("--repository-root must use ID=PATH")
        repository, root = mapping.split("=", 1)
        if not REPOSITORY_ID.fullmatch(repository) or not root:
            parser.error("--repository-root must use a valid repository ID and path")
        repository_roots[repository] = Path(root)
    failures = verify(args.map, repository_roots)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print("PASS — implementation map is structurally valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
