# Prompt 01 — Analyze the application

**Agent:** [`../agents/instrumentation-architect.agent.md`](../agents/instrumentation-architect.agent.md)  
**Skills:** `instrumentation-analyze`, `instrumentation-wiki`,
`baggage-propagation`, `cardinality-budget`, `deliverable-review`
**Input:** digest-authorized local root `obconfig.yaml` and its complete artifact tree
**Output:** one immutable analysis version and its wiki in one reviewed PR

## Contract

Follow the architect agent and
[`../skills/instrumentation-analyze/SKILL.md`](../skills/instrumentation-analyze/SKILL.md).
The review surface is
[`../skills/references/analysis-site.md`](../skills/references/analysis-site.md), not the
legacy monolithic template.
Use `../templates/analysis-site/index.md` and `detail.md` as the approved layout. Do not
replace the long linked index with duplicated object detail.

If config does not exist, invoke `/ob-start`. Do not begin collection unless the atomic
`manage_obconfig.py claim --command <origin> --intended-version V<N>` succeeds for the
schema version, config digest, full artifact manifest/delta and tree digest, originating
command, and intended version. Use its sanitized delta as the only artifact-change input.
After that claim and before workers start, invoke exactly:

```text
python3 <obengineer-root>/skills/engagement-intake/scripts/manage_obconfig.py --project-root . direct-api --phase analysis --command <origin> --intended-version V<N>
python3 <obengineer-root>/skills/engagement-intake/scripts/manage_obconfig.py --project-root . safe-active --command <origin> --intended-version V<N>
```

Consume its centralized-redacted JSON only. Append each source disposition and measured
aggregate to `provenance-ledger.json`; record failed or `not-configured` rows as source
limitations/unresolved evidence. Never import `direct_api.py` in place of this command,
read process environment, or put a credential in command arguments.
The second command makes zero requests in passive/none and records fixed-policy
safe-active outcomes otherwise. Both commands revalidate the claim before and after
network work. After all analysis, network, render, and validation work, invoke
`manage_obconfig.py finalize --command <origin> --intended-version V<N>` with explicit
`--output` paths for `docs/observability` and the generated versioned wiki. Run it
immediately before the first commit/push/PR action and dispatch only after it succeeds.
Consume only after successful analysis and PR dispatch. On failure or decline invoke
`manage_obconfig.py abort` with the same command/version; it releases the claim while
leaving artifact baseline/history unchanged.

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
The supported command above owns every configured direct request and explicit
source-specific disposition in analysis; MCP is supplemental and cannot suppress or
relabel it. Record source provenance and reconcile facts after parallel collection.
Every worker interval fits its manifest `deadlineSeconds`. A `limited` result names
nonempty limitations plus the exact manifest evidence scopes or required outputs that
degraded. Record collection, reconciliation, rendering, validation, and total intervals
in `analysis-run-timing.json`; each interval fits its manifest budget.

Before workers start, hash the full configured artifact directory. Reread every
added/changed file, remove deleted context, and reuse only unchanged
path/length/digest context. Use the host's subagent facility. Launch as many runnable jobs as fit
`min(6, available host slots - 1)` in one parallel tool call before awaiting any result;
start queued jobs as slots free. Do not perform runnable worker jobs serially in the
coordinator. If the host cannot run subagents, keep the PR draft and report the analysis
as blocked rather than presenting a serial shallow run as complete.

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
- every proposed work order and its evidence-bound repository mapping. Missing application
  source produces an explicit unresolved mapping and blocked order, never an invented leg.

Do not create empty product chapters. Put plausible future additions on one Suggested
additions page. Put useful missing human facts on Intake recommendations.
Derive BT and workflow counts from this target. A same-customer prior guide supplies
continuity and a quality floor, not a restrictive list or fixed count. Preserve an
exhaustive catalogue for each evidenced BT while promoting only ranked workflows for
complete span-tree design.

Security follows `security-assessment.md`; confirmed or high-confidence findings link
their remediation work orders. Never display a credential value.

## Artifacts

Create:

```text
docs/observability/analysis/<app>/V<N>/
docs/observability/analysis-job-manifest.json
docs/observability/analysis-worker-results/
docs/observability/analysis-run-timing.json
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
Finalize the generated output roots as specified above, then open one analysis PR without
performing intervening analysis, network, or rendering. Mutation before finalize yields
no dispatch. Input mutation after finalize belongs to the next run and does not
invalidate consumption of the finalized snapshot after successful dispatch.

When ready for review, ask the human to review the linked PR. Process review comments and
commit corrections. Ask:

> Do you accept V<N> and want me to merge this PR?

Only explicit `yes` writes acceptance, makes eligible work orders Ready, and authorizes
merge. Resolve commits and digests internally; never ask for a SHA or a person's name.

After merge, return one host-native documentation link and concise next steps. Never start
a web server, open a browser, return localhost, or paste the analysis into chat.
