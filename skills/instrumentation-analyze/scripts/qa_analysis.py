#!/usr/bin/env python3
"""Run the representative orchestration, semantic, render, and budget QA gate."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import time
from pathlib import Path

from analysis_contract import load_json, validate_contract, validate_worker_results
from render_analysis_site import Renderer
from verify_analysis_site import check

SKILL = Path(__file__).resolve().parent.parent
FIXTURE = SKILL / "tests" / "fixtures" / "representative"


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.md")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def write_work_order_stubs(repo_root: Path, contract: dict) -> None:
    app = contract["application"]
    root = (
        repo_root / "wiki" / "apps" / app["id"] / "versions" /
        app["version"] / "implementation" / "work-orders"
    )
    root.mkdir(parents=True, exist_ok=True)
    for order in contract["workOrders"]:
        (root / f"{order['id']}.md").write_text(
            f"# {order['id']} — {order['title']}\n\n{order['outcome']}\n",
            encoding="utf-8",
        )


def main() -> int:
    contract_path = FIXTURE / "analysis-contract.json"
    contract = load_json(contract_path)
    manifest = load_json(FIXTURE / "job-manifest.json")
    results = [
        load_json(path)
        for path in sorted((FIXTURE / "results").glob("*.json"))
    ]
    started = time.perf_counter()
    failures = validate_contract(contract)
    failures.extend(validate_worker_results(manifest, results))
    validation_seconds = time.perf_counter() - started
    budgets = contract["operations"]["performanceBudgets"]
    if validation_seconds > budgets["validationSeconds"]:
        failures.append(
            f"validation budget exceeded: {validation_seconds:.3f}s > "
            f"{budgets['validationSeconds']:.3f}s"
        )
    with tempfile.TemporaryDirectory(prefix="obengineer-analysis-qa-") as temp:
        root = Path(temp)
        first_repo = root / "first"
        second_repo = root / "second"
        first = (
            first_repo / "docs" / "observability" / "analysis" /
            contract["application"]["id"] / contract["application"]["version"]
        )
        second = (
            second_repo / "docs" / "observability" / "analysis" /
            contract["application"]["id"] / contract["application"]["version"]
        )
        render_started = time.perf_counter()
        Renderer(contract, first).render()
        Renderer(contract, second).render()
        write_work_order_stubs(first_repo, contract)
        write_work_order_stubs(second_repo, contract)
        render_seconds = time.perf_counter() - render_started
        if render_seconds > budgets["renderSeconds"]:
            failures.append(
                f"render budget exceeded: {render_seconds:.3f}s > "
                f"{budgets['renderSeconds']:.3f}s"
            )
        if tree_digest(first) != tree_digest(second):
            failures.append("deterministic rendering failed: repeated output differs")
        failures.extend(check(first, first_repo, contract_path))
        files = [path for path in first.rglob("*") if path.is_file()]
        total_bytes = sum(path.stat().st_size for path in files)
        if len(files) > budgets["maxOutputFiles"]:
            failures.append(
                f"output file budget exceeded: {len(files)} > {budgets['maxOutputFiles']}"
            )
        if total_bytes > budgets["maxOutputBytes"]:
            failures.append(
                f"output byte budget exceeded: {total_bytes} > {budgets['maxOutputBytes']}"
            )
    failures = sorted(set(failures))
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    print(
        "PASS — representative analysis QA: "
        f"validation={validation_seconds:.3f}s, render-twice={render_seconds:.3f}s, "
        f"files={len(files)}, bytes={total_bytes}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
