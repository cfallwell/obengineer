# Entitlement exposure — pricing the recommendation, in its own document

A recommendation costs something to run. Metric time series are billed, Monitoring
MetricSets are bounded, synthetic runs are metered, and platform ingest is a daily volume.
When the customer has told us what they own, the run can say what implementing this will
consume and where it exceeds what they have.

That belongs in **its own document, addressed to the account team** — never as a section
inside the customer analysis, and never as a silent edit to the recommendation.

## Why a separate document

Three audiences, three different questions, and putting them in one artifact serves none
of them:

| Audience | Question | Artifact |
|---|---|---|
| Customer engineering | What should we build, and why | The analysis document |
| Account team | What will this consume, and does the customer need to buy more | This document |
| Implementers and agents | What exactly do I emit | The wiki |

A commercial exposure paragraph inside a customer engineering document reads as a sales
motion in the middle of a technical review, and it undermines the technical content around
it. Removed from the analysis, it also stops the analysis from quietly trimming itself:
the recommendation is what the application needs, and the price of that is a separate
finding for a separate reader.

## The rule that governs it

**Entitlement is reference, not a ceiling.** The run recommends what the application needs
and then prices it. It does not cut a dimension because the budget looks tight, and it does
not present a reduced design as though it were the right one.

The exception is explicit: `entitlement.fit_to_entitlement: true` in the inputs, set
because the customer asked for a recommendation that fits inside what they already own.
Then the run cuts to fit — and this document records **what was cut and which question the
customer can no longer answer**, because a cut nobody can see is worse than an overage
somebody has to approve.

When entitlement is `unknown` across the board, **there is no exposure document**. The
analysis proceeds as though there is enough licensing, its document control says the budget
was not supplied, and Open Items carries the ask. Do not invent a limit in order to have
something to compare against.

## Where it lives

```
docs/observability/entitlement-exposure-<app>-<date>.md
```

Markdown only. It does not get the customer `.docx` treatment: it is an internal working
document, it changes when the tenant changes, and rendering it invites it being forwarded
as a deliverable.

## What it contains

### 1. Header and basis

What was supplied, by whom, and when it was read — the same provenance discipline as
[`version-currency.md`](version-currency.md). A licensed number from an order form and a
consumption number from a screenshot two quarters old are not the same kind of fact, and
the arithmetic inherits the weaker of the two.

### 2. Position today

| Resource | Licensed | In use | Headroom | Source |
|---|---|---|---|---|
| Custom MTS | | | | |
| Hosts / containers | | | | |
| APM traces per minute | | | | |
| MMS slots | | | | |
| RUM sessions per month | | | | |
| Synthetics runs per month | | | | |
| Platform GB/day | | | | |
| ThousandEyes units / test slots | | | | |

`unknown` in a row is a legitimate entry and makes every derived number in that row's
class a range rather than a value. Say so in the row rather than in a footnote.

### 3. What the recommendation adds

One row per promotion or resource the analysis proposes, priced with the arithmetic
visible. The method is [`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md);
this document is where its output is totalled.

| Item | Where it comes from | Arithmetic | MTS added | Cumulative |
|---|---|---|---|---|
| `nuskin.market` on 6 meters × 4 services | Custom Metrics | 14 × 6 × 4 | 336 | 336 |

Rules for this table:

- **Every row shows its multiplication**, not just its result. A number with no arithmetic cannot be argued with, only accepted or rejected.
- **Order by cost, descending.** The conversation is about the top three rows; everything below them is noise in a pricing discussion.
- **Separate the recommendation's floor from its options.** The dimensions required for the named indicators to work at all, then the ones that make troubleshooting faster. A customer cutting to a budget needs to know which cut breaks an SLI.
- **Count MMS and TMS separately from MTS.** They are different bounded resources with different failure modes: MTS overage is a bill, an MMS slot shortage is a feature that cannot be created.

### 4. Projected position, and the overage

The same table as *Position today*, with the recommendation applied, and the overage stated
as both an absolute and a percentage of entitlement. Then, per resource that goes over:

- **The overage**, and what triggers it — full rollout, or one specific phase
- **When it hits**, tied to the phased plan rather than to a date, because the plan is what the customer controls
- **The options**, priced against each other: raise the entitlement, drop specific promotions, aggregate with a Metrics Pipeline Management rule, or shorten retention. Name what each option costs in observability terms, not only in dollars
- **The recommended option**, with the reason. An account team forwarding a document with four options and no recommendation gets four questions back

### 5. Growth headroom

Entitlement is consumed by the customer's own growth as well as by this work. A projection
that consumes all headroom on day one is wrong even if it fits, because the next service
onboarded breaks it. State the assumed growth rate and where it came from; `unknown` is
acceptable and makes the projection a floor.

### 6. What was cut, when `fit_to_entitlement` is true

Every removal, the question it made unanswerable, and the trigger that should bring it
back. This is the section that makes a fitted recommendation honest, and the only one that
is mandatory when the flag is set.

## How it reaches the analysis document

By reference, in one line, in document control: the exposure document exists, its filename,
and that the recommendation was **not** trimmed to fit — or was, on request. Nothing else.
No numbers, no overage, no commercial framing.

The reverse direction carries more: this document cites the analysis section for every
item it prices, so an account team question resolves to a technical justification rather
than to an assertion.

## Warning signs

- **The analysis document grew a licensing section.** Two audiences, one artifact, and the technical reader now distrusts the recommendation.
- **A dimension disappeared between the cardinality section and the catalogue.** Something trimmed to fit without saying so. Either it is recommended, or it is a recorded cut.
- **The exposure document exists with no supplied entitlement.** Then every number in it is invented, and it will be quoted as though it were not.
- **An overage stated with no options.** A problem handed to somebody with no lever is a problem that gets ignored.
- **Consumption numbers with no read date.** Consumption moves weekly; a headroom figure with no date is a headroom figure from an unknown week.
- **The document reads as a quote.** It prices resources, not products. The commercial construction is the account team's job and they are better at it.
