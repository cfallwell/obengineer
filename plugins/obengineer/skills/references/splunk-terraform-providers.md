# Splunk Terraform providers — verified resource reference

Authoring reference for [`observability-as-code`](../observability-as-code/SKILL.md).

**Every name below was read from the provider's own documentation.** Use only these. A
resource type that does not exist fails at `terraform init` or `validate` with an error
that reads like a provider bug, and the hour spent chasing it is worse than the minute
spent saying "no Terraform support — configure this in the UI".

Three separate providers, not one. This surprises people, and it is the first thing to get
right in `required_providers`.

| Provider | Registry address | Covers | Maturity |
|---|---|---|---|
| SignalFx | `splunk-terraform/signalfx` | Splunk Observability Cloud: dashboards, charts, detectors, SLOs, metric rulesets, teams, tokens, data links, integrations | General availability |
| Synthetics | `splunk/synthetics` | Splunk Synthetics checks, variables, locations, certificates | **Beta** — say so when you recommend it |
| Splunk platform | `splunk/splunk` | Splunk Enterprise and Cloud Platform: indexes, HEC, saved searches, roles, apps | General availability |

```hcl
terraform {
  required_providers {
    signalfx   = { source = "splunk-terraform/signalfx" }
    synthetics = { source = "splunk/synthetics" }
    splunk     = { source = "splunk/splunk" }
  }
}
```

Pin versions. An unpinned provider turns an unrelated `terraform init` into an unplanned
upgrade.

## Splunk Observability Cloud — `signalfx`

### Provider configuration

| Argument | Notes |
|---|---|
| `auth_token` | Never a literal. `variable` with `sensitive = true`, or the provider's environment variable. |
| `api_url` | Realm-specific, e.g. `https://api.us1.signalfx.com`. Derive from `tenancy.o11y_realm`. |
| `organization_id` | Required when the token's user belongs to more than one organisation. |
| `teams`, `tags` | Provider-level defaults applied to resources that support them. Useful for stamping ownership onto everything a module creates. |
| `timeout_seconds`, `retry_max_attempts`, `retry_wait_min_seconds`, `retry_wait_max_seconds` | Raise the timeout for large dashboard applies. |
| `email` + `password` | Session-token auth. Do not use; a plan that needs a human's password is not automation. |

### Dashboards and charts

| Resource | Use for |
|---|---|
| `signalfx_dashboard_group` | The container. One per persona is the unit of access control and the thing you hand someone a link to. |
| `signalfx_dashboard` | A dashboard. Key arguments: `name`, `dashboard_group` (required), `chart` / `grid` / `column` layout, `variable`, `filter`, `time_range`, `charts_resolution`, `event_overlay`, `selected_event_overlay`. |
| `signalfx_time_chart` | The workhorse: latency, throughput, error rate over time. |
| `signalfx_single_value_chart` | One number. The executive KPI tile. |
| `signalfx_list_chart` | Ranked list — slowest workflows, top error sources. |
| `signalfx_heatmap_chart` | Per-instance or per-dimension saturation at a glance. |
| `signalfx_table_chart` | Tabular comparison across a dimension. |
| `signalfx_text_chart` | Markdown. Use it for the runbook link and for what the dashboard is *for*; an unexplained dashboard gets rebuilt by the next person. |
| `signalfx_log_view` | Logs in a dashboard, via Log Observer. Requires the entitlement. |
| `signalfx_log_timeline` | Log volume over time alongside metrics. |
| `signalfx_event_feed_chart` | Events, including release markers posted to the Events API. |
| `signalfx_slo_chart` | An SLO's compliance and error budget on a dashboard. |

Dashboard `variable` is how a contract's dimension-eligible keys become interactive
filters. A variable bound to a key that is attribute-only renders an empty dropdown, which
is the most common way a generated dashboard is quietly wrong.

`event_overlay` versus `selected_event_overlay`: the first only *suggests* an overlay in
the UI, the second is on by default. Release-marker overlays belong in
`selected_event_overlay`, or nobody will ever turn them on.

### Alerting

| Resource | Notes |
|---|---|
| `signalfx_detector` | `name` and `program_text` (SignalFlow) are required. Also `rule` blocks with severity and notifications, `max_delay` / `min_delay` (≤ 900s) for late data, `disabled`, `authorized_writer_teams` / `authorized_writer_users`, `tags`, `timezone`. |
| `signalfx_alert_muting_rule` | Scheduled silence. This is how `constraints.change_windows` from the engagement inputs becomes configuration rather than a paragraph. |
| `signalfx_slo` | `name`, `type` (`RequestBased`), `input` { `program_text`, `good_events_label`, `total_events_label` }, `target` { `type` = `RollingWindow` \| `CalendarWindow`, `compliance_period`, `slo`, `alert_rule` }. |
| `signalfx_email_template` | Reusable notification bodies, so severity language is consistent instead of per-detector prose. |

`signalfx_slo` alert rules are the executive layer's real product. `BREACH` is always
required; `ERROR_BUDGET_LEFT` and `BURN_RATE` (with `short_window_*`, `long_window_*`, and
`burn_rate_threshold_*`) are what make an SLO actionable before the budget is gone.

Notification integrations, each its own resource, referenced from a detector's
`notifications` list: `signalfx_pagerduty_integration`, `signalfx_slack_integration`,
`signalfx_opsgenie_integration`, `signalfx_victor_ops_integration`,
`signalfx_service_now_integration`, `signalfx_jira_integration`,
`signalfx_big_panda_integration`, `signalfx_webhook_integration`.

### Metrics pipeline, correlation, and org

| Resource | Notes |
|---|---|
| `signalfx_metric_ruleset` | Metrics Pipeline Management. `metric_name` and `routing_rule` required; `aggregation_rules` and `exception_rules` optional. **This is the lever the cardinality budget actually pulls** — aggregate away a dimension the estate emits but nobody queries, and recover headroom without touching code. |
| `signalfx_data_link` | Related Content. `property_name` / `property_value` as the trigger, then `target_signalfx_dashboard`, `target_splunk` (into the platform), `target_external_url`, or `target_appd_url`. Optionally scoped with `context_dashboard_id`. |
| `signalfx_team` | Ownership. Pair with `authorized_writer_teams` so generated objects are not editable by everyone. |
| `signalfx_org_token` | Ingest tokens. Creates a **secret in state** — only with remote encrypted state, and never in a module a customer clones casually. |
| `signalfx_automated_archival_settings`, `signalfx_automated_archival_exempt_metric` | Archive unused metrics; exempt the ones the contract depends on. |
| Cloud integrations | `signalfx_aws_integration` (+ `signalfx_aws_external_integration`, `signalfx_aws_token_integration`), `signalfx_azure_integration`, `signalfx_gcp_integration`. |

Useful data sources: `signalfx_dimension_values` (discover what a dimension actually
contains before you group by it), `signalfx_builtin_dashboards`, `signalfx_auto_detector`,
`signalfx_organization_members`.

### No Terraform resource for these

Say so plainly and name the manual path:

- **APM MetricSets** — Monitoring and Troubleshooting MetricSets are configured in the UI or API. The contract's promotion list is a TAM task; Terraform cannot take it.
- **APM Business Workflows** — the span tag that becomes a Business Workflow is configured in the tenant. Name the tag in the handover, and check for a data source before assuming.
- **RUM application configuration and session-replay policy** — tenant settings.

Not in the verified list above means not verified. Check the provider docs before adding
anything; do not extrapolate from a resource that looks adjacent.

## Splunk Synthetics — `synthetics` (beta)

Auth is a Splunk Observability API token via the provider's `apikey` argument or its
documented environment variable. Note the naming: resources are `create_*_v2`, which reads
oddly in HCL and is correct.

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

Because the provider is beta, state the version you pinned and say that a provider upgrade
may require a state migration. Run frequency multiplied by locations is billable — size it
against `entitlement.synthetics` before proposing it. Import an existing check by its
numeric check id.

## Splunk platform — `splunk`

| Resource | Use for |
|---|---|
| `splunk_indexes` | The index a contract's logs land in, with retention from `entitlement.splunk_platform.retention_days`. |
| `splunk_inputs_http_event_collector` | A per-source HEC token. Sensitive in state. |
| `splunk_global_http_event_collector` | Enables HEC and sets its listener. |
| `splunk_saved_searches` | Scheduled SPL, including the searches behind a Log Observer Connect panel. |
| `splunk_configs_conf` | Arbitrary `.conf` stanzas — `props`, `transforms`, field extraction for `trace_id`. The escape hatch, and the one most likely to surprise a reviewer, so comment it. |
| `splunk_authorization_roles`, `splunk_authentication_users`, `splunk_acl`, `splunk_generic_acl` | Who can see the index a contract creates. |
| `splunk_apps_local` | App installation. |
| `splunk_lookup_definition`, `splunk_lookup_table_file` | Bounded enrichment — mapping an opaque tenant key to a readable name, which is how a dashboard stays low-cardinality *and* readable. |
| `splunk_inputs_monitor`, `splunk_inputs_script`, `splunk_inputs_tcp_*`, `splunk_inputs_udp`, `splunk_outputs_tcp_*` | Forwarder-era inputs and outputs. Prefer the OpenTelemetry Collector for anything new, and say why. |
| `splunk_data_ui_views` | Dashboard XML. Verbose; use only where the platform must own the view. |
| `splunk_saved_event_types`, `splunk_admin_saml_groups`, `splunk_sh_indexes_manager` | Event types, SSO group mapping, search-head index management. |

**`trace_id` field extraction is the load-bearing one.** Related Content and every
metrics-to-logs jump depend on it, and it is usually a `splunk_configs_conf` stanza. If the
contract specifies Log Observer Connect panels, this is the resource that makes them work.
