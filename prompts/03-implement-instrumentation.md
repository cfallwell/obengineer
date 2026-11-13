# Prompt 03 — Implement the instrumentation

**Agent:** [`../agents/instrumentation-implementer.agent.md`](../agents/instrumentation-implementer.agent.md)  
**Skills:** `instrumentation-implement`  
**Inputs:** accepted analysis version, schema, implementation map, Ready wiki work order, and engagement inputs
**Depends on:** canonical content-bound acceptance record, verified analysis artifacts,
schema, implementation map, and Ready work order.
**Output:** one linked PR per repository leg plus a coordination PR. No deploys. No secrets.

Run **once per unified work order**. Accept any bounded target selector defined in
`skills/references/implementation-work-orders.md`. If the human does not pick one, follow
the accepted phase plan.

**Invoke it, do not paste it.** `/ob-implement <target-selector>` reads this file in
place. If omitted, the accepted phase plan selects the next work order.

---

## System reminder

Follow `instrumentation-implementer.agent.md`. Before any edit run
`python3 <obengineer-root>/skills/instrumentation-wiki/scripts/verify_analysis_acceptance.py --record docs/observability/analysis/<app>/V<N>/acceptance.yaml --repo .`.
Read the guide, schema, map, and accepted work order.
Do not invent attributes. Do not enable always-on session replay unless accepted. Do not
call `SplunkRum.init` from an MFE. Use the work order's accepted review budget. Tests stay
in each repository PR. Zero-code agents/annotations are allowed only **together with** the
shared library and stamp processor.

Implement so the result works in **Splunk Observability Cloud**: stable `applicationName`,
bounded propagated `<org>.bt` for the APM Business Transaction Global tag rule,
`workflow.name` for subordinate intent, low-cardinality tags for MMS, `traceparent` for
Related Content, and schema-approved meter dimensions. Do not assume journey names from
another application.

PII deny list is enforced. If you see tokens in the repo, stop and report. Do not search the repo for unrelated specs.

## Inputs

- Analysis version: `docs/observability/analysis/<app>/V<N>/`
- Wiki work orders: `wiki/apps/<app>/versions/V<N>/implementation/work-orders/`
- Schema: `docs/observability/attribute-schema.json`
- Map: `docs/observability/implementation-map.json`
- Acceptance: `docs/observability/analysis/<app>/V<N>/acceptance.yaml`
- Secure non-secret obconfig projection — `backends.languages` and
  `.deploy_targets` for which SDK, `constraints.who_deploys_front_end` and
  `.who_deploys_collector` for whether this slice is deployable at all, and
  `constraints.change_windows` for when. `initial_scope.authorized` must be
  `full`, `repositories`, or `parent_folders` before this run writes code.
  `unknown` means stop and ask engineering to authorize the full scope, a
  subset of repositories, or a subset of a repository by parent folder. Do not
  adopt every repository a connected host can see.
- **Target selector:** one of `work-order:<id>`, `business-transaction:<id>`,
  `workflow:<name>`, `use-case:<id>`, `detector:<id>`, `alert-condition:<id>`,
  `dashboard:<id>`, `custom-code:<id>`, `objective:<id>`, or `config:<id>`, or
  “follow accepted phase plan”.
- **Override (optional):** `reimplement` to re-run an implemented, verified, or changed
  order.

## Task

Resolve the selector to exactly one Ready work order in the accepted version. Implement **only that unified
work order**, across only its mapped repository legs and authorized paths. Zero or multiple
matches stop and list the missing or ambiguous mappings. A missing repository or Jira
project is requested from engineering after analysis, never guessed.

Work orders are implementation contracts. Foundation orders come first; the gate asks
“Are all foundation work orders complete?” and releases every other order, in any order,
once the answer is yes. `use-case:<id>` runs its next unimplemented subordinate. With
`<app>` and `V<N>` the resolved accepted application and version, run:

```bash
S=<obengineer-root>/skills/instrumentation-wiki/scripts/work_order_state.py
python3 "$S" gate --repo . --app <app> --version V<N> --work-order <id> [--reimplement]
python3 "$S" show --repo . --app <app> --version V<N> --work-order <id>
```

Load the accepted note (R1) and every revision in `revision_paths` in order (R2, R3, ...
from `/ob-revise`), and implement the cumulative `effective_changes` from `show`, not only
the latest revision. A `legacy` ledger (version accepted before work-order kinds) gates on
`depends_on` only and has no revisions. After the PRs open, record status with
`python3 "$S" set-status --repo . --app <app> --version V<N> --work-order <id> --status <status> --pr <url>`
in `wiki/apps/<app>/implementation/V<N>/state.yaml`.

Runtime, Collector/CI, detector, objective, and configuration legs use the same work-order
boundary. Never deploy, apply Terraform, or arm a detector.

### If Phase 0

Match the guide’s Phase 0 contract. Typical browser work when the guide includes RUM:

- Kill switch; dedicated early load; allowlisted instrumentations
- RUM load order per `skills/references/rum-delivery.md`: one init, in `<head>`, no
  `async`/`defer` delay, before `bootstrapApplication`, `createRoot`, `createApp`, or the
  Next.js client entry
- `applicationName` / `deploymentEnvironment` per guide
- Classifier + `setGlobalAttributes` + **host SPA/React route-change listener** (`route.change` span; `document-load` is first document only)
- Custom UX span once per navigation if defined
- Session recording only as the guide specifies (on-demand and/or sampled — not always-on by default)
- Build id / version injection
- Tests: bootstrap, classifier mappings from the schema, custom UX span
- README of every global attribute and cardinality budget
- Optional: CD post to Observability Cloud Events API using **existing** secret references only

Do not start journey/workflow spans in this PR. If the guide is backend-only, implement Collector/agent bootstrap + shared library + propagator — still no invented journeys.

### If shared libraries

Create/extend the language-specific common packages from the guide:

- Composite propagator (trace context + baggage)
- Stamp processor copying allowlisted keys
- `setBaggageEntry` wired **only** at documented call sites
- `injectMessageAttributes` / `extractMessageContext` for listed buses
- Meter helper module (stubs OK if meters are a later slice — export the API)

Unit-test: processor copies baggage to attributes; inject writes `traceparent` + `baggage`; deny-list keys refused if a guard exists.

### If a workflow

1. Wrap each step in a span named **exactly** as the guide.
2. `workflow.name` and `workflow.step` from schema enums (subordinate intent within the
   APM Business Transaction).
   Set and propagate the registered `<org>.bt` global tag and validate the
   `<org>.bt` / `workflow.name` pair from the contract.
3. Span events at documented boundaries.
4. Allowlisted attributes only; money in minor units + currency when amounts exist.
5. On error: `recordException`; span status ERROR.
6. Propagate `traceparent` (and baggage) on backend calls via `context.with`.
7. Never capture card, CVV, full address, email.

Use reviewable commits within each repository leg. The unified work order, not an arbitrary
file count, is the boundary; stop when a leg exceeds its accepted review budget and record
the required follow-up rather than widening scope.

### If custom meters

Add OTel counters/histograms from the guide’s meters section. Dimensions must be schema-approved. Include at least:

- One **business** meter if the schema defines one
- One **execution** meter (transform, handler duration, ack latency, hydration, etc.)

Do not use unbounded ids as dimensions.

## Linked PR requirements

- At most one PR per repository leg, plus the artifact-repository coordination PR.
- Title: `obs(<work-order-id>): <target> — <imperative>`
- Every PR links the work order, coordination PR, and sibling repository PRs.
- List schema keys touched (must already exist in JSON)
- How a reviewer verifies in Splunk Observability Cloud (Business Transaction view, Tag
  Spotlight, `workflow.name`, metric name, Related Content)
- Tests passing locally and one end-to-end verification covering all repository legs.

Do not push with `--force`. Do not skip hooks. Do not add a second RUM vendor.

---

## Audit prompt (read-only, after the PR)

Use a **fresh** turn. Architect or implementer in read-only mode:

```
You are auditing observability for <WORKFLOW or PHASE0>. DO NOT modify code.
Produce docs/observability/audits/<name>-<date>.md answering:
  1. Every new span / meter / global attribute in this slice.
  2. Each attribute vs attribute-schema.json — flag off-list.
  3. PII grep (email regex, card regex, address, phone, ssn, tokens).
  4. Every fetch/XHR/bus publish in a workflow span propagates traceparent
     (and baggage on HTTP; inject on buses).
  5. Exceptions recorded on error paths.
  6. ≥1 test per step / per library API.
  7. Still only one SplunkRum.init (or language SDK start) in the process/page
     when RUM/SDK is in scope.
  8. Telemetry is usable in Splunk Observability Cloud: workflow.name present
     if this is a journey slice; no unbounded ids as metric dimensions;
     applicationName matches the guide.
Exit non-zero (say FAIL) on any PII hit, missing traceparent, second init,
always-on session recorder not in the guide, or off-schema attributes.
```
