---
name: baggage-propagation
description: >-
  Design the cross-cutting attribute set and W3C Baggage propagation contract
  for a target: which keys appear on every span, where each is set once, how
  they ride the baggage header and message attributes, and the
  SpanProcessor.onStart stamp that puts them on every span without per-service
  code. Decides which keys earn a place in the header against a byte and
  key-count budget, and gives the rejected ones a path-scoped or query-time home.
  Produces the mandatory "Cross-Cutting Attributes and Baggage Propagation"
  section with all five code subsections. Use when the user types
  $baggage-propagation, asks about baggage, cross-cutting attributes, whether
  baggage is expensive, what to propagate versus derive, "getting account_id on
  every span", trace context across a message bus, why an attribute is missing on
  backend spans, or when writing or reviewing an instrumentation guide. Writes
  documentation, not application code.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Baggage Propagation — the cross-cutting attribute contract

## Overview

Dashboard variables, detector `group by` clauses, and Related-Content deep links all
read span **attributes**. An attribute that exists only on the span where it was
discovered cannot do any of those three jobs. So a small set of keys has to appear on
every span in the estate — browser and backend — and on log records where the
pipeline allows it.

This is the section that gets dropped, and it is the most expensive one to add late,
because retrofitting it means touching every service that already shipped. **A guide
without it is a failed run.** Full authoring spec, including every code block:
[`../references/cross-cutting-attributes.md`](../references/cross-cutting-attributes.md).

## The pattern

Three steps, and the guide must state the reasoning, not just the mechanism:

1. **Set the attribute once**, where the value is first known — browser boot, login success, or an edge request handler.
2. **Write it into W3C Baggage**, so it propagates over HTTP via the `baggage` header and over messaging via message attributes.
3. **Register a `SpanProcessor` whose `onStart` reads baggage and stamps the value onto each new span.**

Why not the alternatives:

| Approach | Outcome |
|---|---|
| Ask every team to set the keys | Fails. A documentation dependency on people who were not in the room; degrades as services are added. |
| Per-framework middleware copying headers onto spans | Partially works, then fails. Every new framework, worker, and consumer needs a copy, and spans auto-instrumentation creates before the middleware runs are missed. |
| **Set once → baggage → `onStart` stamp** | Works. Written where it is known, carried by the propagator, stamped onto every span the SDK creates. A team that ships later inherits it from the shared library and **cannot forget it**. |

## Process

### Step 1 — Choose the set, and keep it small

Baggage is a request header, re-serialized on every hop, competing with cookies and
`Authorization` for one per-request ceiling, and capped by the bus (Amazon SQS allows
ten message attributes; trace context plus baggage takes three). So the set is chosen
against a budget, not assembled from requests: **six keys, 512 bytes, 64 bytes per
value.** Selection tests, the three tiers, and worked verdicts for the usual candidates:
[`../references/baggage-budget.md`](../references/baggage-budget.md).

A key earns a place only if all five hold — it is needed on spans that do not know it;
the receiver cannot derive it; a **named** dashboard variable, detector `group by`, or
troubleshooting pivot reads it; it is bounded and stable for the request; and it is safe
in plaintext, in a log, and at a third party.

Most rejected candidates are not unimportant, only not estate-wide. Give them a tier, or
they come back as an argument: **Tier 2** is path-scoped propagation, injected at one
boundary and carried along one call chain; **Tier 3** is joined at query time by continue
trace, span link, attribute pivot, or log correlation. "Correlation" is never a reason
for baggage — that is what `trace_id` is for.

Build the table with columns exactly `Attribute | Type | Set at | Dimension? | Notes`.
Include, when they exist in the target: the identity key, the tenant/market/region
key, the bounded attribution subset, `session.id`, and the semconv mirror
(`enduser.id`). Nothing else without a named question it answers.

Carrying and stamping are two decisions. The propagator decides what crosses the wire;
the `onStart` allowlist decides what lands on spans; and whether a stamped key becomes a
metric dimension is a third decision with its own budget
([`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md)). Conflating the
three is how a set of six becomes a set of twenty.

### Step 2 — Classify each key for cardinality before writing any code

- **Bounded enum** → dimension-eligible. Name the enum in `Notes`; "string" with no stated bound is how a dimension list becomes a cardinality incident.
- **High-cardinality identity** (account, order, cart, session) → **attribute-only**. The troubleshooting path is a dedicated bounded MetricSet plus Tag Spotlight, and the `Notes` cell points at the section that explains it. Promoting an identity key to a global metric dimension is the single most expensive mistake available here.
- **Derived at the Collector** → say so in `Set at`, so nobody instruments it in application code.

### Step 3 — Write the five code subsections

Each is required, in this order, with real code and placeholder tokens only:

| Subsection | Must show |
|---|---|
| `Provider bootstrap (<boot artifact> only)` | `init`, `addSpanProcessor`, attribution capture, baggage boot — together, once, in the boot artifact. Plus: remotes must not `init`, and the provider handle must be reachable by other bundles. |
| `The SpanProcessor` | `onStart` iterating an **explicit key allowlist**. A processor that loops over all baggage entries stamps whatever a future caller put there, which is how unbounded values and tokens reach production. |
| `Writing baggage on login` | The identity value written to **both** global attributes (later spans in the session) and baggage (backend spans on the next request). |
| `Reading baggage on the <backend> backend` | Composite propagator (trace context + baggage) plus the same processor. No middleware needed: auto-instrumentation extracts the header before the handler runs. |
| `Messaging boundary — <bus>` | Producer inject and consumer extract, **once per bus**. Baggage does not cross a bus by itself. |

### Step 4 — State the join rules with the bus code

- **One message, same causal request → continue the trace.** The consumer span is a child of the producer span.
- **A batch, or a scheduled run over many records → span links.** One span caused by many traces; a single `parent` would misattribute it.
- **DLQ redrive → span link** to the original message's trace.

### Step 5 — Give the section verifiable exit criteria

Queryable in Observability Cloud, so the contract is checkable rather than
assertable:

- Any backend span from a browser-initiated request carries the cross-cutting keys. If they are only on the browser span, the propagator or the processor is not wired.
- Grouping any workflow chart by the tenant key produces no `UNKNOWN` bucket beyond the agreed threshold.
- Filtering APM by the identity key for a known test account returns both the browser session and the backend traces.
- Publishing and consuming a message yields one `trace_id` across producer and consumer, and the consumer span carries the baggage keys.
- No span carries a key outside the documented allowlist, or a value longer than the ceiling.

## Warning signs

- **A key is in the set with no consumer named.** Every key names the dashboard variable, detector `group by`, or pivot that reads it, or it is removed before the guide ships. This is the check that keeps the set at six.
- **The set grew and nothing was removed.** Tier 1 is closed: an addition displaces a member, or it is Tier 2.
- **A key the receiver could derive is being propagated.** Region, environment, service version, route, and a tenant already in the JWT are all derivable. Prefer a Collector transform, which costs zero header bytes.
- **Nobody measured the header.** The byte budget is arithmetic until someone captures the real header on a real authenticated request.
- **"Use baggage" appears as prose with no code.** Incomplete. Five subsections or an explicit `Not in evidence` under each heading.
- **The stamp processor loops over all baggage entries.** Replace with an allowlist before it ships.
- **The gateway is not mentioned.** The browser only sends `baggage` to origins in the RUM agent's CORS propagation list, and the gateway must allow `traceparent`, `tracestate`, and `baggage`. A gateway that strips them breaks the join, and the symptom looks like an instrumentation bug.
- **A token, email, or serialized object is written into baggage.** `setBaggageEntry` must enforce the allowlist and a value-length ceiling.
- **The bus subsection is missing because there is no bus yet.** Keep the heading, write `Not in evidence — do not deploy yet`, and show the pattern. The team gets the design the day the bus lands.

## Non-goals

- Does not write application runtime code or open PRs against services. That is `instrumentation-implement`.
- Does not decide which journeys exist. That is `instrumentation-analyze`.
