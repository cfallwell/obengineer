# Platform expertise — what the contract must be specific about

Shared reference. Read the part that matches the evidence, not all of it.

This is the material the architect agent used to carry inline. It is here because it is
consulted per language and per platform rather than per run: a Go backend with no browser
needs none of the front-end material, and loading it anyway spends context on a decision
nobody is making.

## Splunk OpenTelemetry — languages

| Language | Zero-code agent | Code-based | Typical shared-library name |
|---|---|---|---|
| Java | Splunk OpenTelemetry Java agent | OTel Java SDK | `<org>-otel-common` (Java) |
| Node.js / JS / TS | Splunk OTel JS | OTel JS SDK | `@<org>/otel-common` |
| .NET | Splunk OTel .NET | OTel .NET | `<Org>.Otel.Common` |
| Go | Splunk OTel Go | OTel Go | `go.<org>.example/otelcommon` |
| Python | Splunk OTel Python | OTel Python | `<org>_otel_common` |
| PHP | Splunk OTel PHP | OTel PHP | `<org>/otel-common` |
| Ruby | Splunk OTel Ruby | OTel Ruby | `<org>-otel-common` |
| C++ | No honest zero-code option | OTel C++ | `<org>_otel_common` |

Replace `<org>` from the customer's naming convention or an existing schema prefix. If
neither exists, propose one prefix and use it consistently — inconsistent prefixes are how a
dictionary ends up with the same concept under two keys.

**OBI / eBPF** covers third-party binaries and languages with no in-process agent. Protocol
visibility only, and never a substitute for user-facing or business journeys.

Kubernetes `instrumentation.opentelemetry.io/inject-*` annotations are **bootstrap**, not
done.

## Front-end languages and runtimes

Angular, React, Next.js (App Router and Pages), Vue, Svelte, Ember, Webpack Module
Federation and micro-frontends (**one host `init`**), vanilla SPA and SSR, Web Components,
tag managers (Adobe Launch, GTM) with their `fetch` / `XHR` / `history` patch collisions, and
CDN or edge injection (Fastly, Cloudflare Workers, Akamai) versus origin `<head>`.

RUM is the **Splunk RUM Browser Agent**. Safe-default instrumentations unless a named
question requires more: `document-load`, `user-interaction`, `xhr`, `fetch`, `long-task`,
`web-vitals`, `visibility`. Plus a kill switch, and a dedicated early script — never only
inside a large main bundle, where it loads after the paint it was meant to measure.

**Those allowlisted instrumentations do not capture client route changes.** Client routing
is application instrumentation, owned by the host. Enabling more auto-instrumentations does
not substitute for the router listener, and reaching for them is the usual wrong turn here.

Required snippet shape — adapt to the router in evidence, tokens stay placeholders, host
only:

```javascript
// React Router v6 — mount once in the host router tree. Remotes must not copy this.
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import SplunkRum from '@splunk/otel-web';
import { trace } from '@opentelemetry/api';
import { classifyPage } from '@<org>/otel-common';

export function RumRouteChange() {
  const location = useLocation();
  useEffect(() => {
    const pageType = classifyPage(location.pathname); // bounded enum, never raw path
    SplunkRum.setGlobalAttributes({ 'page.type': pageType });
    const span = trace.getTracer('<org>-rum').startSpan('route.change', {
      attributes: { 'page.type': pageType },
    });
    span.end();
  }, [location.pathname]);
  return null;
}
```

Per router: Next.js App Router uses the same effect on `usePathname()` in a client
component; Pages Router uses `Router.events.on('routeChangeComplete', …)` in the host
`_app`; React Router v5 uses `history.listen`; with no framework router, one History
`pushState` / `popstate` wrapper in the host and not in remotes.

**Router evidence to look for in a scan:** `react-router-dom`, `react-router`,
`next/navigation`, `next/router`, Remix, `@tanstack/react-router`, Vue Router, Angular
`Router`, or `pushState` without a full reload. Any of these makes section 7 of the template
mandatory, with code.

If there is no browser, say so and omit RUM rather than inventing it.

## Clouds and infrastructure

AWS (EKS, ECS, EC2, Lambda, API Gateway, ALB/NLB, EventBridge, SQS, SNS, Kinesis, Step
Functions, MSK), GCP (GKE, Cloud Run, Cloud Functions, Pub/Sub, GCE), Azure (AKS, App
Service, Functions, Service Bus, Event Hubs, VMSS), Kubernetes and OpenShift, plain VMs, and
edge (Fastly, Cloudflare, Akamai, CloudFront).

Whatever the platform, the contract specifies Collector placement, OTLP paths, OTTL and
redaction, spanmetrics, Metrics Pipeline Management, and the MetricSet split.

## Splunk platform (Enterprise or Cloud Platform)

You design the **log contract**, not a search dashboard farm:

- Which sourcetypes and indexes already exist, and which fields must be extracted: `trace_id`, `span_id`, `session.id`, a stable request id.
- HEC versus universal or heavy forwarder versus the Collector's logs exporter — use what is already deployed unless the human asks to change it. A migration smuggled into an instrumentation contract is how the contract gets rejected.
- CIM, Enterprise Security, and ITSI only when they are in evidence.
- Log Observer Connect: Observability Cloud is the trace UI, the platform is the event store, and the same identifiers exist on both sides. Without `trace_id` on the events, there is no join and the panel is decoration.
- **Never** recommend building the user journey as an SPL transaction as the observability strategy. That is the failure mode this work exists to end.

## Cisco ThousandEyes

You design **path tests**, not a second APM:

- Cloud and enterprise agents running HTTP, page-load, transaction, DNS, and BGP tests, where the diagram shows public or partner network risk.
- Endpoint agents when the workforce or field users are off-LAN.
- Align the test URL or path with the RUM `page.type` and the critical business transactions — as **labels**, not as a source of workflow spans.
- The signature that puts ThousandEyes in scope: RUM LCP is bad while TTFB and origin APM are fine. That is a CDN or ISP question, and no amount of application telemetry will answer it.
- When APM already shows the slow handler, ThousandEyes is supporting evidence, not the root span.
