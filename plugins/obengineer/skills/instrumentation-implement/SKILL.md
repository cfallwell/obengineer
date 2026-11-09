---
name: instrumentation-implement
description: >-
  Implement an accepted instrumentation guide as small reviewable pull
  requests: the shared OTel library, single provider init, the baggage stamp
  processor, identity write, backend composite propagator, bus inject and
  extract, workflow spans and span events, custom meters, Collector config,
  and the CI checks that keep the contract enforced. Use when the user types
  $instrumentation-implement, asks to "implement the guide", "Prompt 03", add
  the shared library, wire baggage, emit workflow spans, or enforce
  instrumentation in CI. Writes application code from one exact-commit accepted,
  bounded work order, with at most one linked PR per repository.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Instrumentation Implement — contract into code

## Overview

The guide is the contract; this skill lands one unified work order through reviewable
repository legs, without depending on telemetry that is not yet trustworthy.

Agent definition: [`../../agents/instrumentation-implementer.agent.md`](../../agents/instrumentation-implementer.agent.md).
Prompt: [`../../prompts/03-implement-instrumentation.md`](../../prompts/03-implement-instrumentation.md).

**Precondition:** the canonical acceptance record and a passing
`verify_analysis_acceptance.py` check for its full commit SHA. Without them, stop and run
analysis/review/generation first. A merged file or generic approval is not acceptance.

**Scope, before any code.** Engineering authorizes `initial_scope` after the
contract exists: `full`, `repositories`, or `parent_folders`. `unknown` means
stop and ask. The field meaning is
[`../references/engagement-inputs.md`](../references/engagement-inputs.md). The
job that refuses to write code without that authorization is
[`../references/ci-integration.md`](../references/ci-integration.md). Do not
adopt every repository a connected host can see. A parent-folder authorization
limits the slice to those folders. Jira is used only when the human named it and
a Jira MCP is connected; otherwise the app-level work order is the manual queue.
Generating linked issues is engineering's option and only when they ask. The rule is
[`../references/mcp-servers.md`](../references/mcp-servers.md).

## Target and work-order boundary

Read [`../references/implementation-work-orders.md`](../references/implementation-work-orders.md).
Resolve one bounded selector to exactly one accepted app-level work order and validate every
repository leg against `implementation-map.json` and repository-qualified `initial_scope`.
One invocation may produce one linked PR per repository plus a coordination PR. This is
still one concern: the unified accepted work order.

Validate [`../references/provenance-ledger.md`](../references/provenance-ledger.md), load
only ledger IDs cited by the work order, and append repository-leg proof without mutating
sealed analysis entries.

## Default dependency order

Use this order when the selected work order contains these runtime slices. It is a default
dependency graph, not the only valid bounded target; accepted detector, objective, CI,
Collector, and configuration work orders are valid without inventing runtime code.

| Stage | Contents | Why here |
|---|---|---|
| 1 | Shared library skeleton: `setBaggageEntry` with allowlist and length ceiling, the stamp processor, `startWorkflow` with name validation, bus inject/extract helpers | Everything else imports this. No behaviour change on its own, so it reviews quickly. |
| 2 | Single provider `init` in the boot artifact, early, with the handle exposed; remove or fail any second `init` | Fixes the trust problem before anything is built on the signal. |
| 3 | Identity write plus the backend composite propagator | The first end-to-end join. Provable: one `trace_id` from browser to backend. |
| 4 | Route-change listener and bounded page/route classifier, if a client router exists | Client navigations become views. |
| 5 | Bus inject and extract for the buses in this work order | Each bus is a separate blast radius. |
| 6 | Workflow spans and span events named by this work order | Proves the accepted shape. |
| 7 | Custom meters named by this work order | Meters depend on the attributes landing first. |
| 8 | Collector config: OTTL derive, redaction, placement before spanmetrics and batch | Central, and reversible without a service deploy. |
| 9 | CI checks | Locks the contract so it cannot silently rot. |

## Rules

- **One unified work order per invocation; at most one PR per repository.** Link every
  repository PR to the coordination PR and its siblings. Do not split one repository leg
  across unrelated PRs or combine two work orders.
- **Run on the branch under review.** The checkout may be an unmerged pull-request branch.
  Commit the mapped repository leg there. The default branch is not required, and this
  skill does not merge. The pre-merge job is [`../references/ci-integration.md`](../references/ci-integration.md).
- **Never widen `init`.** Exactly one artifact initialises the provider. Remotes, micro-frontends, and page bundles consume the shared library.
- **No enable-all.** Turn on the instrumentations the guide named, and no others. Each additional one costs runtime budget on a page that may already be loading several agents.
- **Attribute names come from the guide.** If a name is wrong, change the guide and the schema first, then the code. Renaming in code alone breaks the dashboards the TAM already built.
- **Business Transaction grouping is `<org>.bt`.** Set the bounded global tag at the
  earliest known surface, propagate and stamp it across repository boundaries, and validate
  its registered pair with `workflow.name`. One BT can contain many workflows.
- **Placeholders for every secret.** Tokens arrive from the environment, the edge, or a secret store. No credential value in a repository, ever.
- **Money in minor units** with an ISO 4217 currency code in a sibling attribute.
- **Never emit a deny-list key.** The list in the guide and the `deny` block in `attribute-schema.json` are the same list.

## CI checks to land when the work order requires them

These are what keep the contract true after the people who wrote it move on:

- **Single `init`.** Fail the build if the provider `init` symbol is imported outside the boot package.
- **Workflow name validation.** `startWorkflow` rejects anything that is not bounded dotted-kebab within the length ceiling; in production it degrades to a sentinel rather than throwing, and the sentinel's rate is alerted on.
- **Baggage allowlist.** `setBaggageEntry` rejects unlisted keys and over-long values, so a token cannot become a baggage value.
- **Schema agreement.** `attribute-schema.json` parses, and its deny list matches the guide's.
- **Classifier coverage.** If a route registry generates the page-type classifier, regenerate it in CI and fail on drift, so a new route cannot silently classify as `other`.
- **No deny-list key** appears as a literal attribute key anywhere in the diff.

## Verification per repository leg and unified work order

State applicable checks in each linked PR and the end-to-end check in the coordination PR.
The table is ordered proof, not a requirement to open separate PRs:

| Stage | Proof |
|---|---|
| Signal trust | Time from first paint to first beacon is below the guide's threshold; exactly one application name and session id |
| First hop | A single `trace_id` spans browser and backend; cross-cutting keys are present |
| Route | One `route.change` span per client navigation with bounded page and BT values |
| Bus | Producer and consumer share a `trace_id`; the consumer carries approved baggage |
| Workflow | The journey appears under `<org>.bt`, with `workflow.name` and events visible |
| Meters | Meters appear with documented dimensions and no unbounded dimension |
| Collector | Derived attributes exist on RED metrics, proving placement before spanmetrics |

## Warning signs

- **A repository PR that touches library and journey code not named by the same work-order
  leg.** Remove the unrelated change; do not invent a second work order.
- **A second `init` added "just for this remote."** This is how one session becomes two.
- **An attribute name that differs from the guide by a separator or a plural.** Fix the guide or the code, but do not let them diverge.
- **A detector armed in the same PR that emits the signal.** Let the signal prove itself first.
- **`enable all instrumentations` in a config diff.** Remove it and name what the guide asked for.

## Non-goals

- Does not redesign the contract mid-implementation. Contract changes go back through the guide.
- Does not create dashboards or detectors in the Splunk org; that is TAM configuration work driven by the guide's portfolio mapping.
- Does not remediate the security findings the analysis surfaced. Those are separate, owned work.
