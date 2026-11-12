---
name: cardinality-budget
description: >-
  Decide which span tags become metric dimensions using measured usage, enforced
  system limits, and explicit MTS arithmetic. Sizes Monitoring and Troubleshooting
  MetricSets, replaces raw unbounded values with classifiers, and produces
  dimension-eligible and attribute-only lists. Use for $cardinality-budget,
  cardinality, MTS, MMS/TMS, Tag Spotlight, or grouping questions.
metadata:
  author: obengineer
  version: 0.2.0
  category: observability
---

# Cardinality budget

Every proposed metric-dimension promotion has a visible metric time series cost:

```text
MTS added = distinct values × metrics carrying the tag × reporting services
```

Read current usage and `sf.org.limit.*` through the mandatory direct API procedure in
[`../references/existing-telemetry.md`](../references/existing-telemetry.md). Calculate:

```text
enforced system headroom after proposal
  = enforced system limit - current usage - reserve - proposed MTS
```

An enforced system limit is not contractual entitlement. Contractual entitlement stays
unavailable unless a separate measured Billing/Subscription Usage API or approved export
supports it. No human entitlement input, fit-to-entitlement switch, or order-form guess
may change the instrumentation design.

## Decisions

Every attribute has exactly one outcome:

| Outcome | Rule |
|---|---|
| Dimension-eligible | Bounded by construction, required by a named detector/dashboard, and costed |
| Troubleshooting-only | Useful for Tag Spotlight/trace search but inappropriate for a monitoring dimension |
| Attribute-only | Identity or unbounded value that must never become a metric dimension |

Account, order, cart, session, request, trace, and message identifiers are always
attribute-only. Promotions without a named consumer are omitted.

Replace raw URLs, topic names, SQL statements, user agents, and error text with bounded
classifiers (`page.type`, `route.class`, `messaging.destination.class`, operation/table,
browser/device class, and `error.class`). Preserve sanitized raw values only as trace
attributes when privacy rules permit.

## MetricSets and output

- Monitoring MetricSet dimensions require explicit distinct-value, metric, service, and
  MTS arithmetic.
- Troubleshooting MetricSets require predicted distinct values and an evidence-backed
  reason; they do not use a configurable human ceiling.
- Workflow/business-transaction values require bounded registries.
- Collector transforms and metric rulesets enforce classifiers and remove dimensions no
  consumer reads.

Produce:

1. `Key | Bound | Distinct values | Metrics | Services | MTS cost | Consumer`;
2. `Key | Why attribute-only | Troubleshooting path`; and
3. measured current usage, enforced system limit, reserve, proposed cost, and derived
   system headroom, each with source/time/scope.

When direct metrics are unavailable, keep proposed cost arithmetic, set usage/limit and
system headroom unavailable, and state the direct-attempt disposition. Never substitute
MCP-only evidence or a stated contract value.

This skill does not collect credentials, create tenant objects, or decide baggage keys.
