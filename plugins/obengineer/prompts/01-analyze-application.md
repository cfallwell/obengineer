# Prompt 01 — Analyze the application

**Agent:** [`../agents/instrumentation-architect.agent.md`](../agents/instrumentation-architect.agent.md)  
**Skills:** `engagement-intake`, `instrumentation-analyze`, `baggage-propagation`, `cardinality-budget`, `customer-doc-render`, `deliverable-review`  
**Inputs:** `docs/observability/engagement-inputs.yaml`  
**Human:** TAM + customer architect. Docs-only. No application code changes.

**Invoke it, do not paste it.** `/obengineer-analyze` reads this file in place, so
there is one copy of the run contract and it is the copy under review. If your host
has no commands installed, run [`../install.sh`](../install.sh) or tell the agent to
read this file.

---

## System reminder

Follow `instrumentation-architect.agent.md`. You are analyzing, not opening application PRs. Auto-instrumentation is a bootstrap, never a complete design. **"Analysis" does not mean inventory-only** — this document carries the full contract: the business-transaction and workflow catalogue, custom metrics, detectors with thresholds, SLIs and SLOs, composite use cases, and the enablement code with token placeholders.

**This is the only customer-facing document.** There is no separate instrumentation-recommendations deliverable; the lower-layer, per-note detail the coding agents work from is built by Prompt 02 as a wiki, not as a second document.

Choose the course of action from **how Splunk Observability Cloud, Splunk Enterprise, and Cisco ThousandEyes work** (RUM, APM, Infrastructure, Log Observer Connect, Synthetics, MetricSets, APM Business Workflows, Related Content, Events API, MPM, Enterprise indexes/`trace_id`, ThousandEyes path tests) plus the evidence in this session. Do not assume an industry, a storefront, named journeys, a cloud, or a prior customer document. Discover journeys from the diagrams and scan. Assign each question to one platform: journeys/code → Observability Cloud; durable logs/audit → Enterprise; internet/CDN/SaaS path → ThousandEyes.

Do not search the workspace for unrelated documents. If an existing schema or wiki is present for this customer and application, extend that taxonomy.

**The Word artifact opens the way a review expects:** a simple title page, then the Table of Contents on its own page, then one section per page. Declare the title page in a `<!-- title-page ... -->` block (subtitle, tagline, author, audience, date, version, header) and put nothing else above the first `##`. Application identifier, environment scanned, realm, percentile standard, in-scope languages and buses, evidence basis, recorded tool versions, and token handling go in **`### Document control and evidence basis`** at the end of Purpose and Scope. Markdown `##` renders as Word `Heading 1` and starts a new page; `###` becomes `Heading 2`. The renderer rejects prose above the first section heading and refuses to save a document whose sections would not break, so run `verify_render.py` and expect exit 0. Layout spec: `skills/customer-doc-render/references/document-format.md`.

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
| `backends.languages`, `.buses`, `.cloud_accounts`, `.gateway` | Which SDK and bus subsections must exist |
| `tenancy.o11y_realm`, `.environments` | Whether exit criteria can be phrased as queries |
| `entitlement.*` | The cardinality budget every dimension recommendation is charged against |
| `constraints.*` | What is vetoed regardless of technical merit |
| `standards.percentile` | One percentile, in every chart and detector |
| `outcomes.*` | Ranking when several journeys are equally instrumentable |

Never request or display an ingest token. The inputs file records who holds a
credential, not its value.

## First: is this a first run or a delta?

Check for `wiki/<Customer>/<app>/index.md`.

- **Absent** — first run. Full analysis.
- **Present with entries in `meta/run-log.md`** — **delta run**. Read `meta/versions.md`, `meta/decisions.md`, the accepted BT and workflow names, and the finding frontmatter *before* scanning. Reuse every accepted name and every finding id. Section 3 gains `### Changes since v<N-1>`, and the document reports what changed rather than reproducing itself. Rules: [`../skills/references/incremental-runs.md`](../skills/references/incremental-runs.md).
- **Present but the application has been rebuilt** — declare a **re-baseline** explicitly, archive the old wiki, and say in the document why the baseline was reset.

## Task

If URLs were provided, **deep-scan** the front end (HTML, script order, competing agents, bundle placement of RUM, CSP, 404 shells, consent, third-party pixels, and anything reachable that should not be). Combine with a **diagram-driven** backend map.

Produce `docs/observability/analysis-<app>-<date>.md` and the `.docx` rendered from it, with **every section** from [`../skills/references/document-template.md`](../skills/references/document-template.md) in that order. That table is the only section list; do not restate it here and do not reorder it. If evidence is missing, keep the heading and write **Not in evidence** plus the evidence that would settle it.

Six things this run gets wrong if it is not deliberate about them:

1. **Critical Findings is section 4** — immediately after the architecture it was found in, ordered by severity, each with observation and evidence, the files and surfaces involved, what is exposed and to whom, the risk, the remediation path split into stop-the-bleeding and structural, and how to verify. Stable ids from the start. A credential is recorded by shape and location, never by value. Spec: [`../skills/references/critical-findings.md`](../skills/references/critical-findings.md).
2. **Nothing in the body sits under an appendix heading.** Appendices are the attribute dictionary, long code variants, the agent work-order plan, supplementary evidence, and open items — five topic-scoped appendices, not a container for the analysis.
3. **The catalogue is sections 19–25, contiguous and in this order**: Business Transactions (flat), Workflows (flat), Custom Metrics, BT-Aligned Workflows (the join), Detectors and Thresholds, Service Level Indicators and Objectives, Composite Use Cases. Each is defined in terms of the one before it.
4. **Every detector has a threshold** that is a measured baseline, a customer-agreed target traced to an SLO, or a labelled placeholder with the query that will replace it. There is no fourth option.
5. **Every SLI is written in the customer's voice first**, its query second, with good/total events, objective, window, error budget, and burn-rate alerting. Spec: [`../skills/references/service-levels.md`](../skills/references/service-levels.md).
6. **Every `Use Case:` opens with `Narrative`** — plain language, no attribute or span names, who the user is and what the business loses when it fails. Then identity, attributes, span events, metrics, SLI, dashboard, detectors, and the join labelled **continue trace** | **span link** | **attribute pivot**.

**Cross-Cutting Attributes and Baggage Propagation is mandatory** and is the section most often dropped. Attribute-set table plus all five code subsections: provider bootstrap, the `SpanProcessor.onStart` stamp over an explicit key allowlist, the identity-success baggage write, the backend composite propagator, and producer inject / consumer extract once per bus in the architecture section. Prose saying "use baggage" does not satisfy it. If a piece does not exist in the target, keep the heading and write **Not in evidence — do not deploy** with the pattern shown anyway.

Also required, and easy to drop because they are not sections: record the tool, SDK, semconv, collector, and provider **versions** this document was designed against in `### Document control and evidence basis`, and call out any breaking change since the last run. Spec: [`../skills/references/version-currency.md`](../skills/references/version-currency.md).

## Acceptance

A reader who stops after six pages leaves knowing the architecture and every finding worth acting on this week. A staff engineer can implement Phase 0 and the first workflow without asking what a `workflow.step` value is, how baggage is stamped, or whether a join continues the trace. A TAM can configure MetricSets and Business Workflows from the portfolio mapping. Every row of the pre-delivery checklist in Appendix E is `yes`, and `verify_render.py` exits 0.

Do not modify application source. Do not produce a second customer-facing document.
