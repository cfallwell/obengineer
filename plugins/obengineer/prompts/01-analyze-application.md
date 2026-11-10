# Prompt 01 — Analyze the application

**Agent:** [`../agents/instrumentation-architect.agent.md`](../agents/instrumentation-architect.agent.md)  
**Skills:** `instrumentation-analyze`, `instrumentation-wiki`,
`baggage-propagation`, `cardinality-budget`, `deliverable-review`
**Input:** `docs/observability/engagement-inputs.yaml`
**Output:** one immutable analysis version and its wiki in one reviewed PR

## Contract

Follow the architect agent and
[`../skills/instrumentation-analyze/SKILL.md`](../skills/instrumentation-analyze/SKILL.md).
The review surface is
[`../skills/references/analysis-site.md`](../skills/references/analysis-site.md), not the
legacy monolithic template.
Use `../templates/analysis-site/index.md` and `detail.md` as the approved layout. Do not
replace the long linked index with duplicated object detail.

If inputs do not exist, invoke `/ob-start`. Missing optional inputs do not block analysis
and do not require the human to type `unknown`.
Do not begin collection unless `.obengineer/run-context.json` records
`analysis_authorized: true` and `last_event: review-no`. Only the exact `no` response at
optional review creates that state; a `yes` selection never does.

## Evidence collection

Create the six bounded jobs in `analysis-job-manifest.schema.json`:

- production browser behavior;
- source, configuration, dependencies, and technology;
- diagrams and prior artifacts;
- direct Observability Cloud endpoints and relevant connected integrations;
- direct Splunk Platform endpoints, cloud boundaries, and messaging; and
- public evidence plus authorized security checks.

Reserve one host slot for the coordinator. The host starts workers; the repository can
only audit worker result intervals and must never claim it spawned them. If two or more
jobs are runnable, their recorded intervals overlap without exceeding remaining host
capacity. MCP servers supplement direct APIs. They are not the only tenant source.
Record source provenance and reconcile facts after parallel collection.

The live production scan uses the explicit production URL confirmed during the first
question and is required unless inputs say `no browser: <reason>`. Do not replace it with
a URL discovered from source or connected systems. Test and QA are not substitutes. A
different site's scan or taxonomy is not evidence.

## Design

Produce the full instrumentation strategy:

- architecture, languages, frameworks, runtimes, third parties, and current telemetry;
- accounts, buses, downstreams, third parties by consequence, one init owner, SPA routes,
  diagrams, prior artifacts, and failure points;
- actionable findings;
- dependency-ordered implementation path;
- use cases first, then workflows, then business transactions;
- attributes, metrics, propagation, attribution, collector, and logs where applicable;
- dashboards, detectors with thresholds and windows, objectives with error budgets,
  release correlation, Synthetics and ThousandEyes where applicable, and verification;
- Cross-Cutting Attributes and Baggage Propagation with its applicable provider,
  allowlisted `SpanProcessor.onStart`, identity, backend, and bus patterns; and
- every proposed work order and repository leg.

Do not create empty product chapters. Put plausible future additions on one Suggested
additions page. Put useful missing human facts on Intake recommendations.

Security follows `security-assessment.md`; confirmed or high-confidence findings link
their remediation work orders. Never display a credential value.

## Artifacts

Create:

```text
docs/observability/analysis/<app>/V<N>/
docs/observability/analysis-job-manifest.json
docs/observability/analysis-worker-results/
docs/observability/analysis-contract.json
docs/observability/attribute-schema.json
docs/observability/implementation-map.json
docs/observability/provenance-ledger.json
docs/observability/verification-plan.json
wiki/apps/<app>/versions/V<N>/
```

Run Prompt 02 inside this run. Validate the canonical contract and render the complete
tree deterministically. The landing page carries versions, status, next steps, a table of
contents, a visible architecture summary, and substantive summaries linking every
nonempty detail area and matching work-order snapshot. Word is optional; when requested
it is a summary under 20 pages.

## Review and handoff

Run `make qa-analysis`. Validate manifest intervals and coordinator capacity, canonical
object fields, deterministic rendering, placeholders, links, breadcrumbs, schema, map,
ledger, verification plan schema version 2 with stable `source_ref` values, wiki,
work-order dependencies, reverse links, performance budgets, and credential scanning.
Open one analysis PR.

When ready for review, ask the human to review the linked PR. Process review comments and
commit corrections. Ask:

> Do you accept V<N> and want me to merge this PR?

Only explicit `yes` writes acceptance, makes eligible work orders Ready, and authorizes
merge. Resolve commits and digests internally; never ask for a SHA or a person's name.

After merge, return one host-native documentation link and concise next steps. Never start
a web server, open a browser, return localhost, or paste the analysis into chat.
