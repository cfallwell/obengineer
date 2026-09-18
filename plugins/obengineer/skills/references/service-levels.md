# Service levels — indicators and objectives in the customer's voice

Authoring spec for **section 24** of the customer document, defined in
[`document-template.md`](document-template.md).

## Why the voice matters

Every observability engagement produces a latency chart. Almost none produce a sentence a
non-engineer would recognise as describing their own experience, and that gap is why
dashboards get built and then ignored: the numbers on them are not the numbers anyone is
accountable for.

An indicator written from the system's point of view — "p99 of `POST /v2/orders` under
4,000ms" — is unarguable and unmotivating. The same indicator written from the user's point
of view — "a customer who submits an order sees confirmation within four seconds, 99 times
in 100" — is something a product owner will defend in a planning meeting. **Write the second
one first, then its implementation underneath it.** Both are required. The user-facing
statement without a query is a slogan; the query without the statement is a chart.

## The compiled table

One table, every SLI in the engagement, so the set can be reviewed as a set. Coverage gaps
are visible here and nowhere else.

```markdown
| SLI | User-facing statement | Good events | Total events | Objective | Window | Workflow | Owner |
|---|---|---|---|---|---|---|---|
| checkout-success | A customer who submits an order gets a confirmation | spans where `workflow.name='checkout.order.submit'` and `error=false` | all spans where `workflow.name='checkout.order.submit'` | 99.5% | 28d rolling | `checkout.order.submit` | Commerce |
| checkout-latency | Confirmation appears within four seconds | good events with `duration <= 4s` | all good events | 99% | 28d rolling | `checkout.order.submit` | Commerce |
```

Then an H2 per SLI that carries an error budget, with the budget in both units the reader
thinks in — a percentage and a wall-clock or event count — the burn-rate alerting it
implies, and the dashboard it appears on.

## Rules that keep the section honest

**Every SLI names a workflow from section 20.** An indicator with no workflow behind it
cannot be computed, and this is the check that catches an SLI invented in a meeting. If the
workflow does not exist yet, the SLI is `blocked on instrumentation` and says so.

**Good and total events are queries, not descriptions.** "Successful checkouts" is a
conversation with three answers. A span filter with an explicit error definition is an
indicator. Write the filter, including what counts as an error — and decide deliberately
whether a customer abandoning the flow is a failure of the system, because it is usually
counted by accident.

**Availability and latency are separate indicators on the same workflow.** A request that
fails in 50ms is fast. Merging them produces an objective that cannot be missed for the
reason people care about, and every latency regression hides behind an availability number.

**Objectives come from the customer.** The analysis supplies the measured baseline; the
customer supplies the target. Where no target has been agreed, write `proposed` in the
objective cell and state the baseline next to it, so the negotiation starts from evidence
rather than from a round number. An objective the vendor invented and the customer never
accepted is the one nobody defends when it breaks.

**Set the objective below the current baseline, deliberately.** An SLO set at the
measured p99 is already breaching half the time, which trains the team to mute it. An SLO
set far below is not a constraint. Say which of the two risks you took.

**Windows are rolling unless the customer reports on calendar months.** Rolling windows
detect degradation; calendar windows match reporting. If both are needed, that is two
targets on one indicator, and say so rather than picking one silently.

**Every objective has an error budget and a burn-rate alert.** An SLO with neither is a
number on a slide: nothing happens when it is missed until the review meeting. Budget
consumption is the only signal that turns an objective into an operational one.

## Voice-of-customer coverage

Before the section is finished, check the set against the journeys the way a customer would
complain about them. For each ranked journey there should be an indicator for:

- **Can I do the thing?** — availability of the workflow.
- **Was it quick enough?** — latency, at the agreed percentile, on successful attempts only.
- **Did it stay done?** — where the outcome is asynchronous (an order confirmed but not fulfilled, a subscription created but not billed), the completion of the *downstream* step, which is the class of failure real users notice and internal dashboards miss entirely.

Three indicators per critical journey is usually right. Fewer means something a customer
would phone about is unmeasured; many more means the section is being used as a metric
inventory, which is section 21's job.

## Handing it to configuration

Each objective maps to a `signalfx_slo` resource, so write it in a shape that translates
without a second design pass:

| Document field | Terraform |
|---|---|
| Good events query | `input.program_text` + `good_events_label` |
| Total events query | `input.program_text` + `total_events_label` |
| Objective | `target.slo` |
| Window | `target.type` = `RollingWindow` \| `CalendarWindow`, `target.compliance_period` |
| Burn-rate alerting | `target.alert_rule` — `BREACH` always, plus `BURN_RATE` with short and long windows, and `ERROR_BUDGET_LEFT` |

Resource details: [`splunk-terraform-providers.md`](splunk-terraform-providers.md). Persona
placement — objectives are the executive layer's product, burn rate is the SRE layer's:
[`persona-levels.md`](persona-levels.md).

## Warning signs

- **An SLI with no owner.** It will not be defended, and an undefended objective is deleted at the first inconvenient breach.
- **100% as an objective.** It means no error budget, so no release is ever safe, so the objective will be ignored the first time it matters.
- **Every objective is `99.9%`.** Uniform targets across journeys of different value mean nobody weighed them.
- **An indicator computed from a metric that does not exist yet**, presented without that dependency stated.
- **The objective and the detector threshold in section 23 disagree.** They are the same commitment written twice; reconcile them or drop one.
- **A dashboard panel with no indicator behind it, next to an indicator on no dashboard.** Both are symptoms of the two sections being written independently.
