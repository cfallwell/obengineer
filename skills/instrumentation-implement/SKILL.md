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
  instrumentation in CI. Writes application code, one PR per contract slice,
  only against a guide the human has accepted.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Instrumentation Implement — contract into code

## Overview

The guide is the contract; this skill lands it. The work is ordered so each pull
request is independently reviewable and independently revertible, and so nothing
depends on telemetry that is not yet trustworthy.

Agent definition: [`../../agents/instrumentation-implementer.agent.md`](../../agents/instrumentation-implementer.agent.md).
Prompt: [`../../prompts/03-implement-instrumentation.md`](../../prompts/03-implement-instrumentation.md).

**Precondition:** a guide the human has accepted. Without one, stop and run
`instrumentation-guide` first. Implementing against a draft produces attribute names
that have to be renamed across every service later.

## PR order

The order is the dependency graph, not a preference.

| PR | Contents | Why here |
|---|---|---|
| 1 | Shared library skeleton: `setBaggageEntry` with allowlist and length ceiling, the stamp processor, `startWorkflow` with name validation, bus inject/extract helpers | Everything else imports this. No behaviour change on its own, so it reviews quickly. |
| 2 | Single provider `init` in the boot artifact, early, with the handle exposed; remove or fail any second `init` | Fixes the trust problem before anything is built on the signal. |
| 3 | Identity write plus the backend composite propagator | The first end-to-end join. Provable: one `trace_id` from browser to backend. |
| 4 | Route-change listener and bounded page/route classifier, if a client router exists | Client navigations become views. |
| 5 | Bus inject and extract, one PR per bus | Each bus is a separate blast radius. |
| 6 | Workflow spans and span events for the **first** journey only | Proves the shape before it is copied 40 times. |
| 7 | Custom meters for that journey | Meters depend on the attributes landing first. |
| 8 | Collector config: OTTL derive, redaction, placement before spanmetrics and batch | Central, and reversible without a service deploy. |
| 9 | CI checks | Locks the contract so it cannot silently rot. |
| 10+ | Remaining journeys, one per PR | Repeatable once the shape is proven. |

## Rules

- **One contract slice per PR.** A PR that adds the library, wires identity, and instruments three journeys cannot be reviewed or reverted.
- **Never widen `init`.** Exactly one artifact initialises the provider. Remotes, micro-frontends, and page bundles consume the shared library.
- **No enable-all.** Turn on the instrumentations the guide named, and no others. Each additional one costs runtime budget on a page that may already be loading several agents.
- **Attribute names come from the guide.** If a name is wrong, change the guide and the schema first, then the code. Renaming in code alone breaks the dashboards the TAM already built.
- **Placeholders for every secret.** Tokens arrive from the environment, the edge, or a secret store. No credential value in a repository, ever.
- **Money in minor units** with an ISO 4217 currency code in a sibling attribute.
- **Never emit a deny-list key.** The list in the guide and the `deny` block in `attribute-schema.json` are the same list.

## CI checks to land in PR 9

These are what keep the contract true after the people who wrote it move on:

- **Single `init`.** Fail the build if the provider `init` symbol is imported outside the boot package.
- **Workflow name validation.** `startWorkflow` rejects anything that is not bounded dotted-kebab within the length ceiling; in production it degrades to a sentinel rather than throwing, and the sentinel's rate is alerted on.
- **Baggage allowlist.** `setBaggageEntry` rejects unlisted keys and over-long values, so a token cannot become a baggage value.
- **Schema agreement.** `attribute-schema.json` parses, and its deny list matches the guide's.
- **Classifier coverage.** If a route registry generates the page-type classifier, regenerate it in CI and fail on drift, so a new route cannot silently classify as `other`.
- **No deny-list key** appears as a literal attribute key anywhere in the diff.

## Verification per PR

State the check in the PR description, and make it something a reviewer can run:

| PR | Proof |
|---|---|
| 2 | Time from first paint to first beacon, measured, below the guide's threshold; exactly one application name and one session id per session |
| 3 | A single `trace_id` spanning the browser span and the first backend span; cross-cutting keys present on the backend span |
| 4 | A `route.change` span per client navigation with a bounded page type, and no growth in the `other` bucket |
| 5 | Producer and consumer spans share a `trace_id`; the consumer span carries the baggage keys |
| 6 | The journey renders as one APM Business Workflow, with its span events visible on the workflow span |
| 7 | Meters appear with the documented dimensions and no unbounded dimension |
| 8 | The derived attribute exists as a dimension on the derived RED metrics, which proves placement before the spanmetrics connector |

## Warning signs

- **A PR that touches the library and a journey together.** Split it.
- **A second `init` added "just for this remote."** This is how one session becomes two.
- **An attribute name that differs from the guide by a separator or a plural.** Fix the guide or the code, but do not let them diverge.
- **A detector armed in the same PR that emits the signal.** Let the signal prove itself first.
- **`enable all instrumentations` in a config diff.** Remove it and name what the guide asked for.

## Non-goals

- Does not redesign the contract mid-implementation. Contract changes go back through the guide.
- Does not create dashboards or detectors in the Splunk org; that is TAM configuration work driven by the guide's portfolio mapping.
- Does not remediate the security findings the analysis surfaced. Those are separate, owned work.
