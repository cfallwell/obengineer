#!/usr/bin/env python3
"""Aggregate deduplicated outcome opportunities with explicit coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

METRICS = {
    "schema-miss", "dimension-miss", "detector-disarm",
    "not-in-evidence-reversal",
}
OUTCOMES = {"met", "miss", "unmeasurable"}
COLLECTION_POINTS = {
    "schema-miss": "layer-1-pre-merge",
    "dimension-miss": "first-post-apply-verification",
    "detector-disarm": "post-observation-window-verification",
    "not-in-evidence-reversal": "accepted-claim-recheck",
}
TUPLE_FIELDS = {
    "schema-miss": (
        "contract_commit", "work_order", "repository", "attribute_key",
    ),
    "dimension-miss": ("first_apply", "panel", "dimension_key"),
    "detector-disarm": ("detector_id", "armed_cohort"),
    "not-in-evidence-reversal": ("claim_id", "verification_run"),
}


def opportunity_id(item: dict) -> str:
    metric = item.get("metric", "")
    fields = TUPLE_FIELDS.get(metric, ())
    material = "|".join([metric, *(str(item.get(field, "")) for field in fields)])
    return hashlib.sha256(material.encode()).hexdigest()


def aggregate(data: dict) -> tuple[dict, list[str]]:
    failures: list[str] = []
    opportunities = data.get("opportunities")
    if not isinstance(opportunities, list):
        return {}, ["opportunities must be a list"]
    unique: dict[str, dict] = {}
    for item in opportunities:
        if not isinstance(item, dict):
            failures.append("opportunities entries must be objects")
            continue
        metric = item.get("metric")
        missing_tuple = [
            field for field in TUPLE_FIELDS.get(metric, ())
            if item.get(field) in ("", None)
        ]
        if missing_tuple:
            failures.append(
                f"{metric or 'opportunity'} missing tuple fields: {missing_tuple}"
            )
            continue
        item_id = opportunity_id(item)
        supplied_id = item.get("id")
        if supplied_id and supplied_id != item_id:
            failures.append(f"opportunity id does not match canonical tuple: {supplied_id}")
        if item_id in unique:
            failures.append(f"duplicate opportunity id: {item_id}")
        if metric not in METRICS:
            failures.append(f"{item_id}: unsupported metric")
        if item.get("outcome") not in OUTCOMES:
            failures.append(f"{item_id}: unsupported outcome")
        if not item.get("cohort"):
            failures.append(f"{item_id}: cohort is required")
        if item.get("collection_point") != COLLECTION_POINTS.get(item.get("metric")):
            failures.append(f"{item_id}: collection_point is invalid for metric")
        unique[item_id] = item

    output: dict[str, dict] = {}
    for metric in sorted(METRICS):
        cohort = [item for item in unique.values() if item.get("metric") == metric]
        met = sum(item.get("outcome") == "met" for item in cohort)
        misses = sum(item.get("outcome") == "miss" for item in cohort)
        unmeasurable = sum(
            item.get("outcome") == "unmeasurable" for item in cohort
        )
        measured = met + misses
        eligible = measured + unmeasurable
        output[metric] = {
            "met": met,
            "misses": misses,
            "unmeasurable": unmeasurable,
            "eligible": eligible,
            "numerator": misses,
            "denominator": measured,
            "rate": misses / measured if measured else None,
            "measurement_coverage": measured / eligible if eligible else None,
        }
    return {"schema_version": 1, "metrics": output}, failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.input.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL — outcome input is not valid JSON: {exc}")
        return 1
    output, failures = aggregate(data)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    rendered = json.dumps(output, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
