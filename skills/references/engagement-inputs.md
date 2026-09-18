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
| `artifacts` | Whether the backend map is diagram-driven or guessed; whether an existing taxonomy is extended | Journeys get named from a product playbook instead of this application |
| `surfaces` | Whether there is a front-end scan at all, and whether authenticated pages can be reached | The scan covers only anonymous surfaces, and the checkout journey is missing |
| `backends` | Which SDK sections and which bus inject/extract subsections the guide must contain | The messaging boundary section is written as `Not in evidence` for a bus that exists |
| `tenancy` | Whether exit criteria can be phrased as queries a TAM can run | Exit criteria become assertions instead of checks |
| `entitlement` | What the recommendation will **cost** in MTS, MMS slots, and runs — priced in a separate document for the account team | No entitlement exposure document; the recommendation stands and says the budget was not supplied |
| `constraints` | What is vetoed regardless of technical merit | The guide recommends something legal or platform ownership will reject |
| `outcomes` | Journey ranking when several candidates are equally instrumentable | The run picks a defensible journey that nobody asked for |
| `business_context` | The Business Value Realization section: what an outage costs this business, what triage costs, what the current MTTx actually is | The section is written from public evidence and measured performance only, and names the three numbers that would make it quantitative |
| `public_evidence` | Whether the analysis reads the last twelve months of the public record — outage coverage, complaints, field performance | The value case rests on the customer's recollection alone, which is the version that survives least contact with a sceptical executive |

## Entitlement, in detail

Entitlement is the only section that cannot be measured from the application, and the
only one that turns cardinality from a preference into arithmetic.

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
| `custom_mts_included` | The order form or subscription terms |
| `custom_mts_in_use` | Observability Cloud → Settings → **Subscription Usage** / Org Metrics |
| `hosts_licensed`, `containers_licensed` | Order form; usage on the same page |
| `traces_per_minute` | APM entitlement on the order form |
| `mms_slots_remaining` | Settings → **APM MetricSets**: count the Monitoring MetricSets already defined |
| `tms_cardinality_ceiling` | Not on any page. It is a number the customer agrees to; propose one and get it accepted. |
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
`custom_mts_included - custom_mts_in_use` and keep headroom for growth. The full
method, including the defaults to use when the numbers are `unknown`, is
[`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md).

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

## Credentials

The file records **who holds** a credential, never its value. That applies to ingest
tokens, API tokens, and test-account passwords alike.

A test account is worth asking about, because an unauthenticated scan cannot see
checkout, subscription, or account journeys — which are usually the ones the engagement
is about. Record `held_by` and `rotates_after_run`, and have the human supply the
credential in the session rather than in the file. A credential in a file gets committed.

## Precedence when sources disagree

1. **Measured evidence** from a scan or the tenant. A router observed in the bundle beats a router named in the file.
2. **The inputs file**, for anything not measurable.
3. **Documented platform behaviour**, for how Splunk products work.
4. **Nothing else.** No industry assumption, no prior customer's journey names, no other document in the workspace unless it was attached as an input.

Record the disagreement when 1 overrides 2. A file that says Angular and a bundle that
says React is a finding about the customer's own documentation, and it belongs in the
deliverable.
