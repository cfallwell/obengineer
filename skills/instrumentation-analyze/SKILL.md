---
name: instrumentation-analyze
description: >-
  Analyze a production application and publish a versioned linked Markdown
  strategy: architecture, findings, implementation path, work orders, use cases,
  workflows, business transactions, signal contracts, and verification. Uses
  source, production scans, direct Splunk APIs, and connected MCP tools in
  parallel. Use for $instrumentation-analyze, /ob-start, /ob-analyze, repeat
  analysis, or questions about the generated observability strategy.
metadata:
  author: obengineer
  version: 0.3.0
  category: observability
---

# Instrumentation analysis

Analysis establishes what exists, what is wrong, what to instrument, how to implement it,
and how to prove the result. The human review surface is the linked Markdown site defined
by [`../references/analysis-site.md`](../references/analysis-site.md). The same run creates
the versioned agent wiki and every proposed work order.

The target is read-only. Application changes happen only through accepted work orders.

## Authorities

| Reference | Owns |
|---|---|
| [`../references/analysis-site.md`](../references/analysis-site.md) | Versioned layout, landing page, links, breadcrumbs, side panel handoff, optional Word summary |
| [`../references/critical-findings.md`](../references/critical-findings.md) | Finding evidence, severity, exposure, remediation, and credential handling |
| [`../references/security-assessment.md`](../references/security-assessment.md) | Authorized credential/API checks and OWASP coverage |
| [`../references/analysis-run-lifecycle.md`](../references/analysis-run-lifecycle.md) | Version branch, phase commits, review loop, acceptance, merge, and handoff |
| [`../references/agent-wiki.md`](../references/agent-wiki.md) | Versioned subject notes and work orders |
| [`../references/implementation-work-orders.md`](../references/implementation-work-orders.md) | Bounded targets, repository legs, dependencies, and PR coordination |
| [`../references/provenance-ledger.md`](../references/provenance-ledger.md) | Evidence and run state |
| [`../references/context-loading.md`](../references/context-loading.md) | Evidence-gated technical references |
| [`../references/existing-telemetry.md`](../references/existing-telemetry.md) | Direct APIs, connected integrations, MetricSets, usage, and SignalFlow cross-check |
| [`../references/cross-cutting-attributes.md`](../references/cross-cutting-attributes.md) | Cross-Cutting Attributes and Baggage Propagation |
| [`../references/business-value.md`](../references/business-value.md) | Value from stated, measured, public, and derived evidence |
| [`../references/entitlement-exposure.md`](../references/entitlement-exposure.md) | Separate account-team pricing |

## Output

Always:

```text
docs/observability/analysis/<app>/V<N>/
docs/observability/analysis-contract.json
docs/observability/attribute-schema.json
docs/observability/implementation-map.json
docs/observability/provenance-ledger.json
docs/observability/verification-plan.json
wiki/apps/<app>/versions/V<N>/
```

Version selectors use `[V1] [V2] [V3]` and continue monotonically. Start the landing
page from `templates/analysis-site/index.md` and detail pages from
`templates/analysis-site/detail.md`; after acceptance replace only the next-step callout
from `templates/analysis-site/accepted-next-steps.md`. Do not redesign the approved layout. The analysis
directory contains the landing page and all linked detail pages. The wiki
contains one note per substantive object and every work order. The version landing page
links the matching wiki snapshot.

Create entitlement exposure only when entitlement or a meaningful traffic baseline was
supplied. Create a short `.docx` only when the human asks for it; it is under 20 pages and
contains the summary, architecture, findings, path, work-order summary, and use cases.

## Rules

- Derive names from this application. A different site's artifact is not evidence.
- Use direct Observability Cloud and Splunk Platform APIs when configured. Use connected
  MCP tools as additional sources; do not treat MCP as the only tenant interface.
- Never print or store a secret. Record shape, location, and exposure only.
- Missing optional inputs do not block analysis and do not create empty chapters.
- Findings link affected use cases, workflows, business transactions, contracts, and
  work orders.
- Review use cases before workflows and workflows before business transactions.
- Keep Cross-Cutting Attributes and Baggage Propagation complete in the wiki: provider
  bootstrap, allowlisted `SpanProcessor.onStart`, identity write, backend composite
  propagator, and message inject/extract where applicable.
- Entitlement prices the strategy; it does not silently trim it.
- Every detector has a threshold; every objective has an error budget.
- No named engineer, named owner, or accepter is required.
- Never start a web server, open a browser, or return localhost.

## Process

### 1. Establish version and prior state

Find the latest `[V<N>]`, its acceptance record, stable finding ids, accepted names,
schema, decisions, and work-order outcomes. Create the next immutable version. A repeat
run is a delta, not a rewrite.

### 2. Collect evidence in parallel

Fill every safe sub-agent slot with independent work:

- production browser and route behavior;
- source, configuration, diagrams, and dependencies;
- direct Observability Cloud APIs;
- direct Splunk Platform APIs across approved indexes;
- each relevant connected MCP integration;
- cloud and message boundaries;
- security assessment within authorization; and
- public evidence when permitted.

Do not parallelize naming or schema reconciliation. Merge evidence into the ledger with
measured, stated, public, or derived provenance.

The production scan checks timings, status versus content, router behavior, provider
initialization, competing agents, CSP, consent, third parties, beacons, route changes,
and authenticated surfaces when configured.

### 3. Read architecture and findings

Write the observed site/backend architecture, languages, frameworks, runtimes, accounts,
buses, third parties, and current telemetry. Raise actionable findings with evidence,
impact, confidence, remediation, and verification. Security findings follow
`security-assessment.md`.

### 4. Design from use cases inward

Rank questions the instrumentation must answer. For every use case:

1. state why it matters and the user-facing question;
2. define its workflows and business-transaction grouping;
3. define span boundaries, events, captured context, joins, meters, detectors,
   objective, dashboard, and acceptance proof;
4. register every attribute and dimension decision; and
5. link the work orders that implement it.

Enumerate accepted workflows from source, analytics events, feature flags, UI copy,
diagrams, and message contracts. Do not invent generic journey names.

### 5. Build the strategy and dependency path

Cover only layers in evidence: deterministic guardrails, browser, identity/context,
backend, messaging, collector, metrics/cardinality, logs, dashboards/detectors/objectives,
release events, and verification. Order phases by dependency and trust.

### 6. Materialize wiki and work orders

Run `$instrumentation-wiki` during analysis. Generate the full proposed queue under the
matching wiki version. Dependency-free orders are `proposed`; dependent orders are
`blocked`. Every object links its work orders and every work order links back.

Work order 1 establishes deterministic schema, single-init, workflow-registry, baggage
allowlist, and deny-list checks before journey code.

### 7. Validate

Validate:

- provenance ledger and analysis seal;
- schema version 2 analysis contract and content-bound acceptance inputs;
- schema and implementation map;
- verification plan schema version 2 with stable `source_ref` values and actionable
  `VC-*` criteria;
- landing-page links and breadcrumbs;
- wiki links, frontmatter, work-order dependency graph, and reverse links;
- no credential-shaped values; and
- optional Word summary only when requested.

Run `$deliverable-review` against the linked site and wiki. Fix every blocking defect.

### 8. Review, accept, and hand off

Follow `analysis-run-lifecycle.md`. Open one PR, process review comments, and ask whether
to accept and merge. Explicit `yes` writes content-bound acceptance, marks eligible work
orders Ready, and authorizes merge.

After merge, return only the host-native documentation link plus concise next steps. After
acceptance, include the first Ready work order and exact `/ob-implement` command.

## Non-goals

- No application code, tenant mutation, deployment, Terraform apply, or detector arming.
- No mandatory Word document.
- No second narrative document for implementers.
- No manual input-file editing, manual commit SHA, or required `unknown`.
