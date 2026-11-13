# How obengineer works

This page explains what happens at each stage, from `obconfig.yaml` to verified
telemetry: which files each stage reads and writes, which rules decide what can run
next, and why the outputs are split between a human review site and an agent wiki. For
the step-by-step commands, see [End-to-end usage](usage.md). For running the same loop
on every feature release, see [Continuous integration](ci.md).

## Runtime model

obengineer is not an application with a long-running process. It is a versioned set of
command entry points, agent instructions, skills, references, and Python validators. The
host model (Cursor, Claude Code, Codex) does the investigation and writing; the
repository files constrain what counts as evidence, what the outputs must contain, what
may change, and how results are checked.

Every invocation follows the same path:

```text
host command (/ob-analyze)
  → command entry point            commands/ob-analyze.md
  → agent definition               agents/instrumentation-architect.agent.md
  → ordered run contract           prompts/01-analyze-application.md, prompts/02-build-instrumentation-wiki.md
  → task skills                    skills/instrumentation-analyze/, skills/instrumentation-wiki/, …
  → canonical references           skills/references/*.md
  → engagement state               obconfig.yaml (redacted view), artifacts/, prior versions
  → deterministic validators       skills/*/scripts/*.py
```

A command file stays short and stable. It names the agent, the run contract, the skills,
and the required outputs, but it does not contain the procedure. The procedure lives in
reviewable files, so a review of those files is a review of what the agent will do.

### Repository components

| Path | Role |
|---|---|
| `commands/` | The `/ob-*` entry points copied into each host at install time. |
| `agents/` | Operating doctrine and boundaries for the architect, implementer, Terraform, and verifier roles. |
| `prompts/` | Ordered run contracts: load configuration, analyze, build the wiki, implement, generate Terraform, verify. |
| `skills/` | Canonical task procedures, their scripts, schemas, and tests. |
| `skills/references/` | Shared specifications used by several skills, one authority per fact. |
| `templates/` | The analysis-site page templates and the memory-repository starter. |
| `examples/ci/` | Starting-point CI workflows described in [Continuous integration](ci.md). |
| `scripts/` | Installer, plugin synchronization, and guided credential setup. |
| `plugins/obengineer/` | Self-contained plugin bundle generated from `skills/`; never hand-edited. |
| `.cursor/skills/`, `.agents/skills/` | Generated links to the canonical skills for repository-local discovery. |
| `tests/` | Deterministic contract tests over the commands, skills, and references. |

### One authority per fact

Each cross-cutting fact is defined in exactly one file, and every other file links to it
instead of restating it. When this page and a reference disagree, the reference wins.

| Fact | Authority |
|---|---|
| Configuration fields, defaults, and effects | [`obconfig.yaml.template`](../obconfig.yaml.template) |
| Analysis site layout, versions, breadcrumbs, handoff | [`analysis-site.md`](../skills/references/analysis-site.md) |
| Agent wiki layout, frontmatter, host pointers | [`agent-wiki.md`](../skills/references/agent-wiki.md) |
| Work-order kinds, selectors, foundation gate, state ledger | [`implementation-work-orders.md`](../skills/references/implementation-work-orders.md) |
| Branches, PR review, acceptance, merge | [`analysis-run-lifecycle.md`](../skills/references/analysis-run-lifecycle.md) |
| Repeat-run (delta) behavior | [`incremental-runs.md`](../skills/references/incremental-runs.md) |
| RUM load order and CDN delivery | [`rum-delivery.md`](../skills/references/rum-delivery.md) |
| Contract enforcement in CI | [`ci-integration.md`](../skills/references/ci-integration.md) |
| Evidence and run state | [`provenance-ledger.md`](../skills/references/provenance-ledger.md) |
| Baggage key and byte budget | [`baggage-budget.md`](../skills/references/baggage-budget.md) |
| Terraform resource names | [`splunk-terraform-providers.md`](../skills/references/splunk-terraform-providers.md) |
| Verification and remediation routing | [`verification-run.md`](../skills/references/verification-run.md) |

## Pipeline

```text
 obconfig.yaml + artifacts/
        │  first run: /ob-start creates obconfig.yaml, then validates it
        │  later runs: /ob-analyze validates the edited file and rehashes artifacts
        ▼
 redacted summary + "Proceed with analysis using this configuration? (yes/no)" ── no ──▶ stop
        │ yes
        ▼
 Evidence: six parallel workstreams
   production · source · artifacts · Observability Cloud · Platform/cloud/messaging · public + security
        │  every fact labelled measured / stated / public / derived
        ▼
 Analysis V<N>   (for humans)         docs/observability/analysis/<app>/V<N>/
   + contract, schema, map, ledger,    docs/observability/*.json
     verification plan
   + agent wiki and all work orders    wiki/apps/<app>/versions/V<N>/   (for agents)
        │  validation, one PR on analysis-<app>-v<n>
        ▼
 Review in side panel ── comments ──▶ agent commits corrections
        │ "yes"
        ▼
 Acceptance: content digest ─▶ acceptance.yaml, merge, foundation orders Ready
        │
        ├──▶ /ob-implement  foundation orders ─▶ gate opens ─▶ any other order
        │        │            state + revisions: wiki/apps/<app>/implementation/V<N>/
        │        ├──▶ /ob-revise  R2, R3 … (no new version) ─▶ /ob-implement … reimplement
        │        └──▶ CI contract checks on every application pull request
        ├──▶ /ob-terraform  terraform/apps/<app>/, terraform/portfolio/  (plan only)
        └──▶ /ob-verify     docs/observability/verification/  (read-only)
                 │
                 ▼
   new feature, evidence, or inputs ─▶ edit obconfig.yaml or artifacts/ ─▶ /ob-analyze ─▶ V<N+1>
```

## 1. Inputs and the proceed gate

Analysis reads exactly two things: the local `obconfig.yaml` and every regular file under
`artifacts.directory` (default `artifacts/`).

- **First run.** `/ob-start` creates `obconfig.yaml` from the template and stops with
  `Created local obconfig.yaml. Edit it and rerun /ob-start.` After you fill in the
  minimum fields, `/ob-start` validates the file and runs the first analysis, `V1`.
- **Every later run.** Edit `obconfig.yaml` or `artifacts/` and run `/ob-analyze`. It
  performs the same validation itself; when `obconfig.yaml` does not exist, it tells you
  to run `/ob-start` first.

In both cases the command validates the config against the schema in
[`obconfig.yaml.template`](../obconfig.yaml.template), offers a repair gate when the
YAML is invalid, hashes each artifact, and compares the hashes with the previous run so
that added and changed files are reread and deleted files are dropped. It then prints a
redacted summary and asks `Proceed with analysis using this configuration? (yes/no)`.
Only `yes` starts analysis, and that `yes` covers one run of exactly the configuration
and artifacts that were summarized.

Missing optional inputs never block analysis. When a missing fact would materially
improve the result, the analysis lists it on its **Intake recommendations** page
(`reference/intake-recommendations.md`); nobody is asked to type `unknown`.

## 2. Evidence workstreams

Analysis runs six bounded evidence jobs in parallel, as many at once as the host allows,
with one concurrency slot reserved for the coordinating agent:

| Workstream | Sources |
|---|---|
| Production | A read-only browser scan of `surfaces.production_urls`; test or QA URLs are not a substitute. |
| Source and technology | Application source, configuration, dependencies, frameworks, and current instrumentation. |
| Artifacts | Diagrams, prior guides, prior scans of the same site, and exports in `artifacts/`. |
| Observability Cloud | Direct API calls with the configured read token, plus connected MCP tools. |
| Platform, cloud, and messaging | Direct Splunk Platform searches over allowlisted indexes, cloud accounts, and message buses. |
| Public and security | Bounded public research, and the security review allowed by `security_assessment.mode`. |

When a Splunk block is configured, the direct API calls are mandatory; MCP tools
supplement them but cannot replace or relabel their results. A source that fails or is
not configured is recorded as a limitation, never as a fabricated success. Naming and
schema reconciliation happen serially after the jobs return, so parallel workers cannot
invent competing names for the same workflow or attribute.

The production scan checks page timings, whether an HTTP success response actually
contains valid content, router behavior and client-side route changes, provider
initialization, competing RUM or EUM agents (`constraints.competing_eum_agents`), the
Content Security Policy, consent handling, third-party scripts, beacons, and
authenticated surfaces when a dummy login is configured. Within the security mode, the
same evidence feeds an API inventory and checks for exposed credentials and sensitive
data, OWASP Top 10:2025, and OWASP API Security Top 10:2023; a confirmed or
high-confidence vulnerability becomes a critical finding with a P0 fix.

### RUM load order and CDN delivery

When the target has a web front-end, the analysis records two results in the contract's
`architecture.frontend` and turns them into foundation work:

- **RUM load order.** The Splunk RUM agent must load in `<head>` ahead of the application
  bundle, without `async`, `defer`, or a dynamic import, and initialize exactly once
  before the framework bootstraps (`bootstrapApplication` in Angular,
  `createRoot(...).render` in React, `createApp(...).mount` in Vue, the client
  instrumentation file or `_document` in Next.js). The result is `correct`, `incorrect`,
  or `unresolved`; `unresolved` is used when source or the production page is not
  available, never as a guess. `incorrect` always produces at least one foundation work
  order, because spans started before initialization carry no session and the first
  navigation and bootstrap errors are lost.
- **CDN delivery.** Analysis records the CDN in front of the site (from evidence and
  `surfaces.edge_cdn`) and recommends injecting the RUM snippet at the edge rather than
  in application code. Edge injection puts the agent first in `<head>` on every HTML
  response, keeps one initialization across applications, and lets the token or agent
  version change without an application release. The recommendation never contains a
  RUM token.

The check itself is defined in [`rum-delivery.md`](../skills/references/rum-delivery.md).
CDN-specific injection steps live in one reference per CDN under
`skills/references/cdn/`, indexed by [`cdn/README.md`](../skills/references/cdn/README.md).
[`cdn/fastly.md`](../skills/references/cdn/fastly.md) is the reference implementation
(Fastly classic VCL with an Edge Side Include in the origin `<head>`, plus rollout,
kill-switch, and rollback steps). Akamai, Cloudflare, CloudFront, Azure Front Door, and
Google Cloud CDN are pending; until a CDN has its own file, the analysis cites the index
and the Fastly structure is adapted. The analysis links the matching CDN reference from
its **foundation** section only when the target has a web front-end; a back-end-only
target gets no RUM or CDN content.

## 3. Evidence labels

Every fact in the analysis and the provenance ledger carries one label:

| Label | Meaning | Example |
|---|---|---|
| **measured** | Observed in source, production, a tenant API, or a connected tool. | The RUM script tag has `defer` in `index.html`. |
| **stated** | Supplied by a human, usually through `obconfig.yaml`. | `traffic_baseline.rum.sessions_per_day_avg: 40000` |
| **public** | From permitted, cited public research. | An incident on the customer's status page. |
| **derived** | Calculated from the others, with the arithmetic shown. | Estimated monthly spans from request rate × spans per trace. |

Measured evidence wins when sources disagree, and the disagreement stays visible in
`docs/observability/provenance-ledger.json`, because stale customer documentation is
itself useful evidence. A missing source limits only the conclusions that depend on it:
unknown facts stay unknown and are never filled with industry benchmarks or values from
another engagement. Examples in the canonical references use placeholders such as
`<app>` and `<service>`; they describe shape, not proposed names.

## 4. From evidence to contract

The analysis turns evidence into one canonical contract,
`docs/observability/analysis-contract.json` (schema v4), and renders every page from it.
The renderer is deterministic: the same validated JSON produces byte-identical Markdown.
The contract contains:

- the observed architecture, technology, and current telemetry, including usage against
  enforced system limits;
- critical findings with evidence, confidence, impact, remediation, and verification;
- use cases, each leading to the business transactions and workflows it depends on;
- bounded `<org>.bt` business-transaction values and their registered `workflow.name`
  pairs;
- cross-cutting attributes, W3C Baggage propagation, span trees, events, metrics, and
  Collector processing;
- dimension eligibility, decided by cardinality arithmetic rather than preference;
- detectors with thresholds, SLOs with error budgets, and persona dashboards; and
- the implementation path, every work order, and the read-only verification plan.

A semantic gate rejects unresolved placeholders, empty pages, unbounded meters, detectors
without thresholds, objectives without error budgets, incorrect Collector ordering,
inconsistent cardinality arithmetic, broken links, and missing breadcrumbs.

**Pricing without silently constraining.** When tenant measurement returns usage or an
enforced `sf.org.limit.*` value, or the design's projected cost is material, analysis
writes a separate usage and enforced-limit exposure appendix for the account team. An
enforced limit is never relabeled as a purchased entitlement, and the customer-facing
strategy shows technical dimension arithmetic but no commercial claims. Keeping the
audiences separate stops a design review from becoming a licensing negotiation. See
[`entitlement-exposure.md`](../skills/references/entitlement-exposure.md).

## 5. Analysis outputs

One run produces one immutable version:

```text
docs/observability/analysis/<app>/index.md        version chooser
docs/observability/analysis/<app>/V<N>/index.md   landing page
  overview/ findings/ strategy/ implementation/ use-cases/ workflows/
  business-transactions/ contracts/ operations/ reference/
docs/observability/analysis-contract.json         canonical contract (schema v4)
docs/observability/attribute-schema.json          attributes; dimension-eligible vs attribute-only; deny list
docs/observability/implementation-map.json        selectors → work orders → repositories and paths
docs/observability/provenance-ledger.json         sources, labels, and run records
docs/observability/verification-plan.json         read-only exit criteria
wiki/apps/<app>/versions/V<N>/                     agent wiki and every work order
```

The landing page opens with the version selector (`[V1] [V2] [V3]`), status, next
steps, and `Changes in this version`, then a table summarizing each area, an
architecture summary, and a priority map of findings and use cases. Every page has a
breadcrumb to `Analysis` and its parent. Pages are relative Markdown read in the host's
side panel; no browser or local server is used. Older versions are never edited and
link only to their own wiki snapshot. A Word summary under 20 pages is available through
`/ob-render`; it is generated from the Markdown and is never the contract.

## 6. Two documentation surfaces: the analysis site and the agent wiki

Every analysis run writes the same accepted decisions to two places, in the same version
and the same PR. They exist because humans and coding agents read in opposite ways.

| | Analysis site | Agent wiki |
|---|---|---|
| Path | `docs/observability/analysis/<app>/V<N>/` | `wiki/apps/<app>/versions/V<N>/` |
| Reader | Reviewers: architects, SREs, engineering leads, the account team | Coding agents running `/ob-implement`, `/ob-revise`, `/ob-terraform`, and CI jobs |
| Shape | A long linked index: a landing page that summarizes every area, then detail pages with breadcrumbs | Small addressable notes, one subject per note, with YAML frontmatter and `[[wikilinks]]` |
| Purpose | Decide whether the strategy is right and accept it | Retrieve exactly the context one work order needs, and nothing else |
| Authority | Review narrative and strategy | Per-object spans, events, thresholds, and the work-order queue |
| Defined by | [`analysis-site.md`](../skills/references/analysis-site.md) | [`agent-wiki.md`](../skills/references/agent-wiki.md) |

**Why not one document.** The original deliverable was a single 40 to 150 page Word
document. Reviewers could not navigate it, and an implementation agent could not load it
without spending most of its context on material unrelated to the change in hand. A
separate recommendations document duplicated the analysis and drifted from it. obengineer
therefore keeps one narrative for humans and splits the same accepted catalogue into
retrievable notes for agents. The wiki is not a second customer document: it never
restates a landing-page section verbatim, and its indexes link the canonical detail
rather than repeating it.

**The analysis site** is what the PR reviewer opens. Its landing page summarizes
architecture, findings, strategy, implementation path, work orders, use cases,
workflows, business transactions, shared contracts, operations, and reference, and links
each to a nonempty detail page. A reviewer can move from a finding to a use case to a
workflow to a business transaction to a work order and back without searching. Work-order
rows on the site link into the wiki rather than copying repository legs or code detail.

**The agent wiki** is what agents load. Its layout is:

```text
wiki/apps/<app>/index.md                                 version list; marks the accepted version
wiki/apps/<app>/versions/V<N>/index.md                   version map and analysis breadcrumb
wiki/apps/<app>/versions/V<N>/meta/                      versions, run log, decisions, sanitized config provenance
wiki/apps/<app>/versions/V<N>/implementation/work-orders/<id>.md   every work order
wiki/apps/<app>/versions/V<N>/services/<service>/        architecture, findings, contract, use cases,
                                                         workflows, business transactions, metrics,
                                                         detectors, SLOs, business, as-code notes
wiki/apps/<app>/implementation/V<N>/                     state ledger and revisions (outside the digest)
```

Four rules make it useful to agents:

- **Retrieval rule.** Host pointer files (`.cursor/rules/obengineer-wiki.mdc`,
  `CLAUDE.md`, and `AGENTS.md` in the artifact repository) tell every agent: before
  changing instrumentation, read `wiki/apps/<app>/index.md`, resolve the accepted
  version, then load only the service, object, contract, and work-order notes in scope.
  Do not load every version or the whole wiki. The pointers point; they do not copy the
  contract.
- **A note earns its file.** A workflow, detector, or objective gets its own note only
  when it carries spans, attributes, a threshold, an objective, or a work order. Until
  then it is a line in its parent catalogue, so the wiki stays small enough to navigate.
- **Machine-readable work orders.** Each work-order note has frontmatter (`kind`,
  `parents`, `subordinates`, `selectors`, `depends_on`, `repository_legs` with paths,
  changes, and tests) that the scripts parse with `safe_load`, plus reverse links to the
  findings, use cases, workflows, business transactions, and verification criteria it
  serves.
- **Memory across runs.** `meta/run-log.md`, `meta/versions.md`, and `meta/decisions.md`
  record what each run produced, what the design was built against, and what humans
  accepted or rejected. A repeat run reads them first, which is what makes it a delta
  instead of a rewrite, and what makes a CI pipeline possible at all.

`verify_wiki.py wiki/apps/<app>/versions/V<N>` checks required paths and frontmatter,
breadcrumbs, relative links and unambiguous wikilinks, index counts, work-order
dependencies and reverse links, the accepted-version pointer, schema and provenance
references, host pointers, and credential-shaped values.

## 7. Work-order hierarchy and the foundation gate

Work orders are implementation contracts. Each has one kind:

| Kind | Role |
|---|---|
| `foundation` | A prerequisite from a finding or recommendation, not a use case. No parents or subordinates; may depend only on other foundation orders. At most about ten. |
| `use-case` | A complete unit for one use case. Lists its subordinate orders. |
| `workflow` | One workflow; belongs to exactly one business transaction. |
| `business-transaction` | One business transaction (`<org>.bt` value); a shared one can sit under several use cases. |
| `detector`, `alert-condition` | Detector definitions. |
| `dashboard` | Dashboard definitions. |
| `custom-code` | Custom instrumentation, as small as one span or one attribute. |

A use case maps to one or more business transactions, each business transaction is made
up of one or more workflows, and **each workflow belongs to exactly one business
transaction**. The schema v4 contract validator rejects a workflow listed by two business
transactions or by none. In Splunk APM the business transaction is a Business
Transaction rule of type *Global tag* on the bounded `<org>.bt` span tag, which is set at
the earliest known business surface, propagated across process and repository
boundaries, and never derived from a raw URL. `workflow.name` is the finer-grained
intent inside it.

Every subordinate names its use-case parent and every parent lists its subordinates.
The queue is displayed foundation first, then each use case followed by its workflows,
business transactions, detectors, alert conditions, dashboards, and custom code. The
first foundation order installs the deterministic contract checks (schema agreement,
single initialization, workflow registry, baggage allowlist, and deny list) before any
journey code; see [Continuous integration](ci.md#contract-checks-on-every-pull-request).

Status moves like this:

| Moment | Foundation orders | All other orders |
|---|---|---|
| Before acceptance | `proposed`; `blocked` if they depend on another order or lack a repository mapping. | `blocked` while any foundation order exists, otherwise `proposed`. |
| After acceptance | Dependency-free, mapped orders become `ready`. | Still `blocked`. |
| All foundation orders `implemented` or `verified` | — | Released: runnable in any order. |

`/ob-implement` asks one question before running a non-foundation order: **Are all
foundation work orders complete?** It answers from the state ledger (section 9), not
from the accepted notes. An application with no foundation orders releases everything at
acceptance.

A work order whose repository is not known is still written, with
`repository_mapping: unresolved`, no repository legs, and `blocked` status; analysis
never invents a repository or path. The missing mapping appears on Intake
recommendations.

## 8. Acceptance and the content digest

Before acceptance, obengineer may analyze and revise documentation freely. After
acceptance, names, mappings, and schema decisions become dependencies for code,
dashboards, and detectors. When the PR is ready, the agent asks
`Do you accept V<N> and want me to merge this PR?`. An explicit `yes`:

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
longer matches. Changing an accepted file therefore requires a new version. Nobody copies
a commit SHA or supplies a name.

## 9. State ledger and revisions

Implementation progress and revisions change after acceptance, so they live outside the
digest:

```text
wiki/apps/<app>/implementation/V<N>/state.yaml                  live status, implemented revision, PR URLs
wiki/apps/<app>/implementation/V<N>/revisions/<WO-id>/R<k>.md   revision R2, R3, …
```

`skills/instrumentation-wiki/scripts/work_order_state.py` owns these files with six
subcommands, each taking `--repo . --app <app> --version V<N>`:

| Subcommand | Does |
|---|---|
| `init` | Creates the ledger from the accepted notes on first use. |
| `gate --work-order ID [--reimplement]` | Decides whether an order may run and lists its revision paths. |
| `set-status --work-order ID --status S [--pr URL]` | Records `in-progress`, `implemented`, or `verified` with PR URLs. |
| `revise --work-order ID --file change.yaml` | Appends the next revision. |
| `show --work-order ID` | Applies every revision in order and prints the cumulative `effective_changes`. |
| `verify` | Checks the ledger and the revision hash chain. |

`/ob-revise` changes a subordinate order without a new analysis version. The accepted
note is revision R1; each new revision records the reason, the requester's role (never a
name), and the attribute, span, and naming changes, and stores the SHA-256 of the
previous revision, so the chain cannot be silently edited. Attribute additions on the
schema's deny list are rejected. The revision and ledger change go into one PR in the
artifact repository, merged only after an explicit `yes`.

Implementation always loads the accepted note plus every revision and implements the
cumulative changes, not only the latest one. An order counts as complete only when it is
`implemented` or `verified` at its current revision. Revising an `implemented` or
`verified` order therefore sets it to `changed`, and
`/ob-implement work-order:<id> reimplement` is required to run an implemented,
verified, or changed order again.

Foundation and use-case orders are not revisable: a use case changes through its
subordinate orders, and a foundation change needs a new version (edit `obconfig.yaml` or
`artifacts/`, then run `/ob-analyze`). A version accepted before work-order kinds
existed gets a `legacy` ledger with no foundation gate; its orders run once their
dependencies are complete, and they cannot be revised.

## 10. Implementation pull requests

One `/ob-implement` invocation executes one work order, selected by
`work-order:`, `use-case:`, `workflow:`, `business-transaction:`, `detector:`,
`alert-condition:`, `dashboard:`, `custom-code:`, `objective:`, or `config:`. It
requires `initial_scope.authorized` to be `full`, `repositories`, or `parent_folders`;
with `unknown` it stops and asks engineering for scope instead of adopting every
repository a connected host can see. It edits only the repository legs and authorized
paths named in the work order, reading:

- the analysis for intent;
- `attribute-schema.json` for allowed keys, dimensions, and the deny list;
- the relevant workflow, contract, and work-order notes and their revisions; and
- `implementation-map.json` and `initial_scope` for repository and path authorization.

It stops when required design is missing, because inventing an attribute in code would
make the accepted analysis, schema, wiki, dashboards, and code disagree. Changes inside
an order are sequenced by dependency and trust: the shared library and single provider
initialization precede journeys, identity and propagation precede meters, and signal
production precedes alerting.

It opens:

- one PR per mapped application repository, titled
  `obs(<work-order-id>): <target> — <imperative>`, listing the schema keys touched, the
  tests run, and how a reviewer confirms the result in Splunk Observability Cloud; and
- one coordination PR in the artifact repository that links them all.

Typical changes are the shared OTel library, provider initialization, the baggage stamp
processor, backend propagation, message-bus inject and extract, workflow spans and span
events, custom meters, Collector configuration, and the CI checks that keep the contract
enforced. Implementation never deploys, applies Terraform, arms a detector, adds
attributes that are not in the accepted schema, or commits a credential. After review
and deployment proof the agent records the new status in `state.yaml` and reports which
order is now Ready. When Jira is both named and connected in `developer_tools`, it can
also create one linked issue per mapped project; otherwise the work order includes
copy-and-paste issue text.

## 11. Terraform layout

`/ob-terraform` turns the accepted contract into a plan, in parallel with
implementation. Before writing HCL it maps each contract item to a persona, a provider
resource, the dimensions it needs, and its initial armed state:

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

- **Application rollup.** The per-application `executive` module is one dashboard group
  that rolls up the application's use-case dashboards and links its detectors, so a
  leader reads one application without opening each use case.
- **Leadership portfolio.** `terraform/portfolio/` is a separate root with one dashboard
  across every application. It builds each application's tiles only from that
  application's accepted version and verification results, shows an application without
  an accepted version as *not yet analyzed*, and owns no detectors or SLOs.

Every resource carries a comment naming its contract section. Existing tenant objects are
imported, not duplicated; when inventory is unavailable, import IDs stay `TODO` and the
handover warns about duplication risk. A grouping on an attribute-only key is refused
rather than producing an empty chart. Detectors ship `disabled = true`, thresholds
without a baseline are marked as placeholders, and tokens are sensitive variables. The
run executes `terraform fmt`, `validate`, and `plan` where credentials allow, or reports
"schema-checked" when they do not. Nothing is ever applied by obengineer; a human applies
each root from its environment directory.

## 12. Verification

`/ob-verify` runs after deployment and apply. It validates `acceptance.yaml`,
`verification-plan.json`, any human-approved `verification-exclusions.json`, and the
ledger, then makes only read operations (list, get, search, query) against the tenant.
Each eligible criterion is `met`, `unmet`, or `unmeasurable`; each `unmet` row names the
expected and observed values, the remediation route (`implementation`, `terraform`,
`contract-amendment`, or `human-owner`), the next command, and how to recheck. Results
go to `docs/observability/verification/verification-<app>-<timestamp>.json` and a
matching `.md`, and are appended to the ledger. In CI, `unmet` fails the job and is
listed in the job summary.

Only a human can approve a criterion as unremediable. An approved exclusion stays in the
human report and ledger but is excluded from machine results and metric denominators.
Outcome metrics (schema miss rate, dimension miss rate, detector disarm rate, and
not-in-evidence reversal rate) always publish numerator, denominator, and measurement
coverage. Reusable defects can be published as anonymized GitHub issues after a preview;
see [`outcome-metrics.md`](../skills/references/outcome-metrics.md) and
[`outcome-issues.md`](../skills/references/outcome-issues.md).

## 13. The next version

After the first run, the loop is: edit `obconfig.yaml` or `artifacts/`, run
`/ob-analyze`, review the redacted summary, and answer the proceed question. `yes`
produces `V<N+1>` in its own directory and PR. Only the version marked accepted in
`wiki/apps/<app>/index.md` has an executable work-order queue.

A repeat run is a delta, not the first analysis again. Before scanning, it reads the
prior version's run log, component versions, decisions (including rejected designs), the
accepted business-transaction and workflow names, and finding frontmatter; reading after
scanning would let the scan invent names that already have code and dashboards attached.
It then compares the current production scan with every prior scan of the same site and
sorts each changed surface into changes, merges, or additions.

The new version opens with `Changes in this version` and reports:

- **New surfaces and services.** Routes, bundles, endpoints, queues, and services that
  did not exist at the last run, whether each is instrumented, and the business
  transaction and workflow each needs. This is the most valuable output of a repeat run:
  newly shipped, uninstrumented code produces no telemetry and therefore no gap in any
  chart. Every such surface gets a work order.
- **Removed or retired surfaces.** Their notes move to `status: retired` and their
  detectors and dashboards are named for removal, because an alert on a deleted service
  looks like a silent outage forever.
- **Drift.** Where code, contract, and tenant diverge: an unregistered `workflow.name`,
  an attribute absent from the schema, or a dimension promoted without budget. Each item
  names whether the code or the contract changes.
- **Findings carried forward.** `F-01` stays `F-01` for the life of the application,
  shown as `fixed`, `open`, `regressed`, or `risk-accepted`; new findings continue the
  sequence.
- **Work-order comparison.** Each prior order is marked retained, changed, superseded,
  implemented, or verified.

Catalogues are additive, and accepted identifiers do not change for style. Renaming a
`<org>.bt` or `workflow.name` value, an attribute key, a finding ID, or an SLI name is a
migration: the version states the old and new values, what must be reconfigured, and the
order in which code and configuration cut over. Earlier versions remain readable and
unchanged. The rules are in
[`incremental-runs.md`](../skills/references/incremental-runs.md); the CI form of this
loop is in [Continuous integration](ci.md).

## Safety boundaries

- Production analysis is read-only. Active security checks are limited to the two fixed
  `HEAD` requests of `safe-active` mode, against origins you authorize.
- Secrets stay in ignored mode-0600 `obconfig.yaml`, are sent only in HTTPS request
  headers, and never appear in chat, arguments, logs, or generated files. A dummy login
  used for authenticated scanning must be rotated by its owner after analysis;
  obengineer has no credential-provider integration that can rotate it.
- Code changes need a Ready work order and authorized paths, and never widen the
  accepted attribute schema.
- Terraform is planned, never applied; detectors ship disabled until their signals are
  verified.
- Verification reads and routes remediation; it never remediates.
- No step asks for a named engineer, owner, or approver.

## Deterministic and model-driven parts

| Model-driven | Tool-executed checks |
|---|---|
| Evidence interpretation, architecture mapping, workflow discovery, recommendation writing | Configuration validation, artifact hashing, and the one-shot authorization claim |
| Source and production-surface analysis | Contract schema validation and deterministic site rendering |
| Mapping findings to remediation and work orders | Analysis-site, wiki, implementation-map, and provenance-ledger verifiers |
| Choosing bounded attributes from evidence | Acceptance digest verification |
| Producing application changes within a work order | Foundation gate, state ledger, and revision hash chain (`work_order_state.py`) |
| Mapping accepted requirements into Terraform | `terraform fmt`, `validate`, and provider-schema checks; `plan` depends on external state |
| Writing CI checks for the target repository | The CI checks themselves, which run without a model |

The model-driven parts vary with available evidence. Canonical contracts, stored state,
acceptance gates, and deterministic verification are the control surface that keeps
those variations reviewable.

## Internals

These mechanics keep runs safe and reproducible; you do not need them to use the tool.

- **One-shot authorization ("claim").** The proceed `yes` writes a local record in
  `.obengineer/` tied to the config digest, the artifact hashes, the command
  (`ob-start` or `ob-analyze`), and the intended version. Analysis takes that record
  exactly once before any network work; a repeated or concurrent run fails instead of
  running twice. Each network step re-checks that the inputs still match.
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
