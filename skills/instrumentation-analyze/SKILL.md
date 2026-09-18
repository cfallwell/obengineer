---
name: instrumentation-analyze
description: >-
  Produce the single customer-facing analysis document for a target: deep-scan
  the front end (script order, competing RUM/EUM agents, where the agent
  initialises, router, CSP, consent, 404 shells), map backends and buses from
  diagrams, inventory the existing Splunk and ThousandEyes footprint, raise the
  critical findings, and carry through the full recommendation set — business
  transactions, workflows, custom metrics, detectors with thresholds, SLIs and
  SLOs in the customer's voice, and composite use cases. Emits the Markdown, the
  customer-review .docx rendered from it, and attribute-schema.json. Use when the
  user types $instrumentation-analyze, asks to "analyze this site or app",
  "Prompt 01", for the analysis document, what business transactions exist, why
  RUM data looks wrong, or which observability products are missing. Read-only
  against the target; writes documents, never application code.
metadata:
  author: obengineer
  version: 0.2.0
  category: observability
---

# Instrumentation Analyze — the customer document

## Overview

Every instrumentation mistake that is expensive to reverse comes from designing against an
assumed architecture. This skill produces the evidence base **and the recommendations that
follow from it, in one document**, because splitting them produced two artifacts that
disagreed and asked the customer to read the findings in one file and their consequences in
another.

Analysis does not mean inventory-only. The document carries the full catalogue — business
transactions, workflows, meters, detectors with thresholds, objectives, use cases — and the
enablement code with token placeholders. What it does not carry is the per-note detail the
agents work from; that goes to [`../instrumentation-wiki/SKILL.md`](../instrumentation-wiki/SKILL.md).

Agent definition: [`../../agents/instrumentation-architect.agent.md`](../../agents/instrumentation-architect.agent.md).
Prompt: [`../../prompts/01-analyze-application.md`](../../prompts/01-analyze-application.md).

## Read these first

| Reference | Owns |
|---|---|
| [`../references/document-template.md`](../references/document-template.md) | The canonical section order, every table's columns, and the completeness bar. Non-negotiable. |
| [`../references/critical-findings.md`](../references/critical-findings.md) | Section 4 — severity, remediation, exposure, and the credential rule. |
| [`../references/service-levels.md`](../references/service-levels.md) | Section 24 — indicators in the customer's voice. |
| [`../references/cross-cutting-attributes.md`](../references/cross-cutting-attributes.md) | Section 7 and its five mandatory code subsections. |
| [`../references/portfolio-decision-engine.md`](../references/portfolio-decision-engine.md) | Which question goes to Observability Cloud, Splunk Enterprise, or ThousandEyes. |
| [`../references/incremental-runs.md`](../references/incremental-runs.md) | Whether this is a first run or a delta. |

## Output

| Artifact | Path |
|---|---|
| Markdown | `docs/observability/analysis-<app>-<date>.md` |
| Word | `docs/observability/<Customer>-<App>-Analysis-<date>.docx` |
| Schema | `docs/observability/attribute-schema.json` |

One customer document. If a run is about to produce a second one, it has recreated the
artifact this design removed.

## Rules

- **Assume nothing.** Not the industry, not a storefront, not named journeys, not the cloud, not a prior customer's taxonomy. Derive every name from this session's evidence.
- **Never store a credential.** A found token is a finding referenced by shape and location, never by value. See [`../references/critical-findings.md`](../references/critical-findings.md).
- **Mark gaps as gaps.** "Not in evidence" with a named next step is a finding, not an omission.
- **Nothing goes under an appendix heading that the argument depends on.** Appendices are the dictionary, long code, the work-order plan, supplementary evidence, and open items.

## Process

### Step 1 — Establish the run type

Does `wiki/<Customer>/<app>/index.md` exist? If it does with run-log entries, this is a
**delta**: read `meta/versions.md`, `meta/decisions.md`, the accepted BT and workflow names,
and the finding frontmatter *before* scanning. Section 3 then carries
`### Changes since v<N-1>` and the document reports change rather than reproducing itself.
Rules: [`../references/incremental-runs.md`](../references/incremental-runs.md).

### Step 2 — Front-end deep scan

When a URL is in scope, capture the document and the runtime, not just the HTML.

| Look for | Why it changes the contract |
|---|---|
| Script order in `<head>` and `<body>` | Which agent wins the race; whether a competing EUM patches `fetch` first |
| Where the RUM agent initialises | In a boot script, or deep inside a multi-megabyte bundle behind a config fetch — the second means the agent starts long after first paint |
| Whether the provider handle is reachable | An agent trapped in module scope cannot be used by other bundles, which pushes teams toward a second `init` |
| Router library and version | Client navigations do not create a document span, so `document-load` covers only the entry route |
| Every other RUM / EUM / session-replay / analytics agent | Duplicated collection, resource contention, and consent exposure |
| Consent platform and when it resolves | Data sent before consent resolves is a compliance finding, not a tuning problem |
| CSP and its allowlist | A pixel or beacon host missing from CSP is a silent data gap |
| HTTP status versus rendered content | A route that renders a real page under 404, or "not found" under 200, makes `http.status_code` useless as an error SLI |
| Load-order timing | First paint versus first beacon, measured, is the Phase 0 evidence |
| **Anything reachable that should not be** | Keys, tokens, internal hostnames, unauthenticated endpoints, PII in URLs or storage — section 4, not a footnote |

Record measured facts. "The agent is late" is an opinion; "first paint at 288 ms, first
beacon at 2081 ms" is evidence.

### Step 3 — Raise the critical findings while the evidence is in hand

Anything a competent engineer on this team would act on this week goes to section 4, ordered
by severity, each with observation, files and surfaces, exposure, risk, remediation, and
verification. Stable ids (`F-01`) from the start, because the phased plan, the wiki note, and
the customer's ticket all need to refer to the same finding a year later.

Write these **before** the recommendation sections. Findings collected as a side effect of
other work end up wherever they were found, which is how they get buried.

### Step 4 — Enumerate business transactions and workflows

A **BT** is the page, bundle, app, or surface the user is in. A **workflow** is a discrete
intent inside it. Sources, in order of reliability: route registries and chunk manifests,
module-federation remotes, analytics event flags, payment and feature flags, UI copy and
translations, config JSON, sequence diagrams.

Section 19 is the flat BT list, section 20 the flat workflow list, section 22 the join. All
three, because the flat lists are what expose the duplicate names and the empty BTs that a
per-BT view hides. Do not invent a BT with no evidence, do not collapse a real BT into "view
and click", and leave unidentified bundles in the open items rather than guessing.

### Step 5 — Map backends, accounts, and buses

From diagrams and captured call sequences: owning service per hop, account or subscription
crossings, message buses and their topic patterns, downstream systems, and the failure or DLQ
points the diagram marks. For each named flow, state what is **already visible** in
Observability Cloud versus what is being reconstructed by inference.

### Step 6 — Inventory the portfolio footprint, then assign each question

Present, partial, or absent — from evidence, never assumed — for Observability Cloud (RUM,
APM, Infrastructure, Synthetics, Log Observer Connect), Splunk Enterprise, and Cisco
ThousandEyes, with the raw shape of what is collected today. A decoded beacon payload showing
which attributes are actually populated is worth more than a list of installed products.

Then use [`../references/portfolio-decision-engine.md`](../references/portfolio-decision-engine.md):
journeys and code execution to Observability Cloud; durable logs, audit, and compliance
search to Splunk Enterprise; internet, DNS, CDN, and SaaS path health to ThousandEyes.
Naming the platform per question is what makes the recommendations defensible.

### Step 7 — Write the contract sections at contract depth

Invoke `baggage-propagation` for section 7.
**Cross-Cutting Attributes and Baggage Propagation** is mandatory on every run and is the
section most often omitted: the attribute-set table plus all five code subsections, or a
document that fails review. Invoke
`cardinality-budget` before writing section 11, because a dimension list with no arithmetic
behind it is a preference. Sections 8 through 16 follow the template; keep every
heading and write **Not in evidence** with the evidence that would settle it where the target
has no such surface.

### Step 8 — Write the catalogue, in order, each defined by the one before

Sections 19–25: BTs, workflows, meters, the BT-to-workflow join, detectors with **thresholds
that are measured, agreed, or labelled placeholders**, objectives in the customer's voice per
[`../references/service-levels.md`](../references/service-levels.md), then one
`Use Case:` section per ranked flow opening with a plain-language `Narrative`.

A use case whose narrative cannot be written does not exist. Write it first and the rest
follows; write it last and it reads like a caption.

### Step 9 — State Phase 0 honestly

If the signal cannot be trusted yet, prove it: late agent, duplicate `init`, free-text
workflow names, identifiers or tokens in attributes, broken propagation across the first
backend hop. Each is a blocker with a measured exit criterion, and every criterion is a query
a TAM can run. Critical findings at or above the agreed severity are Phase 0 items by id. If
the signal **is** trustworthy, say so; a Phase 0 invented out of caution costs a release
cycle.

### Step 10 — Render, verify, and check yourself

```bash
python3 ../customer-doc-render/scripts/render_customer_doc.py \
    docs/observability/analysis-<app>-<date>.md \
    -o "docs/observability/<Customer>-<App>-Analysis-<date>.docx"

python3 ../customer-doc-render/scripts/verify_render.py \
    docs/observability/analysis-<app>-<date>.md \
    "docs/observability/<Customer>-<App>-Analysis-<date>.docx"
```

Then run [`../deliverable-review/SKILL.md`](../deliverable-review/SKILL.md) against the
completeness bar and fill the pre-delivery checklist at the end of Appendix E. Any `no` means
do not ship.

## Warning signs

- **A tidy inventory with no measurements.** No timings, no decoded payload, no status-versus-content check means the scan was shallow.
- **No critical findings and no statement of what was checked.** Either the scan was shallow or the section is decoration.
- **A finding written into the section where it was discovered** instead of section 4. That is how it gets buried, and it has happened.
- **Journeys that match a generic commerce playbook** rather than the evidence.
- **One RUM application name for two applications** sharing a hostname.
- **Only one collection agent noticed.** Look again; overlapping EUM is common and changes the recommendation.
- **A detector with no threshold, or an SLO with no error budget.** Both are wish lists.
- **A credential pasted into the document.** Reference it by shape and location; record the exposure.
- **A second document produced "for the implementers".** That is the wiki, and it is notes.

## Non-goals

- Does not modify the target, log in destructively, or run load against production.
- Does not open application pull requests. That is [`../instrumentation-implement/SKILL.md`](../instrumentation-implement/SKILL.md).
- Does not produce a second customer-facing document.
- Does not write Terraform. That is [`../observability-as-code/SKILL.md`](../observability-as-code/SKILL.md).
