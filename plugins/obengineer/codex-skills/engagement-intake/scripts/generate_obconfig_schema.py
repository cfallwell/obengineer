#!/usr/bin/env python3
"""Generate the complete structural obconfig schema from the canonical template."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "obconfig.yaml.template"
OUTPUT = Path(__file__).resolve().parents[1] / "schemas/obconfig.schema.json"

STRING_LISTS = {
    "initial_scope.repositories",
    "surfaces.production_urls",
    "security_assessment.authorized_origins",
    "splunk.platform.index_allowlist",
    "backends.languages",
    "backends.deploy_targets",
    "backends.buses",
    "backends.cloud_accounts",
    "constraints.privacy_regimes",
    "constraints.pii_deny_list_additions",
    "constraints.competing_eum_agents",
    "outcomes.audiences",
    "business_context.operating_cost.observability_tools_in_use",
    "business_context.business_information.strategic_initiatives",
    "public_evidence.brand_terms",
    "public_evidence.status_page_urls",
    "public_evidence.exclude_domains",
    "public_evidence.competitors",
    "developer_tools.named",
}
MAPPING_LIST_SCHEMAS = {
    "initial_scope.parent_folders": {
        "repository": {"type": "string"},
        "path": {"type": "string"},
    },
    "initial_scope.branches": {
        "repository": {"type": "string"},
        "branch": {"type": "string"},
    },
    "developer_tools.matched": {
        "tool": {"type": "string"},
        "via": {"type": "string"},
        "key": {"type": "string"},
    },
    "traffic_baseline.infra_integrations": {
        "name": {"type": "string"},
        "entities": {"type": "number", "minimum": 0},
        "metrics_per_entity": {"type": "number", "minimum": 0},
    },
}
NUMBER_OR_UNKNOWN_PREFIXES = {
    "traffic_baseline.rum",
    "traffic_baseline.apm",
    "traffic_baseline.logs",
    "business_context.incident_experience",
}
NUMBER_OR_UNKNOWN = {
    "business_context.operating_cost.annual_tooling_spend",
    "business_context.operating_cost.duplicate_agents_on_page",
    "business_context.operating_cost.engineering_hours_per_month_on_triage",
    "business_context.operating_cost.fully_loaded_hourly_cost",
    "business_context.revenue_context.revenue_per_hour_online",
    "business_context.revenue_context.orders_per_day",
    "business_context.revenue_context.average_order_value",
    "business_context.revenue_context.conversion_rate_pct",
    "business_context.revenue_context.cart_abandonment_pct",
}
ENUMS = {
    "initial_scope.authorized": ["unknown", "full", "repositories", "parent_folders"],
    "security_assessment.mode": ["passive", "safe-active", "none"],
}
SECRET_PATHS = {
    "splunk.observability.read_token",
    "splunk.platform.read_token",
    "analysis_access.dummy_login.password",
}


def _source_marks(node: yaml.Node, path: str, marks: dict[str, int]) -> None:
    marks[path] = node.start_mark.line + 1
    if isinstance(node, yaml.MappingNode):
        for key, value in node.value:
            key_name = str(getattr(key, "value", ""))
            child = f"{path}.{key_name}" if path else key_name
            _source_marks(value, child, marks)
    elif isinstance(node, yaml.SequenceNode):
        for index, child in enumerate(node.value):
            _source_marks(child, f"{path}[{index}]", marks)


def schema_for(
    value: Any, path: str, marks: dict[str, int]
) -> dict[str, Any]:
    if isinstance(value, dict):
        properties = {
            key: schema_for(
                item,
                f"{path}.{key}" if path else key,
                marks,
            )
            for key, item in value.items()
        }
        return {
            "type": "object",
            "required": list(value),
            "properties": properties,
            "additionalProperties": path == "extensions",
            "x-obengineer-source-line": marks[path],
        }
    if isinstance(value, list):
        result: dict[str, Any] = {
            "type": "array",
            "x-obengineer-source-line": marks[path],
        }
        if path in STRING_LISTS:
            result["items"] = {"type": "string"}
            result["uniqueItems"] = path in {
                "security_assessment.authorized_origins",
                "splunk.platform.index_allowlist",
                "outcomes.audiences",
            }
        elif path in MAPPING_LIST_SCHEMAS:
            properties = MAPPING_LIST_SCHEMAS[path]
            result["items"] = {
                "type": "object",
                "required": list(properties),
                "properties": properties,
                "additionalProperties": False,
            }
        elif path == "business_context.revenue_context.peak_events":
            result["items"] = {
                "oneOf": [
                    {"type": "string"},
                    {"type": "object"},
                ]
            }
        else:
            result["items"] = {}
        return result
    if path == "schema_version":
        return {
            "type": "integer",
            "const": 4,
            "x-obengineer-source-line": marks[path],
        }
    if path == "standards.percentile":
        return {
            "oneOf": [
                {"type": "string"},
                {"type": "number", "x-obengineer-finite": True},
            ],
            "x-obengineer-source-line": marks[path],
        }
    if path == "standards.unknown_dimension_threshold_pct":
        return {
            "type": "number",
            "minimum": 0,
            "x-obengineer-finite": True,
            "x-obengineer-source-line": marks[path],
        }
    if path in ENUMS:
        return {
            "type": "string",
            "enum": ENUMS[path],
            "x-obengineer-source-line": marks[path],
        }
    if path in NUMBER_OR_UNKNOWN or any(
        path.startswith(prefix + ".") for prefix in NUMBER_OR_UNKNOWN_PREFIXES
    ):
        result = {
            "oneOf": [
                {
                    "type": "number",
                    "minimum": 0,
                    "x-obengineer-finite": True,
                },
                {"const": "unknown"},
            ]
        }
        result["x-obengineer-source-line"] = marks[path]
        return result
    if isinstance(value, bool):
        return {
            "type": "boolean",
            "x-obengineer-source-line": marks[path],
        }
    if isinstance(value, int):
        result = {"type": "integer"}
        if path in {
            "engagement.document_version",
            "standards.baggage_header_budget_bytes",
            "standards.baggage_value_ceiling_bytes",
            "public_evidence.window_months",
        }:
            result["minimum"] = 1
        result["x-obengineer-source-line"] = marks[path]
        return result
    if isinstance(value, float):
        return {
            "type": "number",
            "x-obengineer-source-line": marks[path],
        }
    result = {
        "type": "string",
        "x-obengineer-source-line": marks[path],
    }
    if path in SECRET_PATHS:
        result["x-obengineer-secret"] = True
    if path == "analysis_access.dummy_login.login_id":
        result["x-obengineer-sensitive"] = True
    if path in {"engagement.application", "engagement.deployment_environment", "artifacts.directory"}:
        result["minLength"] = 1
    return result


def render_schema() -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    template = yaml.safe_load(text)
    node = yaml.compose(text)
    if node is None:
        raise ValueError("canonical template is empty")
    marks: dict[str, int] = {}
    _source_marks(node, "", marks)
    schema = schema_for(template, "", marks)
    schema.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://obengineer.dev/schemas/obconfig.schema.json",
            "title": "obengineer local configuration v4",
            "x-obengineer-secret-paths": sorted(SECRET_PATHS),
            "x-obengineer-retired-keys": {
                "entitlement": "remove entitlement input; analysis measures sf.org usage and enforced system limits",
                "tenancy.environments": "replace with singular engagement.deployment_environment scalar",
                "outcomes.known_pain": "remove retired pain commentary",
                "business_context.commentary": "remove retired what-hurts commentary",
                "analysis_access.token_ref": "replace with splunk.platform.read_token",
                "analysis_access.api_key_ref": "replace with splunk.observability.read_token",
                "analysis_access.password_ref": "replace with analysis_access.dummy_login.password",
            },
            "x-obengineer-runtime-semantics": (
                "The bundled validator enforces paired credentials, exact HTTPS origins, "
                "URL/index/realm restrictions, and conditional fields after this schema."
            ),
        }
    )
    return json.dumps(schema, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_schema()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("obconfig schema drifted; regenerate it")
        print("PASS — obconfig schema matches canonical YAML contract")
        return
    OUTPUT.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
