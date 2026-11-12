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
| [`../references/analysis-run-lifecycle.md`](../references/analysis-run-lifecycle.md) | Version branch, staged-tree dispatch gate, review loop, acceptance, merge, and handoff |
| [`../references/agent-wiki.md`](../references/agent-wiki.md) | Versioned subject notes and work orders |
| [`../references/implementation-work-orders.md`](../references/implementation-work-orders.md) | Bounded targets, repository legs, dependencies, and PR coordination |
| [`../references/provenance-ledger.md`](../references/provenance-ledger.md) | Evidence and run state |
| [`../references/context-loading.md`](../references/context-loading.md) | Evidence-gated technical references |
| [`../references/existing-telemetry.md`](../references/existing-telemetry.md) | Direct APIs, connected integrations, MetricSets, usage, and SignalFlow cross-check |
| [`../references/cross-cutting-attributes.md`](../references/cross-cutting-attributes.md) | Cross-Cutting Attributes and Baggage Propagation |
| [`../references/business-value.md`](../references/business-value.md) | Value from stated, measured, public, and derived evidence |
| [`../references/entitlement-exposure.md`](../references/entitlement-exposure.md) | Measured usage and enforced-system-limit appendix |
| [`schemas/analysis-job-manifest.schema.json`](schemas/analysis-job-manifest.schema.json) | Six bounded host-run evidence workstreams and coordinator reservation |
| [`schemas/analysis-worker-result.schema.json`](schemas/analysis-worker-result.schema.json) | Auditable worker evidence and execution intervals |
| [`schemas/analysis-contract.schema.json`](schemas/analysis-contract.schema.json) | Canonical content rendered into the linked analysis site |

## Output

Always:

```text
docs/observability/analysis/<app>/V<N>/
docs/observability/analysis-contract.json
docs/observability/analysis-job-manifest.json
docs/observability/analysis-worker-results/
docs/observability/attribute-schema.json
docs/observability/implementation-map.json
docs/observability/provenance-ledger.json
docs/observability/verification-plan.json
wiki/apps/<app>/versions/V<N>/
```

Version selectors use `[V1] [V2] [V3]` and continue monotonically. Validate the canonical
JSON and render the landing page plus detail tree deterministically with
`scripts/render_analysis_site.py`; after acceptance replace only the next-step callout
from `templates/analysis-site/accepted-next-steps.md`. Do not redesign the approved layout. The analysis
directory contains the landing page and all linked detail pages. The wiki
contains one note per substantive object and every work order. The version landing page
links the matching wiki snapshot.

Create the usage/system-limit appendix only when direct measurement or meaningful
bounded recommendation arithmetic supports it. Create a short `.docx` only when the human asks for it; it is under 20 pages and
contains the summary, architecture, findings, path, work-order summary, and use cases.

## Rules

- Derive names from this application. A different site's artifact is not evidence.
- Derive the number of business transactions and workflows from current evidence. A
  same-customer prior guide is a quality and continuity input, not a fixed taxonomy or
  required count; retain, revise, add, or retire names with provenance.
- Load only digest-authorized root `obconfig.yaml`. Rehash the complete artifact
  directory, reread added/changed files, remove deleted context, and preserve accepted
  historical versions.
- Atomically run `manage_obconfig.py claim --command <origin> --intended-version
  V<N>` and use its sanitized full artifact delta. Then run exactly
  `python3 <obengineer-root>/skills/engagement-intake/scripts/manage_obconfig.py
  --project-root . direct-api --phase analysis --command <origin>
  --intended-version V<N>`. This supported path securely loads the
  ignored mode-0600 config and emits centralized-redacted JSON only. Append each direct
  disposition and measured aggregate to provenance; map `not-configured` and failed
  dispositions to source limitations/unresolved evidence. Use connected MCP tools only
  as supplemental evidence; MCP cannot satisfy or relabel the direct attempt.
- Run `manage_obconfig.py safe-active --command <origin> --intended-version V<N>`
  and append its redacted outcomes to provenance. Passive/none must produce no requests.
  The claim is revalidated around every supported network path. After all analysis,
  network, render, and validation work, stage intended analysis paths and run
  `manage_obconfig.py finalize` with the same binding and explicit generated-output
  roots. Commit exactly the bound index tree. Run `dispatch`, then `verify-dispatch`
  immediately before push/PR work. Consume only the successfully published immutable
  dispatch. Decline/failure invokes `manage_obconfig.py abort` with the same binding,
  releasing the claim without changing baseline/history.
- Never print or store a secret. Record shape, location, and exposure only.
- Missing optional inputs do not block analysis and do not create empty chapters.
- Findings link affected use cases, workflows, business transactions, contracts, and
  work orders.
- Review use cases before workflows and workflows before business transactions.
- Keep Cross-Cutting Attributes and Baggage Propagation complete in the wiki: provider
  bootstrap, allowlisted `SpanProcessor.onStart`, identity write, backend composite
  propagator, and message inject/extract where applicable.
- Directly measured usage and `sf.org.limit.*` enforced limits price system headroom;
  they are never contractual entitlement and never silently trim the strategy.
- When usage or an enforced limit is unavailable, preserve proposed MTS arithmetic but
  leave usage, reserve, and system headroom explicitly unavailable.
- Every detector has a threshold; every objective has an error budget.
- No named engineer, named owner, or accepter is required.
- Never start a web server, open a browser, or return localhost.

## Process

### 1. Establish version and prior state

Find the latest `[V<N>]`, its acceptance record, stable finding ids, accepted names,
schema, decisions, and work-order outcomes. Create the next immutable version. A repeat
run is a delta, not a rewrite.

### 2. Collect evidence in parallel

Write one bounded manifest with exactly six workstreams:

- production browser and route behavior;
- source, configuration, dependencies, and technology;
- diagrams and prior artifacts;
- direct Observability Cloud APIs and relevant connected integrations;
- direct Splunk Platform APIs, cloud boundaries, and messaging; and
- public evidence plus security assessment within authorization.

Reserve one host concurrency slot for the coordinator. The host creates workers; this
repository validates only the manifest, result shape, observed intervals, and capacity.
Never claim that a repository script spawns agents. With two or more runnable jobs, the
recorded worker intervals must overlap without exceeding host capacity after the
coordinator reservation. Do not parallelize naming or schema reconciliation. Merge
evidence into the ledger with measured, stated, public, or derived provenance.
Every worker interval fits its job deadline. Limited results identify nonempty
limitations and the exact unavailable manifest scopes or outputs. Persist
`analysis-run-timing.json` with bounded collection, reconciliation, render, validation,
and total intervals.

The production scan checks timings, status versus content, router behavior, provider
initialization, competing agents, CSP, consent, third parties, beacons, route changes,
and authenticated surfaces when configured.

### 3. Read architecture and findings

Write the observed site/backend architecture, languages, frameworks, runtimes, accounts,
buses, third parties, and current telemetry. Raise actionable findings with evidence,
impact, confidence, remediation, and verification. Security findings follow
`security-assessment.md`.

Architecture names the storefront or client composition, every evidenced backend,
account boundary, bus, downstream, third party by contract consequence, initialization
owner, SPA route behavior, and failure point. Technology and Current telemetry are
separate review views. Prior diagrams and guides supply evidence and depth only; they
never donate another target's taxonomy.

Each Current telemetry row records application scope, observation window and read time,
source/provenance, and volume, MetricSet, MTS, and SignalFlow evidence. When those
portfolio checks cannot be obtained, record an explicit `unavailable` disposition and
reason rather than an empty field. Every workflow records repository-relative code
locations.

### 4. Design from use cases inward

Rank questions the instrumentation must answer. For every use case:

1. state why it matters and the user-facing question;
2. define its workflows and business-transaction grouping;
3. define span boundaries, events, captured context, joins, meters, detectors,
   objective with error budget, dashboard, and acceptance proof;
4. register every attribute and dimension decision; and
5. link the work orders that implement it.

Enumerate accepted workflows from source, analytics events, feature flags, UI copy,
diagrams, and message contracts. Do not invent generic journey names.
Keep each business transaction's exhaustive evidence-derived workflow catalogue separate
from the smaller set promoted for complete span-tree and use-case design.

For every ranked use case include the complete span tree; span events; metrics with three
to six bounded dimensions; dashboard variables and panels; threshold, window, and
group-by for every detector; objective and error budget; release correlation; logs;
Synthetics and ThousandEyes when evidence makes them applicable; and runnable
verification. Label every join `continue-trace`, `span-link`, or `attribute-pivot`.

### 5. Build the strategy and dependency path

Cover only layers in evidence: deterministic guardrails, browser, identity/context,
backend, messaging, collector, metrics/cardinality, logs, dashboards/detectors/objectives,
release events, and verification. Order phases by dependency and trust.
Browser attribution, message propagation, and Collector contracts each carry explicit
applicability and evidence. Applicable contracts contain complete code/configuration;
inapplicable contracts produce no detail page or link.

### 6. Materialize wiki and work orders

Run `$instrumentation-wiki` during analysis. Generate the full proposed queue under the
matching wiki version. Dependency-free orders are `proposed`; dependent orders are
`blocked`. Every object links its work orders and every work order links back.

Work order 1 establishes deterministic schema, single-init, workflow-registry, baggage
allowlist, and deny-list checks before journey code.
When application source or authorization is absent, record workflow and work-order
repository mapping as unresolved, leave paths and repository legs empty, and keep affected
orders blocked. Never invent an implementation path to satisfy the contract.

### 7. Validate

Validate:

- job manifest, worker intervals, host capacity, and coordinator reservation;
- canonical analysis contract and deterministic repeated rendering;
- schema-v1 analysis contracts migrate deterministically with
  `scripts/migrate_analysis_contract.py`; newly generated contracts use schema v2;
- provenance ledger and analysis seal;
- schema version 2 analysis contract and content-bound acceptance inputs;
- schema and implementation map;
- verification plan schema version 2 with stable `source_ref` values and actionable
  `VC-*` criteria;
- landing-page links and breadcrumbs;
- wiki links, frontmatter, work-order dependency graph, and reverse links;
- no credential-shaped values; and
- optional Word summary only when requested.

Run `make qa-analysis` against the generic representative fixture and enforce its
validation-time, render-time, output-file, and output-byte budgets.

Run `$deliverable-review` against the linked site and wiki. Fix every blocking defect.
Then stage and finalize `docs/observability` and the generated versioned wiki with the
runtime gate. Commit the exact finalized tree and verify dispatch before external work.
Index or commit mutation blocks dispatch. Working-tree changes after staging belong to
the next run and cannot alter successful consume of the published commit.

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
