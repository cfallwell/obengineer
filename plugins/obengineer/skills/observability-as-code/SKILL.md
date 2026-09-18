---
name: observability-as-code
description: >-
  Turn an accepted instrumentation contract into reviewable Terraform for the
  Splunk portfolio — dashboards, charts, detectors, SLOs, metric rulesets, data
  links, Synthetics checks, and Splunk platform indexes, HEC, and trace_id field
  extraction — organised as three persona modules for executives, SREs, and
  engineers. Imports what the tenant already has rather than duplicating it,
  validates every group-by against the schema's dimension-eligible list, and
  hands over a plan rather than an apply. Use when the user types
  $observability-as-code, asks for Terraform, dashboards as code, detectors as
  code, Splunk providers, signalfx provider, Synthetics checks, or asks to build
  the dashboards and alerts the guide specified.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Observability as Code — the contract, as Terraform

## Overview

A guide that specifies twenty dashboards and thirty detectors is a document until someone
configures them, and configuring them by hand takes weeks, drifts immediately, and cannot
be reviewed. This skill emits the Terraform instead — three persona modules from one
contract, plan-clean, with the refusals stated.

Two references do the load-bearing work, and both should be read before writing any HCL:

- [`../references/splunk-terraform-providers.md`](../references/splunk-terraform-providers.md) — the **verified** resource names across the three providers, and an explicit list of what has no Terraform support.
- [`../references/persona-levels.md`](../references/persona-levels.md) — what each persona gets, and what each must exclude.

## Three providers, not one

This is the first thing people get wrong: `splunk-terraform/signalfx` for Observability
Cloud, `splunk/synthetics` for checks, `splunk/splunk` for the platform. Pin all three to a
major — `~> 9.34`, `~> 3.0`, `~> 1.5` — because `signalfx` currently publishes a `10.0.0`
pre-release, so `latest` resolves to documentation describing resources the
general-availability provider does not have.

Read the reference for the resource names. Do not extrapolate from a name that looks
adjacent, and do not treat a registry documentation page that loaded as evidence the resource
exists — the registry answers `200` for pages that do not. The only mechanical check is
`terraform providers schema -json` against the pinned version. A resource type that does not
exist fails with an error that reads like a provider bug.

## Process

### Step 1 — Read the contract, and refuse what it cannot support

Load the accepted guide, `attribute-schema.json`, and `engagement-inputs.yaml`. Then build
one table before writing any HCL, because it is also the handover document:

`Contract section | Artifact | Persona | Provider resource | Dimensions needed | Exists in schema? | Ship armed?`

Anything failing the dimension check does **not** get generated with a hopeful `group by`.
It becomes a named gap: which contract section asked for it, which key is missing, and what
the implementer must land first. A chart grouped by an attribute-only key renders empty in
a way that is indistinguishable from an outage, and it is found at 3am by someone who then
stops trusting the whole group.

### Step 2 — Discover what already exists, and import it

A tenant that has been used has hand-made dashboards and detectors in it. Generate `import`
blocks for those and create only what is absent.

Where the Splunk Observability MCP server is enabled, read the tenant. Where it is not, ask
the human for an export, or generate the import blocks with the ids left as `TODO` and say
plainly that a first apply without them will duplicate existing objects. **A first apply
that duplicates forty detectors destroys the credibility of everything that follows**, and
no amount of correct HCL recovers it.

Use the data sources: `signalfx_dimension_values` to see what a dimension actually contains
before grouping by it, `signalfx_builtin_dashboards` to avoid rebuilding what ships free.

### Step 3 — Lay out the modules

```
terraform/
  providers.tf        # three providers, pinned; realm from a variable
  variables.tf        # nothing sensitive has a default
  data.tf             # dimension_values lookups, team ids, integration ids
  imports.tf          # import blocks for what the tenant already has
  modules/
    executive/        # SLOs, KPI tiles, one dashboard
    sre/              # golden signals, detectors, muting rules, uptime checks
    engineer/         # step latency, Tag Spotlight, log views, data links, browser checks
    platform/         # indexes, HEC, trace_id extraction, saved searches
  environments/
    prod/             # one workspace per environment, backend configured
    stage/
```

One module per persona, one workspace per environment. No `count` on a persona and no
environment name interpolated from a variable nobody sets — this is code a customer
inherits, and explicitness beats cleverness in inherited code.

### Step 4 — Generate, with the decisions visible in the code

- **Every resource carries a comment naming its contract section.** Six months on, this is how someone decides whether a panel is still wanted. It is the cheapest documentation available and the first thing omitted.
- **Dashboard `variable` blocks come only from the dimension-eligible list.** One per key, so filtering is interactive rather than a code change.
- **Release markers go in `selected_event_overlay`, not `event_overlay`.** The latter only *suggests* the overlay in the UI, so nobody ever turns it on.
- **Detectors get `disabled = true`** until the signal has been clean for the agreed window, plus a runbook URL and an owning team via `authorized_writer_teams`. Map severity to real response: if everything is `Critical`, severity carries no information.
- **Every critical workflow gets a silent-outage detector** — absence of expected traffic, which threshold-on-error-rate alerting structurally cannot see. This is the detector most often missing and most often needed.
- **Thresholds with no baseline are labelled as placeholders in a comment.** A number invented in a text editor and presented as tuned is the fastest way to lose an on-call team.
- **`signalfx_metric_ruleset` is where the cardinality budget is actually enforced.** Aggregate away dimensions the estate emits but nobody queries; drop what is never read. It recovers headroom without a code change, which usually makes it the cheapest item in the plan.
- **`signalfx_data_link` on each identity key**, into traces, into the platform with `target_splunk`, and into the relevant dashboard. It converts "I have a customer id" into "I have their trace" without anyone learning a query language.

### Step 5 — Keep every credential out of the code and out of shared state

- Tokens are `variable` with `sensitive = true`, fed from the environment or a secret manager. Never a literal, never a committed `.tfvars`.
- Synthetics test credentials go through `synthetics_create_variable_v2` or `synthetics_create_totp_variable_v2` — the only supported path, and never inline in HCL.
- `signalfx_org_token` and `splunk_inputs_http_event_collector` put **secrets in state**. Remote encrypted state with access control is part of this deliverable, not a later concern. If the customer has no remote backend yet, say so before generating either resource.
- Never `terraform apply`. Not with a flag, not because the human seemed to want it.

### Step 6 — Validate, plan, and hand over

Run `terraform fmt`, `terraform validate`, and `terraform plan`. Untested Terraform is a
proposal wearing the costume of an implementation.

Where the environment has no credentials to plan against, `terraform providers schema -json`
still runs offline after `init` and proves every resource type and argument name is real.
That is the minimum; report it as schema-checked rather than planned, and do not describe an
unplanned configuration as validated.

The handover states, in this order:

1. **What `apply` will change**, in resource counts by type and by persona.
2. **What was imported** rather than created, and what is still `TODO`.
3. **What was refused**, with the contract section and the missing key for each.
4. **What has no Terraform support** and must be configured in the tenant: APM MetricSets, APM Business Workflows, RUM application settings, and the Log Observer Connect connection itself. The contract's promotion list is a TAM task and Terraform cannot take it — say so rather than leaving a gap the customer discovers during configuration.
5. **Which thresholds are placeholders** awaiting a baseline.
6. **Cost implications**: Synthetics run frequency times locations, and any metric ruleset that raises MTS rather than lowering it.

## Warning signs

- **A dashboard exists in the plan with no contract section behind it.** That is scope invented during generation, and it is the panel nobody will maintain.
- **A `group by` on a key the schema marks attribute-only.** Empty chart, read as an outage. Refuse it and name the gap.
- **No `import` blocks against a tenant that has clearly been used.** The first apply will duplicate, and the duplicate is what gets found.
- **Every detector enabled on the first apply.** Alerts firing on missing instrumentation train people to ignore alerts, and that training is not reversible.
- **Three persona modules containing the same charts with different titles.** Then there is one persona and two decorations; check what each one *excludes*.
- **A token, even a test one, appears in a `.tf` or `.tfvars` file.** Stop and rewrite as a variable before continuing.
- **The plan was never run.** Then this is a proposal, and it must be described as one.

## Non-goals

- Does not run `apply`, and does not create anything in a tenant. It produces code and a plan.
- Does not add telemetry. A dashboard needing a metric nobody emits is a finding for [`../instrumentation-implement/SKILL.md`](../instrumentation-implement/SKILL.md).
- Does not decide which journeys or dimensions exist. That is [`../instrumentation-analyze/SKILL.md`](../instrumentation-analyze/SKILL.md) and [`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md).
- Does not redesign the contract. A contract that cannot be configured is one to send back, with the specific reason.
