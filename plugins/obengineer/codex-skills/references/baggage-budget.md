# Baggage budget — deciding what is worth carrying

Authoring reference for [`baggage-propagation`](../baggage-propagation/SKILL.md). The
mechanism is in that skill and in
[`cross-cutting-attributes.md`](cross-cutting-attributes.md). This file is only about
the harder question: **which keys earn a place in the header, and which do not.**

## Why this needs a budget at all

Baggage is not free storage. It is a request header, re-serialized on every hop, and it
is paid for in four places at once:

| Cost | Where it lands |
|---|---|
| **Bytes on the wire** | Every outbound HTTP request from every service, on every hop, for the life of the system. A 12-hop request pays the same header twelve times. |
| **A shared header budget** | Baggage competes with cookies, `Authorization`, and CSRF tokens against one per-request header ceiling enforced by the edge, the proxy, and the runtime. Baggage is the newest arrival, so baggage is what gets blamed when the ceiling is hit. |
| **Message-attribute slots** | Buses cap attributes per message. Amazon SQS allows **ten** message attributes; trace context plus baggage already consumes three of them before the application has added anything. |
| **Span attributes, if stamped** | Each stamped key is on every span in the estate, which is where cardinality cost and PII exposure actually accrue. |

None of these is catastrophic for a small set. All of them get ugly at fifteen keys,
and the failure is not a clean error — it is an intermittent 400 or 431 from one proxy
in one region, or a message rejected by one consumer, weeks after the change shipped.

### The arithmetic worth putting in the guide

An entry costs `len(key) + len(value) + 2` bytes, before percent-encoding expands any
character outside the allowed set.

```
6 keys × (18-byte key + 20-byte value + 2)  ≈ 240 bytes per request
```

At 5,000 requests per second across a mesh averaging 8 internal hops, that header is
constructed, transmitted, and parsed **40,000 times a second**. It is a small number
that is multiplied by a large one, which is the shape of every cost that gets noticed
late.

### Budget

| Limit | Value | Basis |
|---|---|---|
| Total `baggage` header | **≤ 512 bytes** target, 1,024 hard ceiling | Leaves room under the smallest common per-header limit even when cookies are large |
| Per-value length | **≤ 64 bytes** | Enforced in `setBaggageEntry`, so a caller cannot violate it by accident |
| Key count | **≤ 6** | Beyond this, every addition should displace an existing key rather than extend the set |
| Message-bus attributes used by tracing | **≤ 3** | `traceparent`, `tracestate`, `baggage` — fits inside the SQS ten-attribute cap with room for the application |

Confirm the real per-request header ceiling against **this** target's edge, proxy, and
runtime rather than assuming a number: gateway and load-balancer limits, reverse-proxy
buffer sizes, and language-runtime header caps all differ, and the smallest one governs.
Record it in `standards.baggage_header_budget_bytes` in the engagement inputs.

## The five tests a key must pass

A candidate goes in baggage only if the answer is yes to **all five**. One no, and it
belongs in one of the alternatives below.

### 1. Is it needed on spans other than the one that knows it?

Baggage exists to move a value to code that cannot compute it. If the only consumer is
the browser session, it is a RUM global attribute. If the only consumer is the service
that derived it, it is a local span attribute. **Neither needs a header.**

### 2. Can the receiver derive it instead?

This test eliminates more candidates than the other four together. Anything the
downstream already holds must not be carried:

| Candidate | Derive it from | Verdict |
|---|---|---|
| Region, cluster, environment | The service's own deployment metadata and resource attributes | Never in baggage |
| Tenant, market, or entitlement already in the JWT | The claim the service parses on every request anyway | Not in baggage unless the claim is absent on internal hops |
| Route or operation name | The receiving service's own router | Never in baggage |
| Anything computable from `trace_id` | The trace itself, at query time | Never in baggage |
| Service version | Resource attributes set at build time | Never in baggage |

The Collector is the other derivation point. A tenant key computed by an OTTL transform
from an existing attribute costs zero header bytes and is applied uniformly, which is
strictly better than asking every service to propagate it.

### 3. Does a named artifact consume it?

Name the dashboard variable, the detector `group by`, or the documented troubleshooting
pivot that reads this key. **No named consumer, no baggage.** "It might be useful" is
how a six-key set becomes a twenty-key set, and nobody ever removes one, because
removal requires proving a negative across an estate.

### 4. Is it bounded and stable for the request's lifetime?

A value that changes mid-request produces spans in one trace that disagree with each
other, which is worse than the value being absent — an absent key is a known gap, an
inconsistent key is a wrong answer. Unbounded values also blow the byte budget on the
one request that happens to carry a long one.

### 5. Is it safe in plaintext, in a log, and possibly at a third party?

Baggage is unencrypted, appears in access logs and proxy traces, and reaches every
origin in the propagation allowlist — which is one CORS misconfiguration away from
including a vendor. So: no tokens, no email addresses, no names, no full addresses, no
anything on the PII deny list. The identity key that does ride in baggage must be an
opaque internal identifier, and the guide must say so where the key is introduced.

## Carrying and stamping are two decisions, not one

The propagator decides what crosses the wire. The `SpanProcessor.onStart` allowlist
decides what lands on spans. Conflating them is why sets grow.

| | Stamp on spans | Do not stamp |
|---|---|---|
| **Carry in baggage** | The cross-cutting set. Small, bounded, consumed by dashboards and detectors. | A value a downstream needs for a *decision* but nobody queries. Rare — and if it drives behaviour, it probably belongs in the application's own contract, not in a telemetry header. |
| **Do not carry** | Locally known keys: route class, operation outcome, retry count, anything the Collector derives. This is where most attributes belong. | Not needed. Say so and move on. |

Two consequences the guide should state explicitly:

- **The `onStart` processor iterates an explicit allowlist, never all baggage entries.** A processor that stamps whatever it finds turns any future caller's `setBaggageEntry` into an estate-wide span attribute, including one carrying a token.
- **Adding a key to baggage does not make it a metric dimension.** That is a third, separate decision, with its own budget: [`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md).

## Three tiers, so "no" has somewhere to go

Most rejected candidates are not unimportant — they are simply not estate-wide. Give
them a tier rather than dropping them, or they come back as an argument.

**Tier 1 — Global baggage.** Three to six keys, every request, every service. The
identity key, the tenant/market/region key, `session.id`, and a bounded attribution
class if the front end has one. This tier is closed: an addition displaces a member.

**Tier 2 — Path-scoped propagation.** Injected at one boundary and carried only along
one call chain — a checkout correlation key on the checkout path, a batch identifier
from a scheduler into its workers. Same mechanism, deliberately not global, so the cost
is paid only by requests that benefit. This is the right home for most "we need it in
this flow" requests.

**Tier 3 — Join, do not carry.** The value stays where it is known and the connection
is made at query time:

| Join | Use when |
|---|---|
| **Continue trace** | The downstream work is the same causal request. The context already links them; carrying the value adds nothing. |
| **Span link** | One span caused by many traces, or a delayed cause — webhooks, batch consume, DLQ redrive, schedulers, scatter/gather. |
| **Attribute pivot** | Both sides independently carry a key that is already in Tier 1. This is what Tier 1 buys, and it is why Tier 1 must be small enough to be everywhere. |
| **Related Content / log correlation** | The value is in a log record with `trace_id`. Query it there instead of promoting it to a header. |

## Worked verdicts

Reusable table for the guide, so the reasoning survives the review meeting:

| Candidate | Tier | Reasoning |
|---|---|---|
| Internal account or customer identifier (opaque) | 1, attribute-only | The pivot every troubleshooting path starts from. High cardinality, so stamped on spans but never a metric dimension. |
| Market, locale, or region, as a bounded enum | 1, dimension-eligible | Small enum, wanted as a dashboard variable and a detector `group by`. |
| `session.id` | 1, attribute-only | The only link from a backend trace back to a browser session. |
| Attribution class (`paid` \| `organic` \| `direct` \| `referral`) | 1, dimension-eligible | Bounded by construction. Carry the class, never the raw campaign string. |
| Raw UTM values or full referrer | Not carried | Unbounded, user-controlled, and PII-adjacent. Classify in the browser, carry the class. |
| Cart, order, or transaction identifier | 2 | Wanted on the checkout path, useless on the other ninety percent of requests. |
| Experiment or feature-flag assignments | 2, and only the flags under test | The full assignment set is unbounded and grows silently. Never the whole map. |
| Authenticated user's email or name | Never | PII in plaintext, in logs, potentially cross-origin. Use the opaque identifier. |
| Auth token, API key, or session cookie value | Never | A credential in a header that is copied to every hop and logged by default. |
| Deployment environment, service version, cluster | Not carried | Resource attributes. Already on every span. |
| Route or endpoint name | Not carried | The receiver's own router knows it. |
| Tenant already present as a JWT claim | Not carried, unless internal hops drop the JWT | Derivable. If internal hops do drop it, prefer a Collector transform over a header. |

## Exit criteria

Phrase the section so it can be checked rather than asserted:

- Every key in the documented set has a named dashboard variable, detector `group by`, or troubleshooting pivot that reads it. Any key without one is removed before the guide ships.
- The serialized header for a representative authenticated request is under the agreed byte budget. Measure it; do not estimate it.
- No span in Observability Cloud carries a baggage-derived key outside the allowlist, and no value exceeds the ceiling.
- Publishing and consuming one message yields a single `trace_id` across producer and consumer, with the Tier 1 keys present on the consumer span.
- Grouping any workflow chart by the tenant key produces no `UNKNOWN` bucket beyond `standards.unknown_dimension_threshold_pct`.
- The gateway forwards `traceparent`, `tracestate`, and `baggage`. A gateway that strips them presents as an instrumentation bug and costs days.

## Warning signs

- **A key was added because a team asked, with no consumer named.** Tier 2 or Tier 3, not Tier 1.
- **The set has grown past six and nothing was removed.** The set is closed by design; growth without displacement means the budget is not being enforced.
- **A value is a serialized object, a JSON blob, or a comma-joined list.** Structure in a header is a byte-budget violation waiting for its worst-case request, and usually a sign the value belongs in a span attribute.
- **The reason given for baggage is correlation.** Correlation is what `trace_id` is for. Baggage is for values, not for links.
- **Nobody measured the header.** Every byte estimate in this file is arithmetic; the actual header on the actual authenticated request is the only number that settles an argument.
