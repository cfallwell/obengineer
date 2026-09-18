# Prompt 02 — Develop the instrumentation guide

**Agent:** [`../agents/instrumentation-architect.agent.md`](../agents/instrumentation-architect.agent.md)  
**Skills:** `instrumentation-guide`, `baggage-propagation`, `customer-doc-render`  
**Depends on:** completed Prompt 01 analysis, accepted by the human.  
**Output:** PR 0 — documentation only. **Three artifacts:** the Markdown guide, the customer `.docx`, and `attribute-schema.json`.

Copy below the line. Attach the analysis memo and diagrams again.

---

## System reminder

Follow `instrumentation-architect.agent.md`. Produce the **full guide** using the
canonical customer template in `skills/references/document-template.md` — that file
owns the section order and every table's columns. Read it before writing. You still
do not implement application runtime code. Enablement snippets (baggage,
attribution, SPA/client route-change, span-link vs parent) with token placeholders
are required in the guide.

**Two artifacts from one source.** The Markdown guide is for the implementer agent.
The `.docx` is for customer architecture review and is **rendered from the committed
Markdown** by the `customer-doc-render` skill — never hand-authored, so the two
cannot disagree. Markdown alone is an incomplete delivery.

**The Word artifact opens on a simple title page, then the Table of Contents on its
own page, then one section per page.** Declare the title page in a
`<!-- title-page ... -->` block (subtitle, tagline, author, audience, date, version,
header) and put nothing else above the first `##`. Application identifier,
environment scanned, realm, percentile standard, in-scope languages and buses,
evidence basis, and token handling go in
**`### Document control and evidence basis`** at the end of Purpose and Scope. The
renderer rejects prose above the first section heading and refuses to save a
document whose sections would not break, so run `verify_render.py` and expect
exit 0. Layout spec:
`skills/customer-doc-render/references/document-format.md`.

**Document order.** Purpose and Scope, References, then
**`<Frontend> and Backend Architecture (Observed)`** as a body section near the
front — this is what a customer architecture review opens on, so it is not an
appendix and is not retitled. Lift and deepen the Prompt 01 inventory into it. The
**attribute dictionary is Appendix A** and **open items are Appendix B**, both at
the back. Do not open the file with an executive diagnosis.

**`Cross-Cutting Attributes and Baggage Propagation` is mandatory and is the section
most often dropped. A guide without it is a failed run.** It follows the
architecture section and precedes attribution. Spec:
`skills/references/cross-cutting-attributes.md`.

Zero-code / auto-instrumentation appears only in **Bootstrap vs non-goals** and as
an explicit subset of Phase 0 Collector/agent install — never as the definition of
done.

Map every journey and attribute to the **portfolio**: Observability Cloud (which
product, MMS vs TMS vs OTel metric, APM Business Workflow tag, Related Content),
Splunk Enterprise (log fields + Log Observer Connect), ThousandEyes (path tests for
off-box hops). Use the decision engine in the architect agent. Do not assume
journeys or metric names from another customer.

If an existing contract or `attribute-schema.json` is attached in this session,
**reuse those names and keys**. Extend; do not rename for taste. Do not search the
workspace for other documents.

## Inputs

- Analysis memo: [path or paste]
- Architecture diagrams: [attached]
- Front-end scan notes: [path or “no browser”]
- Percentile standard: **[p90 unless specified]**
- In-scope languages (from analysis): [ ]
- In-scope clouds/buses: [ ]
- Attribute prefix `<org>`: [from evidence, or propose one]
- Author / audience line for the customer document: [ ]

## Task

Write:

1. `docs/observability/INSTRUMENTATION-GUIDE.md` — every section in
   `document-template.md`, in order.
2. `docs/observability/attribute-schema.json` — aligned with Appendix A.
3. `docs/observability/<Customer>-<App>-Instrumentation-Recommendations-<date>.docx`
   — rendered from artifact 1 with `customer-doc-render`: simple title page, Table
   of Contents on its own page, every section a Word `Heading 1` starting a new
   page, `Confidential` footer. Verified with `verify_render.py`.

The guide **must** include:

- **Purpose and Scope**, then **References** — real resolvable URLs, Splunk-primary
  and OpenTelemetry-secondary, limited to what a recommendation here maps back to.
- **`<Frontend>` and Backend Architecture (Observed)** as a body section near the
  front — breakdown analysis, not a stub. BT vs workflow distinguished. Every
  evidenced surface listed. Third-party and **overlapping RUM/EUM agents** with why
  each matters to the contract. Named flows include hop/account crossings and what
  is already visible in Observability Cloud.
- **Cross-Cutting Attributes and Baggage Propagation** — the three-step pattern with
  its rationale, the `Attribute | Type | Set at | Dimension? | Notes` table, and all
  five code subsections: `Provider bootstrap`, `The SpanProcessor` (explicit key
  allowlist), `Writing baggage on login`, `Reading baggage on the <backend> backend`
  (composite propagator), `Messaging boundary — <bus>` once per bus in the
  architecture section. Keep the heading and write **Not in evidence** if a piece
  genuinely does not exist, and show the pattern anyway.
- **RUM ad / first-touch attribution** if a browser exists — classifier function,
  `session.ad_attribution` event table, bounded baggage subset (emit
  `direct`/`organic` if no campaigns seen).
- **OTel Collector Configuration** — OTTL derive, PII redaction, and **processor
  placement** (before the spanmetrics connector, before `batch`).
- **Metrics Pipeline Management** — dimension-eligible vs attribute-only, with the
  cardinality rationale and the bounded-MetricSet escape hatch.
- **Business Transactions and Workflows (Recommendations)** — one heading per BT;
  exhaustive dotted-kebab workflow lists with `workflow.step` enumerated per family.
  Not a restatement of the architecture section's index table.
- **Messaging Observability** — topic convention, producer/consumer attribute table
  (destination **template** is the dimension), cross-account propagation.
- **Use Case: `<flow>`** per ranked flow — workflow identity, span-event table,
  attribute dimension table, metrics, dashboard panel list, detectors, joins labeled
  continue trace | span link | attribute pivot. Span links only for webhooks, batch,
  DLQ, schedulers, scatter/gather.
- **Release Events via the O11y Events API** and **Log Observer Connect**.
- **Dashboards Overview** (workflows grid + per-flow + troubleshooting) and a
  **Detectors Catalog** marking arm-now vs draft-until-trusted.
- **Missing portfolio components** — present/partial/absent for RUM, APM, Infra,
  Synthetics, Enterprise+LOC, ThousandEyes; recommend what is missing and the
  **benefit** for this target.
- Course of action after the architecture section (Phase 0 yes/no, first journey,
  which products).
- RUM placement and **single init** only if a browser exists; omit RUM if not.
- Page/route/operation classifier with **low cardinality** — never a raw URL or a
  full topic name as a dimension.
- **RUM SPA / client route changes** if a client router exists — host listener code,
  `page.type` refresh, `setGlobalAttributes`, `route.change` span; `document-load` is
  first-document only.
- Shared library API **per language in scope** (remotes must not `init`).
- Custom meters split into **business** and **developer/execution** — only meters
  justified by evidence, each with 3–6 bounded dimensions.
- Which span tag the TAM will configure as an **APM Business Workflow**.
- Phase plan with **Observability Cloud–verifiable** exit criteria.
- Draft detectors only after trust exists.
- PII deny list identical to schema `deny`.
- **Appendix A** dictionary and **Appendix B** open items plus the filled
  pre-delivery checklist (every row yes/no).

## Explicit non-goals for this PR

- No application code, no Helm token values, no dashboard JSON unless the human asked for stubs
- No “enable all instrumentations”
- No always-on session replay unless the human accepted cost and CWV risk in writing

## Acceptance

A staff engineer who did not write the guide can implement Phase 0 (if any) and the
first high-value workflow without asking what `workflow.step` values are, how
baggage is stamped and propagated across the bus, or whether a join is
continue-trace or a span link. The architecture section alone is enough to list
every BT and flow. A TAM can configure MetricSets and Business Workflows from the
portfolio mapping section. The customer `.docx` opens with a populated Table of
Contents and one section per page. The pre-delivery checklist is all yes.
