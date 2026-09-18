# Splunk Terraform providers — verified resource reference

Authoring reference for [`observability-as-code`](../observability-as-code/SKILL.md).

**Every name below was cross-checked two ways: the registry documentation for one exact
provider version, and the provider's own resource map at the matching release tag.** Use
only these. A resource type that does not exist fails at `terraform init` or `validate` with
an error that reads like a provider bug, and the hour spent chasing it is worse than the
minute spent saying "no Terraform support — configure this in the UI".

Do not verify a resource name by fetching its registry documentation URL.
`registry.terraform.io` is a single-page application and answers `200` for pages that do not
exist, so a link check proves nothing. The only mechanical check is
`terraform providers schema -json` against the pinned version.

Three separate providers, not one. This surprises people, and it is the first thing to get
right in `required_providers`.

| Provider | Registry address | Covers | Version verified |
|---|---|---|---|
| SignalFx | `splunk-terraform/signalfx` | Splunk Observability Cloud: dashboards, charts, detectors, SLOs, metric rulesets, teams, tokens, data links, integrations | 9.34.0 — 35 resources, 5 data sources |
| Synthetics | `splunk/synthetics` | Splunk Synthetics checks, variables, locations, certificates | 3.0.0 — partner-maintained |
| Splunk platform | `splunk/splunk` | Splunk Enterprise and Cloud Platform: indexes, HEC, saved searches, roles, apps | 1.5.5 — 26 resources, no data sources |

```hcl
terraform {
  required_providers {
    signalfx   = { source = "splunk-terraform/signalfx", version = "~> 9.34" }
    synthetics = { source = "splunk/synthetics", version = "~> 3.0" }
    splunk     = { source = "splunk/splunk", version = "~> 1.5" }
  }
}
```

Pin versions, and pin them to a major. An unpinned provider turns an unrelated
`terraform init` into an unplanned upgrade. Two specific reasons here: `signalfx` currently
publishes a `10.0.0` pre-release, so `latest` is ambiguous and the registry's `/latest/`
documentation path may describe resources the general-availability provider does not have;
and `signalfx` 10 will require Terraform 1.11 or newer, so that upgrade is gated on the
customer's Terraform version, not only on the provider constraint.

## Splunk Observability Cloud — `signalfx`

### Provider configuration

| Argument | Notes |
|---|---|
| `auth_token` | Never a literal. `variable` with `sensitive = true`, or the provider's environment variable. |
| `api_url` | Realm-specific, e.g. `https://api.us1.signalfx.com`. Derive from `tenancy.o11y_realm`. |
| `teams`, `tags` | Provider-level defaults applied to resources that support them. Useful for stamping ownership onto everything a module creates. |
| `timeout_seconds`, `retry_max_attempts`, `retry_wait_min_seconds`, `retry_wait_max_seconds` | Raise the timeout for large dashboard applies. |
| `email` + `password` + `organization_id` | The alternative to `auth_token`, and mutually exclusive with it — supplying both is a provider error, not a fallback. This trio mints a session token. Do not use it; a plan that needs a human's password is not automation. |
| `feature_preview` | Map of booleans gating experimental behaviour. Leave it out unless something specific requires it. |

**There is no `realm` argument on this provider.** The realm lives inside `api_url`. This
matters because the Synthetics provider *does* take `realm` as a required argument, so the
two provider blocks look inconsistent and are both correct. There is also no
`splunk_observability` provider — the local name is `signalfx`.

### Dashboards and charts

| Resource | Use for |
|---|---|
| `signalfx_dashboard_group` | The container. One per persona is the unit of access control and the thing you hand someone a link to. |
| `signalfx_dashboard` | A dashboard. Required: `name`, `dashboard_group`. Layout is repeated `chart` blocks of `chart_id`, `width`, `height`, `row`, `column`. Then `variable`, `filter`, `time_range`, `charts_resolution`, `event_overlay`, `selected_event_overlay`. |
| `signalfx_time_chart` | The workhorse: latency, throughput, error rate over time. |
| `signalfx_single_value_chart` | One number. The executive KPI tile. |
| `signalfx_list_chart` | Ranked list — slowest workflows, top error sources. |
| `signalfx_heatmap_chart` | Per-instance or per-dimension saturation at a glance. |
| `signalfx_table_chart` | Tabular comparison across a dimension. |
| `signalfx_text_chart` | Markdown. Use it for the runbook link and for what the dashboard is *for*; an unexplained dashboard gets rebuilt by the next person. |
| `signalfx_log_view` | Logs in a dashboard, via Log Observer. Requires the entitlement. |
| `signalfx_log_timeline` | Log volume over time alongside metrics. |
| `signalfx_event_feed_chart` | Events, including release markers posted to the Events API. |
| `signalfx_slo_chart` | An SLO's compliance and error budget on a dashboard. The one chart with **no `program_text`** — `slo_id` is its only required argument, so a generator that templates SignalFlow into every chart will break on this one. |

Dashboard `variable` is how a contract's dimension-eligible keys become interactive
filters. A variable bound to a key that is attribute-only renders an empty dropdown, which
is the most common way a generated dashboard is quietly wrong.

`event_overlay` versus `selected_event_overlay`: the first only *suggests* an overlay in
the UI, the second is on by default. Release-marker overlays belong in
`selected_event_overlay`, or nobody will ever turn them on.

### Alerting

| Resource | Notes |
|---|---|
| `signalfx_detector` | `name` and `program_text` (SignalFlow) required, plus at least one `rule` block. Each rule needs `detect_label` — matching a `detect(...).publish('<label>')` in the SignalFlow — and `severity` (`Critical`, `Major`, `Minor`, `Warning`, `Info`). Also per rule: `notifications`, `runbook_url`, `tip`, `parameterized_body` / `parameterized_subject`, `reminder_notification`. Detector level: `max_delay` / `min_delay` (≤ 900s) for late data, `disabled`, `authorized_writer_teams` / `authorized_writer_users`, `tags`. |
| `signalfx_alert_muting_rule` | Scheduled silence. Required: `description` and `start_time`. This is how `constraints.change_windows` from the engagement inputs becomes configuration rather than a paragraph. |
| `signalfx_slo` | `name`, `type` (only `RequestBased`), `input` { `program_text`, `good_events_label`, `total_events_label` }, `target` { `type` = `RollingWindow` \| `CalendarWindow`, `compliance_period`, `slo`, `alert_rule` }. |
| `signalfx_email_template` | Reusable notification bodies, so severity language is consistent instead of per-detector prose. Required: `name`, `trigger_subject`, `to`. |

`signalfx_slo` alert rules are the executive layer's real product. `BREACH` is always
required; `ERROR_BUDGET_LEFT` and `BURN_RATE` (with `short_window_*`, `long_window_*`, and
`burn_rate_threshold_*`) are what make an SLO actionable before the budget is gone.

**Notifications are delimited strings, not resource references.** There is no notification
resource to point a detector at. Each entry in `rule.notifications` is a comma-delimited
string whose first token names the transport, and positional commas are required even when a
field is unused:

```hcl
notifications = [
  "Email,oncall@example.com",
  "Slack,${signalfx_slack_integration.chat.id},checkout-alerts", # channel, no leading '#'
  "PagerDuty,${signalfx_pagerduty_integration.pd.id}",
  "Opsgenie,${signalfx_opsgenie_integration.og.id},Payments,${var.responder_id},Team",
  "Team,${signalfx_team.checkout.id}",
  "Webhook,${signalfx_webhook_integration.hook.id},,",           # trailing commas required
]
```

The integration resources exist to produce the credential id these strings consume:
`signalfx_pagerduty_integration`, `signalfx_slack_integration`,
`signalfx_opsgenie_integration`, `signalfx_victor_ops_integration` (this is Splunk On-Call),
`signalfx_service_now_integration`, `signalfx_jira_integration`,
`signalfx_big_panda_integration`, `signalfx_webhook_integration`.

Two traps in muting rules. `start_time` and `stop_time` are **epoch seconds**, not RFC 3339,
so a readable timestamp in the plan is a bug. And `detectors` accepts **one** detector id —
muting a change window across twelve detectors is twelve rules, or one filter-based rule on
a shared property, which is the better answer and the reason to tag detectors consistently.

### Metrics pipeline, correlation, and org

| Resource | Notes |
|---|---|
| `signalfx_metric_ruleset` | Metrics Pipeline Management — the **whole** of it. `metric_name` and `routing_rule` required; `aggregation_rules` and `exception_rules` optional. **This is the lever the cardinality budget actually pulls** — aggregate away a dimension the estate emits but nobody queries, and recover headroom without touching code. |
| `signalfx_data_link` | Related Content. `property_name` / `property_value` as the trigger, then `target_signalfx_dashboard`, `target_splunk` (into the platform), or `target_external_url`. Optionally scoped with `context_dashboard_id`. |
| `signalfx_team` | Ownership. Pair with `authorized_writer_teams` so generated objects are not editable by everyone. |
| `signalfx_org_token` | Ingest tokens. Creates a **secret in state** — only with remote encrypted state, and never in a module a customer clones casually. |
| `signalfx_automated_archival_settings`, `signalfx_automated_archival_exempt_metric` | Archive unused metrics; exempt the ones the contract depends on. |
| Cloud integrations | `signalfx_aws_integration` (+ `signalfx_aws_external_integration`, `signalfx_aws_token_integration`), `signalfx_azure_integration`, `signalfx_gcp_integration`. |

Useful data sources: `signalfx_dimension_values` (discover what a dimension actually
contains before you group by it), `signalfx_builtin_dashboards`, `signalfx_auto_detector`,
`signalfx_organization_members`, `signalfx_pagerduty_integration`.

Four things about `signalfx_metric_ruleset` that cost a plan cycle each if guessed:

- **There is no separate drop-rule or aggregation-rule resource.** Dropping is `routing_rule { destination = "Drop" }`; `RealTime` and `Archived` are the other two destinations. One resource per metric name.
- `matcher.type` is always the literal `"dimension"` and `aggregator.type` is always `"rollup"`. They read like enumerations with alternatives and currently have none.
- **A drop rule needs an admin session token**, not an org token, or the API refuses it. Say this in the handover, because the failure surfaces as an opaque 4xx during `apply` and looks like malformed HCL.
- The negation key inside a ruleset filter is **`not`**. The negation key inside `signalfx_alert_muting_rule`'s filter is **`negated`**. They are not interchangeable, and the wrong one is a schema error rather than a silent inversion — which is the good outcome.

### No Terraform resource for these

Say so plainly and name the manual path:

- **APM MetricSets** — Monitoring and Troubleshooting MetricSets are configured in the UI or API. The contract's promotion list is a TAM task; Terraform cannot take it.
- **APM Business Workflows** — the span tag that becomes a Business Workflow is configured in the tenant. Name the tag in the handover.
- **RUM application configuration and session-replay policy** — tenant settings.
- **Log Observer Connect** — the connection itself is console-side. What Terraform *can* express is the consumer and the plumbing: `signalfx_log_view` and `signalfx_log_timeline` take a `default_connection` naming an already-configured connection, and the platform side is `splunk_inputs_http_event_collector` plus the `trace_id` extraction below.

The whole of APM is absent from this provider — searching the 9.34.0 resource map for
metricset, business workflow, and span tag returns nothing. A read-only
`signalfx_apm_service_topology` data source exists **only in the 10.0.0 pre-release**, so it
is not available under a `~> 9.34` pin and should not be generated.

Three more names are declared in the provider source but **not registered** in 9.34.0, so
they will not resolve: `signalfx_integration_splunk_oncall` (use
`signalfx_victor_ops_integration`), `signalfx_customized_auto_detector`, and
`signalfx_dashify_template`. All three appear in 10.0.0 pre-release documentation, which is
exactly how an unverified name gets into generated code.

Not in the verified list above means not verified. Confirm with
`terraform providers schema -json` before adding anything; do not extrapolate from a resource
that looks adjacent, and do not trust a registry page that loaded.

## Splunk Synthetics — `synthetics`

A different provider with a differently shaped configuration: `apikey` (**required** — a
Splunk Observability API token) and `realm` (**required**, e.g. `us1`), optionally `apiurl`.
`product` is deprecated. Both required arguments have documented environment variables; use
them rather than a `.tfvars`.

Two structural quirks to build into any generator:

- Every resource type begins `synthetics_create_` — the verb is part of the type name, which reads oddly in HCL and is correct.
- **Every resource wraps its entire configuration in one nested block, and the block name differs per resource** (`test`, `variable`, `totp_variable`, `location`, `downtime_configuration`, `ca_certificate`, `client_certificate`). The top level has no flat arguments at all, so a check written against a flat schema will produce HCL that validates as empty.

```hcl
resource "synthetics_create_http_check_v2" "checkout_api" {
  test {
    name                = "checkout-api-availability"
    url                 = var.checkout_url
    request_method      = "GET"
    location_ids        = ["aws-us-east-1"]
    frequency           = 5
    verify_certificates = true
    active              = true
  }
}
```

| Resource | Use for |
|---|---|
| `synthetics_create_browser_check_v2` | Real-browser journey test. The one that maps to a ranked journey from the contract. |
| `synthetics_create_http_check_v2` | Single-request uptime and latency. |
| `synthetics_create_api_check_v2` | Multi-step API transaction. |
| `synthetics_create_port_check_v2` | TCP reachability. |
| `synthetics_create_ssl_check_v2` | Certificate expiry and chain validity. |
| `synthetics_create_variable_v2`, `synthetics_create_totp_variable_v2` | Test inputs, including MFA. **The only supported way** to get a test-account credential into a check — never inline in HCL. |
| `synthetics_create_location_v2` | Private location. |
| `synthetics_create_downtime_configuration_v2` | Planned downtime, so maintenance is not an incident. |
| `synthetics_create_ca_certificate_v2`, `synthetics_create_client_certificate_v2` | mTLS and private CA. |

**Generate `_v2` names only.** Version 3.0.0 removed the legacy
`synthetics_create_browser_check` and `synthetics_create_http_check` resources and the
`synthetics_check` data source. Emitting a non-`_v2` name fails against any 3.x provider, and
the pre-3.0 examples still in circulation are the likeliest source of one. There is also no
"uptime check" type — an uptime monitor is `synthetics_create_http_check_v2`.

Data sources are suffixed rather than prefixed: `synthetics_browser_v2_check`,
`synthetics_http_v2_check`, `synthetics_locations_v2_check` and the rest, with
`synthetics_chrome_flags` the one exception to the pattern.

Two areas are only partly verified, so read the current provider documentation before
generating them rather than inferring: the `requests` block inside an API check, and the valid
`action` and `type` values for browser-check `steps`. The provider documentation defers to the
Synthetics REST API reference for both, which means the field set can move without a provider
release.

Run frequency multiplied by locations is billable — size it against `entitlement.synthetics`
before proposing it. Import an existing check by its numeric check id.

## Splunk platform — `splunk`

Provider configuration: `url` (**required**), then either `auth_token` (a JWT) or
`username` + `password`. Also `insecure_skip_verify` — which **defaults to `true`**, so
verification is off unless someone turns it on, and that is worth a line in the handover — plus
`timeout` and `acl_get_mode` (`enterprise` by default, `cloud` for Splunk Cloud).

| Resource | Use for |
|---|---|
| `splunk_indexes` | The index a contract's logs land in, with retention from `entitlement.splunk_platform.retention_days` as `frozen_time_period_in_secs`. `datatype` is `event` or `metric`. |
| `splunk_sh_indexes_manager` | The **Splunk Cloud** equivalent, managed from the search head. Use this instead of `splunk_indexes` against Cloud, or the apply fails on a self-service tenant. |
| `splunk_inputs_http_event_collector` | A per-source HEC token. `token` is computed if not supplied, which is the way to want it. Sensitive in state. |
| `splunk_global_http_event_collector` | Singleton that enables HEC and sets its listener. |
| `splunk_saved_searches` | Scheduled SPL, including the searches behind a Log Observer Connect panel. `search` is required; `actions` is a comma-separated string, not a list. |
| `splunk_configs_conf` | Arbitrary `.conf` stanzas — `props`, `transforms`, field extraction for `trace_id`. `name` is `"<conf_file>/<stanza>"`, e.g. `props/otel_json`. The escape hatch, and the one most likely to surprise a reviewer, so comment it. |
| `splunk_authorization_roles`, `splunk_authentication_users`, `splunk_admin_saml_groups`, `splunk_generic_acl` | Who can see the index a contract creates. |
| `splunk_apps_local` | App installation. |
| `splunk_lookup_definition`, `splunk_lookup_table_file` | Bounded enrichment — mapping an opaque tenant key to a readable name, which is how a dashboard stays low-cardinality *and* readable. |
| `splunk_inputs_monitor`, `splunk_inputs_script`, `splunk_inputs_udp`, `splunk_inputs_tcp_raw`, `splunk_inputs_tcp_cooked`, `splunk_inputs_tcp_ssl`, `splunk_inputs_tcp_splunk_tcp_token`, `splunk_outputs_tcp_default`, `splunk_outputs_tcp_group`, `splunk_outputs_tcp_server`, `splunk_outputs_tcp_syslog` | Forwarder-era inputs and outputs. Prefer the OpenTelemetry Collector for anything new, and say why. |
| `splunk_data_ui_views` | Dashboard XML in `eai:data`. Verbose; use only where the platform must own the view. |
| `splunk_saved_event_types` | Named event types. |

Two naming traps here, both of which produce a plan that will not initialise:

- **There is no `splunk_acl` resource**, despite documentation with "acl" in the title. `acl` is a *nested block* — `app`, `owner`, `sharing` (`app` \| `global` \| `user`), `read`, `write`, `can_change_perms` — available on the namespaced resources. Permissions on a standalone path are `splunk_generic_acl`.
- The token resource is **`splunk_inputs_tcp_splunk_tcp_token`**. Its documentation is filed under the slug `inputs_tcp_splunktcptoken`, which is not a usable type name.

**`trace_id` field extraction is the load-bearing one.** Related Content and every
metrics-to-logs jump depend on it, and it is usually a `splunk_configs_conf` stanza. If the
contract specifies Log Observer Connect panels, this is the resource that makes them work.
