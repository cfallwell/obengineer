# Business value realization — the section an executive reads

Instrumentation is bought to change an outcome: an outage found by a dashboard instead of a
customer, a release rolled back in four minutes instead of forty, a checkout regression
caught before a sales event rather than during it. The technical body of the document
describes the machinery. This section says what the machinery is for, in the customer's
terms, and it is the last body section before the appendices — because it is the argument
the preceding sections have earned, not the promise they open with.

It is an **ad-hoc business value assessment**, not a formal one. It has no discounted cash
flow, no three-year model, and no benchmark table. It has three ingredients: what the
customer told us, what the public record shows, and what this scan measured — and it does
arithmetic only where all three permit.

## The three sources, and the label each carries

Every figure in the section is labelled with where it came from. Four labels, no fifth:

| Label | Means | Example |
|---|---|---|
| `stated` | The customer said it, in `business_context` | "MTTR averages 90 minutes" |
| `measured` | This scan or the tenant produced it | "RUM initialises 1.8 s after first paint" |
| `public` | The open record, cited with a URL and a date | "Status page records four checkout incidents in March" |
| `derived` | Arithmetic over the three above, with the calculation shown | "40 incidents/month × 3 responders × 90 min = 180 engineer-hours/month" |

A figure with no label is not allowed in this section. The labels are the whole defence of
the section: an executive who sees `stated` next to their own number and `derived` next to
ours knows exactly which part to argue with, and that is what makes the rest credible.

**Never infer a business number.** No industry benchmark, no "typical" conversion rate, no
revenue-per-minute estimated from a public filing and presented as this application's.
Where a needed number is absent, name it as an ask — see *Writing it with no business
context* below.

## Reading the public record

`public_evidence.allowed` in the inputs gates this; when true, read the last
`window_months` (default twelve) of what anyone can see. The point is not to embarrass the
customer. It is that a value case built only on internal recollection is the version that
collapses first under a sceptical question, while "your customers wrote this, on these
dates, in public" does not.

### What to look for

| Class | Where | What it establishes |
|---|---|---|
| Outage and degradation coverage | Trade press, tech press, regional press in the customer's markets | That incidents reached the outside world, and how they were characterised |
| The customer's own incident history | `status_page_urls`, status-page archives, service advisories | Frequency and duration, in the customer's own publication |
| Customer complaints | App-store reviews, review sites, community forums, public social posts | What the failure feels like from outside, in the words the section can quote |
| Field performance | Public field-data sources for the origin, plus the scan's own measurements | Whether real users experience the performance the customer believes they do |
| Company statements | Press releases, earnings commentary, investor decks | Which initiative this work attaches to, and the language the executive audience already uses |
| Peak-event coverage | Coverage of named sales events in `peak_events` | Where the value is concentrated |

### The rules

- **Cite or delete.** URL, publication, date, and one sentence on what it shows. An uncited claim about a customer's outage history is a liability in a document with their logo on it.
- **A complaint is a complaint, not an outage.** Report what the source is — a review, a post, a status entry, a news report — and never promote one class into another.
- **Volume without a baseline is not a signal.** Ten complaints means nothing without knowing whether ten is high for this brand. Where no baseline is available, say so and use the complaints as narrative rather than as measurement.
- **Absence is a finding too.** A twelve-month search that finds nothing public says the incidents were contained, which is worth stating: the value case then rests on internal cost rather than on brand exposure.
- **Nothing sensitive, nothing personal.** No named individuals, no screenshots of customer accounts, no PII quoted out of a public complaint.
- **Recency over volume.** Three incidents in the last quarter matter more than thirty from eighteen months ago, and the window exists to enforce that.

## Performance analysis

"Proper performance analysis" means measured, current, and attributable — not a lab score
quoted once.

1. **Field data first, lab data second.** What real users experience on the real origin governs; a synthetic run from one location is a diagnostic, not a claim about the population.
2. **The scan's own numbers count as evidence.** First paint, first contentful paint, DOMContentLoaded, load, long tasks, transfer and decode sizes, and the timing of every agent initialisation — recorded with the URL, the date, the network conditions, and the device class. Unrecorded conditions make a number unreproducible, which makes it unusable.
3. **Attribute the cost to something the contract can change.** A 14 MB bundle, an agent that initialises 1.8 seconds after first paint, three overlapping RUM agents on one page, a render-blocking third party in the head. Each is a line the implementation touches.
4. **State what the instrumentation does *not* fix.** Observability makes a slow page visible, measurable, and attributable; it does not make it fast. A section that implies otherwise is the reason the next one is not believed.
5. **Compare against the customer's own history where the data exists**, and against `competitors` only for field performance, only if supplied, and never as a teardown.

## What the section contains

Six subsections, in this order.

### `### The problem in the customer's words`

The `commentary` input, quoted, attributed to the role that said it. Where there is no
commentary, the `known_pain` list serves; where there is neither, this subsection is one
sentence saying so, and the section leads with measured and public evidence instead.

Quote, do not paraphrase. A paraphrase reads as our characterisation of their problem, and
the executive reading it stops recognising themselves in the document.

### `### What the public record shows`

The twelve-month evidence, oldest to newest, each entry cited. Grouped by class, with a
count and a date range per class, and one line on what the group establishes. Close with
the honest read: what this evidence supports, and what it does not.

### `### Measured performance today`

The scan's numbers, with conditions. A table of measurements, then a short paragraph
attributing each to a cause the contract addresses, then the explicit statement of what
instrumentation will and will not change.

### `### Where the time goes today`

The incident lifecycle from the `stated` MTTx figures, and which instrumentation slice
touches each stage:

| Stage | Today | What moves it | Which slice |
|---|---|---|---|
| Detect | `stated` MTTD | An indicator that fires without a customer report | The SLI and its detector |
| Acknowledge | `stated` MTTA | A detector that routes to an owner rather than a channel | Detector `group by` and ownership |
| Isolate | `stated` MTTI | Trace context across the boundary the failure crosses | Baggage, span links, the shared library |
| Restore | `stated` MTTR | Attribution to a service, release, or market | Dimensions and release events |

Where a stage has no `stated` number, the row says `not supplied` and names it as an ask.
Do not fill it with a plausible figure — a fabricated baseline makes the improvement
fabricated too.

### `### What realisation looks like`

The value, per claim, with four things each: the claim, the mechanism, the evidence class,
and the horizon tied to the phased plan rather than to a calendar date.

| Claim | Mechanism | Basis | Realised at |
|---|---|---|---|
| Checkout failures detected without a customer report | `checkout-success` SLI + burn-rate detector | `stated` 62% of incidents found by customers; `public` four March incidents | End of Phase 2 |

Rules:

- **Every claim names its mechanism**, and the mechanism must exist in this document. A claim with no workflow, indicator, or detector behind it is marketing, and it is the first thing a technical reviewer will attack.
- **No claim without a `stated` or `measured` basis.** `public` alone supports narrative, not a value claim.
- **Ranges, not point estimates.** `derived` arithmetic inherits the widest input range.
- **Order by defensibility, not by size.** The largest number in the section is the one most likely to be wrong, and leading with it invites the whole section to be dismissed with it.
- **Include the claims that are not yet supportable**, with the input that would support them. That list is also the intake's next conversation.

### `### What this section needs to become quantitative`

Every `not supplied` input, what it would let the section say, and where the customer finds
it. Short, specific, and answerable — the same discipline as Open Items. This subsection is
what turns a qualitative first run into a quantitative second one.

## Writing it with no business context

The section is still written. It contains, in order: one sentence stating that no business
inputs were supplied; the public record if research is allowed; the measured performance,
which needs nobody's permission; the value **model** with its coefficients named and
unfilled; and the asks. It does not contain a single invented number.

That version is short and honest, and it does something a fabricated version cannot: it
tells the account team exactly which three questions turn it into a quantitative case.

## Where it sits, and what owns it

Last body section, immediately before the appendices, in the section list in
[`document-template.md`](document-template.md). It is written by the analysis run, from
inputs the intake collected and evidence the analysis gathered.

**It is not the entitlement exposure document.** Value belongs in the customer's document;
cost and overage belong in [`entitlement-exposure.md`](entitlement-exposure.md), addressed
to the account team. Mixing them turns a technical review into a negotiation.

In the wiki, `business/` carries the working notes: `value-model.md` for the arithmetic and
its coefficients, `public-evidence.md` for the cited sources with their read dates, and
`asks.md` for the unfilled inputs. The document states the case; the wiki holds the
workings, so a later run updates a coefficient rather than re-researching a quarter.

## Warning signs

- **A number with no label.** The labels are the section's credibility; one unlabelled figure makes every other one suspect.
- **An industry benchmark.** Someone could not get the customer's number and substituted one. Delete it and ask.
- **A value claim with no mechanism in this document.** Marketing in a technical deliverable, and the reason the technical parts get skimmed.
- **Public evidence with no citation, or a complaint reported as an outage.** Both are unsafe in a document carrying the customer's name.
- **A performance claim with no conditions recorded.** Unreproducible, and it will be re-measured by someone who gets a different answer.
- **The section implies instrumentation makes the application faster.** It makes slowness visible and attributable. Overclaiming here is what makes the whole document read as a pitch.
- **The section is the longest in the document.** It is an argument built on the sections above it. If it needs that much space, the sections above it did not do their job.
