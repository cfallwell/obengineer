#!/usr/bin/env python3
"""Validate analysis orchestration results and the canonical content contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from analysis_contract import (
    load_json,
    validate_contract,
    validate_manifest,
    validate_worker_results,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--results",
        type=Path,
        help="Directory containing one worker-result JSON file per runnable job",
    )
    args = parser.parse_args(argv)
    if not args.contract and not args.manifest:
        parser.error("provide --contract, --manifest, or both")
    failures: list[str] = []
    if args.contract:
        failures.extend(validate_contract(load_json(args.contract)))
    if args.manifest:
        manifest = load_json(args.manifest)
        if args.results:
            result_paths = sorted(args.results.glob("*.json"))
            if not result_paths:
                failures.append(f"results: no JSON files under {args.results}")
            else:
                failures.extend(
                    validate_worker_results(
                        manifest,
                        [load_json(path) for path in result_paths],
                    )
                )
        else:
            failures.extend(validate_manifest(manifest))
    elif args.results:
        parser.error("--results requires --manifest")
    failures = sorted(set(failures))
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    checked = ", ".join(
        name
        for name, value in (
            ("contract", args.contract),
            ("manifest", args.manifest),
            ("worker intervals", args.results),
        )
        if value
    )
    print(f"PASS — validated {checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
