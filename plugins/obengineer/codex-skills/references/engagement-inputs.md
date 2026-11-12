# Engagement inputs — what each answer decides

Authoring reference for [`engagement-intake`](../engagement-intake/SKILL.md). The
template is [`../../inputs/engagement-inputs.template.yaml`](../../inputs/engagement-inputs.template.yaml).

This file exists so that a run can be told the inputs **by reference** rather than by
having them re-typed into a prompt. Prompts name the inputs file; they do not carry a
copy of the questions. When a question needs to change, it changes here and in the
template, and every run picks it up.

## Why an inputs file rather than prompt placeholders

Bracketed placeholders inside a prompt have three failure modes, all of which happened:

1. **They get pasted unfilled.** `Realm: [ ]` reaches the agent verbatim, and the agent either asks again or proceeds without it.
2. **They drift between prompts.** The same question appears in the analyze prompt and the guide prompt with different wording, so the two runs get different answers to what should be one fact.
3. **They are lost when the session ends.** The second run cannot see what the first was told, so the human answers twice and the deliverables disagree.

A file fixes all three: it is filled once, visible, diffable, and reviewable. It also
gives the engagement an artifact that outlives the chat.

## Sections, and what goes wrong when they are blank

| Section | Decides | Blank means |
|---|---|---|
| `engagement` | Filenames, document title, version on the deliverable | The run invents a name, and the next run invents a different one |
| `initial_scope` | What engineering has authorized to instrument, after the contract exists: the full scope, repository-qualified repositories or parent folders, and optional per-repository branches. Intake does not ask for it | Instrumentation stops and asks. An empty authorization is not permission to scan every project a host can see. An empty branch mapping means each current checkout, including an unmerged pull request |
| `artifacts` | The project-scaffolded artifact location; whether the backend map starts from a diagram the human already has; whether an existing taxonomy of **this** application is extended; which earlier scans of **this** site to compare | Journeys get named from a product playbook instead of this application. A file from a different site is not this row |
| `cloud_diagrams` | Whether the run may draw production architecture from a cloud inventory MCP already connected for this site. Test and QA inventories are not the diagram | No generated diagram. The human's own diagrams still count. Any cloud |
| `surfaces` | The live production site scan. Required for whatever site this engagement names, unless `front_end_scan_notes` is `no browser: <reason>`. Test and QA URLs are not the scan | The run stops and asks for the production URL. It does not invent a site and it does not substitute a test or QA environment |
| `security_assessment` | Whether security screening is passive, explicitly safe-active, or opted out; and the origins, exclusions, and request limits for safe-active checks | Passive source/runtime review only. No mutation, brute force, load, destructive fuzzing, or cross-tenant access |
| `analysis_access` | Whether a token, an API key, or a dummy test login was submitted so the scan can see authenticated surfaces, and that its owner must rotate it when analysis completes | The scan stays unauthenticated and says so. `unknown` is acceptable. A secret value in the file is not |
| `traffic_baseline` | The optional averages and peaks the consumption prediction multiplies: daily sessions, hourly log volume, request rate, infrastructure integrations | The expectation is a wide range that names the missing factor. The design is not capped |
| `backends` | Which SDK sections and which bus inject/extract subsections the guide must contain | The messaging boundary section is written as `Not in evidence` for a bus that exists |
| `tenancy` | Whether exit criteria can be phrased as queries a TAM can run | Exit criteria become assertions instead of checks |
| `entitlement` | What the recommendation will **cost** in MTS, MMS cardinality, and runs — priced in a separate document for the account team | No entitlement exposure document; the recommendation stands and says the budget was not supplied |
| `constraints` | What is vetoed regardless of technical merit | The guide recommends something legal or platform ownership will reject |
| `outcomes` | Journey ranking when several candidates are equally instrumentable | The run picks a defensible journey that nobody asked for |
| `developer_tools` | Which tools the human says they use, and which of those already have an MCP server or an environment variable name in this environment | The run does not guess a server and does not ask for a token. Credentials stay in the user environment or the MCP server |
| `business_context` | The Business Value Realization section: what an outage costs this business, what triage costs, what the current MTTx actually is | The section is written from public evidence and measured performance only, and names the three numbers that would make it quantitative |
| `public_evidence` | Whether the analysis reads the last twelve months of the public record — outage coverage, complaints, field performance | The value case rests on the customer's recollection alone, which is the version that survives least contact with a sceptical executive |

## Entitlement, in detail

Entitlement is the only section that cannot be measured from the application, and the
only one that turns cardinality from a preference into arithmetic.

**Read the tenant before asking the human.** The existing-telemetry pass reads every
available subscription-usage and limit fact through the configured Splunk integrations.
Write those values with measured provenance, then ask only for order-form terms or gaps the
tenant does not expose. A measured value outranks a stated one; retain disagreements for
review rather than silently choosing the larger or smaller number.

**It is reference, not a ceiling.** Supplied, the numbers let the run price its own
recommendations and hand the account team a document that says what implementing this
will consume and where it goes over. They do not shrink the recommendation. A customer
who learns that full checkout observability needs 40,000 more MTS may buy them, may
promote fewer dimensions, or may phase it — and all three are their decision, made with
a number in front of them rather than ours, made silently, by deleting a dimension they
were never told about.

Two consequences worth stating plainly:

- **The overage lives in its own document.** `entitlement-exposure-<app>-<date>.md`, for the account team, never a section inside the customer analysis. Full spec: [`entitlement-exposure.md`](entitlement-exposure.md).
- **`unknown` no longer cripples the run.** It used to be described as the most expensive blank in this file. It is not: with no numbers the run recommends what the application needs, says the budget was not supplied, and skips the exposure document. What `unknown` costs is the pricing conversation, not the design.

`fit_to_entitlement: true` is the exception, and only on explicit customer request. Then
entitlement becomes a constraint: the run cuts to fit, and records in the exposure
document what it cut and which question the customer can no longer answer as a result.
A cut nobody can see is worse than an overage somebody has to approve.

### The numbers and where the human finds them

| Field | Where it comes from |
|---|---|
| `custom_mts_entitled` | The order form, Billing, or Subscription Usage |
| `custom_mts_in_use` | Observability Cloud → Settings → **Subscription Usage** / Org Metrics |
| `custom_mts_system_limit` | Enforced `sf.org.limit.*` value; never substitute it for contractual entitlement |
| `hosts_licensed`, `containers_licensed` | Order form; usage on the same page |
| `traces_per_minute` | APM entitlement on the order form |
| `mms_cardinality_entitled`, `mms_cardinality_in_use` | Subscription Usage and APM MetricSets; MMS entitlement is cardinality, not object slots |
| `tms_cardinality_ceiling` | Optional. An observed peak of distinct values on an existing Troubleshooting MetricSet. A baseline the prediction can compare with, not a cap the design must fit under. |
| `sessions_per_month` (RUM) | Order form; usage in Subscription Usage |
| Synthetics run quota | Order form; Synthetics usage page |
| Platform `ingest_gb_per_day`, `retention_days` | The platform license and index definitions |
| ThousandEyes units and slots | Account Settings → usage |

### How the numbers become decisions

```
proposed MTS for one promotion
  = distinct values of the tag
  × number of metrics the tag is added to
  × number of services reporting them
```

Compare the sum of proposed promotions against
`custom_mts_entitled - custom_mts_in_use` and keep headroom for growth. The full
method is a **prediction**, not a license ceiling: RUM sessions, APM trace rate,
hourly log volume, and infrastructure-integration metrics come from
`traffic_baseline` when the human supplied them. Unknown factors widen the range.
[`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md) is the only
formula. More accurate baselines produce a tighter expectation. They do not
change what the application needs.

Two entitlement answers are hard vetoes rather than budget inputs:

- **`session_replay_accepted_in_writing: false`** — always-on session replay stays out of the recommendation. Cost and the Core Web Vitals cost are both real, and "the customer seemed keen" is not acceptance.
- **`log_observer_connect_entitled: false`** — the guide must not specify Log Observer Connect panels. Reroute those questions to platform dashboards and say why in the portfolio mapping.

## Business context, in detail

The one section a scan cannot approach and a search engine cannot answer. Instrumentation
is bought to change an operational or commercial outcome, and the deliverable's Business
Value Realization section is where that gets stated in the customer's own terms rather
than in ours.

### What each answer unlocks

| Field | What the value section can then say |
|---|---|
| `commentary` | The problem in the customer's words, quoted. The one input that cannot be reconstructed later and the first thing an executive recognises as their own |
| `mttd_minutes` / `mtta_minutes` / `mttr_minutes` | Where in the incident lifecycle the time actually goes, and therefore which instrumentation slice touches it. Detection time falls to telemetry that exists; restore time falls to telemetry that localises |
| `incidents_per_month`, `sev1_per_quarter` | The multiplier. A twenty-minute detection improvement is a rounding error at one incident a quarter and a headline at forty a month |
| `responders_per_incident`, `fully_loaded_hourly_cost` | Triage cost per incident as arithmetic rather than assertion |
| `pct_incidents_found_by_customers` | The number executives react to fastest, and the one a customer-facing SLI moves directly |
| `observability_tools_in_use`, `annual_tooling_spend` | Consolidation value, checked against the agents the scan actually found on the page |
| `revenue_per_hour_online`, `orders_per_day`, `average_order_value`, `conversion_rate_pct` | Exposure per outage minute, and the value of a conversion-step regression caught before a release rather than after |
| `peak_events` | When the value is concentrated. Value realised the week before a named sales event is worth more than the same value in an average week |
| `business_model`, `seasonality`, `growth_or_margin_pressure`, `strategic_initiatives` | Which of the three audiences the section leads with, and which initiative the work attaches to |

### The rules that keep it honest

- **Never infer a business number.** No industry benchmark, no "typical e-commerce conversion rate", no revenue estimate from a public filing presented as this application's. An invented number in front of an executive who knows the real one costs the whole document its credibility.
- **Label every figure with its origin**: `stated by the customer`, `measured in this scan`, `public report (cited)`, or `arithmetic from the above`. Four labels, and the fourth is only ever built from the first three.
- **Ranges, not point estimates**, wherever an input is a range or an estimate. A single number implies a precision the inputs do not have.
- **A value claim with no instrumentation behind it does not belong.** Every claim names the workflow, indicator, or detector that produces it, or it is marketing.

Spec for the section itself, including what to write when this whole block is `unknown`:
[`business-value.md`](business-value.md).

## Public evidence, in detail

`public_evidence.allowed` decides whether the analysis reads the last twelve months of
what anyone can see: outage coverage, the customer's own status history, app-store and
review-site complaints, and field performance data. The value case is stronger for it —
"your customers said this in public, on these dates" is evidence, where "outages are
costly" is a sentiment.

`brand_terms` matters more than it looks. A global business trades under sub-brands and
country sites, and a search for the parent name finds the investor-relations record while
missing the market where customers are actually complaining.

`competitors` is for field-performance comparison only. It is not a competitive teardown,
and a document that reads as one gets forwarded to the wrong people.

## The site, and the scans that belong to it

The design runs against any site. `engagement.application` and `surfaces` name
the one this file is about. A URL, diagram, brand term, or schema from a
**different** site is not evidence. Remove it. `prior_contract`, `prior_schema`,
and `prior_scans` are earlier revisions of **this** site only.

A previous scan of this site is an input. Several may be listed. Comparing them
with the current production scan — changes, merges, and additions, including
uninstrumented code that has already shipped — is
[`incremental-runs.md`](incremental-runs.md).

The live scan is the **current production site**. Test and QA environments vary
from production and are not the scan. `front_end_scan_notes: "no browser: <reason>"`
is the only opt-out. A non-production URL does not satisfy the requirement.

`cloud_diagrams.generate: true` lets the analyze run draw a mermaid diagram of
production when a cloud inventory MCP for this site is already connected. The
capability is any cloud. No access means an open item, not a failed intake, and
never a stored credential.

Which MCP servers are mandatory, recommended, or used only when already present:
[`mcp-servers.md`](mcp-servers.md).

## Traffic baseline

Optional, and worth asking for in the same breath as entitlement. Daily average
and peak sessions, hourly log volume, request rate, spans per trace, and the
entity count of each infrastructure integration are the factors the prediction
uses. The formulas have one home:
[`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md). Tell the human
that more accurate numbers produce a tighter expectation, and that `unknown` is
a legitimate answer. A round number they are unsure of stays `unknown`. An empty
list is unsupplied, the same as `unknown`.

## Developer tools

Ask for the list the human actually uses. Examples of shape: Jira, GitHub,
GitLab, Artifactory. Then match that list to MCP servers already connected and
to environment variable **names** already present. Record `{tool, via, key}` in
`developer_tools.matched`. Never read the value into this file,
and never ask the human to paste one. A tool with no match stays in `named` and
is not installed by the run. How a matched server is used:
[`mcp-servers.md`](mcp-servers.md).

Jira is usable only when the human named Jira **and** `matched` records a connected
Jira MCP. A connected server the human did not name is ignored. A named tool without
a match remains a manual workflow; the wiki work order supplies copy/paste-ready text.

Repository and Jira ownership are mapped after analysis in
`docs/observability/implementation-map.json`, when the contract subjects are known.
Intake does not guess repository or project ownership.

## Security assessment authorization

`security_assessment.mode` defaults to `passive`. `safe-active` is valid only with
explicit `authorized_origins`, exclusions, and request limits. It permits non-mutating
checks only. `none` records an intentional coverage gap. The complete assessment and
OWASP coverage rules are in [`security-assessment.md`](security-assessment.md).

## Credentials

A token, an API key, or a login may be submitted so the analysis can see
authenticated surfaces. Without one, checkout, subscription, and account
journeys stay closed, and the scan records that limit.

`analysis_access` stores a **reference**, never the token, key, or password. Token and
API-key references may use the existing named-secret convention. `password_ref` is
stricter: it must be exactly `${ENV_VAR}`. A value written here gets committed.

`login_id` and `password_ref` are a **dummy account used for testing only**.
A production login is not an input. `login_id` names that dummy account.
`password_ref` points at its password and does not contain it.
The two fields must be supplied together.

When any of `token_ref`, `api_key_ref`, `login_id`, or `password_ref` is
supplied, `rotate_on_completion` is `true`. The token, the API key, the login
ID, and the password must be rotated by their owner when analysis completes. `unknown` on
every field means nothing was submitted; leave `rotate_on_completion` as
`unknown`.

`tenancy.tokens_held_by` is a different fact: who can issue the ingest token
when instrumentation starts. It is a name, not a token.
`developer_tools.matched` records `{tool, via, key}` for a server key or environment
variable name already present. It records no value and is not permission to read one.

Splunk API credentials are the memory repository `.env`, copied from
`templates/memory-repo/.env.template`. They are not new fields.
`api_key_ref` is `${SPLUNK_ACCESS_TOKEN}` when that secret is the Observability
Cloud API key (`Splunk_O11y_API_Key` is the same secret). `token_ref` is
`${SPLUNK_TOKEN}` when that secret is the Enterprise API token
(`SPLUNK_ENTERPRISE_TOKEN` is the same secret). Indexes to search are
`SPLUNK_ENTERPRISE_INDEXES` in `.env`, not a key in this file. Realm is
`SPLUNK_REALM`. Enterprise host is `SPLUNK_HOST`. The analyze pass that reads
them is [`existing-telemetry.md`](existing-telemetry.md). Do not write the value.

## Precedence when sources disagree

1. **Measured evidence** from a scan or the tenant. A router observed in the bundle beats a router named in the file.
2. **The inputs file**, for anything not measurable.
3. **Documented platform behaviour**, for how Splunk products work.
4. **Nothing else.** No industry assumption, no prior customer's journey names, no other document in the workspace unless it was attached as an input.

Record the disagreement when 1 overrides 2. A file that says Angular and a bundle that
says React is a finding about the customer's own documentation, and it belongs in the
deliverable.
