# Versioned analysis review requirements

Traceable requirements for the linked analysis site. The authoring authorities are
`skills/references/analysis-site.md` and the canonical
`skills/instrumentation-analyze/schemas/analysis-contract.schema.json`.

## Artifacts

| ID | Requirement | Verified by |
|---|---|---|
| R1 | Every run emits `analysis-contract.json`, linked Markdown, schema, implementation map, ledger, verification plan, versioned wiki, and work orders | `make qa-analysis`; acceptance verifier |
| R2 | The same validated contract renders byte-identical Markdown | deterministic renderer test |
| R3 | Word is optional, generated, and under 20 pages | Word renderer/verifier when requested |
| R4 | No credential-shaped value reaches any artifact | contract/site/wiki credential scans |
| R5 | Every accepted artifact is content-digest bound | acceptance verifier |

## Landing and navigation

| ID | Requirement | Verified by |
|---|---|---|
| R6 | The landing page contains status, next steps, changes, and linked substantive summaries | analysis-site verifier |
| R7 | Contents order is Architecture, Technology, Current telemetry, Findings, Strategy, Path, Work orders, Use cases, Workflows, Business transactions, Contracts, Operations, Reference | renderer and contract tests |
| R8 | Observed architecture is substantive on the landing page | analysis contract semantic gate |
| R9 | Every content row links a nonempty detail view in the same immutable version | link and semantic verifier |
| R10 | Every detail page has an Analysis breadcrumb, related links, and next review step | site verifier |
| R11 | No browser, localhost server, or high port is required | site verifier and workflow contract tests |

## Content depth

| ID | Requirement | Verified by |
|---|---|---|
| R12 | Architecture covers client composition, route model, init owner, backends, accounts, buses, downstreams, third-party consequences, diagrams, and failure points | contract schema and semantic validator |
| R13 | Technology and Current telemetry are first-class evidence-linked views | contract schema and renderer tests |
| R14 | Findings carry evidence, confidence, exposure, risk, remediation, affected objects/work orders, and runnable verification | semantic validator |
| R15 | Business transactions have bounded grouping values, owning artifacts, exhaustive workflow membership, set/propagation rules, tenant configuration, and proof | semantic validator |
| R16 | Workflows have boundaries, span trees, events, bounded metrics, joins, dashboard, detectors, objectives, code locations, verification, and work orders | semantic validator |
| R17 | Use cases have narrative, question, signals, metrics, dashboard, thresholded detectors, objective/error budget, join type, proof, and work orders | semantic validator |
| R18 | Cross-cutting contracts include one init, SPA route code, allowlisted baggage stamp, identity write, backend propagator, bus propagation, attribution, Collector OTTL/redaction/order, and cardinality arithmetic | semantic validator |
| R19 | Operations include dashboard hierarchy, detector catalogue, objectives, release overlays, log correlation, conditional Synthetics/ThousandEyes, and verification | semantic validator |
| R20 | Every discovered object has an accepted, deferred, rejected, or unresolved disposition with evidence | analysis contract and live QA |

## Performance and orchestration

| ID | Requirement | Verified by |
|---|---|---|
| R21 | `/ob-start` emits the first required question locally before discovery and within five seconds | run-context tests and live QA |
| R22 | Analysis begins only after an exact `no` at optional review | run-context state tests |
| R23 | At most six evidence jobs run with one coordinator slot reserved | manifest validator |
| R24 | When two or more jobs are runnable, audited intervals overlap | worker-result validator |
| R25 | Representative validation and rendering stay within recorded budgets | `make qa-analysis` |

## Version and implementation

| ID | Requirement | Verified by |
|---|---|---|
| R26 | `[V1] [V2] ...` versions are immutable and do not link newer detail | site verifier |
| R27 | Analysis creates the complete work-order queue before acceptance | wiki and contract validators |
| R28 | Acceptance changes only eligible proposed orders to Ready | acceptance and wiki tests |
| R29 | Implementation consumes one Ready order from the accepted version | implement command/skill tests |
| R30 | Verification uses stable `source_ref` values for new plans and reads legacy plans only for migration | verification v1/v2 tests |
