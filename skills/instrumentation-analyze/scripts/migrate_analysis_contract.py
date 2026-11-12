#!/usr/bin/env python3
"""Explicitly migrate a mutable schema-v1/v2 analysis contract copy to schema v3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from analysis_contract import load_json, migrate_contract, validate_contract


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.contract.resolve() == args.output.resolve():
        print(
            "FAIL — migration output must differ from the source; "
            "accepted snapshots are immutable"
        )
        return 1
    original = load_json(args.contract)
    migrated = migrate_contract(original)
    failures = validate_contract(migrated)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(migrated, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"PASS — wrote analysis contract schema v{migrated['schemaVersion']} "
        f"to {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
