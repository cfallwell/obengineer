#!/usr/bin/env python3
"""Render a canonical analysis-contract JSON file as linked Markdown."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

from analysis_contract import load_json, validate_contract

SECTIONS = (
    ("Architecture", "architecture", "overview/index.md"),
    ("Technology", "technology", "technology/index.md"),
    ("Current telemetry", "currentTelemetry", "telemetry/index.md"),
    ("Findings", "findings", "findings/index.md"),
    ("Instrumentation strategy", "strategy", "strategy/index.md"),
    ("Implementation path", "implementationPath", "implementation/index.md"),
    ("Work orders", "workOrders", "work-orders/index.md"),
    ("Use cases", "useCases", "use-cases/index.md"),
    ("Workflows", "workflows", "workflows/index.md"),
    ("Business transactions", "businessTransactions", "business-transactions/index.md"),
    ("Shared signal contracts", "contracts", "contracts/index.md"),
    ("Operations and verification", "operations", "operations/index.md"),
    ("Reference", "reference", "reference/index.md"),
)


def esc(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def bullets(values: Iterable[Any]) -> str:
    return "\n".join(f"- {esc(value)}" for value in values)


def numbered(values: Iterable[Any]) -> str:
    return "\n".join(f"{index}. {esc(value)}" for index, value in enumerate(values, 1))


def code(value: str, language: str = "text") -> str:
    return f"```{language}\n{value.rstrip()}\n```"


def table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    header_list = list(headers)
    lines = [
        "| " + " | ".join(header_list) + " |",
        "|" + "|".join("---" for _ in header_list) + "|",
    ]
    lines.extend("| " + " | ".join(esc(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def breadcrumb(parent: str | None = None, current: str | None = None) -> str:
    if parent and current:
        return f"[Analysis](../index.md) / [{parent}](index.md) / **{current}**"
    if current:
        return f"[Analysis](../index.md) / **{current}**"
    return "[Analysis](../index.md)"


def nested_breadcrumb(parent: str, current: str) -> str:
    return f"[Analysis](../../index.md) / [{parent}](../index.md) / **{current}**"


def finish(related: Iterable[tuple[str, str]], next_link: tuple[str, str]) -> str:
    links = "\n".join(f"- [{label}]({target})" for label, target in related)
    return (
        "\n\n## Related documentation\n\n"
        f"{links}\n\n"
        "## Continue review\n\n"
        f"[{next_link[0]}]({next_link[1]})\n"
    )


class Renderer:
    def __init__(self, contract: dict[str, Any], output: Path) -> None:
        self.c = contract
        self.output = output
        self.written: set[Path] = set()

    def write(self, relative: str, text: str) -> None:
        path = self.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = text.rstrip() + "\n"
        path.write_text(normalized, encoding="utf-8")
        self.written.add(path)

    def versions(self) -> list[str]:
        versions = {
            path.name
            for path in self.output.parent.glob("V[1-9]*")
            if path.is_dir() and path.name[1:].isdigit()
        }
        versions.add(self.c["application"]["version"])
        return sorted(versions, key=lambda value: int(value[1:]))

    def version_selector(self) -> str:
        selected = self.c["application"]["version"]
        return " ".join(
            f"**[{version}]**"
            if version == selected
            else f"[{version}](../{version}/index.md)"
            for version in self.versions()
        )

    def link_list(self, ids: Iterable[str], directory: str, labels: dict[str, str]) -> str:
        return ", ".join(
            f"[{esc(labels.get(identifier, identifier))}](../{directory}/{identifier}.md)"
            for identifier in ids
        )

    def render(self) -> None:
        self.render_root()
        self.render_landing()
        self.render_architecture()
        self.render_technology()
        self.render_telemetry()
        self.render_findings()
        self.render_strategy()
        self.render_implementation()
        self.render_work_orders()
        self.render_use_cases()
        self.render_workflows()
        self.render_transactions()
        self.render_contracts()
        self.render_operations()
        self.render_reference()

    def render_root(self) -> None:
        app = self.c["application"]
        root = self.output.parent / "index.md"
        root.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            f"- **[{version}]({version}/index.md)** — "
            + (
                app["status"]
                if version == app["version"]
                else "existing immutable version"
            )
            for version in self.versions()
        ]
        root.write_text(
            f"# {app['name']} analysis versions\n\n"
            + "\n".join(rows)
            + "\n\n"
            "Open a version to review its immutable evidence, strategy, contracts, "
            "implementation queue, and verification plan.\n",
            encoding="utf-8",
        )

    def render_landing(self) -> None:
        app = self.c["application"]
        summaries = self.c["summaries"]
        rows = [
            (label, summaries[key], f"[Open]({target})")
            for label, key, target in SECTIONS
        ]
        finding_names = ", ".join(f["title"] for f in self.c["findings"])
        use_case_names = ", ".join(u["title"] for u in self.c["useCases"])
        content = (
            f"{self.version_selector()}\n\n"
            f"{breadcrumb()}\n\n"
            f"# {app['name']} observability analysis\n\n"
            f"{app['scope']}\n\n"
            "## Status\n\n"
            f"**{app['version']} · {app['status'].replace('-', ' ')}.** "
            "This linked version is canonical for review; each detail page carries its own "
            "breadcrumb and all navigation remains in the host document panel.\n\n"
            "## Next steps\n\n"
            f"{numbered(app['nextSteps'])}\n\n"
            "## Changes in this version\n\n"
            f"{bullets(app['changes'])}\n\n"
            "## Table of contents and section summaries\n\n"
            + table(("Section", "Substantive summary", "Open"), rows)
            + "\n\n## Architecture summary\n\n"
            + summaries["architecture"]
            + "\n\n"
            + self.c["architecture"]["narrative"]
            + "\n\n## Priority review map\n\n"
            + table(
                ("Priority findings", "Primary use cases"),
                (
                    (finding_names, use_case_names),
                    ("[Review findings](findings/index.md)", "[Review use cases](use-cases/index.md)"),
                ),
            )
            + "\n\n## Side-panel navigation\n\n"
            "All links are relative Markdown links. No browser, localhost service, loopback "
            "address, JavaScript router, or high port is required to review this analysis.\n"
        )
        self.write("index.md", content)

    def render_architecture(self) -> None:
        a = self.c["architecture"]
        frontend = a["frontend"]
        sections = [
            breadcrumb(current="Architecture"),
            "",
            "# Architecture",
            "",
            a["narrative"],
        ]
        if frontend["applicable"]:
            sections.extend((
                "", "## Storefront and route model", "",
                f"The observed client is **{frontend['runtimeModel']}**, uses **{frontend['router']}**, "
                f"and assigns the sole provider initialization to `{frontend['initOwner']}`. "
                f"Single initialization is contractually {'required' if frontend['singleInit'] else 'unresolved'}.",
                "",
                table(
                    ("Path class", "Bounded page type", "Navigation", "Evidence"),
                    ((r["pathClass"], r["pageType"], r["navigation"], ", ".join(r["evidenceIds"])) for r in frontend["routes"]),
                ),
            ))
        sections.extend((
            "", "## Backend services and failure points", "",
            table(
                ("Service", "Runtime", "Account", "Role", "Failure points"),
                (
                    (
                        b["name"],
                        b["runtime"],
                        b["accountId"],
                        b["role"],
                        "; ".join(b["failurePoints"]),
                    )
                    for b in a["backends"]
                ),
            ), "", "## Accounts, buses, and downstream systems", "",
            table(
                ("Account", "Provider", "Boundary", "Evidence"),
                ((x["id"], x["provider"], x["boundary"], ", ".join(x["evidenceIds"])) for x in a["accounts"]),
            ),
        ))
        if a["buses"]:
            sections.extend(
                (
                    "",
                    table(
                        ("Bus", "Technology", "Cross-account", "Context carrier", "Failure points"),
                        (
                            (
                                x["id"],
                                x["technology"],
                                x["crossesAccounts"],
                                x["contextCarrier"],
                                "; ".join(x["failurePoints"]),
                            )
                            for x in a["buses"]
                        ),
                    ),
                )
            )
        if a["downstreams"]:
            sections.extend(
                (
                    "",
                    table(
                        ("Downstream", "Role", "Protocol", "Consequence"),
                        ((x["id"], x["role"], x["protocol"], x["consequence"]) for x in a["downstreams"]),
                    ),
                )
            )
        if a["thirdParties"]:
            sections.extend(
                (
                    "",
                    "## Third parties by consequence",
                    "",
                    table(
                        ("Third party", "Category", "Contract consequence", "Required controls"),
                        (
                            (x["name"], x["category"], x["consequence"], "; ".join(x["controls"]))
                            for x in a["thirdParties"]
                        ),
                    ),
                )
            )
        sections.extend(
            (
                "",
                "## Architecture failure register",
                "",
                table(
                    ("ID", "Surface", "Effect", "Detection"),
                    ((x["id"], x["surface"], x["effect"], x["detection"]) for x in a["failurePoints"]),
                ),
                finish(
                    (("Technology", "../technology/index.md"), ("Shared contracts", "../contracts/index.md")),
                    ("Continue to Technology", "../technology/index.md"),
                ),
            )
        )
        self.write("overview/index.md", "\n".join(sections))

    def render_technology(self) -> None:
        rows = (
            (x["name"], x["category"], x["versionEvidence"], x["observabilityConsequence"], ", ".join(x["evidenceIds"]))
            for x in self.c["technology"]
        )
        text = (
            f"{breadcrumb(current='Technology')}\n\n# Technology\n\n"
            f"{self.c['summaries']['technology']}\n\n"
            "## Evidence-derived technology inventory\n\n"
            + table(("Technology", "Category", "Version evidence", "Observability consequence", "Evidence"), rows)
            + finish(
                (("Architecture", "../overview/index.md"), ("Current telemetry", "../telemetry/index.md")),
                ("Continue to Current telemetry", "../telemetry/index.md"),
            )
        )
        self.write("technology/index.md", text)

    def render_telemetry(self) -> None:
        rows = (
            (
                x["component"], x["applicationScope"],
                f"{x['observedFrom']} to {x['observedTo']} (read {x['readAt']})",
                f"{x['source']} ({x['provenance']})",
                self._portfolio_evidence(x["portfolioEvidence"]),
                x["status"], x["trust"], x["observed"],
                "; ".join(x["gaps"]), ", ".join(x["evidenceIds"]),
            )
            for x in self.c["currentTelemetry"]
        )
        text = (
            f"{breadcrumb(current='Current telemetry')}\n\n# Current telemetry\n\n"
            f"{self.c['summaries']['currentTelemetry']}\n\n"
            "## Portfolio footprint and trust\n\n"
            + table((
                "Component", "Application scope", "Observation window",
                "Source and provenance", "Volume / MetricSet / MTS / SignalFlow evidence",
                "Status", "Trust", "Observed", "Gaps", "Evidence",
            ), rows)
            + "\n\nSignals marked present are not assumed trustworthy. Trust depends on verified "
            "load order, stable resource identity, complete propagation, and queryable data "
            "at the product surface that owns the question.\n"
            + finish(
                (("Architecture", "../overview/index.md"), ("Findings", "../findings/index.md")),
                ("Continue to Findings", "../findings/index.md"),
            )
        )
        self.write("telemetry/index.md", text)

    @staticmethod
    def _portfolio_evidence(value: dict[str, Any]) -> str:
        if value["disposition"] == "unavailable":
            return f"Unavailable: {value['reason']}"
        return (
            f"Volume: {value['volume']}; MetricSets: {value['metricSets']}; "
            f"MTS: {value['mts']}; SignalFlow: {value['signalFlow']}"
        )

    def render_findings(self) -> None:
        rows = (
            (
                f["id"],
                f["severity"],
                f["confidence"],
                f["priority"],
                f["title"],
                f["exposure"],
                f"[Detail]({f['id'].lower()}.md)",
            )
            for f in self.c["findings"]
        )
        index = (
            f"{breadcrumb(current='Findings')}\n\n# Findings\n\n"
            f"{self.c['summaries']['findings']}\n\n"
            + table(("ID", "Severity", "Confidence", "Priority", "Conclusion", "Exposure", "Detail"), rows)
            + finish(
                (("Current telemetry", "../telemetry/index.md"), ("Strategy", "../strategy/index.md")),
                ("Continue to Instrumentation strategy", "../strategy/index.md"),
            )
        )
        self.write("findings/index.md", index)
        for finding in self.c["findings"]:
            body = (
                f"{breadcrumb('Findings', finding['id'])}\n\n"
                f"# {finding['id']} — {finding['title']}\n\n"
                f"**Severity:** {finding['severity']} · **Confidence:** {finding['confidence']} · "
                f"**Priority:** {finding['priority']} · **Class:** {finding['class']}\n\n"
                "## Observed evidence\n\n"
                f"{finding['observed']}\n\nEvidence ids: {', '.join(finding['evidenceIds'])}\n\n"
                "## Files and surfaces involved\n\n"
                f"{bullets(finding['surfaces'])}\n\n"
                "## Exposure\n\n"
                f"{finding['exposure']}\n\n"
                "## Risk if unaddressed\n\n"
                f"{finding['risk']}\n\n"
                "## Remediation path\n\n"
                f"{numbered(finding['remediation'])}\n\n"
                "## Verification\n\n"
                f"{finding['verification']}\n\n"
                "## Affected contract objects\n\n"
                + table(
                    ("Object type", "IDs"),
                    (
                        ("Use cases", ", ".join(finding["useCaseIds"])),
                        ("Workflows", ", ".join(finding["workflowIds"])),
                        ("Business transactions", ", ".join(finding["businessTransactionIds"])),
                        ("Contracts", ", ".join(finding["contractIds"])),
                        ("Work orders", ", ".join(finding["workOrderIds"])),
                    ),
                )
                + finish(
                    (("Findings index", "index.md"), ("Work orders", "../work-orders/index.md")),
                    ("Return to Findings", "index.md"),
                )
            )
            self.write(f"findings/{finding['id'].lower()}.md", body)

    def render_strategy(self) -> None:
        parts = [
            breadcrumb(current="Instrumentation strategy"),
            "",
            "# Instrumentation strategy",
            "",
            self.c["summaries"]["strategy"],
        ]
        for item in self.c["strategy"]:
            parts.extend(
                (
                    "",
                    f"## {item['title']}",
                    "",
                    f"**Question:** {item['question']}",
                    "",
                    f"**Product surface:** {item['productSurface']} · "
                    f"**Retention/cost class:** {item['retentionClass']}",
                    "",
                    item["recommendation"],
                    "",
                    f"Evidence: {', '.join(item['evidenceIds'])}",
                )
            )
        parts.append(
            finish(
                (("Findings", "../findings/index.md"), ("Contracts", "../contracts/index.md")),
                ("Continue to Implementation path", "../implementation/index.md"),
            )
        )
        self.write("strategy/index.md", "\n".join(parts))

    def render_implementation(self) -> None:
        rows = (
            (
                p["id"],
                p["title"],
                p["outcome"],
                ", ".join(p["dependsOn"]) or "None",
                ", ".join(p["workOrderIds"]),
                "; ".join(p["exitCriteria"]),
            )
            for p in self.c["implementationPhases"]
        )
        text = (
            f"{breadcrumb(current='Implementation path')}\n\n# Implementation path\n\n"
            f"{self.c['summaries']['implementationPath']}\n\n"
            + table(("Phase", "Title", "Outcome", "Depends on", "Work orders", "Exit criteria"), rows)
            + "\n\nThe path separates bootstrap telemetry from the instrumentation contract. "
            "Provider setup and automatic spans do not satisfy workflow identity, propagation, "
            "bounded dimensions, operational detectors, or end-to-end verification.\n"
            + finish(
                (("Strategy", "../strategy/index.md"), ("Work orders", "../work-orders/index.md")),
                ("Continue to Work orders", "../work-orders/index.md"),
            )
        )
        self.write("implementation/index.md", text)

    def render_work_orders(self) -> None:
        app = self.c["application"]
        wiki_root = (
            f"../../../../../../wiki/apps/{app['id']}/versions/"
            f"{app['version']}/implementation/work-orders"
        )
        rows = (
            (
                w["id"],
                w["outcome"],
                ", ".join(w["dependsOn"]) or "None",
                w["status"],
                ", ".join(w["unlocks"]) or "None",
                f"[Open canonical work order]({wiki_root}/{w['id']}.md)",
            )
            for w in self.c["workOrders"]
        )
        index = (
            f"{breadcrumb(current='Work orders')}\n\n# Work orders\n\n"
            f"{self.c['summaries']['workOrders']}\n\n"
            + table(("ID", "Outcome", "Depends on", "Status", "Unlocks", "Detail"), rows)
            + finish(
                (("Implementation path", "../implementation/index.md"), ("Use cases", "../use-cases/index.md")),
                ("Continue to Use cases", "../use-cases/index.md"),
            )
        )
        self.write("work-orders/index.md", index)

    def render_use_cases(self) -> None:
        workflow_labels = {x["id"]: x["name"] for x in self.c["workflows"]}
        bt_labels = {x["id"]: x["name"] for x in self.c["businessTransactions"]}
        rows = (
            (
                u["title"],
                u["question"],
                ", ".join(workflow_labels[x] for x in u["workflowIds"]),
                ", ".join(bt_labels[x] for x in u["businessTransactionIds"]),
                f"[Detail]({u['id']}.md)",
            )
            for u in self.c["useCases"]
        )
        index = (
            f"{breadcrumb(current='Use cases')}\n\n# Use cases\n\n"
            f"{self.c['summaries']['useCases']}\n\n"
            + table(("Use case", "Question", "Workflows", "Business transactions", "Detail"), rows)
            + finish(
                (("Work orders", "../work-orders/index.md"), ("Workflows", "../workflows/index.md")),
                ("Continue to Workflows", "../workflows/index.md"),
            )
        )
        self.write("use-cases/index.md", index)
        for item in self.c["useCases"]:
            joins = (
                (j["from"], j["to"], j["type"], j["carrier"], j["reason"])
                for j in item["joins"]
            )
            text = (
                f"{breadcrumb('Use cases', item['title'])}\n\n# Use Case: {item['title']}\n\n"
                f"{item['narrative']}\n\n"
                "## Question answered\n\n"
                f"{item['question']}\n\n"
                "## Workflow identity\n\n"
                f"- Workflows: {self.link_list(item['workflowIds'], 'workflows', workflow_labels)}\n"
                f"- Business transactions: {self.link_list(item['businessTransactionIds'], 'business-transactions', bt_labels)}\n"
                f"- Span ids: {', '.join(item['spanIds'])}\n\n"
                "## Span events and metrics\n\n"
                f"- Events: {', '.join(item['eventNames'])}\n"
                f"- Metrics: {', '.join(item['metricNames'])}\n\n"
                "## Dashboard, detectors, and objective\n\n"
                f"- Dashboard: [{item['dashboardId']}](../operations/dashboards/{item['dashboardId']}.md)\n"
                f"- Detectors: {', '.join(item['detectorIds'])}\n"
                f"- Objectives: {', '.join(item['objectiveIds'])}\n\n"
                "## Cross-workflow joins\n\n"
                + table(("From", "To", "Join type", "Carrier", "Reason"), joins)
                + "\n\n## Verification\n\n"
                + bullets(item["verification"])
                + "\n\n## Delivery\n\n"
                f"Work orders: {', '.join(item['workOrderIds'])}. Evidence: {', '.join(item['evidenceIds'])}.\n"
                + finish(
                    (("Use-case index", "index.md"), ("Workflows", "../workflows/index.md")),
                    ("Return to Use cases", "index.md"),
                )
            )
            self.write(f"use-cases/{item['id']}.md", text)

    def render_workflows(self) -> None:
        rows = (
            (
                x["name"],
                x["narrative"],
                ", ".join(x["businessTransactionIds"]),
                f"[Detail]({x['id']}.md)",
            )
            for x in self.c["workflows"]
        )
        index = (
            f"{breadcrumb(current='Workflows')}\n\n# Workflows\n\n"
            f"{self.c['summaries']['workflows']}\n\n"
            + table(("Workflow", "Boundary", "Business transactions", "Detail"), rows)
            + finish(
                (("Use cases", "../use-cases/index.md"), ("Business transactions", "../business-transactions/index.md")),
                ("Continue to Business transactions", "../business-transactions/index.md"),
            )
        )
        self.write("workflows/index.md", index)
        for item in self.c["workflows"]:
            spans = (
                (
                    s["id"], s["name"], s["kind"], s["parentId"] or "None",
                    s["joinType"], s["service"], ", ".join(s["attributes"]),
                )
                for s in item["spans"]
            )
            events = ((e["name"], e["when"], ", ".join(e["attributes"])) for e in item["events"])
            metrics = (
                (m["name"], m["type"], m["unit"], m["purpose"], ", ".join(m["dimensions"]))
                for m in item["metrics"]
            )
            joins = ((j["from"], j["to"], j["type"], j["carrier"], j["reason"]) for j in item["joins"])
            text = (
                f"{breadcrumb('Workflows', item['name'])}\n\n# Workflow: {item['name']}\n\n"
                f"{item['narrative']}\n\n"
                "## Span tree\n\n"
                + table(("ID", "Span", "Kind", "Parent", "Join", "Service", "Attributes"), spans)
                + "\n\n## Span events\n\n"
                + table(("Event", "When", "Attributes"), events)
                + "\n\n## Metrics\n\n"
                + table(("Metric", "Type", "Unit", "Purpose", "Bounded dimensions"), metrics)
                + "\n\n## Join contract\n\n"
                + table(("From", "To", "Join type", "Carrier", "Reason"), joins)
                + "\n\n## Code locations\n\n"
                + bullets(item["codeLocations"])
                + "\n\n## Operations and verification\n\n"
                f"- Dashboard: [{item['dashboardId']}](../operations/dashboards/{item['dashboardId']}.md)\n"
                f"- Detectors: {', '.join(item['detectorIds'])}\n"
                f"- Objectives: {', '.join(item['objectiveIds'])}\n"
                + bullets(item["verification"])
                + f"\n- Work orders: {', '.join(item['workOrderIds'])}\n"
                + finish(
                    (("Workflow index", "index.md"), ("Business transactions", "../business-transactions/index.md")),
                    ("Return to Workflows", "index.md"),
                )
            )
            self.write(f"workflows/{item['id']}.md", text)

    def render_transactions(self) -> None:
        workflow_labels = {x["id"]: x["name"] for x in self.c["workflows"]}
        rows = (
            (
                x["name"], x["groupingValue"], x["artifact"],
                ", ".join(workflow_labels[i] for i in x["workflowIds"]),
                f"[Detail]({x['id']}.md)",
            )
            for x in self.c["businessTransactions"]
        )
        index = (
            f"{breadcrumb(current='Business transactions')}\n\n# Business transactions\n\n"
            f"{self.c['summaries']['businessTransactions']}\n\n"
            + table(("Transaction", "Bounded value", "Owning artifact", "Evidence-derived workflows", "Detail"), rows)
            + finish(
                (("Workflows", "../workflows/index.md"), ("Shared contracts", "../contracts/index.md")),
                ("Continue to Shared signal contracts", "../contracts/index.md"),
            )
        )
        self.write("business-transactions/index.md", index)
        for item in self.c["businessTransactions"]:
            text = (
                f"{breadcrumb('Business transactions', item['name'])}\n\n# BT: {item['name']}\n\n"
                f"{item['summary']}\n\n"
                f"**Grouping value:** `{item['groupingValue']}` · **Artifact:** `{item['artifact']}`\n\n"
                "## Exhaustive evidence-derived workflow catalogue\n\n"
                + "\n".join(
                    f"- [{workflow_labels[workflow_id]}](../workflows/{workflow_id}.md)"
                    for workflow_id in item["workflowIds"]
                )
                + "\n\n## Set, propagate, and query\n\n"
                f"- **Where set:** {item['whereSet']}\n"
                f"- **Propagation:** {item['propagation']}\n"
                f"- **Tenant rule:** {item['tenantRule']}\n"
                f"- **Verification:** {item['verification']}\n\n"
                f"Work orders: {', '.join(item['workOrderIds'])}. Evidence: {', '.join(item['evidenceIds'])}.\n"
                + finish(
                    (("Business-transaction index", "index.md"), ("Shared contracts", "../contracts/index.md")),
                    ("Return to Business transactions", "index.md"),
                )
            )
            self.write(f"business-transactions/{item['id']}.md", text)

    def render_contracts(self) -> None:
        c = self.c["contracts"]
        pages = [
            (
                "Cross-cutting propagation",
                "cross-cutting.md",
                "Write-once baggage, an allowlisted stamp processor, and backend extraction"
                + (
                    " with explicit message carriers."
                    if c["crossCutting"]["messagePropagation"]["applicable"]
                    else "."
                ),
            ),
            ("Parent-child, span links, and pivots", "joins.md", "An explicit join type for every evidenced causal or identity boundary."),
            ("Cardinality and MPM", "cardinality.md", "Entitlement arithmetic and explicit dimension-eligible versus attribute-only lists."),
        ]
        if c["spaRoutes"]["applicable"]:
            pages.insert(0, ("Single initialization and SPA routes", "single-init-spa-routes.md", "One provider owner, bounded route classification, and client-navigation spans."))
        if c["attribution"]["applicable"]:
            pages.insert(2 if c["spaRoutes"]["applicable"] else 1, ("First-touch attribution", "attribution.md", "One event per session, first and last touch storage, and a bounded baggage subset."))
        if c["collector"]["applicable"]:
            pages.insert(-1, ("Collector processing", "collector.md", "Derivation, privacy controls, processor ordering, and export-safe signal handling."))
        index = (
            f"{breadcrumb(current='Shared signal contracts')}\n\n# Shared signal contracts\n\n"
            f"{self.c['summaries']['contracts']}\n\n"
            + table(("Contract", "Purpose", "Open"), ((x[0], x[2], f"[Open]({x[1]})") for x in pages))
            + finish(
                (("Business transactions", "../business-transactions/index.md"), ("Operations", "../operations/index.md")),
                ("Continue to Operations and verification", "../operations/index.md"),
            )
        )
        self.write("contracts/index.md", index)
        spa = c["spaRoutes"]
        if spa["applicable"]:
            self.write(
                "contracts/single-init-spa-routes.md",
                f"{breadcrumb('Shared signal contracts', 'Single initialization and SPA routes')}\n\n"
                "# Single initialization and SPA routes\n\n"
                f"{c['singleInit']}\n\n"
                "## Route instrumentation\n\n"
                f"**Owner:** `{spa['owner']}` · **Navigation span:** `{spa['navigationSpan']}`\n\n"
                f"{spa['classifier']}\n\n"
                + code(spa["code"], "javascript")
                + finish((("Contracts", "index.md"), ("Architecture", "../overview/index.md")), ("Return to Contracts", "index.md")),
            )
        cross = c["crossCutting"]
        cross_related = [("Contracts", "index.md")]
        if c["collector"]["applicable"]:
            cross_related.append(("Collector", "collector.md"))
        self.write(
            "contracts/cross-cutting.md",
            f"{breadcrumb('Shared signal contracts', 'Cross-cutting propagation')}\n\n"
            "# Cross-Cutting Attributes and Baggage Propagation\n\n"
            "Set each key once where it becomes known, carry the allowlisted subset in W3C "
            "Baggage, and stamp every new span in `SpanProcessor.onStart`. This makes dashboard "
            "variables, detector groups, and Related Content consistent without per-service code.\n\n"
            "## Attribute set\n\n"
            + table(
                ("Attribute", "Type", "Source", "Set at", "Cardinality", "Dimension", "Propagation", "Consumers"),
                (
                    (
                        a["name"], a["type"], a["source"], a["setAt"], a["cardinalityClass"],
                        a["dimensionEligible"], a["propagation"], "; ".join(a["consumers"]),
                    )
                    for a in cross["attributes"]
                ),
            )
            + "\n\n## Provider bootstrap\n\n"
            + code(cross["providerBootstrap"], "javascript")
            + "\n\n## Allowlisted SpanProcessor\n\n"
            + code(cross["spanProcessor"], "typescript")
            + "\n\n## Identity write\n\n"
            + code(cross["identityWrite"], "javascript")
            + "\n\n## Backend composite propagator\n\n"
            + code(cross["backendPropagator"], "javascript")
            + (
                "\n\n## Message inject and extract\n\n"
                + code(cross["messagePropagation"]["code"], "javascript")
                if cross["messagePropagation"]["applicable"] else ""
            )
            + finish(cross_related, ("Return to Contracts", "index.md")),
        )
        attr = c["attribution"]
        if attr["applicable"]:
            self.write(
                "contracts/attribution.md",
                f"{breadcrumb('Shared signal contracts', 'First-touch attribution')}\n\n"
                "# First-touch attribution\n\n"
                f"{attr['trigger']}\n\n"
                f"- Event: `{attr['event']}`\n"
                f"- First touch: {attr['firstTouch']}\n"
                f"- Last touch: {attr['lastTouch']}\n"
                f"- Baggage subset: {', '.join(attr['baggageKeys'])}\n\n"
                "## Deterministic classifier and capture\n\n"
                + code(attr["code"], "javascript")
                + finish((("Contracts", "index.md"), ("Use cases", "../use-cases/index.md")), ("Return to Contracts", "index.md")),
            )
        self.write(
            "contracts/joins.md",
            f"{breadcrumb('Shared signal contracts', 'Join contract')}\n\n# Parent-child, span links, and pivots\n\n"
            "Continue the trace for one causal request or message. Use span links only when "
            "a parent would lie, including fan-in, scheduled batches, webhooks that begin a "
            "new trace, and DLQ redrive. Use an attribute pivot for high-cardinality business ids.\n\n"
            + table(
                ("From", "To", "Join type", "Carrier", "Reason"),
                ((j["from"], j["to"], j["type"], j["carrier"], j["reason"]) for j in c["joins"]),
            )
            + finish((("Contracts", "index.md"), ("Workflows", "../workflows/index.md")), ("Return to Contracts", "index.md")),
        )
        collector = c["collector"]
        if collector["applicable"]:
            self.write(
                "contracts/collector.md",
                f"{breadcrumb('Shared signal contracts', 'Collector processing')}\n\n# Collector processing\n\n"
                f"{collector['placement']}\n\n"
                f"**Processor order:** {' → '.join(collector['processorOrder'])}. Derivation and "
                "redaction run before spanmetrics so generated series contain bounded values and "
                "never preserve fields that policy requires removing.\n\n"
                "## OTTL derivation\n\n"
                + code(collector["ottl"], "yaml")
                + "\n\n## Redaction contract\n\n"
                + table(("Field", "Action", "Reason"), ((r["field"], r["action"], r["reason"]) for r in collector["redactions"]))
                + finish((("Contracts", "index.md"), ("Cardinality", "cardinality.md")), ("Return to Contracts", "index.md")),
            )
        card = c["cardinality"]
        self.write(
            "contracts/cardinality.md",
            f"{breadcrumb('Shared signal contracts', 'Cardinality and MPM')}\n\n# Cardinality and MPM\n\n"
            "The budget is arithmetic against the supplied entitlement. The proposed promotion "
            "must fit after current use and the operational reserve; identity and raw-route keys "
            "remain trace attributes even when they are valuable troubleshooting pivots.\n\n"
            + table(
                ("Entitlement", "In use", "Reserved", "Proposed cost", "Headroom after"),
                ((card["entitlement"], card["inUse"], card["reserved"], card["proposedCost"], card["headroomAfter"]),),
            )
            + "\n\n## Dimension-eligible\n\n"
            + bullets(card["dimensionEligible"])
            + "\n\n## Attribute-only\n\n"
            + bullets(card["attributeOnly"])
            + finish((("Contracts", "index.md"), ("Operations", "../operations/index.md")), ("Return to Contracts", "index.md")),
        )

    def render_operations(self) -> None:
        o = self.c["operations"]
        conditional_lines = []
        if o["synthetics"]["applicable"]:
            conditional_lines.append(
                f"- **Synthetics:** {o['synthetics']['design']} "
                f"Evidence: {o['synthetics']['evidence']}"
            )
        if o["thousandEyes"]["applicable"]:
            conditional_lines.append(
                f"- **ThousandEyes:** {o['thousandEyes']['design']} "
                f"Evidence: {o['thousandEyes']['evidence']}"
            )
        index = (
            f"{breadcrumb(current='Operations and verification')}\n\n# Operations and verification\n\n"
            f"{self.c['summaries']['operations']}\n\n"
            "## Catalogues\n\n"
            + table(
                ("Area", "Count", "Open"),
                (
                    ("Dashboards", len(o["dashboards"]), "[Open](dashboards/index.md)"),
                    ("Detectors", len(o["detectors"]), "[Open](detectors/index.md)"),
                    ("Objectives", len(o["objectives"]), "[Open](objectives/index.md)"),
                    ("Verification criteria", len(o["verificationCriteria"]), "[Open](verification.md)"),
                ),
            )
            + "\n\n## Release and log correlation\n\n"
            + f"- **Release correlation:** {o['releaseCorrelation']}\n"
            + f"- **Log correlation:** {o['logCorrelation']}\n"
            + (
                "\n## Conditional path and canary coverage\n\n"
                + "\n".join(conditional_lines)
                + "\n"
                if conditional_lines
                else ""
            )
            + finish(
                (("Contracts", "../contracts/index.md"), ("Reference", "../reference/index.md")),
                ("Continue to Reference", "../reference/index.md"),
            )
        )
        self.write("operations/index.md", index)
        self.write(
            "operations/dashboards/index.md",
            f"{nested_breadcrumb('Operations and verification', 'Dashboards')}\n\n# Dashboards\n\n"
            "Each dashboard uses bounded variables, p90 latency unless another percentile was "
            "supplied, release overlays, workflow deep links, and trace-to-log correlation.\n\n"
            + table(
                ("Dashboard", "Variables", "Panels", "Release overlay", "Detail"),
                (
                    (
                        d["title"], "; ".join(d["variables"]), "; ".join(d["panels"]),
                        d["releaseOverlay"], f"[Detail]({d['id']}.md)",
                    )
                    for d in o["dashboards"]
                ),
            )
            + finish((("Operations", "../index.md"), ("Detectors", "../detectors/index.md")), ("Return to Operations", "../index.md")),
        )
        for item in o["dashboards"]:
            self.write(
                f"operations/dashboards/{item['id']}.md",
                f"{nested_breadcrumb('Operations and verification', item['title'])}\n\n# Dashboard: {item['title']}\n\n"
                "This operational view combines long-term bounded metrics with trace and log "
                "deep links. Aggregate panels use metric dimensions; identifiers remain query-time pivots.\n\n"
                "## Variables\n\n"
                + bullets(item["variables"])
                + "\n\n## Panels\n\n"
                + bullets(item["panels"])
                + "\n\n## SignalFlow\n\n"
                + code(item["signalFlow"], "python")
                + f"\n\n**Release overlay required:** {item['releaseOverlay']}.\n"
                + finish((("Dashboard catalogue", "index.md"), ("Detectors", "../detectors/index.md")), ("Return to Dashboards", "index.md")),
            )
        self.write(
            "operations/detectors/index.md",
            f"{nested_breadcrumb('Operations and verification', 'Detectors')}\n\n# Detectors catalog\n\n"
            "Every detector has an explicit threshold, evaluation window, bounded group-by, "
            "severity, response path, and a verification method before arming.\n\n"
            + table(
                ("ID", "Name", "Signal", "Threshold", "Window", "Group by", "Severity", "Runbook"),
                (
                    (
                        d["id"], d["name"], d["signal"], d["threshold"], d["window"],
                        ", ".join(d["groupBy"]), d["severity"], d["runbook"],
                    )
                    for d in o["detectors"]
                ),
            )
            + finish((("Operations", "../index.md"), ("Objectives", "../objectives/index.md")), ("Return to Operations", "../index.md")),
        )
        self.write(
            "operations/objectives/index.md",
            f"{nested_breadcrumb('Operations and verification', 'Objectives')}\n\n# Objectives and error budgets\n\n"
            "Objectives define the measured SLI, target, rolling window, explicit error budget, "
            "and the query or controlled test that proves the calculation is usable.\n\n"
            + table(
                ("ID", "Name", "SLI", "Target", "Window", "Error budget", "Verification"),
                (
                    (
                        x["id"], x["name"], x["sli"], x["target"], x["window"],
                        x["errorBudget"], x["verification"],
                    )
                    for x in o["objectives"]
                ),
            )
            + finish((("Operations", "../index.md"), ("Verification", "../verification.md")), ("Return to Operations", "../index.md")),
        )
        budgets = o["performanceBudgets"]
        self.write(
            "operations/verification.md",
            f"{breadcrumb('Operations and verification', 'Verification')}\n\n# Verification criteria and QA budgets\n\n"
            "The checks below are outcome proofs, not assertions that installation succeeded. "
            "They cover propagation, semantic rendering, detector inputs, portfolio joins, and "
            "the deterministic QA path used before review.\n\n"
            + table(
                ("ID", "Criterion", "Method", "Expected"),
                ((x["id"], x["criterion"], x["method"], x["expected"]) for x in o["verificationCriteria"]),
            )
            + "\n\n## Performance budgets\n\n"
            + table(
                ("Validation seconds", "Render seconds", "Maximum files", "Maximum bytes"),
                ((budgets["validationSeconds"], budgets["renderSeconds"], budgets["maxOutputFiles"], budgets["maxOutputBytes"]),),
            )
            + finish((("Operations", "index.md"), ("Reference", "../reference/index.md")), ("Return to Operations", "index.md")),
        )

    def render_reference(self) -> None:
        r = self.c["reference"]
        text = (
            f"{breadcrumb(current='Reference')}\n\n# Reference\n\n"
            f"{self.c['summaries']['reference']}\n\n"
            "## Evidence register\n\n"
            + table(("Evidence id", "Label", "Provenance"), ((x["id"], x["label"], x["provenance"]) for x in r["evidence"]))
            + "\n\n## Sources consulted\n\n"
            + bullets(r["sources"])
            + "\n\n## Prior artifacts used as evidence or quality bars\n\n"
            + bullets(r["priorArtifacts"])
            + "\n\n## Open evidence questions\n\n"
            + bullets(r["unknowns"])
            + finish(
                (("Architecture", "../overview/index.md"), ("Operations", "../operations/index.md")),
                ("Return to analysis landing page", "../index.md"),
            )
        )
        self.write("reference/index.md", text)


def render(contract_path: Path, output: Path, clean: bool = False) -> int:
    contract = load_json(contract_path)
    failures = validate_contract(contract)
    if failures:
        for failure in failures:
            print(f"FAIL — {failure}")
        return 1
    if output.exists() and any(output.iterdir()):
        if not clean:
            print(f"FAIL — output is not empty: {output}; pass --clean to replace it")
            return 1
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(contract, output)
    renderer.render()
    print(f"PASS — rendered {len(renderer.written)} Markdown pages to {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv)
    return render(args.contract, args.output, args.clean)


if __name__ == "__main__":
    sys.exit(main())
