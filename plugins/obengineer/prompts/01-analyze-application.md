# Prompt 01 — Analyze the application

**Agent:** [`../agents/instrumentation-architect.agent.md`](../agents/instrumentation-architect.agent.md)  
**Skills:** `engagement-intake`, `instrumentation-analyze`, `baggage-propagation`, `cardinality-budget`, `customer-doc-render`, `deliverable-review`  
**Inputs:** `docs/observability/engagement-inputs.yaml`  
**Human:** TAM + customer architect. Docs-only analysis PR. No application code changes.

**Invoke it, do not paste it.** `/ob-analyze` reads this file in place, so
there is one copy of the run contract and it is the copy under review. If your host
has no commands installed, run [`../install.sh`](../install.sh) or tell the agent to
read this file.

---

## System reminder

Follow `instrumentation-architect.agent.md`. You are analyzing and will open the
docs-only analysis PR defined by `analysis-run-lifecycle.md`, never an application-code
PR. Auto-instrumentation is a bootstrap, never a complete design. **"Analysis" does not mean inventory-only** — this document carries the full contract: the business-transaction and workflow catalogue, custom metrics, detectors with thresholds, SLIs and SLOs, composite use cases, and the enablement code with token placeholders.

**This is the only customer-facing document.** There is no separate instrumentation-recommendations deliverable; the lower-layer, per-note detail the coding agents work from is built by Prompt 02 as a wiki, not as a second document.

Choose the course of action from **how Splunk Observability Cloud, Splunk Enterprise, and Cisco ThousandEyes work** (RUM, APM, Infrastructure, Log Observer Connect, Synthetics, MetricSets, APM Business Transactions, Related Content, Events API, MPM, Enterprise indexes/`trace_id`, ThousandEyes path tests) plus the evidence in this session. Do not assume an industry, a storefront, named journeys, a cloud, or a prior customer document. The design runs against any site this engagement names. A scan, diagram, or taxonomy from a different site is not evidence. Previous scans of this site are inputs; compare them with the current production scan by the procedure in `incremental-runs`. The live production site scan is required unless the inputs record `no browser` with a reason. Test and QA environments are not the scan. Discover journeys from this site's diagrams and production scan. When a cloud inventory MCP is already connected, generate the production diagram by the procedure in `instrumentation-analyze`. Assign each question to one platform: journeys/code → Observability Cloud; durable logs/audit → Enterprise; internet/CDN/SaaS path → ThousandEyes.

Do not search the workspace for unrelated documents. If an existing schema or wiki is present for this customer and application, extend that taxonomy.

**The Word artifact opens the way a review expects:** a simple title page, then the Table of Contents on its own page, then one section per page. Declare the title page in a `<!-- title-page ... -->` block (subtitle, tagline, author, audience, date, version, header) and put nothing else above the first `##`. Application identifier, environment scanned, realm, percentile standard, in-scope languages and buses, evidence basis, recorded tool versions, and token handling go in **`### Document control and evidence basis`** at the end of Purpose and Scope. Markdown `##` renders as Word `Heading 1` and starts a new page; `###` becomes `Heading 2`. The renderer rejects prose above the first section heading and refuses to save a document whose sections would not break, so run `verify_render.py` and expect exit 0. **Cross-references are clickable:** write `Appendix E`, `section 4`, and `sections 5 and 6` plainly and the renderer links them; write a reference that names a section as an anchor link on its slug — `[Business Transactions](#business-transactions)` — and leave the same words plain where they mean the Splunk feature rather than the heading. A reference that resolves to nothing fails the render. Layout spec: `skills/customer-doc-render/references/document-format.md`.

## Inputs

Everything the human supplies lives in **one file**, not in this prompt:
`docs/observability/engagement-inputs.yaml`, from
[`../inputs/engagement-inputs.template.yaml`](../inputs/engagement-inputs.template.yaml).

Load it first. If it is absent or incomplete, run `$engagement-intake` and ask for the
gaps in **one** message. Do not re-ask for anything the file already answers, and do
not ask for anything this scan can measure — composition, router, load order, competing
agents, CSP, and consent gating are all evidence, and asking about them converts
evidence into opinion.

The fields this run depends on:

| Field | Used for |
|---|---|
| `engagement.application`, `.customer`, `.scope`, `.date` | Filenames, headings, and the wiki path |
| `artifacts.diagrams`, `.narrative` | The diagram-driven backend map |
| `artifacts.prior_contract`, `.prior_schema` | An existing taxonomy to **extend**, never rename for taste |
| `surfaces.*` | Whether there is a front-end deep scan, and whether authenticated journeys are reachable |
| `security_assessment.*` | Passive, safe-active, or opted-out security screening and its authorized boundary |
| `backends.languages`, `.buses`, `.cloud_accounts`, `.gateway` | Which SDK and bus subsections must exist |
| `tenancy.o11y_realm`, `.environments` | Whether exit criteria can be phrased as queries |
| `entitlement.*` | **Pricing, not a ceiling.** What the recommendation will consume, written up for the account team in a separate document. It does not shrink the recommendation unless `fit_to_entitlement` is true |
| `constraints.*` | What is vetoed regardless of technical merit |
| `standards.percentile` | One percentile, in every chart and detector |
| `outcomes.*` | Ranking when several journeys are equally instrumentable |
| `business_context.*` | Section 26, Business Value Realization: the quoted commentary, the current MTTx, incident volume, triage and tooling cost, revenue exposure |
| `public_evidence.*` | Whether to read the last twelve months of outage coverage, complaints, and field performance, and which brand terms to search |

Never request or display an ingest token. Analysis access is recorded in the
inputs file; what that section decides is
[`../skills/references/engagement-inputs.md`](../skills/references/engagement-inputs.md).
Splunk API values are not a second scheme. They live in the memory repository `.env`.

**Existing telemetry is required.** Before the portfolio footprint is written,
the analyze run uses the `splunk-observability` and `splunk-platform` MCP servers
and the Splunk API endpoints (Observability and Enterprise). The procedure is
[`../skills/references/existing-telemetry.md`](../skills/references/existing-telemetry.md).

## First: is this a first run or a delta?

Check for `wiki/apps/<app>/services/<service>/index.md`.

- **Absent** — first run. Full analysis.
- **Present with entries in `meta/run-log.md`** — **delta run**. Read `meta/versions.md`, `meta/decisions.md`, the accepted BT and workflow names, and the finding frontmatter *before* scanning. Reuse every accepted name and every finding id. Section 3 gains `### Changes since v<N-1>`, and the document reports what changed rather than reproducing itself. Rules: [`../skills/references/incremental-runs.md`](../skills/references/incremental-runs.md).
- **Present but the application has been rebuilt** — declare a **re-baseline** explicitly, archive the old wiki, and say in the document why the baseline was reset.

## Task

If URLs were provided, **deep-scan** the front end (HTML, script order, competing agents,
bundle placement of RUM, CSP, 404 shells, consent, third-party pixels, exposed credentials,
and anything reachable that should not be). Inventory APIs and assess the authorized source
and runtime surfaces against OWASP Top 10:2025 and OWASP API Security Top 10:2023 using
[`../skills/references/security-assessment.md`](../skills/references/security-assessment.md).
Combine with a **diagram-driven** backend map.

Produce `docs/observability/analysis-<app>-<date>.md` and the `.docx` rendered from it, with **every section** from [`../skills/references/document-template.md`](../skills/references/document-template.md) in that order. That table is the only section list; do not restate it here and do not reorder it. If evidence is missing, keep the heading and write **Not in evidence** plus the evidence that would settle it.

Eight things this run gets wrong if it is not deliberate about them:

1. **Critical Findings is section 4** — immediately after the architecture it was found
   in, with complete OWASP coverage matrices and findings ordered by severity. Each finding
   has confidence, class, OWASP mapping, priority, evidence, files/surfaces, exposure, risk,
   stop-the-bleeding and structural remediation, and verification. Every confirmed or
   high-confidence vulnerability is referenced in `P0 recommended fixes` in section 5.
   P0 is not observability Phase 0. A credential is recorded by shape and location, never
   by value. Specs: [`../skills/references/critical-findings.md`](../skills/references/critical-findings.md)
   and [`../skills/references/security-assessment.md`](../skills/references/security-assessment.md).
2. **Nothing in the body sits under an appendix heading.** Appendices are the attribute dictionary, long code variants, the agent work-order plan, supplementary evidence, and open items — five topic-scoped appendices, not a container for the analysis.
3. **The catalogue is sections 19–25, contiguous and in this order**: Business Transactions (flat), Workflows (flat), Custom Metrics, BT-Aligned Workflows (the join), Detectors and Thresholds, Service Level Indicators and Objectives, Composite Use Cases. Each is defined in terms of the one before it.
4. **Every detector has a threshold** that is a measured baseline, a customer-agreed target traced to an SLO, or a labelled placeholder with the query that will replace it. There is no fourth option.
5. **Every SLI is written in the customer's voice first**, its query second, with good/total events, objective, window, error budget, and burn-rate alerting. Spec: [`../skills/references/service-levels.md`](../skills/references/service-levels.md).
6. **Every `Use Case:` opens with `Narrative`** — plain language, no attribute or span names, who the user is and what the business loses when it fails. Then identity, attributes, span events, metrics, SLI, dashboard, detectors, and the join labelled **continue trace** | **span link** | **attribute pivot**.
7. **Business Value Realization is section 26**, the last body section before the appendices, and it is written from three things only: the customer's `business_context`, the last twelve months of the **public record** (outage coverage, their own status history, complaints, field performance — each entry cited with URL, publication, and date), and the performance this run **measured**. Every figure carries a `stated` / `measured` / `public` / `derived` label, every claim names a workflow, indicator, or detector that exists in this document, and **no business number is ever inferred from an industry benchmark**. With no business inputs the section is still written — short, honest, coefficients named and unfilled. Spec: [`../skills/references/business-value.md`](../skills/references/business-value.md).
8. **Entitlement prices the recommendation; it does not cap it.** Recommend what the application needs. When entitlement numbers were supplied, or a traffic baseline factor was supplied, also write `docs/observability/entitlement-exposure-<app>-<date>.md` for the **account team** — position today, what this adds with the arithmetic per row, the projected overage, the options, and a recommendation — and reference it from the customer document in exactly one document-control line, with no licensing or overage numbers in that document at all. A factor is supplied only when it is neither `unknown` nor an empty collection. When neither entitlement nor a supplied baseline exists, there is no exposure document and no assumed limit. A baseline with no entitlement is an expectation range, not an overage. Spec: [`../skills/references/entitlement-exposure.md`](../skills/references/entitlement-exposure.md). The trace-rate formula is in `cardinality-budget`; do not multiply requests per minute by spans per trace.

**Cross-Cutting Attributes and Baggage Propagation is mandatory** and is the section most often dropped. Attribute-set table plus all five code subsections: provider bootstrap, the `SpanProcessor.onStart` stamp over an explicit key allowlist, the identity-success baggage write, the backend composite propagator, and producer inject / consumer extract once per bus in the architecture section. Prose saying "use baggage" does not satisfy it. If a piece does not exist in the target, keep the heading and write **Not in evidence — do not deploy** with the pattern shown anyway.

Also required, and easy to drop because they are not sections: record the tool, SDK, semconv, collector, and provider **versions** this document was designed against in `### Document control and evidence basis`, and call out any breaking change since the last run. Spec: [`../skills/references/version-currency.md`](../skills/references/version-currency.md).

Emit `docs/observability/implementation-map.json` and map every BT, workflow, use case,
detector, objective, and configuration target to repository legs and optional Jira projects.
Use `<org>.bt` as the bounded propagated global tag configured by the Splunk APM Business
Transaction Global tag rule; `workflow.name` remains subordinate intent. Ask engineering
once after analysis for unresolved repository/Jira ownership. Spec:
[`../skills/references/implementation-work-orders.md`](../skills/references/implementation-work-orders.md).

## Acceptance

A reader who stops after six pages leaves knowing the architecture and every finding worth acting on this week. A staff engineer can implement Phase 0 and the first workflow without asking what a `workflow.step` value is, how baggage is stamped, or whether a join continues the trace. A TAM can configure MetricSets and Business Transaction rules from the portfolio mapping. An executive reading only section 26 sees their own words, cited public evidence, measured numbers, and no benchmark. Every row of the pre-delivery checklist in Appendix E is `yes`, and `verify_render.py` exits 0.

Follow [`../skills/references/analysis-run-lifecycle.md`](../skills/references/analysis-run-lifecycle.md):
include the intake artifact, create `initial-<app>-analysis` for the first run or
`ci-initiated-<app>-analysis` for later CI runs, commit each analysis phase, push, and open
one docs-only PR. Do not modify application source, merge the PR, or produce a second
customer-facing document. The entitlement exposure document is for the account team, is
markdown only, and is not part of the customer review.
