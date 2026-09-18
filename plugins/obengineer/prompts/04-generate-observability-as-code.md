# Prompt 04 — Generate the observability configuration as code

**Agent:** [`../agents/observability-as-code.agent.md`](../agents/observability-as-code.agent.md)  
**Skills:** `observability-as-code`, `cardinality-budget`  
**Inputs:** `docs/observability/engagement-inputs.yaml` + the accepted guide and schema  
**Depends on:** an accepted analysis document and `attribute-schema.json`. Runs in parallel with Prompt 03 — configuration and instrumentation do not block each other.  
**Output:** a `terraform/` tree, a `terraform plan`, and a handover. **No `apply`.**

**Invoke it, do not paste it.** `/obengineer-as-code` reads this file in place.

---

## System reminder

Follow `observability-as-code.agent.md`. The contract is the source: every dashboard,
detector, SLO, and check traces to a named section of the accepted guide and to a key in
`attribute-schema.json`. A panel with no origin in the contract is scope you invented.

Use only the resource names in `skills/references/splunk-terraform-providers.md`. Three
providers, pinned to a major: `splunk-terraform/signalfx` `~> 9.34`, `splunk/synthetics`
`~> 3.0`, `splunk/splunk` `~> 1.5`. Do not extrapolate a resource name from one that looks
adjacent, and do not accept a registry documentation page as proof a resource exists — that
site answers `200` for pages that do not. Where a name is not in the reference, say "no
Terraform support" and name the manual path instead.

You produce a **plan**. You do not run `apply`, and you do not create anything in a tenant.

## Inputs

| Source | Used for |
|---|---|
| `docs/observability/analysis-<app>-<date>.md` | Dashboards Overview, Detectors and Thresholds, SLIs and SLOs, use cases, phase plan |
| `wiki/<Customer>/<app>/detectors/`, `slos/`, `as-code/` | Per-detector thresholds with provenance, objectives, and what the tenant already has |
| `docs/observability/attribute-schema.json` | Which keys are dimension-eligible, which are attribute-only |
| `engagement-inputs.yaml` → `tenancy.o11y_realm`, `.environments` | Provider `api_url`, one workspace per environment |
| `engagement-inputs.yaml` → `entitlement.synthetics` | Run frequency times locations, before proposing checks |
| `engagement-inputs.yaml` → `entitlement.splunk_platform` | Index retention, and whether Log Observer Connect may be specified at all |
| `engagement-inputs.yaml` → `constraints.change_windows` | `signalfx_alert_muting_rule` schedules |
| `engagement-inputs.yaml` → `standards.percentile` | The one percentile in every chart and detector |
| The tenant, via MCP if enabled | What already exists, so it is imported rather than duplicated |

Tokens are never inputs to a file. `variable` with `sensitive = true`, fed from the
environment or a secret manager.

## Task

1. **Build the traceability table first** — `Contract section | Artifact | Persona | Provider resource | Dimensions needed | Exists in schema? | Ship armed?` — and refuse every row whose dimensions do not exist. Refusals become named gaps, not hopeful `group by` clauses.
2. **Discover and import.** Generate `import` blocks for objects the tenant already has. If ids are unavailable, leave them `TODO` and state that a first apply without them will duplicate.
3. **Generate three persona modules**, per `skills/references/persona-levels.md`. Be as disciplined about each one's exclusions as its contents:
   - **Executive** — SLOs and error budget per ranked journey, journey volume, trend, one screen. No service names, no percentiles, no panel with an empty state. Alerts by email or business channel on a schedule; never a page.
   - **SRE** — golden signals at the contract's percentile, dependency and off-box-hop health, Synthetics uptime, release markers as `selected_event_overlay`, burn rate. Every critical workflow gets a **silent-outage detector**. Runbook URL and owning team on every detector. Muting rules for change windows.
   - **Engineer** — `workflow.step` latency breakdown, error rate by bounded `error.class`, Tag Spotlight pivots on the Troubleshooting MetricSet tags, `trace_id`-filtered log views, browser checks, and **`signalfx_data_link` on every identity key** into traces, the platform, and the dashboard.
4. **Generate the platform module** where the contract needs it: indexes with the licensed retention, HEC, saved searches, and the `trace_id` field extraction that Related Content and every metrics-to-logs jump depends on.
5. **Generate `signalfx_metric_ruleset` rules** from the cardinality budget — aggregate away dimensions the estate emits but nobody queries, drop what is never read. This is the lever that recovers MTS headroom without a code change.
6. **Ship detectors `disabled = true`** until the signal has been clean for the agreed window. Label every threshold that has no baseline as a placeholder, in a comment.
7. **`terraform fmt`, `validate`, `plan`.** Then write the handover.

## Handover

In this order:

1. What `apply` will change, in resource counts by type and by persona.
2. What was imported rather than created, and what is still `TODO`.
3. What was refused, with the contract section and the missing key for each.
4. What has **no Terraform support** and is a TAM task in the tenant: APM MetricSets, APM Business Workflows, RUM application and session-replay settings.
5. Which thresholds are placeholders awaiting a baseline.
6. Cost implications: Synthetics runs times locations, and any ruleset that raises MTS rather than lowering it.

## Acceptance

A platform engineer who did not write this can read the plan, see which contract section
each resource came from, apply it in a non-production workspace, and get dashboards with no
empty panels and no detector that fires on missing instrumentation. Every refusal names the
key that would unblock it.
