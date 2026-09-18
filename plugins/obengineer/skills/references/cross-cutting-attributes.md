# Cross-Cutting Attributes and Baggage Propagation — authoring spec

The section this file describes is **mandatory on every instrumentation guide**.
It is the most frequently omitted section and the most expensive one to add
later, because retrofitting it means touching every service that already shipped.

Substitute `<org>` (attribute prefix from evidence), `<boot>` (the artifact that
owns provider `init`), `<backend-lang>`, and `<bus>` throughout. Keep the key
names the customer already uses if a prior contract exists; extend, never rename
for taste.

---

## Why this section exists

Dashboard variables, detector `group by` clauses, and Related-Content deep links
all read span **attributes**. An attribute that is only present on the span where
it was discovered is useless for those three jobs. So a small set of keys has to
appear on *every* span — browser and backend — and on log records where the
logging pipeline allows it.

There are three ways to make that happen, and only one of them survives contact
with a large engineering org:

| Approach | Why it fails / works |
|---|---|
| Ask every team to set the keys on their spans | Fails. It is a documentation dependency on people who were not in the room, and it silently degrades as services are added. |
| A middleware per framework that copies headers onto spans | Partially works, then fails. Every new framework, worker, and consumer needs its own copy, and spans created by auto-instrumentation before the middleware runs are missed. |
| **Set once → W3C Baggage → `SpanProcessor.onStart` stamp** | Works. The value is written where it is first known, the propagator carries it across process boundaries, and the processor stamps it onto every span the SDK creates, including spans from auto-instrumentation. It cannot be forgotten by a team that ships later, because they inherit it from the shared library. |

The guide must state that reasoning in the section, not just the mechanism.

---

## Required structure

### Opening paragraph, then the three-step pattern as bullets

Say what the set is for (dashboard variables, detector groupings,
Related-Content deep links), then:

- **Set the attribute once** — at the point the value is first known: browser boot, login success, or an incoming request handler at the edge.
- **Write it into W3C Baggage** so it propagates over HTTP (`baggage` header) and over messaging (bus message attributes) automatically.
- **On every service, register a custom `SpanProcessor`** whose `onStart` hook reads baggage and stamps the value onto each new span as an attribute. This removes per-service get/put code and cannot be forgotten.

### H2 — `Cross-cutting attribute set`

Table with exactly these columns:

| Attribute | Type | Set at | Dimension? | Notes |
|---|---|---|---|---|

Populate from evidence. The set is deliberately small — every key here is
stamped on every span, so each addition is a cost paid on every span in the
estate. A working baseline:

| Attribute | Type | Set at | Dimension? | Notes |
|---|---|---|---|---|
| `<org>.account_id` | string | login success (browser) | No (attr only; bounded MetricSet for troubleshooting) | Mirror to `enduser.id` for semconv parity |
| `<org>.market` (or tenant/region) | string | Collector (OTTL) | Yes | Derived from the URL path segment; see the Collector section |
| `<org>.attribution.source` | enum | first pageview | Yes | Bounded channel enum |
| `<org>.attribution.platform` | enum | first pageview | Yes | Bounded platform enum |
| `<org>.utm.source` | string | first pageview | Yes | Bounded by the configured channel list |
| `<org>.utm.medium` | string | first pageview | Yes | Bounded |
| `<org>.ads.attributed` | bool | first pageview | Yes | True when any UTM or click ID is present |
| `<org>.attribution.has_click_id` | bool | first pageview | Yes | Quality signal: click IDs survive redirects that strip UTMs |
| `session.id` | string | RUM SDK (automatic) | Yes | Provided by the browser SDK |
| `enduser.id` | string | login success | No | Same value as `<org>.account_id`, kept for semconv compatibility |

Rules for this table:

- The identity key is **attribute-only**. It is high cardinality; promoting it to a
  global metric dimension is the single most expensive mistake available here. The
  troubleshooting path is a dedicated bounded MetricSet plus Tag Spotlight, and the
  table's `Notes` cell must point at the section that explains it.
- Anything derived by the Collector says so in `Set at`, so no one instruments it
  in application code.
- The bounded enums are named in `Notes`. "String" with no bound is how a
  dimension list becomes a cardinality incident.

### H2 — `Shared <language> library: @<org>/otel-common`

One paragraph: a single shared library owns baggage read/write, the stamp
processor, and the helpers (`startWorkflow`, attribution capture). Every business
bundle or service depends on it, and **exactly one artifact** calls the provider
`init`. Name that artifact.

Then the five H3 code subsections below, in this order. Tokens are **placeholders
only** — `window.__<ORG>_RUM_TOKEN__`, `${SPLUNK_ACCESS_TOKEN}`, `process.env.*`.
No real token, key, or secret value ever appears in a guide.

---

#### H3 — `Provider bootstrap (<boot> only)`

Browser example. The point of the subsection is that `init`, the processor
registration, attribution capture, and baggage boot happen together, once, in the
boot artifact.

```js
import { SplunkRum } from '@splunk/otel-web';
import {
  BaggageStampProcessor,
  captureAdAttribution,
  installBaggageBoot,
} from '@<org>/otel-common';

SplunkRum.init({
  realm: '<realm>',
  rumAccessToken: window.__<ORG>_RUM_TOKEN__,   // placeholder, injected at edge/SSR
  applicationName: '<app>',
  deploymentEnvironment: window.__<ORG>_ENV__,  // prod | stage | dev
  version: window.__<ORG>_BUILD__,              // maps to service.version
});

// Stamp baggage-derived attributes onto every span created after this point,
// including spans created by auto-instrumentation.
SplunkRum.provider.addSpanProcessor(new BaggageStampProcessor());

// Fire the one-per-session attribution event and seed baggage + storage.
captureAdAttribution();

// Wire the W3C baggage propagator into the global propagator so fetch/XHR
// send the `baggage` header to first-party origins.
installBaggageBoot();
```

Two details the guide must state alongside the snippet, because both are common
production defects:

- Business bundles, module-federation remotes, and micro-frontends **must not**
  call `init`. A second `init` produces two application names and two session
  identifiers in one browser session.
- Expose the provider handle deliberately (for example `window.__<ORG>_RUM__`) if
  other bundles or a tag manager need `setGlobalAttributes`. An agent whose handle
  is trapped in module scope cannot be used by anything else, which is what pushes
  teams toward a second `init`.

#### H3 — `The SpanProcessor`

The **explicit key allowlist** is the whole point. A processor that loops over
every baggage entry will stamp whatever a future caller puts in baggage, which is
how unbounded values and tokens reach production telemetry.

```ts
// @<org>/otel-common/src/BaggageStampProcessor.ts
import { Context, SpanProcessor, Span } from '@opentelemetry/sdk-trace-base';
import { propagation } from '@opentelemetry/api';

const KEYS = [
  '<org>.account_id',
  '<org>.market',
  '<org>.attribution.source',
  '<org>.attribution.platform',
  '<org>.utm.source',
  '<org>.utm.medium',
  '<org>.ads.attributed',
  '<org>.attribution.has_click_id',
] as const;

export class BaggageStampProcessor implements SpanProcessor {
  onStart(span: Span, ctx: Context): void {
    const bag = propagation.getBaggage(ctx);
    if (!bag) return;
    for (const k of KEYS) {
      const e = bag.getEntry(k);
      if (e?.value !== undefined) span.setAttribute(k, e.value);
    }
  }
  onEnd(): void {}
  async shutdown(): Promise<void> {}
  async forceFlush(): Promise<void> {}
}
```

State in prose: this is the "better via SDK" approach — automatic, uniform across
browser and `<backend-lang>` because both run the same OTel SDK, and impossible
for a downstream bundle to forget. **Do not sprinkle `baggage.getEntry(...)` calls
across services.**

#### H3 — `Writing baggage on login`

The identity value goes to **both** places: global attributes so later spans in
the same browser session inherit it, and baggage so backend spans inherit it on
the next request.

```js
// login.js — inside the login-success handler
import { setBaggageEntry } from '@<org>/otel-common';
import { SplunkRum } from '@splunk/otel-web';

function onLoginSuccess(accountId) {
  SplunkRum.setGlobalAttributes({
    '<org>.account_id': accountId,
    'enduser.id': accountId,
  });
  setBaggageEntry('<org>.account_id', accountId);
}
```

`setBaggageEntry` enforces the allowlist and a value-length ceiling, so a token or
a serialized object cannot become a baggage value. Never write the access token,
ID token, code verifier, email, or any credential into baggage or a span
attribute.

#### H3 — `Reading baggage on the <backend-lang> backend`

Register the baggage propagator in a composite alongside trace context, then
attach the **same** processor to the backend SDK.

```js
// backend service bootstrap — required before application code
import { NodeSDK } from '@opentelemetry/sdk-node';
import {
  W3CBaggagePropagator,
  W3CTraceContextPropagator,
  CompositePropagator,
} from '@opentelemetry/core';
import { BaggageStampProcessor } from '@<org>/otel-common';

const sdk = new NodeSDK({
  textMapPropagator: new CompositePropagator({
    propagators: [new W3CTraceContextPropagator(), new W3CBaggagePropagator()],
  }),
  spanProcessors: [new BaggageStampProcessor() /* + your BatchSpanProcessor */],
});
sdk.start();
```

State the two things this buys: **no middleware is needed**, because the
auto-instrumentations already extract baggage from the incoming `baggage` header
before the handler runs; and the browser only sends that header to origins listed
in the RUM agent's CORS propagation config, so the guide must also name those
origins and require the gateway to allow `traceparent`, `tracestate`, and
`baggage` on the request. A gateway that strips those headers silently breaks the
join, and the symptom looks like an instrumentation bug.

Add a `B3Propagator` to the composite only while a legacy hop still speaks B3, and
say when it can be removed.

#### H3 — `Messaging boundary — <bus>`

Baggage does **not** propagate over a message bus by itself. Producers copy
`traceparent`, `tracestate`, and `baggage` into message attributes; consumers
extract before creating the consumer span. One subsection per bus in the
architecture section.

```js
// producer
import { injectMessageAttributes } from '@<org>/otel-common';

const params = {
  Entries: [{
    Source: '<org>.orders',
    DetailType: 'OrderCreated',
    Detail: JSON.stringify(payload),
    EventBusName: bus,
  }],
};
injectMessageAttributes(params.Entries[0]);   // adds traceparent/tracestate/baggage
await eventbridge.putEvents(params).promise();
```

```js
// consumer
import { extractMessageContext } from '@<org>/otel-common';

export const handler = async (event) => {
  for (const record of event.Records) {
    const ctx = extractMessageContext(record.messageAttributes);
    await context.with(ctx, async () => {
      // consumer span here inherits trace_id + baggage
    });
  }
};
```

Then state the decision rule that keeps traces honest:

- **One message, same causal request → continue the trace.** The consumer span is
  a child of the producer span.
- **A batch of messages, or a scheduled run over many records → span links.** The
  span is caused by many traces, so a single `parent` would misattribute it. Link
  backward instead.
- **A DLQ redrive → a span link** to the original message's trace.

Close with the cross-account sentence: this is the piece most teams miss, and
without it outbound producer requests cannot be correlated to inbound consumer
responses at all.

---

## Not in evidence

If the target has no bus, no IdP, or no browser, keep the H3 heading and write
**Not in evidence — do not deploy yet**, then show the pattern anyway with one
line on what would have to be true to enable it. The team gets the design the day
the component lands instead of rediscovering this section.

## Verification

The guide's own exit criteria for this section — all queryable in Observability
Cloud, so they are checkable rather than assertable:

- Pick any backend span from a browser-initiated request: the cross-cutting keys
  are present on it. If they are only on the browser span, the propagator or the
  processor is not wired.
- Group any workflow chart by the tenant/market key: no `UNKNOWN` bucket beyond
  the agreed threshold.
- Filter APM by the identity key for a known test account: browser session and
  backend traces both return.
- Publish a message and consume it: producer and consumer spans share one
  `trace_id`, and the consumer span carries the baggage keys.
- Search all spans for allowlist violations: zero spans carry a key outside the
  documented set with a value longer than the ceiling.
