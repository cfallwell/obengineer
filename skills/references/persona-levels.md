# Persona levels — three audiences, three products

Authoring reference for [`observability-as-code`](../observability-as-code/SKILL.md) and
for the guide's Dashboards Overview.

The same telemetry serves three audiences who want different things and are harmed by
each other's views. One dashboard that tries to serve all three serves none: the
executive cannot find the number, the SRE has to scroll past business framing during an
incident, and the engineer cannot get to a trace.

So build **three dashboard groups**, one per persona, from one contract — and be as
disciplined about what each excludes as about what it contains.

## The distinction that makes this work

| | Executive | SRE | Engineer |
|---|---|---|---|
| Asks | Are we meeting the commitment we made? | Is it broken, and where? | Why is this slow or failing? |
| Time horizon | Weeks and quarters | Minutes and hours | Minutes, then a single trace |
| Unit | The journey, in business terms | The service and its dependencies | The workflow step, the span, the log line |
| Cares about the number | Trend and budget | Deviation from normal | The outlier, not the aggregate |
| Wakes up for | Nothing. Reads it deliberately. | Alerts, and only actionable ones | Nothing. Arrives after an alert. |
| Fails when | The chart needs explaining | The dashboard needs a second dashboard | It ends at a metric with no path to a trace |

## Executive

**One dashboard, one screen, no scrolling.** If it does not fit, it is not the executive
view — it is the SRE view with a title change.

Built on **SLOs**, because an SLO is the only construct here that expresses a commitment
rather than a measurement. `signalfx_slo` per ranked journey, with the compliance period
the business actually talks in, surfaced through `signalfx_slo_chart` and
`signalfx_single_value_chart`.

Contains:

- Compliance and remaining error budget per ranked journey, current period.
- Journey completion volume — the business quantity, in the customer's own words, from the contract's business meters.
- Trend against the previous period. A number with no trend cannot be acted on by someone who reads it monthly.
- One `signalfx_text_chart` naming the owner of each journey and where the detail lives.

Excludes, deliberately:

- **Service names, pod names, host names.** Infrastructure vocabulary in an executive view invites the wrong conversation.
- **Percentile charts.** The percentile standard belongs in the SRE and engineer views; here it appears only as "within target" or not.
- **Anything with an empty state.** An executive dashboard that is blank on a Monday morning because a dimension is missing has cost more trust than it will ever return.

Alerting: SLO `BURN_RATE` and `ERROR_BUDGET_LEFT` rules, notified by email or a business
channel on a schedule. **Never a page.** An executive paged at 3am is an escalation
failure, not an observability feature.

## SRE

**One dashboard group, organised by blast radius**, not by team boundary. During an
incident the question is what is affected, and the org chart is not the answer.

Contains:

- Golden signals per service at the contract's percentile: latency, throughput, error rate, saturation. `signalfx_time_chart` for trend, `signalfx_heatmap_chart` for per-instance saturation.
- Dependency and topology health, including the off-box hops the contract assigned to ThousandEyes. A hop nobody owns is the hop that causes the longest incidents.
- Synthetics uptime for each critical entry point — `synthetics_create_http_check_v2` — because a silent outage looks identical to a quiet night in real-user data.
- Release markers as `selected_event_overlay`, from the contract's Events API section. "What changed" is the first question of most incidents and the overlay answers it without a second tab.
- Error-budget burn rate, shared with the executive view — the one number both personas should read the same way.

Alerting is where this persona is actually served, and the bar is high:

- Every detector is actionable, with a runbook URL and a named owner. A detector with no runbook is a notification, and notifications get filtered.
- **Silent-outage detection on every critical workflow.** Absence of traffic where traffic is expected, which threshold-on-error-rate alerting structurally cannot see. This is the detector most often missing and most often needed.
- `signalfx_alert_muting_rule` for `constraints.change_windows`, so planned work does not train people to ignore alerts.
- Severities mapped to real response: `Critical` pages, `Major` notifies, `Minor` and `Warning` are dashboard-only. If everything is `Critical`, nothing is.
- Detectors ship `disabled = true` until the signal has been clean for the agreed window.

Excludes: business framing, and span-level detail. Both belong one layer away, reachable
by a `signalfx_data_link`, not present by default.

## Engineer

**Optimised for the path from a symptom to a span**, not for surveillance. Nobody watches
this view; they arrive at it with a question.

Contains:

- Workflow-step latency breakdown, so the slow step is visible without opening a trace. This is what the contract's `workflow.step` enumeration buys, and the view is the reason those enumerations must be exhaustive.
- Error rate by `error.class` and bounded reason code, never by raw message text.
- Tag Spotlight pivots on the contract's Troubleshooting MetricSet tags — the honest home for the identity-adjacent keys that cardinality rules kept out of the executive and SRE views.
- Logs beside metrics: `signalfx_log_view` or `signalfx_log_timeline`, filtered by `trace_id`.
- **`signalfx_data_link` on the contract's identity keys**, into traces, into the platform via `target_splunk`, and into the relevant dashboard. This is the highest-value resource in the whole persona: it converts "I have a customer id" into "I have their trace" without anybody learning a query language.
- Browser checks for the ranked journeys — `synthetics_create_browser_check_v2` — with credentials only through `synthetics_create_variable_v2`.
- Dashboard `variable` blocks for every dimension-eligible key, so filtering is interactive rather than a code change.

Excludes: SLO compliance framing, and anything aggregated so far that the outlier
disappears. An engineer's question is almost always about the tail.

## Building all three from one contract

| Contract section | Executive | SRE | Engineer |
|---|---|---|---|
| Ranked journeys | An SLO and a KPI tile each | Golden signals and a silent-outage detector each | A step-latency breakdown each |
| `workflow.name` / `workflow.step` | Journey name only | Workflow-level charts | Step-level charts, and the trace link |
| Dimension-eligible keys | At most one, as a segment | Dashboard variables and detector `group by` | Dashboard variables |
| Attribute-only keys | Never | Never | Tag Spotlight and data links |
| Business meters | The headline volume | Volume as a sanity check against silent outage | Rarely |
| Execution meters | Never | Saturation and queue depth | Retries, cache behaviour, contention |
| Named integration flows | Never | The hop and who owns it | The span link or attribute pivot that crosses it |
| Release events | Never | `selected_event_overlay` | `selected_event_overlay` |
| Off-box hops | Never | ThousandEyes path test | Occasionally, for a specific dependency |
| Log requirements | Never | Volume and error trend | `trace_id`-filtered log view |

## Warning signs

- **The three groups are the same charts with different titles.** Then there is one persona and two decorations. Check what each *excludes*.
- **The executive dashboard has a service name on it.** Rewrite in journey terms or remove the panel.
- **The SRE group has no silent-outage detector.** The most expensive outage class is invisible to every threshold detector in the group.
- **The engineer group has no data link.** The path from symptom to span is the entire point; without it this is the SRE view with more charts.
- **A persona's dashboard variable is bound to an attribute-only key.** Empty dropdown, and it will be read as broken instrumentation.
- **Every detector is `Critical`.** Severity carries no information, and the group has trained its audience to ignore it.
