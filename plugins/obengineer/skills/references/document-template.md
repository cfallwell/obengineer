# Customer instrumentation document — canonical template

This file **is** the template. It is self-contained on purpose: no external PDF,
Word file, or prior customer deliverable is needed to reproduce the format. Any
run that produces an instrumentation guide must emit these sections, in this
order, with these sub-structures and table columns.

`<org>` is the customer's attribute prefix, taken from evidence (an npm scope, a
package namespace, a resource-tag prefix) or proposed once and used everywhere.
`<app>` is the application identifier from evidence, kebab-case.

---

## Two artifacts, one source

Every guide run produces **both**:

| Artifact | Path | Audience | Built by |
|---|---|---|---|
| Markdown | `docs/observability/INSTRUMENTATION-GUIDE.md` | the implementer agent and engineers working the PRs | authored directly |
| Word | `docs/observability/<Customer>-<App>-Instrumentation-Recommendations-<date>.docx` | customer architecture review | `customer-doc-render` skill, from the markdown |

The `.docx` is never hand-maintained. It is rendered from the markdown so the two
can never disagree. A guide delivered as markdown only is incomplete; a `.docx`
that was not rendered from the committed markdown is not reviewable.

Also emitted: `docs/observability/attribute-schema.json`, the machine form of the
attribute dictionary appendix.

---

## Page 1 — a simple title page

Declare it in a `title-page` block at the top of the markdown. The renderer puts
these lines, and only these lines, on page 1:

```markdown
# Instrumentation Guide — <App> (`<host>`) — <date> — v<N>

<!-- title-page
subtitle: Instrumentation, attribution, and dashboarding
tagline: Splunk Observability Cloud • OpenTelemetry • RUM   (only products in scope)
author: <name>, <role>
audience: <customer engineering org>
date: <yyyy-mm-dd>
version: v<N>
header: Implementation Recommendations
-->
```

No executive summary, no diagnosis, and **no metadata dump**. The application
identifier, environment scanned, realm, percentile standard, org prefix, in-scope
languages and buses, evidence basis, and token-handling note are content, not
title-page furniture. They go in the body as
**`### Document control and evidence basis`**, the last subsection of Purpose and
Scope, as a `Field | Value` table plus the notes. The renderer rejects anything
else above the first section heading, so this is enforced rather than advised.

First page header: the banner plus the document class (`Implementation
Recommendations` for a guide, `Application Analysis` for a Prompt 01 memo).
Footer: `Confidential` on page 1, `Confidential | Page N of M` after it.

## Page 2 — Table of Contents

Mandatory in the Word artifact: `Table of Contents` as `Heading 1` on its own
page, then a Word field covering levels 1–3 with dot leaders and page numbers,
refreshed on open. The markdown artifact does not need a ToC; the renderer inserts
it.

## Paging and heading levels

Markdown `##` renders as Word `Heading 1` and **starts a new page**; `###` becomes
`Heading 2`; `####` becomes `Heading 3`. The break is set with
`w:pageBreakBefore` on the heading itself and read back before the file is saved,
so "every section starts on a new page" is a guarantee. Layout details live in
[`customer-doc-render/references/document-format.md`](../customer-doc-render/references/document-format.md).

---

## Section order

Numbered here for reference only; do not number the headings in the output.

| # | Heading | Level |
|---|---|---|
| 1 | Purpose and Scope | H1 |
| 2 | References | H1 |
| 2a | Splunk documentation (primary) | H2 |
| 2b | OpenTelemetry upstream (secondary) | H2 |
| 3 | **\<Frontend\> and Backend Architecture (Observed)** | H1 |
| 4 | **Cross-Cutting Attributes and Baggage Propagation** | H1 |
| 5 | RUM Ad Attribution Capture | H1 |
| 6 | OTel Collector Configuration | H1 |
| 7 | Metrics Pipeline Management (Index-as-Dimension) | H1 |
| 8 | Business Transactions and Workflows (Recommendations) | H1 |
| 9 | Messaging Observability | H1 |
| 10 | Use Case: \<flow\> — one H1 per ranked flow | H1 |
| 11 | Release Events via the O11y Events API | H1 |
| 12 | Log Observer Connect | H1 |
| 13 | Dashboards Overview | H1 |
| 14 | Detectors Catalog | H1 |
| 15 | Appendix A: Master Attribute Dictionary | H1 |
| 16 | Appendix B: Open Items and Assumptions | H1 |

Rules that are easy to get wrong:

- **Architecture (Observed) is section 3 — a named body section near the front, not an appendix.** It is the section the customer reviews first in an architecture review. Do not retitle it "Appendix A — Target breakdown" and do not move it behind Purpose.
- **The attribute dictionary is Appendix A, at the back.** Architecture at the front, dictionary at the back.
- Every H1 starts on a new page in the Word artifact.
- If a section has no evidence, keep the heading and write **Not in evidence**, plus one line on what evidence would settle it. Never delete a heading.

---

## 1. Purpose and Scope

One paragraph naming the target and the audience's assumed knowledge, then a
numbered inline list of what the document covers. Close with the language and
collector assumptions ("JavaScript for RUM via the Splunk RUM Browser Agent,
OTel Contrib Collector for the collection tier, backend snippets in
`<language>`"), and the citation rule: Splunk-authored docs first, OpenTelemetry
upstream where no Splunk equivalent exists.

## 2. References

Two bulleted lists of real, resolvable URLs. Not a bibliography of everything —
only documents a recommendation in this guide maps back to.

**Splunk documentation (primary)** covers, at minimum, the products in scope:
RUM browser install, RUM `setGlobalAttributes`, APM Business Workflows, Tag
Spotlight and MetricSets, Metrics Pipeline Management, Log Observer Connect,
Related Content, the Events API, detectors, and the Splunk Collector
distribution.

**OpenTelemetry upstream (secondary)** covers: W3C Baggage, the Baggage API for
the in-scope language, the `SpanProcessor` interface, the transform processor
(OTTL), semantic conventions, the spanmetrics connector, and the web SDK.

## 3. `<Frontend>` and Backend Architecture (Observed)

Prose first, then bullets. Every claim carries its evidence.

1. **Composition paragraph.** Runtime model (SPA/MPA/SSR, module federation host vs remotes, mobile, batch), which bundle or process owns `init`, and the routing consequence for RUM stated explicitly — for a client-routed app: a single `init` in the boot bundle governs the whole session and per-page bundles must not re-initialise the provider.
2. **Third-party surfaces bullet list.** Grouped by class, and each class states why it matters to the contract (consent gate, PII processor, span attribution, CSP entry): payments, personalization, KYC/identity, affiliate, consent, engagement, ad pixels, **overlapping RUM/EUM/session-replay tools**, and the analytics event names already wired (so span-event names can mirror them and both stacks agree).
3. **Backend accounts and buses paragraph.** Name each cloud account or subscription and what it hosts, the bus topology between them, the downstream systems each fans out to, and the sentence that the contract turns on: trace context must be propagated across the account boundary via message attributes.

Call out gaps inline as gaps (a missing pixel in the CSP allowlist, an overlapping
agent with no decommission plan) rather than saving them for the appendix.

## 4. Cross-Cutting Attributes and Baggage Propagation

**This section is mandatory on every run and is the one most often omitted. A
guide without it is rejected.** It is what makes every later dashboard variable,
detector grouping, and Related-Content link work, and it is the difference
between a contract and a list of spans.

Full authoring spec, including the code blocks: `cross-cutting-attributes.md` in
this directory. Structure, in order:

1. **Opening paragraph plus the three-step pattern.** A small set of attributes must appear on every span, RUM and backend, and on log records where possible. Then, as bullets: (a) set the attribute once, where the value is first known — RUM boot, login, or an edge request handler; (b) write it into W3C Baggage so it propagates over HTTP via the `baggage` header and over messaging via message attributes; (c) on every service register a custom `SpanProcessor` whose `onStart` hook reads baggage and stamps the value onto each new span. State the reason plainly: this removes per-service get/put code and **cannot be forgotten** by a team that ships later.
2. **`Cross-cutting attribute set`** (H2) — table, columns exactly: `Attribute | Type | Set at | Dimension? | Notes`. Include the identity key, the tenant/market key, the attribution subset, `session.id`, and the semconv mirror (`enduser.id`). The `Dimension?` cell is `Yes`, `No`, or `No (bounded MetricSet — see <section>)`.
3. **`Shared <language> library: @<org>/otel-common`** (H2) — one paragraph: the library owns baggage read/write, the stamp processor, and helpers; every bundle or service depends on it; exactly one artifact calls `init`. Then these H3 subsections, each with a real code block:
   - `Provider bootstrap (<boot artifact> only)` — `init`, `addSpanProcessor`, attribution capture, baggage boot. Tokens as placeholders only.
   - `The SpanProcessor` — the full `onStart` implementation over an explicit allowlist of keys. State that this is the "better via SDK" approach and that `baggage.getEntry(...)` must not be sprinkled across services.
   - `Writing baggage on login` — the identity-success handler promoting the identity key into both global attributes and baggage.
   - `Reading baggage on the <backend language> backend` — composite propagator (trace context + baggage) plus the same processor, with the note that auto-instrumentation already extracts the header before the handler runs, so no middleware is needed.
   - `Messaging boundary — <bus>` — producer inject and consumer extract, once per bus in the architecture section. Baggage does **not** cross a bus by itself.

If a piece genuinely does not exist in the target (no bus, no IdP), keep the H3
and write **Not in evidence — do not deploy** with the pattern shown anyway, so
the team has it the day the bus lands.

## 5. RUM Ad Attribution Capture

Only when a browser exists. Subsections: `Trigger logic (runs once per session)`,
`Span event: <org>.session.ad_attribution` (attribute table with a `Dimension?`
column), `Source classification` (the pure classifier function, stated as
unit-testable in isolation), `Multi-touch handling` (first touch in
`localStorage`, last touch in `sessionStorage`, both emitted on the event), and
`Baggage subset (what propagates to the backend)` — the bounded low-cardinality
subset only, with the reason: header size. Campaign IDs, keywords, and click IDs
are attribute-only and travel on the order record, not in baggage.

If no campaigns are in evidence, still ship the section; the classifier returns
`direct` / `organic` / `unknown` so a later campaign cannot land unattributed.

## 6. OTel Collector Configuration

Real YAML. Two responsibilities minimum: **deriving** the low-cardinality
tenant/market/route class with the transform processor (OTTL) so no service has
to set it, and **redaction** before export (hash email, truncate client IP to
/24 or /48, delete raw cookie and authorization headers, drop URLs carrying query
strings).

State processor **placement** explicitly: the transform processor runs before the
spanmetrics connector, or the derived attribute will not exist as a dimension on
the derived RED metrics, and before `batch` so every exporter sees it. Include the
consumer-inheritance statement: non-URL spans (bus consumers) receive the derived
attribute via baggage from the upstream URL-bearing span. Bucket unknowns to a
sentinel value so a detector can find them.

For regulated markets, gate the browser SDK on the consent platform's decision
and say why: the browser should not have sent the data, so server-side filtering
is not sufficient.

## 7. Metrics Pipeline Management (Index-as-Dimension)

Two bulleted lists under H2 headings: `Dimension-eligible list (add to MPM)` and
`Attribute-only (never a dimension by default)`. Open with the cardinality budget
sentence and the escape hatch: a high-cardinality key becomes queryable through a
dedicated, bounded MetricSet for one troubleshooting dashboard, never as a global
dimension.

## 8. Business Transactions and Workflows (Recommendations)

Open by separating the two concepts in one short paragraph: a **Business
Transaction** (`<org>.bt`) is the page, bundle, or surface the user is in; a
**Workflow** (`workflow.name`) is a discrete user intent that runs inside a BT. A
BT hosts many workflows; a workflow can span BTs and backend hops. Then state
that this section is the master registry and that all instrumentation code, APM
Workflows entries, and dashboard variables draw names from it. Kebab-case
throughout.

Then **one `BT: <name>` heading per BT**, each with the owning artifact and any
feature flag on one line, then `Workflows:` and an exhaustive dotted-kebab bullet
list. Platform-only artifacts (the boot bundle) get a heading that states they own
`init` and emit **no** workflow spans.

This is not a restatement of the architecture section's index table.

## 9. Messaging Observability

Subsections: `Topic naming convention` (the pattern, then real examples),
`Producer/consumer span attributes` (table: `Attribute | Example | Notes`, aligned
to `messaging.*` semconv with `<org>.*` extensions, and marking the full
destination name as high-cardinality/not-a-dimension while the destination
**template** is the bounded dimension), and `Cross-account trace propagation` —
which boundary is crossed, that context does not travel automatically, and what
breaks without it.

## 10. Use Case: `<flow>`

One H1 per ranked flow. Fixed sub-shape, every time:

- Opening paragraph: why this flow, and any constraint that changes the design.
- `Workflow identity` — `workflow.name`, owning service per account/hop, sub-operations.
- `Span events on the <x> span` — table: `Span event | Attributes`, marking attribute-only keys inline as `(attr)`.
- `Attributes` — table with a `Dimension?` column, where the flow adds keys beyond the cross-cutting set.
- `Metrics` — bullets, each `<org>.<name>` with instrument type and its dimension list.
- `Dashboard: <name>` — variables, KPI row, timeline, pies/funnels, the Log Observer Connect panel that replaces the raw-event table, and the release-event overlay.
- `Detectors` — bullets, each with a trigger condition and a group-by.
- Close with the cross-workflow join: what propagates into the next flow's span, and which Related-Content link exists.

## 11. Release Events via the O11y Events API

Why: every RED chart carries a release overlay so a regression is attributable to
a deploy. Subsections: `CD job POST` (the real `curl` with `service.name` and
`service.version` as the essential dimensions and tokens as env vars),
`Chart overlay wiring` (the `eventQuery` JSON keyed off the dashboard variable),
and `CD pipeline placement` (fire after the deploy is healthy, one event per
service per environment, include the commit SHA, and use a separate browser-agent
release event so agent releases overlay distinctly from backend deploys).

## 12. Log Observer Connect

Name the platform indexes. State that every dashboard's raw-event table becomes an
LOC panel joined to traces by `trace_id`. Subsections:
`OTel Collector logs pipeline requirements` (resource attributes on every record,
`trace_id`/`span_id` injection, pod-level keys, the derived tenant key, and the
redaction rule) and `LOC dashboard panel shape` (a real SPL search bound to the
dashboard variables, with a `trace_id` column rendered as a deep link).

## 13. Dashboards Overview

Three layers, in this order: `Workflows Overview` (one row per `workflow.name`
with rate, error %, p90/p95 latency, last deploy; filter bar; click-through),
`Per-flow dashboards` (named, one per use case), `Troubleshooting dashboards`
(the parent/child deep-dive pairs). Then `Example SignalFlow snippets` with at
least two real snippets, and the percentile stated explicitly rather than left to
the chart UI default.

## 14. Detectors Catalog

One consolidated table: `Detector | Trigger | Group by`. Every detector from every
use case appears here. State the routing and runbook convention once.

Mark which detectors may be **armed immediately** (telemetry-integrity and
configuration-safety detectors) versus which stay **drafts until the signal is
trusted**, and why — a detector built on an untrustworthy attribute trains people
to ignore alerts.

## 15. Appendix A: Master Attribute Dictionary

Alphabetical. Columns: `Attribute | Type | Dim? | Source`. `Dim?` is
dimension-eligibility in Metrics Pipeline Management. Every attribute named
anywhere in the document appears exactly once. This appendix and
`attribute-schema.json` are generated from each other; they may not disagree.

## 16. Appendix B: Open Items and Assumptions

Bullets, each an answerable question with the decision it blocks. Unidentified
bundles, unconfirmed cardinality, gaps flagged in the architecture section, the
decommission timeline for overlapping agents, and the consent-gated tracker list.

---

## Pre-delivery checklist

Every row must be `yes` before the guide ships. Emit it filled in at the end of
Appendix B.

- [ ] Both artifacts exist: markdown and a `.docx` rendered from that markdown
- [ ] Table of Contents present in the `.docx`, field-driven, auto-updating
- [ ] Every H1 starts on a new page in the `.docx`
- [ ] `<Frontend> and Backend Architecture (Observed)` is a body section near the front, not an appendix
- [ ] `Cross-Cutting Attributes and Baggage Propagation` present, with the attribute-set table and all five code subsections
- [ ] Stamp processor shown as `SpanProcessor.onStart` over an explicit key allowlist
- [ ] Identity-success baggage write shown
- [ ] Backend composite propagator (trace context + baggage) shown
- [ ] Producer inject / consumer extract shown once per bus in the architecture section
- [ ] Attribution section present if a browser exists, with the classifier function and a bounded baggage subset
- [ ] Collector OTTL derive + redaction, with processor placement stated
- [ ] MPM dimension-eligible and attribute-only lists
- [ ] One `BT:` heading per business transaction, with exhaustive workflow lists
- [ ] Every use case has span events, metrics, dashboard, detectors, and a labelled join
- [ ] Release-event overlay wiring
- [ ] Log Observer Connect panel shape with `trace_id` join
- [ ] Detectors Catalog consolidating every detector
- [ ] Appendix A dictionary agrees with `attribute-schema.json`
- [ ] Appendix B open items are answerable questions
- [ ] No ingest token, secret, or credential value anywhere — placeholders only
