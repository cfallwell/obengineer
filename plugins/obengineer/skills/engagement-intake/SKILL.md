---
name: engagement-intake
description: >-
  Collect and validate the human-supplied inputs every other skill depends on —
  artifacts and diagrams, front-end URLs, backend languages and buses, Splunk
  realm and tenancy, entitlement and cardinality budget, privacy regime,
  percentile standard — into a single engagement-inputs.yaml. Asks only for what
  is missing, one short round of questions, and records `unknown` rather than
  guessing. Use when the user types $engagement-intake, starts an engagement,
  says they have diagrams or a URL to analyze, asks what information you need,
  or when any other skill finds the inputs file absent or incomplete. Never
  requests or stores a credential value.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Engagement Intake — ask once, reuse everywhere

## Overview

Every run in this bundle needs the same facts: what the application is called, where
the diagrams are, which realm, which percentile, and what the customer is licensed
for. Asking for them inside each prompt produced three copies that drifted, and a
human who pasted the third prompt with the second prompt's answers still in it.

So the inputs live in one file — `engagement-inputs.yaml`, from
[`../../inputs/engagement-inputs.template.yaml`](../../inputs/engagement-inputs.template.yaml) —
and this skill is the only thing that writes it. Field-by-field meaning and the
consequence of leaving each blank:
[`../references/engagement-inputs.md`](../references/engagement-inputs.md).

## The rule that makes this worth having

**Ask for what is missing. Never re-ask for what the file already answers, and never
ask for anything a scan can measure.**

A run that asks the human which router the application uses has given up on the job it
was hired for. Router, bundle order, competing agents, CSP, consent gating, and the
existing Splunk footprint are all *discoverable*, and asking about them converts
evidence into opinion. The intake exists for the facts no scan can reach: commercial
entitlement, who deploys what, which privacy regime applies, and what the customer is
trying to fix.

| Category | Who answers | Why |
|---|---|---|
| Composition, router, load order, competing agents, CSP, consent | The scan | Measurable. Asking invites a stale answer from memory. |
| Existing MetricSets, workflows, dashboards, tests | The tenant, via MCP if enabled, otherwise the human | Measurable in principle, often gated by access. |
| Entitlement and cardinality budget | The human, from Org Metrics and the order form | Not in the application, not in the tenant's data plane. |
| Privacy regime, residency, deny-list additions | The human | A legal position, not a technical one. |
| Who deploys the front end and the Collector | The human | Determines whether Phase 0 is possible at all. |
| First journey and known pain | The human, optionally | The run can rank candidates; the human breaks ties. |

## Process

### Step 1 — Find or create the file

Look for `engagement-inputs.yaml` beside the deliverables (conventionally
`docs/observability/engagement-inputs.yaml`), then at the workspace root. If none
exists, copy the template and say so — the human should be able to see and edit the
file, not only answer questions into a chat that ends.

If the human attached a filled file or pasted values, load those first and treat the
questions as gap-filling.

### Step 2 — Compute what is missing, then ask once

Group the gaps and ask them in **one message**, numbered, each with the consequence of
skipping it. A drip of single questions across a session is the failure mode this skill
exists to remove.

Ask in this order, because early answers make later questions unnecessary:

1. **Application, customer, scope, date.** Without these there is no filename.
2. **Artifacts.** Diagrams, prior contract, prior schema, house-style `.docx`. Say explicitly that a prior schema will be *extended* and its key names reused, never renamed for taste.
3. **Surfaces.** Production and non-production URLs; whether a test account exists and who holds it. Ask for the holder, never the credential.
4. **Backends.** Languages, deploy targets, buses, account boundaries, what terminates TLS.
5. **Tenancy.** Realm, org, environments. Identifiers only.
6. **Entitlement.** The numbers in the table below.
7. **Constraints.** Privacy regime, residency, consent platform, change windows, who deploys.
8. **Outcomes.** Known pain, and whether they want to nominate the first journey.

### Step 3 — Press once on entitlement, then move on

This is the section humans skip, and it is the one that changes the design. Ask for it
plainly and explain why in one line each:

| Ask | Why the design changes |
|---|---|
| Custom MTS included, and current consumption | Sets the budget every proposed dimension is charged against. Without it, "keep cardinality low" is advice instead of arithmetic. |
| MMS slots remaining | Monitoring MetricSets are bounded. The contract must fit the promotions it recommends into the slots that exist. |
| Agreed per-tag TMS cardinality ceiling | Decides whether an identity key can be a Troubleshooting MetricSet tag or must stay attribute-only. |
| RUM sessions per month; replay entitled | Decides sampling, and whether replay may be discussed at all. |
| Synthetics run quota and private locations | Decides test frequency and which locations the plan may assume. |
| Platform GB/day and retention | Decides what goes to Splunk platform versus what stays in Observability Cloud. |
| ThousandEyes agent units and test slots | Decides how many off-box hops can actually be covered. |

If the human does not have the numbers, record `unknown` and note who would. Then apply
the conservative default from
[`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md) and say in the
deliverable that the budget is assumed, not measured. Do not stall the run on a
procurement question.

### Step 4 — Validate before handing off

Refuse to proceed, and say which check failed, when:

- **A value looks like a credential.** Long random strings, anything matching a known token shape, `-----BEGIN`. Strip it, tell the human it was not stored, and ask for the holder's name instead.
- **A referenced path does not exist.** A diagram in the file but not on disk becomes a phantom citation in the deliverable.
- **`standards.percentile` is not a single value.** One percentile, everywhere. Two percentiles in one contract means two definitions of "slow".
- **A URL is in `surfaces` but the human said there is no browser.** One of the two is wrong; ask which.
- **`session_replay_entitled` is true but `session_replay_accepted_in_writing` is false.** Replay stays out of the recommendation until the cost and Core Web Vitals risk are accepted in writing.

### Step 5 — Write the file and report the gaps

Write `engagement-inputs.yaml`, then print a short report: what was filled, what stayed
`unknown`, and which sections of the eventual deliverable each `unknown` will weaken.
That report is the seed of the guide's "Open items and assumptions" appendix — the two
should not be written twice.

## Warning signs

- **The run asks the human a question the scan already answered.** The evidence wins; correct the file from the measurement and note the disagreement.
- **An `unknown` silently becomes a number later in the run.** If the budget was assumed, every sentence that depends on it says so.
- **Intake grows a field for something one skill wanted once.** The file is read by every run; a field that serves one paragraph belongs in that paragraph.
- **The file accumulates a credential because someone pasted a whole config.** The validator exists for exactly this. Never commit the filled file to a customer repository without checking.

## Non-goals

- Does not scan, measure, or infer anything about the application. That is `instrumentation-analyze`.
- Does not decide dimensions or budgets, only records the limits they are charged against. That is `cardinality-budget`.
- Does not hold credentials. It records who holds them.
