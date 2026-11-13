# How obengineer works

This page explains what happens at each stage, from `obconfig.yaml` to verified
telemetry, which files each stage reads and writes, and which rules decide what can run
next. For the step-by-step commands, see [End-to-end usage](usage.md).

obengineer is a set of command entry points, agent instructions, skills, and Python
validators. The host model (Cursor, Claude Code, Codex) does the investigation and
writing; the repository files constrain what counts as evidence, what the outputs must
contain, what may change, and how results are checked.

## Pipeline

```text
 obconfig.yaml + artifacts/
        │  /ob-start: validate, hash artifacts, redacted summary
        ▼
 "Proceed with analysis using this configuration? (yes/no)"  ── no ──▶ stop
        │ yes
        ▼
 Evidence: six parallel workstreams
   production · source · artifacts · Observability Cloud · Platform/cloud/messaging · public + security
        │  every fact labelled measured / stated / public / derived
        ▼
 Analysis V<N>                         docs/observability/analysis/<app>/V<N>/
   + contract, schema, map, ledger,    docs/observability/*.json
     verification plan
   + versioned wiki and all work orders wiki/apps/<app>/versions/V<N>/
        │  validation, one PR on analysis-<app>-v<n>
        ▼
 Review in side panel ── comments ──▶ agent commits corrections
        │ "yes"
        ▼
 Acceptance: content digest ─▶ acceptance.yaml, merge, foundation orders Ready
        │
        ├──▶ /ob-implement  foundation orders ─▶ gate opens ─▶ any other order
        │        │            state + revisions: wiki/apps/<app>/implementation/V<N>/
        │        └──▶ /ob-revise  R2, R3 … (no new version)
        ├──▶ /ob-terraform  terraform/apps/<app>/, terraform/portfolio/  (plan only)
        └──▶ /ob-verify     docs/observability/verification/  (read-only)
                 │
                 ▼
         new evidence or inputs ─▶ /ob-start ─▶ V<N+1>
```

## 1. Inputs

`/ob-start` reads exactly two things: the local `obconfig.yaml` and every regular file
under `artifacts.directory` (default `artifacts/`). It validates the config against the
schema in [`obconfig.yaml.template`](../obconfig.yaml.template), hashes each artifact,
and compares the hashes with the previous run so that added and changed files are
reread and deleted files are dropped. It then prints a redacted summary and asks the
proceed question. Only `yes` starts analysis, and that `yes` covers one run of exactly
the configuration and artifacts that were summarized.

Missing optional inputs never block analysis. When a missing fact would materially
improve the result, the analysis lists it on its **Intake recommendations** page.

## 2. Evidence workstreams

Analysis runs six bounded evidence jobs in parallel, as many at once as the host allows:

| Workstream | Sources |
|---|---|
| Production | A read-only browser scan of `surfaces.production_urls`; test or QA URLs are not a substitute. |
| Source and technology | Application source, configuration, dependencies, frameworks, and current instrumentation. |
| Artifacts | Diagrams, prior guides, and exports in `artifacts/`. |
| Observability Cloud | Direct API calls with the configured read token, plus connected MCP tools. |
| Platform, cloud, and messaging | Direct Splunk Platform searches over allowlisted indexes, cloud accounts, and message buses. |
| Public and security | Bounded public research, and the security review allowed by `security_assessment.mode`. |

When a Splunk block is configured, the direct API calls are mandatory; MCP tools
supplement them but cannot replace or relabel their results. A source that fails or is
not configured is recorded as a limitation, never as a fabricated success. Naming and
schema reconciliation happen serially after the jobs return, so parallel workers cannot
invent competing names.

The front-end evidence includes two checks recorded in the contract's
`architecture.frontend`:

- **RUM load order.** The Splunk RUM agent must load in `<head>` ahead of the application
  bundle, without `async`, `defer`, or a dynamic import, and initialize exactly once
  before the framework bootstraps (`bootstrapApplication` in Angular,
  `createRoot(...).render` in React, `createApp(...).mount` in Vue, the client
  instrumentation file or `_document` in Next.js). The result is `correct`, `incorrect`,
  or `unresolved`. `incorrect` always produces at least one foundation work order.
- **CDN delivery.** Analysis records the CDN in front of the site and recommends
  injecting the RUM snippet at the edge rather than in application code. Detailed
  per-CDN guidance lives in [`rum-delivery.md`](../skills/references/rum-delivery.md);
  the Fastly, Akamai, Cloudflare, CloudFront, Azure Front Door, and Google Cloud CDN
  sections are placeholders until the maintainer supplies them.

## 3. Evidence labels

Every fact in the analysis and the provenance ledger carries one label:

| Label | Meaning | Example |
|---|---|---|
| **measured** | Observed in source, production, a tenant API, or a connected tool. | The RUM script tag has `defer` in `index.html`. |
| **stated** | Supplied by a human, usually through `obconfig.yaml`. | `traffic_baseline.rum.sessions_per_day_avg: 40000` |
| **public** | From permitted, cited public research. | An incident on the customer's status page. |
| **derived** | Calculated from the others, with the arithmetic shown. | Estimated monthly spans from request rate × spans per trace. |

Measured evidence wins when sources disagree, and the disagreement stays visible in
`docs/observability/provenance-ledger.json`.

## 4. Analysis outputs

One run produces one immutable version:

```text
docs/observability/analysis/<app>/index.md        version chooser
docs/observability/analysis/<app>/V<N>/index.md   landing page
  overview/ findings/ strategy/ implementation/ use-cases/ workflows/
  business-transactions/ contracts/ operations/ reference/
docs/observability/analysis-contract.json         canonical contract (schema v4)
docs/observability/attribute-schema.json          attributes; dimension-eligible vs attribute-only
docs/observability/implementation-map.json        selectors → work orders → repositories and paths
docs/observability/provenance-ledger.json         sources, labels, and run records
docs/observability/verification-plan.json         read-only exit criteria
```

The landing page opens with the version selector (`[V1] [V2] [V3]`), status, next
steps, and `Changes in this version`, then a table summarizing each area, an
architecture summary, and a priority map of findings and use cases. Every page has a
breadcrumb to `Analysis` and its parent. Pages are relative Markdown read in the host's
side panel; no browser or local server is used. Older versions are never edited and
link only to their own wiki snapshot.

## 5. Wiki

The same run writes the agent-facing wiki under `wiki/apps/<app>/versions/V<N>/`:

```text
wiki/apps/<app>/index.md                                 version list; marks the accepted version
wiki/apps/<app>/versions/V<N>/meta/                      versions, run log, decisions, sanitized config provenance
wiki/apps/<app>/versions/V<N>/implementation/work-orders/<id>.md   every work order
wiki/apps/<app>/versions/V<N>/services/<service>/        architecture, findings, contract, use cases,
                                                         workflows, business transactions, metrics,
                                                         detectors, SLOs, as-code notes per service
```

Each work-order note has YAML frontmatter (kind, parents, subordinates, selectors,
dependencies, repository legs with paths, changes, and tests) that the scripts parse.
Implementation agents load only the selected version's notes, not every version or the
whole wiki.

## 6. Work-order hierarchy and the foundation gate

Work orders are implementation contracts. Each has one kind:

| Kind | Role |
|---|---|
| `foundation` | A prerequisite from a finding or recommendation, not a use case. No parents or subordinates; may depend only on other foundation orders. At most about ten. |
| `use-case` | A complete unit for one use case. Lists its subordinate orders. |
| `workflow` | One workflow; may cross business-transaction boundaries. |
| `business-transaction` | One business transaction (`<org>.bt` value); a shared one can sit under several use cases. |
| `detector`, `alert-condition` | Detector definitions. |
| `dashboard` | Dashboard definitions. |
| `custom-code` | Custom instrumentation, as small as one span or one attribute. |

Every subordinate names its use-case parent and every parent lists its subordinates.
The queue is displayed foundation first, then each use case followed by its workflows,
business transactions, detectors, alert conditions, dashboards, and custom code.

Status moves like this:

| Moment | Foundation orders | All other orders |
|---|---|---|
| Before acceptance | `proposed`; `blocked` if they depend on another order or lack a repository mapping. | `blocked` while any foundation order exists, otherwise `proposed`. |
| After acceptance | Dependency-free, mapped orders become `ready`. | Still `blocked`. |
| All foundation orders `implemented` or `verified` | — | Released: runnable in any order. |

`/ob-implement` asks one question before running a non-foundation order: **Are all
foundation work orders complete?** It answers from the state ledger (stage 8), not from
the accepted notes. An application with no foundation orders releases everything at
acceptance.

A work order whose repository is not known is still written, with
`repository_mapping: unresolved`, no repository legs, and `blocked` status; analysis
never invents a repository or path. The missing mapping appears on Intake
recommendations.

## 7. Acceptance and the content digest

When the PR is ready, the agent asks `Do you accept V<N> and want me to merge this PR?`.
An explicit `yes`:

1. marks eligible foundation orders `ready` (all dependency-free orders when there is no
   foundation);
2. computes a SHA-256 digest over the version's analysis pages, `analysis-contract.json`,
   attribute schema, implementation map, sealed ledger entries, verification plan, and
   wiki snapshot;
3. checks that the same files and bytes exist in the commit being accepted;
4. writes `docs/observability/analysis/<app>/V<N>/acceptance.yaml` with the version,
   commit, digest, PR URL, and timestamp; and
5. commits it to the PR and merges with the repository's merge strategy.

Because the digest covers content rather than commit ancestry, it survives squash and
rebase merges. Every later command (`/ob-implement`, `/ob-revise`, `/ob-terraform`,
`/ob-verify`) first runs `verify_analysis_acceptance.py` and stops if the digest no
longer matches. Changing an accepted file therefore requires a new version.

## 8. State ledger and revisions

Implementation progress and revisions change after acceptance, so they live outside the
digest:

```text
wiki/apps/<app>/implementation/V<N>/state.yaml                  live status, implemented revision, PR URLs
wiki/apps/<app>/implementation/V<N>/revisions/<WO-id>/R<k>.md   revision R2, R3, …
```

`skills/instrumentation-wiki/scripts/work_order_state.py` owns these files with five
subcommands: `init` (create the ledger from the accepted notes), `gate` (decide whether
an order may run), `set-status` (`in-progress`, `implemented`, or `verified`, with PR
URLs), `revise`, and `verify` (check the ledger and revision chain).

`/ob-revise` changes a subordinate order without a new analysis version. The accepted
note is revision R1; each new revision records the reason, the requester's role, and the
attribute, span, and naming changes, and stores the SHA-256 of the previous revision, so
the chain cannot be silently edited. Attribute additions on the schema's deny list are
rejected. Revising an `implemented` or `verified` order sets it to `changed`, and
`/ob-implement <selector> reimplement` is required to run an implemented, verified, or
changed order again. Foundation and use-case orders are not revisable; changing them
needs a new version.

## 9. Implementation pull requests

One `/ob-implement` invocation executes one work order. It requires
`initial_scope.authorized` to be `full`, `repositories`, or `parent_folders`, and it
edits only the repository legs and authorized paths named in the work order. It opens:

- one PR per mapped application repository, titled
  `obs(<work-order-id>): <target> — <imperative>`, listing the schema keys touched, the
  tests run, and how a reviewer confirms the result in Splunk Observability Cloud; and
- one coordination PR in the artifact repository that links them all.

Implementation never deploys, applies Terraform, arms a detector, adds attributes that
are not in the accepted schema, or commits a credential. After review and deployment
proof the agent records the new status in `state.yaml` and reports which order is now
Ready. When Jira is both named and connected in `developer_tools`, it can also create
one linked issue per mapped project; otherwise the work order includes copy-and-paste
issue text.

## 10. Terraform layout

`/ob-terraform` turns the accepted contract into a plan, in parallel with
implementation:

```text
terraform/
  apps/<app>/
    providers.tf variables.tf data.tf imports.tf
    modules/executive/     application rollup: one dashboard group over the app's use-case dashboards, SLOs, KPIs
    modules/sre/           golden signals, detectors, muting rules for change windows, uptime checks
    modules/engineer/      workflow step latency, Tag Spotlight, trace-filtered log views, data links
    modules/platform/      Splunk Platform indexes, HEC, trace_id extraction, saved searches
    environments/<env>/    one workspace per environment; apply runs here
  portfolio/               leadership dashboard: every application's SLO attainment,
                           error-budget burn, detector state, and use-case verification status
```

Every resource traces to a contract section. Existing tenant objects are imported, not
duplicated. Groupings on attribute-only keys are refused. Detectors ship
`disabled = true`, thresholds without a baseline are marked as placeholders, and tokens
are sensitive variables. The portfolio root only reads and charts: it shows an
application without an accepted version as *not yet analyzed* and owns no detectors or
SLOs. Nothing is ever applied by obengineer; a human applies each root.

## 11. Verification

`/ob-verify` runs after deployment and apply. It validates `acceptance.yaml`,
`verification-plan.json`, any human-approved `verification-exclusions.json`, and the
ledger, then makes only read operations (list, get, search, query) against the tenant.
Each eligible criterion is `met`, `unmet`, or `unmeasurable`; each `unmet` row names the
remediation route (`implementation`, `terraform`, `contract-amendment`, or
`human-owner`), the next command, and how to recheck. Results go to
`docs/observability/verification/verification-<app>-<timestamp>.json` and a matching
`.md`, and are appended to the ledger. A criterion a human has approved as unremediable
stays in the human report and ledger but is excluded from the machine results and
metrics.

## 12. The next version

Rerunning `/ob-start` after changing `obconfig.yaml` or `artifacts/` repeats the
pipeline as `V<N+1>`. It reuses accepted names and finding ids, records every resulting
change under `Changes in this version`, and leaves earlier versions untouched. Only the
version marked accepted in `wiki/apps/<app>/index.md` has an executable work-order
queue.

## Safety boundaries

- Production analysis is read-only. Active security checks are limited to the two fixed
  `HEAD` requests of `safe-active` mode.
- Secrets stay in ignored mode-0600 `obconfig.yaml`, are sent only in HTTPS request
  headers, and never appear in chat, arguments, logs, or generated files.
- Code changes need a Ready work order and authorized paths.
- Terraform is planned, never applied. Verification never remediates.
- No step asks for a named engineer, owner, or approver.

## Internals

These mechanics keep runs safe and reproducible; you do not need them to use the tool.

- **One-shot authorization ("claim").** The proceed `yes` writes a local record in
  `.obengineer/` tied to the config digest, the artifact hashes, the command, and the
  intended version. Analysis takes that record exactly once before any network work;
  a repeated or concurrent run fails instead of running twice. Each network step
  re-checks that the inputs still match.
- **Redacted configuration view.** Analysis never reads `obconfig.yaml`. It reads a JSON
  view from `manage_obconfig.py config-projection` that has targets and constraints but
  no secrets. `manage_obconfig.py direct-api` and `safe-active` make the tenant and
  security calls and return redacted results, which go into the ledger. All script
  output goes through one redactor.
- **Publishing exactly what was validated ("finalize" and "dispatch").** After
  generation and validation, the agent stages the output and runs `finalize`, which
  records the exact Git tree. The commit must match that tree. `dispatch` records the
  commit and `verify-dispatch` re-checks it immediately before push and PR creation.
  After the PR is published, `consume` marks the artifact snapshot as analyzed; a
  declined or failed run calls `abort`, which releases the authorization without moving
  that baseline. Edits made after `finalize` belong to the next run.
- **Ledger seal.** At acceptance the ledger's analysis-owned entries are sealed and the
  seal's digest is part of `acceptance.yaml`. Implementation, Terraform, and
  verification can append ledger records but cannot alter sealed ones.
- **Parallel workers.** The host launches the evidence workers; the repository only
  audits the recorded intervals and budgets. If the host cannot run subagents, the PR
  stays a draft and the analysis is reported as blocked rather than run serially and
  called complete.
