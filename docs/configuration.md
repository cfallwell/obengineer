# Configuration and behavior controls

obengineer has four configuration layers:

1. installer flags decide host, scope, and link-versus-copy behavior;
2. environment variables provide tenant endpoints and secret values at run time;
3. MCP configuration decides which external systems the agent can inspect; and
4. `docs/observability/engagement-inputs.yaml` controls engagement-specific behavior.

Command arguments can narrow a single invocation, but they do not replace the accepted
contract or engagement inputs.

## Environment variables

Copy [`templates/memory-repo/.env.template`](../templates/memory-repo/.env.template)
to `.env` in the artifact repository. The analyze run reads `.env` or the process
environment.

| Variable | Used for | Effect when absent |
|---|---|---|
| `SPLUNK_REALM` | Observability Cloud realm; the API base is derived as `https://api.<realm>.signalfx.com`. | Observability API inventory cannot run. |
| `SPLUNK_ACCESS_TOKEN` | Admin-level Observability Cloud API access used by the MCP integration and existing-telemetry inventory. | Observability tenant facts remain stated or “Not in evidence.” |
| `SPLUNK_HOST` | Splunk Enterprise API base URL, such as `https://<host>:8089`. | Enterprise search and introspection cannot run. |
| `SPLUNK_TOKEN` | Splunk Enterprise API token. | Enterprise tenant facts remain stated or “Not in evidence.” |
| `SPLUNK_ENTERPRISE_INDEXES` | Comma-separated allowlist of indexes the analyze run may search. | Log-volume inventory is “Not in evidence”; the run does not search arbitrary indexes. |
| `TE_OAUTH_BEARER_TOKEN` | ThousandEyes API access when that optional integration is enabled. | ThousandEyes inventory is skipped. |

`SPLUNK_ACCESS_TOKEN` is the one supported variable for the secret sometimes called
`Splunk_O11y_API_Key`. `SPLUNK_TOKEN` is the one supported variable for the secret
sometimes called `SPLUNK_ENTERPRISE_TOKEN`. Do not define duplicate aliases in
engagement inputs.

Keep values in `.env`, a host secret store, or the process environment. Put only
references such as `${SPLUNK_ACCESS_TOKEN}` in committed files. The `.env.template`
contains names and comments, never values.

## MCP integrations

The plugin's committed
[`plugins/obengineer/.mcp.json`](../plugins/obengineer/.mcp.json) contains an empty
`mcpServers` object. This prevents an unconfigured placeholder command from failing
every host session.

Use [`plugins/obengineer/.mcp.optional.json`](../plugins/obengineer/.mcp.optional.json)
as a template:

1. copy only the required server entry into the active MCP configuration;
2. replace its placeholder command or URL with the command your organization operates;
3. retain `${ENV_VAR}` references instead of literal credential values; and
4. restart the host and verify the server before analysis.

Do not copy the `$comment` array into hosts that reject non-server keys.

### Server classes

| Class | Integration | Behavior |
|---|---|---|
| Required for measured tenant inventory | `splunk-observability` | Reads MetricSets, APM workflows, Tag Spotlight, RUM, Synthetics, and subscription usage. |
| Required for measured tenant inventory | `splunk-platform` | Reads approved indexes, sourcetypes, trace linking, Log Observer Connect configuration, and ITSI when present. |
| Recommended when applicable | `local-otel-tools` | Audits local SDK or Collector configuration when the organization provides such a server. |
| Recommended when applicable | `thousandeyes` | Inventories off-box path tests and agent locations. |
| Recommended when applicable | a cloud inventory MCP already connected for the target cloud | Supports production architecture diagrams. obengineer does not install one or guess a provider. |
| Use only if already connected | Jira and repository hosts | Matches developer tools during intake and supports explicitly requested work-order flow. obengineer does not add or authenticate these servers. |

Analysis can continue without required tenant integrations: it scans supplied source and
production surfaces, uses stated inputs, labels unavailable tenant evidence, and records
open items. It must not relabel stated information as measured.

## Engagement inputs

`/ob-intake` creates:

```text
docs/observability/engagement-inputs.yaml
```

The complete schema and comments live in
[`inputs/engagement-inputs.template.yaml`](../inputs/engagement-inputs.template.yaml).
Do not delete unknown fields. Set them to `unknown`, an empty string, or the documented
empty collection so later runs can distinguish an explicit gap from an outdated schema.

### Evidence precedence

When sources disagree, the run uses:

1. measured source, site, or tenant evidence;
2. engagement inputs for facts that cannot be measured;
3. documented platform behavior; then
4. no assumption.

The analysis records a disagreement when measured evidence overrides a stated input.

### Core identity and scope

| Input | Controls |
|---|---|
| `engagement.application`, `customer`, `date`, `document_version` | Filenames, title-page identity, wiki path, and versioning. |
| `engagement.scope` | The application and surfaces the analysis describes. It is not implementation authorization. |
| `initial_scope.authorized` | Whether implementation may touch `full` scope, named `repositories`, or named `parent_folders`. `unknown` stops implementation and asks engineering to authorize scope. Intake intentionally does not set this. |
| `initial_scope.repositories` | Repository allowlist when authorization is `repositories`. |
| `initial_scope.parent_folders` | Repository-qualified `{repository, path}` allowlist when authorization is `parent_folders`. |
| `initial_scope.branches` | Optional `{repository, branch}` mappings. Missing entries mean each current checkout, including an unmerged branch. |

A connected repository host is discovery, not permission. obengineer never interprets
access to several repositories as authorization to instrument all of them.

### Supplied evidence and scan behavior

| Input | Controls |
|---|---|
| `artifacts.diagrams` and `narrative` | Backend, bus, account, and ownership mapping. Missing diagrams become open evidence gaps rather than invented architecture. |
| `artifacts.prior_contract`, `prior_schema`, `prior_scans` | Reuse of accepted names and comparison with earlier scans of the same application. Inputs from another application are invalid. |
| `artifacts.house_style_docx` | Approved layout to match when rendering. |
| `artifacts.front_end_scan_notes` | Notes from an earlier production scan. The exact form `no browser: <reason>` is the only opt-out from the required live production scan. |
| `surfaces.production_urls` | Current production surfaces to inspect. Test and QA URLs do not satisfy this requirement. |
| `surfaces.non_production_urls` | Context only; these do not replace the production scan. |
| `surfaces.host_and_remotes`, `edge_cdn` | Micro-frontend ownership and edge boundaries to verify. |
| `cloud_diagrams.generate` | Attempts a production diagram when a suitable cloud inventory server is already connected. Failure becomes an open item, not a failed analysis. |
| `cloud_diagrams.environments` | Limits diagram evidence to named production environments. |

The production scan is read-only: no destructive form submission, load generation, or
state changes.

`security_assessment.mode` is `passive`, `safe-active`, or `none`. Passive reviews source
and normal traffic. Safe-active additionally requires explicit authorized origins,
excluded paths, and request/rate limits, and remains non-mutating. The analysis records
credential/API checks and complete OWASP Top 10:2025 and API Security Top 10:2023 coverage.

### Authenticated analysis access

`analysis_access` stores references only:

- `token_ref` normally points to `${SPLUNK_TOKEN}`;
- `api_key_ref` normally points to `${SPLUNK_ACCESS_TOKEN}`;
- `login_id` identifies a dummy test account, never a production account;
- `password_ref` names the secret that holds the dummy password; and
- `rotate_on_completion` becomes `true` when any temporary access was supplied.

Leaving all fields `unknown` keeps the scan unauthenticated and requires the analysis
to state that limitation. Never put a token, API key, password, private key, or session
value in this file.

### Architecture and tenancy

| Input | Controls |
|---|---|
| `backends.languages` | Which language-specific OpenTelemetry guidance the contract needs. |
| `backends.deploy_targets` | Runtime and Collector recommendations. |
| `backends.buses` | Required message inject/extract and trace-context sections. |
| `backends.cloud_accounts` and `gateway` | Propagation boundaries where headers or identity can be lost. |
| `tenancy.o11y_realm`, `o11y_org_id`, `environments` | Tenant identity and deployment-environment validation. |
| `tenancy.splunk_platform_host` | Stated Enterprise host; the secret-bearing endpoint value remains in `SPLUNK_HOST`. |
| `tenancy.thousandeyes_account_group` | ThousandEyes inventory scope. |
| `tenancy.tokens_held_by` | Owner who can issue future ingest credentials; this is a role or team, not a credential. |

### Entitlement and consumption behavior

Entitlement normally prices the recommendation; it does not cap it.

- When entitlement values are supplied, the run computes expected consumption and
  writes `entitlement-exposure-<app>-<date>.md` for the account team.
- When any meaningful traffic baseline is supplied without entitlement, it still
  writes the exposure document as an expectation range.
- When both entitlement and traffic baseline are entirely unsupplied, the run skips
  the exposure document and recommends what the application needs.
- `entitlement.fit_to_entitlement: true` is the explicit exception. It constrains the
  recommendation to available entitlement and requires the exposure document to name
  each omitted capability and consequence.

An empty list or map and `unknown` are unsupplied. A scalar value or a populated
collection is supplied.

Important hard controls:

| Input | Behavior |
|---|---|
| `entitlement.rum.session_replay_accepted_in_writing: false` | Excludes always-on session replay. |
| `entitlement.splunk_platform.log_observer_connect_entitled: false` | Excludes Log Observer Connect panels and routes those questions to supported alternatives. |
| `observability_cloud.custom_mts_*` | Prices promoted metric dimensions against current custom MTS capacity. |
| `mms_slots_remaining` and `tms_cardinality_ceiling` | Informs MetricSet selection and cardinality risk; the TMS value is a measured baseline, not a design cap. |
| RUM, Synthetics, platform, and ThousandEyes entitlement fields | Prices the matching recommendations and records unavailable licensed features. |

Traffic values under `traffic_baseline.rum`, `apm`, `logs`, and
`infra_integrations` tighten consumption ranges. Unknown values widen the range; they
do not reduce the design.

### Contract standards

| Input | Behavior |
|---|---|
| `standards.percentile` | One percentile used consistently in charts, detectors, and objectives. |
| `standards.workflow_naming` | Naming pattern for newly discovered workflows. Accepted existing names remain stable on repeat runs. |
| `standards.baggage_header_budget_bytes` | Maximum aggregate W3C Baggage budget used when selecting cross-cutting keys. |
| `standards.baggage_value_ceiling_bytes` | Per-value limit in the baggage design. |
| `standards.unknown_dimension_threshold_pct` | Tolerated `UNKNOWN` bucket when validating a grouping key. |

These values shape the generated contract. They do not permit renaming an accepted
workflow or silently changing an attribute key during a repeat run.

### Constraints and outcomes

`constraints` are vetoes, not suggestions:

- `privacy_regimes`, `pii_deny_list_additions`, and `data_residency` constrain what
  telemetry may contain and where it may go;
- `consent_platform` controls when front-end telemetry may initialize;
- `competing_eum_agents` makes duplicate browser agents an explicit design concern;
- `change_windows` shapes rollout phases; and
- `who_deploys_front_end` and `who_deploys_collector` identify required owners.

`outcomes.first_journey` selects the first journey when the customer has decided one.
When blank, the analysis ranks candidates from evidence. `known_pain` influences
prioritization, and `audiences` controls which executive, SRE, engineer, or platform
views the contract and Terraform need.

### Developer tools

`developer_tools.named` records tools the human says they use.
`developer_tools.matched` records `{tool, via, key}` for an already-connected MCP server
or environment variable name. It never stores a value. A named but unmatched tool is not installed
automatically.

Jira is usable only when the human named Jira and `matched` records a Jira MCP. Issue
creation is opt-in after acceptance: at most one linked issue per mapped Jira project for
a unified work order. If Jira is unavailable or another tool is used, obengineer does not
attempt Jira; the app-level wiki work order provides copy/paste-ready issue text.

### Business value and public evidence

`business_context` controls what can be stated quantitatively in the final Business
Value Realization section. Unknown values are not replaced with industry benchmarks.
Figures are labeled `stated`, `measured`, `public`, or `derived`.

`public_evidence.allowed` controls open-web research. When true, `window_months`,
`brand_terms`, `status_page_urls`, and `exclude_domains` bound the search. When false,
the analysis uses only supplied and measured evidence. `competitors` permits
field-performance comparison only, not a general competitive assessment.

## Per-command arguments

Installed commands append free-form invocation text to their run contract:

| Command | Useful argument |
|---|---|
| `/ob-intake` | An alternate output path or relevant context not already represented in the workspace. |
| `/ob-analyze` | The application or service focus when the inputs file covers several supplied artifacts. |
| `/ob-generate` | Required `accept <analysis-path> at <analysis-commit-sha>`; verifies and records exact-commit acceptance before generating the wiki. |
| `/ob-implement` | Optional bounded selector: work order, BT, workflow, use case, detector, objective, or config target. It must resolve to one accepted unified work order; if omitted, the accepted phase plan selects one. |
| `/ob-terraform` | Application or environment focus already authorized by the accepted contract. |
| `/ob-review` | Deliverable path; defaults to the analysis under `docs/observability/`. |
| `/ob-render` | Markdown source path; defaults to the analysis under `docs/observability/`. |

Arguments cannot waive acceptance gates, widen `initial_scope`, introduce attributes
outside `attribute-schema.json`, authorize Terraform apply, or override credential and
privacy rules.
