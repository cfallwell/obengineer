---
name: instrumentation-guide
description: >-
  Write the full instrumentation contract for a target from an accepted
  analysis: architecture observed, cross-cutting attributes and baggage,
  attribution, Collector config, MPM dimensions, per-BT workflow registry,
  messaging, per-flow use cases with dashboards and detectors, release
  overlays, Log Observer Connect, and the attribute dictionary. Emits three
  artifacts: the Markdown guide, a customer-review .docx rendered from it, and
  attribute-schema.json. Use when the user types $instrumentation-guide, asks
  for an instrumentation guide or contract, "develop the guide", "Prompt 02",
  a business-transaction and workflow registry, or dashboards and detectors
  for a scanned application. Documentation only; no application runtime code.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Instrumentation Guide — the full contract

## Overview

An instrumentation guide is not an inventory and not a list of spans. It is a
contract a staff engineer can implement without asking what a `workflow.step` value
is, how baggage is stamped, or whether a join continues the trace or needs a span
link — and that a TAM can configure MetricSets and Business Workflows from.

Agent definition: [`../../agents/instrumentation-architect.agent.md`](../../agents/instrumentation-architect.agent.md).
Prompt: [`../../prompts/02-develop-instrumentation-guide.md`](../../prompts/02-develop-instrumentation-guide.md).

## Read these first

| Reference | Owns |
|---|---|
| [`../references/document-template.md`](../references/document-template.md) | The canonical section order and every table's columns. Non-negotiable. |
| [`../references/cross-cutting-attributes.md`](../references/cross-cutting-attributes.md) | The mandatory baggage section, with all five code subsections. |
| [`../references/portfolio-decision-engine.md`](../references/portfolio-decision-engine.md) | Which question goes to Observability Cloud, Splunk Enterprise, or ThousandEyes. |

## Three artifacts, one source

| Artifact | Path | Audience |
|---|---|---|
| Markdown | `docs/observability/INSTRUMENTATION-GUIDE.md` | the implementer agent and the engineers working the PRs |
| Word | `docs/observability/<Customer>-<App>-Instrumentation-Recommendations-<date>.docx` | customer architecture review |
| Schema | `docs/observability/attribute-schema.json` | CI, and the machine form of Appendix A |

The `.docx` is rendered from the Markdown by `customer-doc-render`, never
hand-authored. Markdown alone is an incomplete delivery.

## Process

### Step 1 — Lift the accepted analysis, do not re-derive it

Reuse the BT names, `workflow.name` strings, and attribute keys already accepted.
Extend from new evidence; never rename for taste. If a prior contract or
`attribute-schema.json` is attached, it is the naming authority.

### Step 2 — Write the body in template order

Purpose and Scope → References → **`<Frontend>` and Backend Architecture
(Observed)** → Course of action → Missing portfolio components → **Cross-Cutting
Attributes and Baggage Propagation** → route changes → attribution → Collector →
MPM → BT registry → Messaging → Use Cases → meters → Release Events → Log Observer
Connect → portfolio mapping → Dashboards → Detectors → phases → non-goals →
**Appendix A: dictionary** → **Appendix B: open items**.

Three placements that are routinely got wrong:

- **Architecture (Observed) is a body section near the front, not an appendix.** It is what a customer architecture review opens on. Do not retitle it.
- **The attribute dictionary is Appendix A, at the back.** Architecture front, dictionary back.
- **Cross-Cutting Attributes and Baggage Propagation comes immediately after architecture**, before attribution. It is mandatory; see Step 3.

### Step 3 — Do not skip the baggage section

Invoke `baggage-propagation`. The section needs the three-step pattern with its
rationale, the `Attribute | Type | Set at | Dimension? | Notes` table, and five code
subsections: provider bootstrap, the `SpanProcessor` over an explicit key allowlist,
the login write, the backend composite propagator, and producer inject / consumer
extract once per bus. Prose saying "use baggage" does not satisfy it.

### Step 4 — Enumerate workflows from evidence

One `BT:` heading per business transaction, with the owning artifact and any feature
flag, then an exhaustive dotted-kebab workflow list and the bounded `workflow.step`
enum for that family. Sources: named chunks and surface files, module-federation
remotes, analytics event flags, payment and feature flags, UI copy, config JSON,
sequence diagrams.

A BT whose only workflows are `view`, `click`, and `start` has not been analyzed.
The boot artifact gets a heading stating it owns `init` and emits no workflow spans.

### Step 5 — One use case per ranked flow

Fixed shape every time: workflow identity, span-event table, attribute table with a
`Dimension?` column, metrics with dimension lists, a dashboard panel list including
the Log Observer Connect panel and the release overlay, detectors with trigger and
group-by, and the cross-workflow join labeled **continue trace** | **span link** |
**attribute pivot**. Span links only for webhooks, batch consume, DLQ redrive,
schedulers, and scatter/gather.

### Step 6 — Gate the detectors on trust

If the scan proved the signal is unreliable — a late or duplicated browser agent,
free-text workflow names, HTTP status decoupled from rendered content — those are
Phase 0 blockers. Detectors built on an untrustworthy attribute train people to
ignore alerts. Arm only the telemetry-integrity and configuration-safety detectors
immediately; everything else stays a draft with a stated exit criterion.

### Step 7 — Emit the schema, generated from the guide

Generate `attribute-schema.json` **from** the committed Markdown where possible — the
BT catalog, workflow names, and span events can be parsed out — so the two cannot
drift. Appendix A and the schema must agree.

### Step 8 — Render and verify

```bash
python3 ../customer-doc-render/scripts/render_customer_doc.py \
    docs/observability/INSTRUMENTATION-GUIDE.md \
    -o "docs/observability/<Customer>-<App>-Instrumentation-Recommendations-<date>.docx"

python3 ../customer-doc-render/scripts/verify_render.py \
    docs/observability/INSTRUMENTATION-GUIDE.md \
    "docs/observability/<Customer>-<App>-Instrumentation-Recommendations-<date>.docx"
```

Then fill the pre-delivery checklist at the end of Appendix B. Any `no` means do not
ship.

## Warning signs

- **No `Cross-Cutting Attributes and Baggage Propagation` section.** Failed run.
- **Markdown with no `.docx`,** or a `.docx` newer than the Markdown.
- **Architecture in an appendix** or the dictionary at the front.
- **BT registry restated as a summary table** instead of one heading per BT.
- **Dashboards described in prose** with no panel list, or detectors with no group-by.
- **Joins described as "via traceparent and an id"** with no join type named.
- **Any real token, key, or credential.** Placeholders only.

## Non-goals

- No application runtime code, no Helm token values, no dashboard JSON unless the human asked for stubs.
- No "enable all instrumentations."
- No always-on session replay unless the human accepted the cost and Core Web Vitals risk in writing.
