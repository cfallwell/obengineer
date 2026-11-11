#!/usr/bin/env python3
"""Prefill local inputs silently, then emit the first deterministic intake turn."""

from __future__ import annotations

import argparse
from pathlib import Path

import manage_run_context
import prefill_engagement_inputs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = root / manage_run_context.INPUTS_RELATIVE_PATH
    try:
        prefill_engagement_inputs.prefill(root, output)
    except prefill_engagement_inputs.PrefillError as exc:
        print(f"FAIL — {exc}")
        return 1
    return manage_run_context.main([
        "start",
        "--project-root",
        str(root),
    ])


if __name__ == "__main__":
    raise SystemExit(main())
