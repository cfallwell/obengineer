---
name: instrumentation-analyze
description: >-
  Discover what an application actually is before designing instrumentation:
  deep-scan the front end (script order, competing RUM/EUM agents, where the
  agent initialises, router, CSP, consent, 404 shells), map backends and buses
  from diagrams and captured calls, inventory the existing Splunk and
  ThousandEyes footprint, and enumerate business transactions and named
  integration flows from evidence. Use when the user types
  $instrumentation-analyze, asks to "analyze this site or app", "Prompt 01",
  what business transactions exist, why RUM data looks wrong, or which
  observability products are missing. Read-only against the target; writes an
  analysis memo only.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Instrumentation Analyze — evidence before design

## Overview

Every instrumentation mistake that is expensive to reverse comes from designing
against an assumed architecture. This skill produces the evidence base: what the
application is, which agent already runs and when, what else is competing for the
same events, where the account and bus boundaries fall, and which business
transactions actually exist.

Agent definition: [`../../agents/instrumentation-architect.agent.md`](../../agents/instrumentation-architect.agent.md).
Prompt: [`../../prompts/01-analyze-application.md`](../../prompts/01-analyze-application.md).

Output: `docs/observability/analysis-<app>-<date>.md`, optionally rendered for
review with `customer-doc-render`. This memo becomes the architecture section of the
guide, so write it at that depth.

## Rules

- **Assume nothing.** Not the industry, not a storefront, not named journeys, not the cloud, not a prior customer's taxonomy. Derive every name from this session's evidence.
- **Never store a credential.** If the scan finds an exposed token, key, or secret, record it as a finding referenced as `<redacted>` and never reproduce the value.
- **Mark gaps as gaps.** "Not in evidence" is a finding with a named next step, not an omission.

## Process

### Step 1 — Front-end deep scan

When a URL is in scope, capture the document and the runtime, not just the HTML.

| Look for | Why it changes the contract |
|---|---|
| Script order in `<head>` and `<body>` | Which agent wins the race; whether a competing EUM patches `fetch` first |
| Where the RUM agent initialises | In a boot script, or deep inside a multi-megabyte bundle behind a config fetch — the second means the agent starts long after first paint |
| Whether the provider handle is reachable | An agent trapped in module scope cannot be used by other bundles, which pushes teams toward a second `init` |
| Router library and version | Client navigations do not create a document span, so `document-load` covers only the entry route |
| Every other RUM / EUM / session-replay / analytics agent | Duplicated collection, resource contention, and consent exposure |
| Consent platform and when it resolves | Data sent before consent resolves is a compliance finding, not a tuning problem |
| CSP and its allowlist | A pixel or beacon host missing from CSP is a silent data gap |
| HTTP status versus rendered content | A route that renders a real page under 404, or "not found" under 200, makes `http.status_code` useless as an error SLI |
| Load-order timing | First paint versus first beacon, measured, is the Phase 0 evidence |

Record the measured facts. "The agent is late" is an opinion; "first paint at 288 ms,
first beacon at 2081 ms" is evidence.

### Step 2 — Enumerate business transactions and workflows

A **BT** is the page, bundle, app, or surface the user is in. A **workflow** is a
discrete intent inside it. Sources, in order of reliability: route registries and
chunk manifests, module-federation remotes, analytics event flags, payment and
feature flags, UI copy and translations, config JSON, sequence diagrams.

Do not invent a BT with no evidence, do not collapse a real BT into "view and click",
and leave unidentified bundles in the unknowns list rather than guessing.

### Step 3 — Map backends, accounts, and buses

From diagrams and captured call sequences: owning service per hop, account or
subscription crossings, message buses and their topic patterns, downstream systems,
and the failure or DLQ points the diagram marks. For each named flow, state what is
**already visible** in Observability Cloud versus what is being reconstructed by
inference.

### Step 4 — Inventory the existing portfolio footprint

Present, partial, or absent — from evidence, never assumed — for Observability Cloud
(RUM, APM, Infrastructure, Synthetics, Log Observer Connect), Splunk Enterprise, and
Cisco ThousandEyes. Include the raw shape of what is being collected today: a decoded
beacon payload showing which attributes are actually populated is worth more than a
list of installed products.

### Step 5 — Assign each question to a platform

Use [`../references/portfolio-decision-engine.md`](../references/portfolio-decision-engine.md).
Journeys and code execution go to Observability Cloud; durable logs, audit, and
compliance search to Splunk Enterprise; internet, DNS, CDN, and SaaS path health to
ThousandEyes. Naming the platform per question is what makes the later
recommendations defensible.

### Step 6 — State Phase 0 honestly

If the signal cannot be trusted yet, say so and prove it. Late agent, duplicate
`init`, free-text workflow names, identifiers or tokens in attributes, broken
propagation across the first backend hop — each is a blocker with a measured exit
criterion. If the signal **is** trustworthy, say that too; a Phase 0 invented out of
caution costs the customer a release cycle.

## Warning signs

- **A tidy inventory with no measurements.** No timings, no decoded payload, no status-versus-content check means the scan was shallow.
- **Journeys that match a generic commerce playbook** rather than the evidence.
- **One RUM application name for two applications** sharing a hostname.
- **Only one collection agent noticed.** Look again; overlapping EUM is common and changes the recommendation.
- **A credential pasted into the memo.** Reference it as `<redacted>` and record the exposure.

## Non-goals

- Does not design the contract, name meters, or write dashboards. That is `instrumentation-guide`.
- Does not modify the target, log in destructively, or run load against production.
- Does not open PRs.
