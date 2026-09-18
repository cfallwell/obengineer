---
name: cardinality-budget
description: >-
  Decide which span tags become metric dimensions and which stay attribute-only,
  as arithmetic against the customer's entitlement rather than as advice. Sizes
  Monitoring and Troubleshooting MetricSets, computes the metric time series a
  proposed promotion costs, sets the low-cardinality classifiers that replace raw
  URLs and topic names, and produces the dimension-eligible and attribute-only
  lists the Collector and MPM sections depend on. Use when the user types
  $cardinality-budget, asks about cardinality, MTS or DPM cost, MMS versus TMS,
  whether a tag can be a dimension, Tag Spotlight, metric ruleset or Metrics
  Pipeline Management rules, or why a dashboard variable is missing a value.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Cardinality Budget — dimensions as arithmetic

## Overview

"Keep cardinality low" is the most repeated and least actionable sentence in
instrumentation guidance. It loses every argument with a team that wants to group a
chart by order identifier, because it offers no number.

This skill replaces the advice with a budget. Given the entitlement in
`engagement-inputs.yaml`, a proposed promotion has a **cost in metric time series**, and
that cost either fits the remaining allowance or it does not. A guide that shows the
arithmetic gets a decision in the review meeting. A guide that says "avoid high
cardinality" gets an exception.

## The cost model

Splunk Observability Cloud bills and throttles on **metric time series**: one series per
unique combination of metric name and dimension values. A dimension does not add rows,
it multiplies them.

```
MTS added by one promotion
  = distinct values of the tag
  × metrics the tag is applied to
  × services reporting those metrics
```

The multiplication is what surprises people. A tag with 50 values, on 4 metrics, across
12 services, is 2,400 new series — from one checkbox. The same tag on a single
service's single metric is 50, which is nothing. **The tag is not the problem; the
product is.** So the question is never "is this tag high cardinality", it is "what does
this tag cost *here*".

Compare the total of all proposed promotions against:

```
headroom = custom_mts_included - custom_mts_in_use
```

and keep a reserve — the estate grows, and a promotion is far harder to withdraw than
to make, because withdrawing it breaks the dashboards that came to depend on it.

### When the numbers are `unknown`

Do not stall on a procurement question and do not silently proceed. Apply these
defaults, and state in the deliverable that the budget is assumed rather than measured:

| Assumption | Default |
|---|---|
| Total new MTS across every promotion in the contract | ≤ 25,000 |
| Distinct values of any single promoted tag | ≤ 100 |
| Monitoring MetricSets created by the contract | ≤ 10 |
| Per-tag ceiling for a Troubleshooting MetricSet | ≤ 10,000 distinct values |
| Reserve left unallocated | 30% of headroom |

Every one of these is a number a customer can disagree with, which is the point. An
assumption stated as a number gets corrected; an assumption stated as a principle gets
ignored.

## Process

### Step 1 — Sort every attribute into three outcomes

There is no fourth outcome, and every attribute in the dictionary gets exactly one.

| Outcome | Means | Costs |
|---|---|---|
| **Dimension-eligible** | Bounded enum, promoted to a Monitoring MetricSet, usable as a dashboard variable and a detector `group by` | MTS, by the formula above |
| **Troubleshooting-only** | Available in Tag Spotlight and trace search, groupable ad hoc, not a metric dimension | Indexing cost, bounded by the per-tag ceiling |
| **Attribute-only** | On spans, queryable in trace search and Related Content, never a MetricSet tag | Effectively nothing |

The test for dimension-eligible is all four of:

1. **The value set is bounded by construction**, not by observation. "We only see about twenty" is not a bound; an enum in code, a classifier function, or a Collector transform is.
2. **A named alert or dashboard variable needs it.** A detector cannot `group by` an attribute-only key, so this is the only reason a promotion is ever necessary.
3. **The computed MTS cost fits the headroom** with the reserve intact.
4. **It is not an identity.** Account, order, cart, session, and request identifiers are attribute-only regardless of how convenient a dimension would be. Promoting an identity key is the single most expensive mistake available in this design, and it is usually made in the first week by someone being helpful.

### Step 2 — Replace every unbounded value with a classifier

An unbounded value does not become acceptable by being useful. It becomes acceptable by
being classified, in code or in the Collector, into a bounded set — and the raw value
stays on the span for troubleshooting.

| Never a dimension | Classify to | Keep the raw value |
|---|---|---|
| Raw URL or path with identifiers in it | `page.type` / `route.class` — a bounded enum of page or route kinds | As a span attribute |
| Full topic, queue, or stream name | `messaging.destination.class` — a bounded family name | As a span attribute |
| SQL statement | Operation plus table, from instrumentation | Statement as an attribute, sanitized |
| User agent string | Browser family, device class | As a span attribute |
| Error message text | `error.class` plus a bounded reason code | Message as an attribute |
| Campaign or UTM string | Attribution class: `paid` \| `organic` \| `direct` \| `referral` | Not at all if user-controlled and PII-adjacent |

Name the enum in the attribute dictionary's `Notes` column. **A type of "string" with no
stated bound is how a dimension list becomes a cardinality incident** — the reviewer has
no way to see the cost, so nobody objects.

### Step 3 — Size the MetricSets, do not just name them

- **Monitoring MetricSets** produce the metrics detectors and dashboards read. They are a bounded resource: count the slots already used, and fit the contract's promotions into what remains. If the contract needs more than `mms_slots_remaining`, say which promotions were deferred and why, rather than listing all of them and letting the TAM discover the limit.
- **Troubleshooting MetricSets** serve Tag Spotlight and ad-hoc grouping. Cheaper, still not free, and governed by the agreed per-tag ceiling. This is where identity-adjacent keys go when someone needs to slice by them — the honest answer to "but I need to group by tenant" is usually a TMS, not an MMS.
- **The workflow tag is a special case.** Exactly one span tag becomes the APM Business Workflow. Name it explicitly, say which value shape it carries, and state that the workflow name is itself a bounded enum. An unbounded workflow tag is a cardinality incident with a dashboard attached to it.

### Step 4 — Push the enforcement into the pipeline

Guidance that depends on every future team remembering it has already failed. Put the
bound somewhere it is applied:

- **Classify at the Collector** with a transform, so the bounded value exists whether or not a service was updated. Say so in the attribute's `Set at` column, so nobody instruments it twice.
- **Use metric rulesets / Metrics Pipeline Management** to aggregate away a dimension the estate emits but nobody queries, and to drop what is never read. This is the lever that recovers headroom without a code change, and it is usually the cheapest thing on the table.
- **Enforce the enum where the value is produced**, so an unexpected value becomes a known bucket rather than a new series. A classifier whose default is the raw input is not a classifier.

### Step 5 — Write the two lists, with the cost visible

The Collector and MPM sections consume these directly, so produce them in the shape they
are read in:

**Dimension-eligible (add to MPM)** — one row per key: `Key | Bound | Distinct values | Metrics | Services | MTS cost | Consumer`.
The `Consumer` cell names the detector or dashboard variable. No consumer, no promotion.

**Attribute-only (never a dimension by default)** — one row per key:
`Key | Why not | Troubleshooting path`. The troubleshooting path is what makes this list
acceptable to the people who wanted the dimension: it says how they get their answer
instead. Usually a bounded Troubleshooting MetricSet plus Tag Spotlight, or a trace
search filtered by the identity key, or a Related Content jump into logs.

Then state the total: proposed MTS, headroom, reserve remaining. One line, and the
review meeting has a number to argue with instead of a principle.

## Warning signs

- **A dimension list with no MTS arithmetic anywhere in the document.** The list is a wish; nobody can approve it.
- **An identity key in the dimension list.** Reject it and offer the Troubleshooting MetricSet path in the same sentence, or it comes back.
- **`Type: string` with no bound named.** Either name the enum or move the key to attribute-only.
- **The workflow tag is described but never named.** The TAM cannot configure a Business Workflow from a description.
- **Cardinality is discussed only as a risk.** Risk language produces exceptions. Numbers produce decisions.
- **The contract's promotions exceed `mms_slots_remaining` and the document does not mention it.** The limit will be discovered during configuration, by the person least able to renegotiate it.

## Non-goals

- Does not decide what rides in the baggage header. That is [`../baggage-propagation/SKILL.md`](../baggage-propagation/SKILL.md), against a byte budget rather than an MTS budget.
- Does not collect the entitlement numbers. That is [`../engagement-intake/SKILL.md`](../engagement-intake/SKILL.md).
- Does not create MetricSets or rulesets in a tenant. It produces the lists a TAM configures, or that [`../observability-as-code/SKILL.md`](../observability-as-code/SKILL.md) renders as Terraform.
