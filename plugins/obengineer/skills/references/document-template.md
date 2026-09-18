# Customer instrumentation document — canonical template

This file **is** the template. It is self-contained on purpose: no external PDF,
Word file, or prior customer deliverable is needed to reproduce the format. Any
run that produces an instrumentation guide must emit these sections, in this
order, with these sub-structures and table columns.

`<org>` is the customer's attribute prefix, taken from evidence (an npm scope, a
package namespace, a resource-tag prefix) or proposed once and used everywhere.
`<app>` is the application identifier from evidence, kebab-case.

---

## One customer document, two renderings

There is **one** customer-facing deliverable, and it carries both the analysis and the
recommendations. A separate "instrumentation recommendations" document does not exist:
splitting them produced two documents that disagreed, and asked the customer to read the
findings in one file and their consequences in another.

| Artifact | Path | Audience | Built by |
|---|---|---|---|
| Markdown | `docs/observability/analysis-<app>-<date>.md` | the source of record; engineers and reviewers | authored directly |
| Word | `docs/observability/<Customer>-<App>-Analysis-<date>.docx` | customer architecture review | `customer-doc-render` skill, from the markdown |

The `.docx` is never hand-maintained. It is rendered from the markdown so the two can never
disagree. Delivered as markdown only it is incomplete; a `.docx` that was not rendered from
the committed markdown is not reviewable.

Also emitted: `docs/observability/attribute-schema.json`, the machine form of the attribute
dictionary appendix.

**The lower layer is a wiki, not a second document.** Everything an agent needs that a
customer does not read — per-BT notes, per-workflow notes, work orders, run history, tracked
versions — goes into the structured wiki described in
[`agent-wiki.md`](agent-wiki.md), one note per subject, addressable and diffable. A
document is the wrong shape for agent context: it is read whole or not at all.

---

## Page 1 — a simple title page

Declare it in a `title-page` block at the top of the markdown. The renderer puts
these lines, and only these lines, on page 1:

```markdown
# Application Analysis — <App> (`<host>`) — <date> — v<N>

<!-- title-page
subtitle: Observed architecture, findings, and instrumentation recommendations
tagline: Splunk Observability Cloud • OpenTelemetry • RUM   (only products in scope)
author: <name>, <role>
audience: <customer engineering org>
date: <yyyy-mm-dd>
version: v<N>
header: Application Analysis
-->
```

No executive summary, no diagnosis, and **no metadata dump**. The application
identifier, environment scanned, realm, percentile standard, org prefix, in-scope
languages and buses, evidence basis, and token-handling note are content, not
title-page furniture. They go in the body as
**`### Document control and evidence basis`**, the last subsection of Purpose and
Scope, as a `Field | Value` table plus the notes. The renderer rejects anything
else above the first section heading, so this is enforced rather than advised.

First page header: the banner plus the document class, `Application Analysis`.
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

**This table is the only section list in the bundle.** The agent files, the skills, and
the prompts point here rather than restating it. A second copy drifts, and then two
documents both claim to be the authority on what a deliverable contains.

The document has three movements: **what is there and what is wrong with it** (1–5),
**what to build** (6–18), **the catalogue the build works from** (19–25), then appendices.

| # | Heading | Level |
|---|---|---|
| 1 | Purpose and Scope | H1 |
| 2 | References | H1 |
| 3 | **\<Frontend\> and Backend Architecture (Observed)** | H1 |
| 4 | **Critical Findings** | H1 |
| 5 | Course of action | H1 |
| 6 | Missing portfolio components | H1 |
| 7 | **Cross-Cutting Attributes and Baggage Propagation** | H1 |
| 8 | RUM SPA / client route changes | H1 |
| 9 | RUM Ad Attribution Capture | H1 |
| 10 | OTel Collector Configuration | H1 |
| 11 | Metrics Pipeline Management (Index-as-Dimension) | H1 |
| 12 | Messaging Observability | H1 |
| 13 | Release Events via the O11y Events API | H1 |
| 14 | Log Observer Connect | H1 |
| 15 | Splunk portfolio mapping | H1 |
| 16 | Dashboards Overview | H1 |
| 17 | Phased plan and exit criteria (portfolio-verifiable) | H1 |
| 18 | Bootstrap vs non-goals | H1 |
| 19 | **Business Transactions** | H1 |
| 20 | **Workflows** | H1 |
| 21 | **Custom Metrics** | H1 |
| 22 | **BT-Aligned Workflows** | H1 |
| 23 | **Detectors and Thresholds** | H1 |
| 24 | **Service Level Indicators and Objectives** | H1 |
| 25 | **Composite Use Cases** | H1 |
| 25n | Use Case: \<flow\> — one H1 per ranked flow, immediately after 25 | H1 |
| 26 | Appendix A: Master Attribute Dictionary | H1 |
| 27 | Appendix B: Supplementary Code and Configuration | H1 |
| 28 | Appendix C: Instrumentation Agent Work Order | H1 |
| 29 | Appendix D: Supplementary Evidence | H1 |
| 30 | Appendix E: Open Items and Assumptions | H1 |

Rules that are easy to get wrong:

- **Nothing in the body belongs under an appendix heading.** An earlier revision nested the whole analysis under "Appendix A — Target breakdown", which put the substance of the document behind a heading that reads as optional. Body sections are body sections. Appendices are topic-scoped breakout detail — the dictionary, long code, the agent work order, supplementary evidence, open items — and exist to keep the main document short enough to read.
- **Architecture (Observed) is section 3 — a named body section near the front.** It is what the customer reviews first in an architecture review. Do not retitle it as an appendix and do not move it behind Purpose.
- **Critical Findings is section 4, immediately after the architecture it was found in, and nothing displaces it.** Not the course of action, not the portfolio gaps, not an executive summary. A finding that a credential is reachable from the browser is worth more to the reader than everything after it, and burying it at page 180 has happened and must not happen again. Full spec in [`critical-findings.md`](critical-findings.md).
- **Sections 19–25 are the catalogue and are contiguous, in that order, ending the body.** They are what the implementer and the Terraform run read: the BT list, the workflow list, the meters, the BT-to-workflow mapping, every detector with its threshold, every SLI with its objective, then the use cases that compose them. Order matters because each one is defined in terms of the one before it.
- **Every H1 starts on a new page in the Word artifact**, including each `Use Case:` and each appendix. `BT:` and per-workflow entries are H2 inside their section and do not force a page each; forty-six page breaks for forty-six one-line entries makes a document nobody carries.
- If a section has no evidence, keep the heading and write **Not in evidence**, plus one line on what evidence would settle it. Never delete a heading.
- On a **repeat run** against a target with prior history in the wiki, section 3 gains a `### Changes since v<N-1>` subsection and the document is a delta rather than a rewrite. See [`incremental-runs.md`](incremental-runs.md).

---

## 1. Purpose and Scope

One paragraph naming the target and the audience's assumed knowledge, then a
numbered inline list of what the document covers. Close with the language and
collector assumptions ("JavaScript for RUM via the Splunk RUM Browser Agent,
OTel Contrib Collector for the collection tier, backend snippets in
`<language>`"), and the citation rule: Splunk-authored docs first, OpenTelemetry
upstream where no Splunk equivalent exists.

Last subsection is **`### Document control and evidence basis`** — the `Field | Value`
table the title page is not allowed to carry. On a repeat run it also carries the
previous document version, its date, and the tool and schema versions this run was
produced against, from [`version-currency.md`](version-currency.md).

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

Every reference carries the **version** it was read at, because a link that has
silently changed meaning is worse than a missing one.

## 3. `<Frontend>` and Backend Architecture (Observed)

Prose first, then bullets. Every claim carries its evidence.

1. **Composition paragraph.** Runtime model (SPA/MPA/SSR, module federation host vs remotes, mobile, batch), which bundle or process owns `init`, and the routing consequence for RUM stated explicitly — for a client-routed app: a single `init` in the boot bundle governs the whole session and per-page bundles must not re-initialise the provider.
2. **Third-party surfaces bullet list.** Grouped by class, and each class states why it matters to the contract (consent gate, PII processor, span attribution, CSP entry): payments, personalization, KYC/identity, affiliate, consent, engagement, ad pixels, **overlapping RUM/EUM/session-replay tools**, and the analytics event names already wired (so span-event names can mirror them and both stacks agree).
3. **Backend accounts and buses paragraph.** Name each cloud account or subscription and what it hosts, the bus topology between them, the downstream systems each fans out to, and the sentence that the contract turns on: trace context must be propagated across the account boundary via message attributes.
4. **Existing portfolio footprint.** Present, partial, or absent per product, with the measured shape of what is collected today — a decoded beacon payload showing which attributes are actually populated is worth more than a list of installed products.

Call out gaps inline as gaps (a missing pixel in the CSP allowlist, an overlapping
agent with no decommission plan) rather than saving them for the appendix. Security and
exposure gaps get one line here and their full treatment in section 4; do not resolve
them in this section and do not omit the pointer.

On a repeat run, add **`### Changes since v<N-1>`** as the last subsection: surfaces
added or removed, new buses, new third parties, and code that has landed since the last
run and is not instrumented. Full rules in [`incremental-runs.md`](incremental-runs.md).

## 4. Critical Findings

**Section 4, immediately after the architecture, on every run.** Anything a reasonable
engineer would want to act on this week — exposed credentials, PII reachable from the
browser, a consent gate that resolves after data is sent, an unauthenticated endpoint, a
broken trace boundary that makes an SLI unusable — appears here, not in an appendix and
not in a paragraph two hundred pages in.

Ordered by severity, highest first, never by discovery order or by section of origin.
Open with a `Severity | Finding | Exposure | Owner surface` summary table, then one H2 per
finding carrying, in this order and all of them: what was observed with its evidence,
the file or surface involved, what is exposed and to whom, the risk if unaddressed, the
remediation path as concrete steps, and how to verify the fix.

Full spec, including the severity ladder and the credential-handling rule (record the
finding, never the value): [`critical-findings.md`](critical-findings.md).

If the scan found nothing at or above the "act this quarter" bar, keep the heading and
say so explicitly with the classes checked. A missing section reads as a scan that did
not look.

## 5. Course of action

What is reconstructable today versus what has to be emitted. The decision-engine result
per question, from [`portfolio-decision-engine.md`](portfolio-decision-engine.md). Phase 0
yes or no, with the blockers **proven from the scan** rather than assumed. The first
journey, and why. Three bullets on why auto-instrumentation alone will fail on this
target specifically — generic reasons are a sign nobody looked.

This section comes **after** the architecture and the findings, never before them. A
course of action that precedes the evidence reads as a product pitch.

## 6. Missing portfolio components

Present, partial, or absent for each of: RUM, APM, Infrastructure, Synthetics, Splunk
platform with Log Observer Connect, and ThousandEyes.

For every gap, one paragraph: the question this target has that the missing component
answers, and the benefit of adding it. Recommend a component **only** when the evidence
creates such a question — a recommendation with no question behind it is a line item, and
it is the first thing a customer strikes.

Do not silently omit ThousandEyes, platform log correlation, or Synthetics when the
evidence shows an off-box hop, logs with no `trace_id`, or a route with no canary.

## 7. Cross-Cutting Attributes and Baggage Propagation

**This section is mandatory on every run and is the one most often omitted. A
document without it is rejected.** It is what makes every later dashboard variable,
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

Long variants — every bus, every language, the full generated classifier — go to
Appendix B. The five subsections above stay here; they are the contract, not supporting
material.

## 8. RUM SPA / client route changes

Required whenever the scan shows a client-side router. `document-load` and the first-paint
web vitals fire on the **first HTML document only**: React Router, the Next.js App Router,
Remix, Vue Router, Angular Router, and any other `history.pushState` navigation create no
new document span, so without this section every business transaction after the landing
page is invisible in RUM.

Contains: the **host-owned** listener as real code, the bounded `page.type` classifier and
its refresh on navigation, `SplunkRum.setGlobalAttributes`, and a `route.change` (or
`page.view`) span per client navigation. State plainly that remotes and micro-frontends must
not add a second listener or a second `init`.

Raw path is never the dimension. Classify.

MPA with full document loads, or no browser at all: keep the heading and write
**Not in evidence**, with the one line of evidence that would change the answer.

## 9. RUM Ad Attribution Capture

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

## 10. OTel Collector Configuration

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

Name the collector **distribution and version** the YAML was written against. A config
that silently depends on a processor added in a later release is a Phase 0 surprise.

## 11. Metrics Pipeline Management (Index-as-Dimension)

Two bulleted lists under H2 headings: `Dimension-eligible list (add to MPM)` and
`Attribute-only (never a dimension by default)`. Open with the cardinality budget
sentence and the escape hatch: a high-cardinality key becomes queryable through a
dedicated, bounded MetricSet for one troubleshooting dashboard, never as a global
dimension.

Every promotion carries its arithmetic, from
[`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md). A list with no
numbers behind it is a preference.

## 12. Messaging Observability

Subsections: `Topic naming convention` (the pattern, then real examples),
`Producer/consumer span attributes` (table: `Attribute | Example | Notes`, aligned
to `messaging.*` semconv with `<org>.*` extensions, and marking the full
destination name as high-cardinality/not-a-dimension while the destination
**template** is the bounded dimension), and `Cross-account trace propagation` —
which boundary is crossed, that context does not travel automatically, and what
breaks without it.

## 13. Release Events via the O11y Events API

Why: every RED chart carries a release overlay so a regression is attributable to
a deploy. Subsections: `CD job POST` (the real `curl` with `service.name` and
`service.version` as the essential dimensions and tokens as env vars),
`Chart overlay wiring` (the `eventQuery` JSON keyed off the dashboard variable),
and `CD pipeline placement` (fire after the deploy is healthy, one event per
service per environment, include the commit SHA, and use a separate browser-agent
release event so agent releases overlay distinctly from backend deploys).

## 14. Log Observer Connect

Name the platform indexes. State that every dashboard's raw-event table becomes an
LOC panel joined to traces by `trace_id`. Subsections:
`OTel Collector logs pipeline requirements` (resource attributes on every record,
`trace_id`/`span_id` injection, pod-level keys, the derived tenant key, and the
redaction rule) and `LOC dashboard panel shape` (a real SPL search bound to the
dashboard variables, with a `trace_id` column rendered as a deep link).

## 15. Splunk portfolio mapping

The section a TAM configures from, so it is written as instructions rather than as
description. Per product: what to configure and **the UI path to get there**.

Must state, unambiguously:

- Which span tag becomes the **APM Business Workflow**. One tag, named, with its value shape.
- Which tags are promoted to **Monitoring MetricSets**, which stay **Troubleshooting MetricSets**, and which are attribute-only — with the cardinality arithmetic from [`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md), not an assertion.
- Which **Related Content** joins exist, and the key each one travels on.
- Which **ThousandEyes** test type covers each off-box hop.
- Which parts have **no Terraform support** and are therefore tenant configuration: APM MetricSets, APM Business Workflows, RUM application settings, and the Log Observer Connect connection. Everything else is generated as code by [`../observability-as-code/SKILL.md`](../observability-as-code/SKILL.md).

## 16. Dashboards Overview

Three layers, in this order: `Workflows Overview` (one row per `workflow.name`
with rate, error %, p90/p95 latency, last deploy; filter bar; click-through),
`Per-flow dashboards` (named, one per use case), `Troubleshooting dashboards`
(the parent/child deep-dive pairs). Then `Example SignalFlow snippets` with at
least two real snippets, and the percentile stated explicitly rather than left to
the chart UI default.

Name which persona each layer serves, from
[`persona-levels.md`](persona-levels.md), and what each layer deliberately excludes.

## 17. Phased plan and exit criteria (portfolio-verifiable)

Phase 0 first, and **only** if blockers were proven from the scan, then the journeys in
ranked order.

Every exit criterion is a **query a TAM can run**, not a statement someone can assert:
Tag Spotlight shows the tag; the MetricSet cardinality dialog is acceptable; a test trace
crosses every bus with one `trace_id`; a detector could be built on the MetricSet; a
platform search by `trace_id` returns the log; a ThousandEyes test covers the public path
the real users take.

An exit criterion that cannot be checked is a hope with a deadline attached.

Critical findings from section 4 with a severity at or above the agreed bar are **Phase 0
items**, listed here by their finding id. An exposure that is documented but unscheduled
is documented, not addressed.

## 18. Bootstrap vs non-goals

What auto-instrumentation gives — library spans, a service map, host and container metrics
— and what it does not: identity, journeys, business meters, MetricSets, CI enforcement.
Zero-code appears **here and in Phase 0 only**, never as the definition of done.

Then the explicit non-goals for this delivery, so scope is settled in writing rather than in
the review meeting: no application code, no token values, no dashboard JSON unless it was
asked for, no "enable all instrumentations", and no always-on session replay unless the
human accepted the cost and the Core Web Vitals risk in writing.

---

Sections 19 through 25 are the **catalogue**: the enumerable content the implementer agent,
the Terraform run, and the TAM read directly. They are contiguous, in this order, and they
close the body. Each is defined in terms of the one before it, which is why the order is not
a preference.

## 19. Business Transactions

The flat, complete list of business transactions — the pages, bundles, apps, and surfaces a
user can be in — with no workflows in it. One table: `BT (<org>.bt) | Surface | Owning
artifact | Feature flag | Evidence`. Kebab-case throughout.

Open with one short paragraph separating the two concepts, because every reader confuses
them once: a **Business Transaction** (`<org>.bt`) is *where the user is*; a **Workflow**
(`workflow.name`) is *what they are trying to do*. A BT hosts many workflows; a workflow can
span BTs and backend hops.

Platform-only artifacts — the boot bundle, a config loader — appear in the table with their
owning artifact and an explicit note that they emit **no** workflow spans and exist here so
nobody instruments them by accident.

Completeness is the point of this section. A BT list that stops at the routes someone
remembered is the reason half an application ends up uninstrumented.

## 20. Workflows

The flat, complete list of workflows, independent of which BT hosts them, so the reader can
see the naming scheme as a whole and catch the duplicates that a per-BT view hides. One
table: `workflow.name | Intent | Entry surface | Crosses accounts? | Bus hops |
APM Business Workflow?`.

Dotted-kebab, `{surface}.{object}.{verb}`, derived from UI copy, analytics event names,
feature flags, and route registries — not from three generic verbs per BT. `view`, `click`,
and `start` as a complete workflow list means nobody read the application.

State the naming rule once, here, and state that every later section draws its
`workflow.name` strings from this table rather than restating them.

**At scale** — beyond roughly a hundred workflows — a full table here would be section 22
transcribed, which is a fact with two homes. In that case this section carries the naming rule,
the bounded verb vocabulary, a coverage table of counts per BT with the evidence each count came
from, and the full row treatment for every workflow whose columns carry information: those that
cross an account, traverse a bus, or are candidates for the APM Business Workflow. Say
explicitly that the exhaustive enumeration is section 22 and why it is not repeated. The
coverage counts are the part that cannot be dropped — they are what makes an under-analysed BT
visible.

## 21. Custom Metrics

Two tables, and the split matters: **business meters** answer "did the outcome happen" and
are what an executive view is built from; **developer and execution meters** answer "why was
it slow or wrong" and belong to the engineer view.

Every meter: name (`<org>.<name>`), instrument type, unit, and three to six **bounded**
dimensions, each of which must appear in the section 11 dimension-eligible list — a meter
dimensioned on an attribute-only key is a meter that cannot be charted. An identity key is
marked attribute-only, never a meter dimension.

Only meters justified by evidence, each with the question it answers named. A meter nobody
named a question for will never be read, and it costs metric time series forever.

## 22. BT-Aligned Workflows

The mapping: **one H2 per BT**, in the same order as section 19, each with the owning
artifact and any feature flag on one line, then `Workflows:` and the exhaustive
dotted-kebab list drawn from section 20.

This is the section the implementer works down and the section a reviewer uses to find the
BT nobody wrote workflows for. It is not a restatement of section 19 or 20: sections 19 and
20 are the two vocabularies, and this is the join between them. A BT with an empty workflow
list is a finding, not a formatting problem — say which evidence would fill it.

## 23. Detectors and Thresholds

One consolidated table, every detector in the document, with the threshold made explicit:
`Detector | Signal | Condition | Threshold | Window | Severity | Group by | Arm now? |
Runbook`.

**Beyond roughly fifty detectors**, `Signal` and `Runbook` may be stated once as conventions
instead of per row — the signal is implied by the condition, and the runbook path follows a
rule such as `runbooks/<workflow-name>`. `Threshold`, `Window`, `Severity`, `Group by`, and
`Arm now?` stay per row, because those five differ per detector and are the five a responder
needs at 03:00. Severity may be derived by a rule as long as the rule is written down above
the table, so a reader can check a row rather than trust it.

The threshold column is what distinguishes this from a wish list. Every row is one of:

- **A measured baseline**, with the observation window it came from.
- **A customer-agreed target**, traced to the SLO in section 24.
- **A placeholder**, marked as such in the row, with the baseline query that will replace it.

There is no fourth category. A number invented in a text editor and presented as tuned is
the fastest way to lose an on-call team, and it is indistinguishable from a real threshold
once the document ships — so it gets labelled at birth.

Mark which detectors may be **armed immediately** (telemetry-integrity and
configuration-safety detectors, which do not depend on the new signal being trustworthy)
versus which stay **drafts until the signal is trusted**. State the routing and runbook
convention once. Every critical workflow has a **silent-outage** detector — absence of
expected traffic — because threshold-on-error-rate alerting structurally cannot see it.

## 24. Service Level Indicators and Objectives

Written from the **voice of the customer**: each SLI states what a user experiences, not
what a server reports. "Checkout completes within 4 seconds for 99% of attempts" is an
objective; "p99 latency of `POST /orders` under 4s" is its implementation, and the document
needs both, in that order, or the executive view and the engineer view drift apart.

One table: `SLI | User-facing statement | Good events | Total events | Objective | Window |
Workflow | Owner`. Then, per SLI that earns one, an H2 with the error budget, the burn-rate
alerting the budget implies, and the dashboard it appears on.

Rules that keep this section honest:

- **Every SLI names the workflow from section 20 it measures.** An SLI with no workflow behind it cannot be computed.
- **Good and total events are defined as queries**, so two engineers get the same number. "Successful checkouts" is a conversation; a `spans` filter with an explicit error definition is an SLI.
- **Availability and latency are separate SLIs.** A request that fails fast is not fast.
- **Objectives come from the customer, not from the analysis.** Where no target has been agreed, write `proposed` and say what the measured baseline is, so the conversation starts from evidence.
- Map each objective to a `signalfx_slo` `target` shape — `RollingWindow` or `CalendarWindow`, compliance period, `BREACH` plus burn-rate rules — so section 24 is directly implementable by [`../observability-as-code/SKILL.md`](../observability-as-code/SKILL.md).

An SLO with no error budget and no burn-rate alert is a number on a slide.

## 25. Composite Use Cases

One short opening section explaining what a composite use case is and how to read the ones
that follow: a use case composes a workflow from section 20, its BT from section 19, the
meters from section 21, the detectors from section 23, and the objective from section 24
into the thing an engineer actually builds. Then a ranking table — `Use case | Workflow |
Rank | Why ranked here` — so the reading order is deliberate.

Then **one H1 per ranked flow**, titled `Use Case: <flow>`, immediately following, each on
its own page with this fixed sub-shape, every time, in this order:

- **`Narrative`** — three to six sentences in plain language: who the user is, what they are trying to do, what they experience when it goes wrong, and what the business loses. No attribute names, no span names. This is the part a non-engineer reads and the part that survives a reorganisation, and it is written first because a use case whose narrative cannot be written does not exist.
- **`Workflow identity`** — `workflow.name`, the owning service per account and hop, and the sub-operations.
- **`Attributes`** — table with a `Dimension?` column, covering the keys this flow adds beyond the cross-cutting set.
- **`Span events on the <x> span`** — table: `Span event | Attributes`, marking attribute-only keys inline as `(attr)`.
- **`Metrics`** — bullets, each `<org>.<name>` with instrument type and its dimension list, drawn from section 21.
- **`SLI and objective`** — the row from section 24 that governs this flow, with its error budget.
- **`Dashboard: <name>`** — variables, KPI row, timeline, pies/funnels, the Log Observer Connect panel that replaces the raw-event table, and the release-event overlay.
- **`Detectors`** — the rows from section 23 that belong to this flow, each with trigger and group-by.
- **`Join to the next flow`** — what propagates into the next flow's span, which Related-Content link exists, and the join labelled **continue trace** \| **span link** \| **attribute pivot**.

## 26. Appendix A: Master Attribute Dictionary

Alphabetical. Columns: `Attribute | Type | Dim? | Source`. `Dim?` is
dimension-eligibility in Metrics Pipeline Management. Every attribute named
anywhere in the document appears exactly once. This appendix and
`attribute-schema.json` are generated from each other; they may not disagree.

## 27. Appendix B: Supplementary Code and Configuration

The long code that would break the reading flow of the body: the full collector YAML
including every pipeline, the generated route classifier in full, per-bus inject and
extract variants beyond the first, per-language ports of the stamp processor, and the SPL
behind each Log Observer Connect panel.

What does **not** move here: the five mandatory subsections of section 7. They are the
contract and they stay in the body. This appendix holds variants and volume, not the
canonical form — if a reviewer has to turn to an appendix to find out how baggage is
stamped, the document has failed.

Each block names the file it belongs in and the artifact that owns it.

## 28. Appendix C: Instrumentation Agent Work Order

What the implementer agent will do, in the order it will do it, so a human can approve the
plan before any code is written and can review the resulting pull requests against
something.

One H2 per slice, each with: the contract sections it implements, the files and packages it
will touch, the new dependencies, the CI checks it adds, the acceptance evidence, and the
estimated review surface as a rough diff size. Slices are ordered so each one is
independently reviewable and independently revertible.

Close with what the agent will **not** do without a human decision: change a public API,
add a runtime dependency to a shared bundle, touch a payment or identity path, or widen a
CSP allowlist.

This appendix is the customer-readable face of the agent wiki work orders described in
[`agent-wiki.md`](agent-wiki.md); the wiki holds the executable detail and this holds the
plan.

## 29. Appendix D: Supplementary Evidence

The measured material that supports a claim in the body but would bury it: the full route
and chunk inventory, the load-order timing table, the decoded beacon payload, the CSP
allowlist as found, the third-party host list with what each one does, and the raw diagram
inventory with what each diagram settled.

Every entry is referenced from a body section. Evidence nothing points at is not evidence,
it is an attachment.

## 30. Appendix E: Open Items and Assumptions

Bullets, each an answerable question with the decision it blocks. Unidentified
bundles, unconfirmed cardinality, gaps flagged in the architecture section, the
decommission timeline for overlapping agents, and the consent-gated tracker list.

Then the assumptions the document rests on, each with what would falsify it, and the
filled-in pre-delivery checklist.

---

## Completeness bar — fail the deliverable if any row is true

A document titled as an application analysis, instrumentation, RUM, APM, or
backend-observability deliverable **fails review** when any of these hold. This table is the
review, so read it before writing rather than after.

| Defect | What "good" looks like |
|---|---|
| **No `Cross-Cutting Attributes and Baggage Propagation` section** | Section 7 exists with the attribute-set table (`Attribute \| Type \| Set at \| Dimension? \| Notes`) and all five code subsections: provider bootstrap, the `SpanProcessor`, login write, backend composite propagator, bus inject/extract |
| **A critical finding anywhere except section 4** | Section 4 follows the architecture section, ordered by severity, each finding carrying evidence, files, exposure, risk, remediation, and verification. See [`critical-findings.md`](critical-findings.md) |
| **A finding with no remediation path** | Every finding names concrete steps, the surface or file that changes, and how to verify the fix. A finding is not a complaint |
| **Body content under an appendix heading** | Appendices hold the dictionary, long code, the agent work order, supplementary evidence, and open items — nothing the argument depends on |
| Stamp processor loops over all baggage entries | `onStart` iterates an **explicit key allowlist**, so a future caller cannot leak an unbounded value or a token into telemetry |
| A baggage key with no named consumer | Every key names the dashboard variable, detector `group by`, or pivot that reads it. See [`baggage-budget.md`](baggage-budget.md) |
| Markdown shipped without a customer `.docx` | Both renderings, the `.docx` rendered from the committed Markdown, `verify_render.py` exiting 0 |
| A second customer-facing document | One customer document. The lower layer is the wiki in [`agent-wiki.md`](agent-wiki.md), not a parallel guide that will disagree with it |
| Metadata dumped on the title page | A simple title page from the `<!-- title-page ... -->` block; identifiers, realm, percentile standard, and evidence basis in `### Document control and evidence basis` |
| Sections render as Word `Heading 2`, or flow onto the previous page | Markdown `##` renders as `Heading 1` with `w:pageBreakBefore`; the contents list shows sections at level 1 |
| Architecture buried in an appendix | Section 3 is a body section near the front; the attribute dictionary is Appendix A at the back |
| No `References` section | Real, resolvable Splunk-primary and OTel-secondary URLs for every recommendation class, each with the version read |
| Course of action placed before the architecture or the findings | Evidence first, then what is wrong, then what to do. A course of action that precedes them reads as a product pitch |
| Bus in evidence but no `Messaging Observability` section | Topic convention, producer/consumer attribute table with the destination **template** as the dimension, and cross-account propagation |
| Dashboards with no release overlay or Log Observer Connect panel | Sections 13 and 14 present, and every use-case dashboard names both |
| **Catalogue sections out of order or interleaved** | 19 Business Transactions, 20 Workflows, 21 Custom Metrics, 22 BT-Aligned Workflows, 23 Detectors and Thresholds, 24 SLIs and SLOs, 25 Composite Use Cases — contiguous, in that order, closing the body |
| **A flat BT list with no separate workflow list, or the reverse** | Sections 19 and 20 are the two vocabularies; section 22 is the join. All three exist |
| BT registry is only a summary table | Section 22 has one H2 per BT with **exhaustive** dotted-kebab workflows |
| Workflows are three generic verbs per BT (`view`, `click`, `start`) | Workflows match UI copy, analytics events, and feature flags (`*.item.add`, `*.promo.apply`, `*.payment.tokenize`, …) |
| **A detector with no threshold** | Section 23 gives every detector a threshold that is a measured baseline, a customer-agreed target traced to an SLO, or a labelled placeholder with the query that will replace it |
| **No SLI/SLO section, or SLOs written as server metrics** | Section 24 states each SLI as what a user experiences first and its query second, with good/total events, objective, window, error budget, and burn-rate alerting |
| **A use case with no narrative** | Every `Use Case:` opens with `Narrative` in plain language — no attribute or span names — then workflow identity, attributes, span events, metrics, SLI, dashboard, detectors, join |
| No monitoring use cases | Ranked flows each have identity, span events, metrics, **dashboard**, and **detectors** |
| "Analysis only" used to omit the contract | Inventory still leads; the catalogue and use cases still ship in the same file. A repeat run deepens and deltas — it does not introduce BTs or use cases for the first time |
| Meters without dimensions | Every meter lists three to six bounded dimensions, each in the section 11 dimension-eligible list; identity keys marked attribute-only |
| A dimension list with no cardinality arithmetic | MTS cost per promotion, against the entitlement headroom. See [`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md) |
| "Use baggage" with no code | Host `init`, `SpanProcessor.onStart`, identity write, backend propagator, bus inject/extract — or `Not in evidence` under each heading |
| No ad/first-touch section on a browser application | Classifier function, `session.ad_attribution`, bounded baggage subset; `direct` when no campaigns were seen |
| A client router in evidence, only `document-load` in the document | Section 8: host listener, classifier, `setGlobalAttributes`, and a `route.change` span on **every** client navigation |
| Joins described as "via traceparent and an id" with no join type | Every use-case join labelled **continue trace** \| **span link** \| **attribute pivot** |
| The APM Business Workflow tag is described but never named | Section 15 names one tag and its value shape. A TAM cannot configure a description |
| **No recorded versions for the tools the recommendations depend on** | Document control names the collector distribution, SDK, semconv, and provider versions this run was written against. See [`version-currency.md`](version-currency.md) |
| **A repeat run that reproduces the previous document** | With prior history in the wiki, section 3 carries `Changes since v<N-1>` and the document is a delta. See [`incremental-runs.md`](incremental-runs.md) |
| Cookie dump into RUM attributes | Forbidden. Bounded allowlist only |
| Checklist skipped | Every row below marked yes or no in Appendix E |

If the human names a **prior document as the quality bar**, match that document's section shape
and reuse its BT and `workflow.name` strings where they are in evidence. Extend from the new
scan; do not rename for taste.

## Pre-delivery checklist

Every row must be `yes` before the document ships. Emit it filled in at the end of
Appendix E.

- [ ] Both renderings exist: markdown and a `.docx` rendered from that markdown
- [ ] No second customer-facing document was produced; lower-layer detail went to the wiki
- [ ] Table of Contents present in the `.docx`, field-driven, auto-updating
- [ ] Every H1 starts on a new page in the `.docx`, including each `Use Case:` and appendix
- [ ] `<Frontend> and Backend Architecture (Observed)` is section 3, a body section, not an appendix
- [ ] `Critical Findings` is section 4, severity-ordered, with remediation, files, exposure, risk, and verification per finding
- [ ] Findings at or above the agreed severity bar appear as Phase 0 items in section 17
- [ ] Course of action and Missing portfolio components follow the architecture and findings
- [ ] `Cross-Cutting Attributes and Baggage Propagation` present, with the attribute-set table and all five code subsections
- [ ] Stamp processor shown as `SpanProcessor.onStart` over an explicit key allowlist
- [ ] Identity-success baggage write shown
- [ ] Backend composite propagator (trace context + baggage) shown
- [ ] Producer inject / consumer extract shown once per bus in the architecture section
- [ ] `RUM SPA / client route changes` present if a client router exists (or `Not in evidence`)
- [ ] Attribution section present if a browser exists, with the classifier function and a bounded baggage subset
- [ ] Collector OTTL derive + redaction, with processor placement and the distribution version stated
- [ ] MPM dimension-eligible and attribute-only lists, each promotion with its arithmetic
- [ ] `Splunk portfolio mapping` names the one span tag that becomes the APM Business Workflow
- [ ] Release-event overlay wiring
- [ ] Log Observer Connect panel shape with `trace_id` join
- [ ] Catalogue sections 19–25 present, contiguous, and in order
- [ ] Section 19 lists every BT; section 20 lists every workflow; section 22 joins them with no empty list unexplained
- [ ] Every meter in section 21 has an instrument type, a unit, and bounded dimensions that exist in section 11
- [ ] Every detector in section 23 has a threshold that is measured, agreed, or labelled a placeholder
- [ ] Every SLI in section 24 has a user-facing statement, good/total event queries, an objective, a window, and an error budget
- [ ] Every use case opens with `Narrative` and has span events, metrics, SLI, dashboard, detectors, and a labelled join
- [ ] Phase plan exit criteria are each a query a TAM can run
- [ ] Bootstrap appears only in non-goals and Phase 0, never as the definition of done
- [ ] Appendix A dictionary agrees with `attribute-schema.json`
- [ ] Appendix C work order lists slices, files, CI checks, and acceptance evidence
- [ ] Appendix E open items are answerable questions
- [ ] Tool, SDK, semconv, and provider versions recorded; breaking changes since the last run called out
- [ ] No ingest token, secret, or credential value anywhere — placeholders only
