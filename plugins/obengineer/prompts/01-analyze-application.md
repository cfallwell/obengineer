# Prompt 01 — Analyze the application

**Agent:** [`../agents/instrumentation-architect.agent.md`](../agents/instrumentation-architect.agent.md)  
**Human:** TAM + customer architect. Docs-only. No application code changes.

Copy everything below the line into the agent chat. Replace the bracketed sections. Redact tokens.

---

## System reminder

Follow `instrumentation-architect.agent.md`. You are analyzing, not opening application PRs. Auto-instrumentation is a bootstrap, never a complete design. The deliverable is still the **full Always-on contract** (BT catalog, use cases, baggage/attribution/span-link/SPA-route-change **code with placeholders**, Collector/MPM). “Analysis” does not mean inventory-only.

Choose the course of action from **how Splunk Observability Cloud, Splunk Enterprise, and Cisco ThousandEyes work** (RUM, APM, Infrastructure, Log Observer Connect, Synthetics, MetricSets, APM Business Workflows, Related Content, Events API, MPM, Enterprise indexes/`trace_id`, ThousandEyes path tests) plus the evidence in this session. Do not assume an industry, a storefront, named journeys, a cloud, or a prior customer document. Discover journeys from the diagrams and scan. Assign each question to one platform: journeys/code → Observability Cloud; durable logs/audit → Enterprise; internet/CDN/SaaS path → ThousandEyes.

Do not search the workspace for unrelated documents. If an existing schema or guide is attached below, extend that taxonomy.

## Context

We are preparing an Observability-Driven Design contract for **[application identifier]**.

Environment(s): **[prod / stage / …]**. Realm or region if known: **[ ]**.

## Inputs

**Architecture**

- [Attach diagrams: C4, sequence, MFE map, account/VPC diagram, etc.]
- Narrative (if any): [paste]

**Front-end surfaces to deep-scan** (omit this block if there is no browser)

- Production URL(s): [ ]
- Non-prod URL(s): [ ]
- Known host vs remotes / MFEs: [ ]
- Edge / CDN: [ ]

**Backends (if known)**

- Languages and deploy targets: [ ]
- Buses: [ ]
- Cloud accounts / subscription boundaries: [ ]

**Constraints**

- Consent / overlapping EUM or RUM tools: [observed or unknown]
- Percentile standard: [default p90 if unspecified]
- Do not request or display ingest tokens.

## Task

If URLs were provided, **deep-scan** the front end (HTML, script order, competing agents, bundle placement of RUM, CSP, 404 shells, consent, third-party pixels). Combine with a **diagram-driven** backend map.

Produce `docs/observability/analysis-<app>-<date>.md` or a Word file with **every Always-on heading** from the architect agent (not an inventory stub). **Lead with a target breakdown analysis** in the same shape as Appendix A. Prompt 02 deepens schema JSON and span-tree detail — it does not introduce workflows, baggage code, attribution, SPA/React route-change code, or the span-link table for the first time.

Cover every heading in the architect agent’s **Always-on contract sections** table (same order). If evidence is missing, keep the heading and write **Not in evidence**. Do not drop a section because this is “analysis.”

1. **Target breakdown (Observed)** — this is the first page:
   - Composition (SPA/MFE/host vs remotes, API, batch)
   - Client surfaces / bundles and load-order timeline if a browser exists
   - Third parties and overlapping EUM/RUM
   - Backend accounts, buses, partners, DLQ/failure points from diagrams
   - **Business transaction registry** (every BT/surface discovered)
   - **Named integration flows** (hops across accounts/buses; what is already in Observability Cloud vs reconstructed in logs)
   - Unknowns
2. **Course of action** and **Missing portfolio components** — after the inventory, not before. Phase 0 yes/no; first journey; which products. Present/partial/absent for RUM, APM, Infra, Synthetics, Enterprise+LOC, ThousandEyes.
3. **Front-end deep scan** — keep the heading; one-line “no browser” if none. Name the router and whether navigations are client-side.
3a. **RUM SPA / React route changes** — if React or any SPA client router is in evidence: host-owned listener **code** (`useLocation` / `usePathname` / Pages `Router.events` / History), bounded `page.type`, `SplunkRum.setGlobalAttributes`, `route.change` span. `document-load` does not cover client navigations. MPA-only: **Not in evidence**.
4. **Identity and baggage enablement code** — attribute table + `SplunkRum.init` / language SDK, `SpanProcessor.onStart`, identity-success baggage write, backend composite propagator, bus inject/extract. Placeholders only for tokens.
5. **Shared libraries** — package name per language; remotes must not `init`.
6. **RUM ad / first-touch attribution** (if a browser exists) — classifier function, `session.ad_attribution`, bounded baggage subset, first vs last touch. If no UTM/pixels, still include the section (`direct`/`organic`).
7. **Parent-child vs span links** — table of every join; span links only for webhooks, batch consume, DLQ redrive, schedulers, scatter/gather. Not for RUM fetch → APM handler.
8. **Collector / MPM / PII redaction** — OTTL classify; no cookie dump; dimension vs attribute-only lists.
9. **Business Transactions and Workflows (Recommendations)** — one heading per BT; **exhaustive** dotted-kebab workflow lists (`{surface}.{object}.{verb}`). Enumerate from namedChunks, remotes, GTM/feature/payment flags, UI/translation copy, and diagrams. Do not stop at three generic verbs per BT.
10. **Monitoring use cases** for every ranked journey and every A.6 flow: workflow identity, span events, attributes (dimension yes/no), metrics, **dashboard** (variables, KPI row, p90, LOC, event overlay), **detectors** (including silent-outage), cross-workflow joins labeled **continue trace** | **span link** | **attribute pivot**. Then **Dashboards Overview** and a **Detectors Catalog**.
11. **Identity gaps**, **Phase 0 blockers** (observed only), **Bootstrap vs contract**, and **Questions for the human** (numbered). Draft detectors anyway; arm after trust. Do not guess PII-adjacent fields.
12. **Appendix C pre-delivery checklist** from the architect agent — every Always-on row yes/no.

Do not omit BT catalog, use cases, baggage code, attribution, SPA/React route-change code, or the span-link table because this is “analysis.” Do not modify application source.
