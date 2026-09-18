# Prompt 03 — Implement the instrumentation

**Agent:** [`../agents/instrumentation-implementer.agent.md`](../agents/instrumentation-implementer.agent.md)  
**Depends on:** merged (or explicitly approved) Instrumentation Guide + `attribute-schema.json`.  
**Output:** small code PRs. No deploys. No secrets.

Run **once per slice**. If the human does not pick a slice, follow the guide’s phase plan: trust the signal first, then the highest-ranked journey, then meters.

Copy below the line. Set the slice variables.

---

## System reminder

Follow `instrumentation-implementer.agent.md`. Read the guide and `attribute-schema.json` before any edit. Do not invent attributes. Do not enable always-on session replay unless the guide says the human accepted it. Do not call `SplunkRum.init` from an MFE. Diff budget 400 lines. Tests in the same PR. Zero-code agents/annotations are allowed only **together with** the shared library and stamp processor.

Implement so the result works in **Splunk Observability Cloud**: stable `applicationName`, `workflow.name` for APM Business Workflows, low-cardinality tags for MMS, `traceparent` for Related Content, schema-approved meter dimensions. Do not assume journey names from another application.

PII deny list is enforced. If you see tokens in the repo, stop and report. Do not search the repo for unrelated specs.

## Inputs

- Guide: `docs/observability/INSTRUMENTATION-GUIDE.md` (or [path])
- Schema: `docs/observability/attribute-schema.json`
- Additional files attached this session (optional): [ ]
- Repos in scope: [ ]
- **Slice (pick one, or “follow guide phase plan”):**
  - [ ] Phase 0 — signal trust (RUM/APM bootstrap as specified: early load, kill switch, allowlist, classifier, app name, replay policy, **no** journey spans)
  - [ ] Shared libraries only (`@<org>/otel-common` or guide names + stamp processor + baggage boot + message inject/extract)
  - [ ] Workflow: `[name from guide]` steps: `[list]`
  - [ ] Custom meters only: `[schema metric names — at least one business if the domain has one, one execution]`

## Task

Implement **only the selected slice**.

### If Phase 0

Match the guide’s Phase 0 contract. Typical browser work when the guide includes RUM:

- Kill switch; dedicated early load; allowlisted instrumentations
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
2. `workflow.name` and `workflow.step` from schema enums (required for APM Business Workflows).
3. Span events at documented boundaries.
4. Allowlisted attributes only; money in minor units + currency when amounts exist.
5. On error: `recordException`; span status ERROR.
6. Propagate `traceparent` (and baggage) on backend calls via `context.with`.
7. Never capture card, CVV, full address, email.

One commit per step if history style allows; otherwise one PR still one workflow, ≤400 lines. **Stop after 3 steps** and request review.

### If custom meters

Add OTel counters/histograms from the guide’s meters section. Dimensions must be schema-approved. Include at least:

- One **business** meter if the schema defines one
- One **execution** meter (transform, handler duration, ack latency, hydration, etc.)

Do not use unbounded ids as dimensions.

## PR requirements

- Title: `obs: <slice> — <imperative>`
- List schema keys touched (must already exist in JSON)
- How a reviewer verifies in Splunk Observability Cloud (Tag Spotlight, APM Business Workflows, metric name, Related Content)
- Tests passing locally

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
