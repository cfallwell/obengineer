# Portfolio decision engine — Observability Cloud, Splunk Enterprise, ThousandEyes

Shared reference. Every recommendation in any deliverable must name a **product
surface**, a **retention/cost class**, and a **question**. If you cannot name all
three, do not add the telemetry.

The three platforms are complementary. Collapsing them produces two truths and a
dashboard nobody trusts.

## Which platform — pick from the question

| Question | Platform | Not this |
|---|---|---|
| What did this user, session, or journey do? How did the code run? | **Observability Cloud** — RUM, APM, custom meters | Reconstructing journeys from URL search in the log platform; ThousandEyes page-load as a stand-in for RUM |
| Where are the durable logs, audit, security, compliance, and long-retention investigation? | **Splunk Enterprise** (or Cloud Platform) | Inventing `workflow.name` in SPL |
| Did the internet, ISP, DNS, CDN, or SaaS path fail between the user and the origin? | **ThousandEyes** | Blaming the application from RUM and APM alone when the failing hop is off-box |
| Can I click from a trace to the log line and back? | **Log Observer Connect** plus `trace_id` / `span_id` on platform events | Publishing the same journey into both products with no shared identifier |

## Product surfaces — pick from evidence

| If the evidence shows | Primary surface | Typical contract |
|---|---|---|
| Browser, SPA, module-federated front end, mobile WebView | **RUM** | Early load, one `applicationName`, global attributes, web vitals plus custom UX spans, sampled sessions |
| Services, functions, containers, any server runtime | **APM** | `service.name`, span tree, `workflow.name`, baggage stamp, error status |
| Hosts, Kubernetes, process, in-cluster network | **Infrastructure** | Collector plus resource attributes. Not a substitute for journeys or for internet path |
| Logs that must join a trace; long retention; SIEM or audit | **Splunk Enterprise** + **Log Observer Connect** | Index `trace_id`, `span_id`, a stable request id; CIM-friendly field names; existing HEC and forwarders |
| "Does this route work for a probe?" | **Splunk Synthetics** | Canaries on critical routes. Not a replacement for RUM or for path visualization |
| User ↔ CDN ↔ origin, DNS, BGP, public SaaS (identity provider, payments, API gateways) | **ThousandEyes** | HTTP, page-load, and transaction tests from relevant clouds and ISPs; endpoint agents where the users are; alert on path versus origin. Correlate test labels with RUM geography — do not rebuild the workflow span tree in ThousandEyes |
| Deploy and change correlation | **Events API** | Post `service.version` and build id as chart overlays |

Shape shortcuts:

- **API-only backend** — skip RUM. Start with Collector, APM workflows, and meters.
- **Static browser-only site** — RUM plus a route classifier. Do not invent backend workflows.
- **Hybrid** — RUM must propagate `traceparent` and `baggage` onto the first backend hop, or Related Content will not join and the two halves stay separate products.

## Attribute vs event vs metric vs MetricSet

| Need | Mechanism | Do this in code |
|---|---|---|
| Find one session or trace; Tag Spotlight for roughly 8 days | Span **attribute** (troubleshooting) | Set it on the span. Do not promote a high-cardinality key to a Monitoring MetricSet |
| Chart, detector, 13-month trend, dashboard variable | **Monitoring MetricSet** on a low-cardinality span tag, or an OTel **metric** with bounded dimensions | Classify first — page type, workflow name, status class, tenant enum. Check cardinality before promoting |
| Cheap, short-lived debug tag | **Troubleshooting MetricSet** | Rare error codes, experiment flags, replay-mode pivots |
| Rate, value, or duration SLI | OTel **counter or histogram**; MPM index-as-dimension only for approved dimensions | Custom meter. Never use an `*.id` as a dimension |
| A milestone inside one request | Span **event** | `span.addEvent` with allowlisted attributes |
| End-to-end journey in APM | **APM Business Workflow** on a stable span tag, usually `workflow.name` | Emit the tag on the root and children, and tell the TAM which tag to configure |
| "What did this user do?" | RUM session plus **Related Content** into APM | One `traceparent` chain, `session.id`, and `enduser.id` as attribute-only |
| "What changed at 14:02?" | Chart **event overlay** | CD posts to the Events API with `service.version` |

**Cardinality rule of thumb:** a tag that can exceed roughly 1,000 values without a
bounded enum is attribute-only, or a Troubleshooting MetricSet at most. Identity keys
— user, account, order, cart, trace, session — are never Monitoring MetricSet
dimensions on custom business meters. `session.id` as a RUM troubleshooting dimension
is a semconv-sanctioned exception; do not copy the pattern onto business meters.

## Course-of-action algorithm

Run in order. The result becomes the **Course of action** section.

1. **Inventory what is already landing** across all three platforms. Distinguish "SDK, test, or index is present" from "the signal is trusted."
2. **Front end present?** Deep-scan load order. If the first RUM beacon lands after first paint, another agent patches `fetch` first, replay is always-on, or the application name is unstable — **Phase 0 for trust** before any journey spans.
3. **Discover journeys from evidence** — user tasks, APIs, message flows, batch jobs. Rank by business impact times blast radius. Names come from the observed domain, never a template.
4. **Design each journey for Business Workflows and Tag Spotlight** — one `workflow.name`, a bounded `workflow.step`, span events at decision points, baggage for identity that must appear on every hop.
5. **Plan identity** — which keys are global RUM attributes, which ride baggage, and which the Collector derives with OTTL so the application does not explode cardinality.
6. **Plan meters** for the questions that need detectors: error rate, duration, value, and zero-activity silent outage. Prefer metrics with three to six bounded dimensions over promoting every span tag.
7. **Plan Related Content** — RUM to APM via `traceparent`, APM to platform logs via `trace_id` through Log Observer Connect, APM to infrastructure via resource attributes.
8. **Plan ThousandEyes** when the evidence shows a CDN, multi-region users, public SaaS dependencies, or the "slow but the origin looks fine" pattern. Place tests on the hops APM cannot see. If ThousandEyes is absent, still write the recommendation and the benefit.
9. **Bootstrap last in the narrative, first in the calendar.** Collector, zero-code, and operator injection get library spans. They do not get journeys, the baggage stamp, or business meters.
10. **Name the missing components** — present, partial, or absent for RUM, APM, Infrastructure, Synthetics, Enterprise with Log Observer Connect, and ThousandEyes.
11. **Make exit criteria portfolio-verifiable** — Tag Spotlight shows the tag; the MetricSet cardinality dialog is acceptable; a test trace crosses every bus; a detector could be built on a Monitoring MetricSet or metric; a platform search by `trace_id` returns the log; a ThousandEyes test covers the public path the real users take.

## Pitfalls to prevent

- Raw URL, `location.href`, or a full messaging topic as a metric dimension. Classify instead: page type, `messaging.destination.template`.
- Custom tags used in dashboards without a Monitoring MetricSet — they vanish from long-term charts. Tag Spotlight is not a dashboard strategy.
- More than one RUM `applicationName` for one product, which breaks MetricSets and sessionization.
- Always-on session replay: cost plus a Core Web Vitals regression. Default to sampled and on-demand.
- Enabling every RUM instrumentation, which causes long-task and interaction regressions and collides with tag-manager wrappers.
- Assuming `document-load` and LCP cover client-router navigations. They do not, so later business transactions never appear as RUM views.
- Auto-instrumented HTTP with no `workflow.name`: a service map with no Business Workflows.
- Logs with no `trace_id`, which leaves operators reconstructing journeys in SPL — the failure mode this work exists to end.
- A detector on a troubleshooting tag or an identity dimension: noisy, expensive, or impossible at 13 months.
- ThousandEyes page-load used as a substitute for RUM: no session, no workflow, no baggage. ThousandEyes answers the path; RUM answers the user.
- The same dashboard duplicated in both platforms with no shared identity.
