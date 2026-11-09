# End-to-end usage

obengineer is a gated workflow, not a single generator:

```text
intake → analyze → human acceptance → wiki
                                  ├─ implement one slice at a time
                                  └─ build Terraform and a plan
```

`review` independently grades artifacts. `render` rebuilds the Word representation
from Markdown.

Run the commands from the repository where obengineer was installed. Paths are relative
to that workspace unless an absolute path is supplied.

## Before the first run

Prepare:

- the current production URL;
- source repositories and architecture diagrams;
- the application and customer identifiers;
- Splunk realm, org, environments, and approved Enterprise indexes;
- any existing analysis or schema for this same application;
- business context and known incidents;
- entitlement and traffic baselines when available;
- privacy, consent, residency, and deployment constraints; and
- the developer tools and MCP integrations already available.

`unknown` is a valid answer. An explicit gap is safer than a guessed value.

Configure `.env` and MCP integrations as described in
[Configuration](configuration.md). Remove credentials from HAR files, HTML captures,
sample environment files, and diagrams before adding them to the workspace.

## Run 0: intake

```text
/ob-intake
```

### What it does

Intake reads the existing workspace and input file, then asks one numbered round of
questions for facts a scan cannot measure. It does not ask for facts it can determine
from source, a production scan, or tenant inventory.

It writes:

```text
docs/observability/engagement-inputs.yaml
```

The file persists answers across later runs so realm, naming, scope, entitlement,
business context, and constraints do not drift between prompts.

### What to verify

- `engagement.application`, `customer`, `scope`, and date identify one application.
- Production URLs are current; test and QA URLs are not substituted.
- Diagrams and prior artifacts refer to this application.
- Missing values are explicit.
- Secret-bearing fields contain only environment-variable or secret-store references.
- Temporary authenticated access has `rotate_on_completion: true`.

Intake does not authorize implementation scope. Engineering sets `initial_scope` only
after reviewing the contract.

## Run 1: analyze

```text
/ob-analyze
```

### Preconditions

- `docs/observability/engagement-inputs.yaml` exists.
- A production URL exists unless `artifacts.front_end_scan_notes` explicitly says
  `no browser: <reason>`.
- Every referenced source, diagram, and artifact path resolves. A referenced but
  missing file blocks intake so it cannot become a phantom citation. Evidence that was
  not supplied is recorded as a gap rather than guessed.
- Tenant integrations are configured when tenant facts must be measured.

If inputs are absent or incomplete, the command invokes intake rather than filling gaps
with guesses.

### What it reads

- engagement inputs and referenced artifacts;
- front-end production behavior, including script order, router behavior, competing
  agents, provider initialization, CSP, consent, and status-versus-content behavior;
- backend and messaging architecture from source and diagrams;
- exposed credentials, API inventory, and authorized OWASP Web 2025/API 2023 security
  checks with explicit coverage and limitations;
- existing Observability Cloud and Enterprise telemetry through enabled MCP servers
  and approved APIs; and
- an existing wiki's metadata and accepted names when this is a repeat run.

The scan is read-only. Analysis does not edit application code or tenant configuration.

### What it writes

Required:

```text
docs/observability/analysis-<app>-<date>.md
docs/observability/<Customer>-<App>-Analysis-<date>.docx
docs/observability/attribute-schema.json
docs/observability/implementation-map.json
docs/observability/provenance-ledger.json
docs/observability/verification-plan.json
```

Conditional:

```text
docs/observability/entitlement-exposure-<app>-<date>.md
```

The entitlement exposure file exists when entitlement or a meaningful traffic baseline
was supplied. It is for the account team and is not rendered into the customer document.

Intake itself creates no git history. Analysis includes the validated intake file, creates
`initial-<app>-analysis` for the first run or `ci-initiated-<app>-analysis` for a later
CI run, commits evidence/security, contract/map, and render/review as phase commits, then
opens one docs-only PR. It never merges that PR.

### Completion conditions

Analysis is complete only when:

- the Markdown follows the canonical section order;
- section 4 is Critical Findings and includes exposed-credential/API checks, complete
  OWASP coverage matrices, and confidence-rated findings;
- every confirmed or high-confidence vulnerability is also listed under section 5's
  P0 recommended fixes;
- cross-cutting attributes and baggage propagation includes all required code patterns;
- business transactions, workflows, metrics, joins, detectors, objectives, and use
  cases form a consistent catalogue;
- the attribute dictionary agrees with `attribute-schema.json`;
- every accepted target maps to repository legs in `implementation-map.json`, or the
  missing ownership is an explicit engineering question;
- Business Value Realization is the last body section and labels each figure by origin;
- the Word file was generated from Markdown, not edited independently;
- the render verifier exits successfully; and
- an independent deliverable review passes with no defects.

### Human acceptance gate

Review the contract before continuing. Acceptance covers names, attribute semantics,
dimension eligibility, thresholds and objectives, rollout order, work boundaries, and
known open items. Later runs reuse accepted names exactly because dashboards, detectors,
MetricSets, and code depend on them.

Do not treat a generated document as accepted merely because rendering succeeded. Review
and merge the analysis PR, then accept the exact analysis commit with:

```text
/ob-generate accept docs/observability/analysis-<app>-<date>.md at <analysis-commit-sha>
```

The command verifies the Markdown, schema, and implementation map at that SHA and writes
`analysis-<app>-<date>.acceptance.yaml`. A missing path/SHA or later file changes stop
generation and require a new review.

## Run 2: accept and generate the wiki

```text
/ob-generate accept docs/observability/analysis-<app>-<date>.md at <analysis-commit-sha>
```

### Preconditions

- a person supplies the reviewed analysis path and exact commit SHA;
- the analysis and `attribute-schema.json` are present; and
- accepted application and service names are known.

If the path or SHA is missing, the command prints the exact acceptance invocation and
stops. File presence, successful rendering, generic approval, or merge alone is not
acceptance.

### What it writes

```text
wiki/README.md
wiki/apps/<app>/index.md
wiki/apps/<app>/implementation/work-orders/
wiki/apps/<app>/services/<service>/
    index.md
    meta/
    architecture/
    findings/
    contract/
        attribute-schema.json
    business-transactions/
    workflows/
    use-cases/
    metrics/
    detectors/
    slos/
    business/
    implementation/enforcement.md
    as-code/
```

It also creates short host pointers, such as
`.cursor/rules/obengineer-wiki.mdc`, `CLAUDE.md`, and `AGENTS.md`, that point to the
wiki index. The pointers do not duplicate the contract.

### How the wiki is used

The customer-facing Markdown remains the only narrative document. The wiki splits the
accepted catalogue into one retrievable note per subject, allowing an implementation
run to load the index and only the relevant workflow, contract, and work-order notes.

App-level `implementation/work-orders/` defines bounded unified work orders. One order
may span service and repository boundaries and coordinates one linked PR per repository.
`meta/run-log.md`, `meta/versions.md`, and `meta/decisions.md` preserve state for repeat
runs. `attribute-schema.json` remains the machine-readable enforcement contract.

Wiki generation does not write application code, Terraform, or another `.docx`.

### Verify

From the toolkit checkout:

```bash
export OB_PROJECT=/path/to/project-repo
make verify-wiki WIKI="wiki/apps/<app>/services/<service>"
```

The verifier checks a minimal required-path set and selected frontmatter fields, plus
wikilinks, recognized index counts, promoted-note content, pointer rules, limited version
and value provenance, and credential-shaped values. The canonical wiki reference remains
the authority for directories and metadata that the current verifier does not enforce.

## Run 3: implement one bounded target

```text
/ob-implement use-case:<accepted-id>
```

Supported selectors are `work-order:<id>`, `business-transaction:<id>`,
`workflow:<name>`, `use-case:<id>`, `detector:<id>`, `objective:<id>`, and
`config:<id>`. Omit the selector only to follow the accepted phase plan.

### Preconditions

- the analysis is accepted;
- the selector resolves to exactly one accepted app-level work order;
- `attribute-schema.json` contains every attribute the slice needs;
- `implementation-map.json` maps every repository leg;
- `initial_scope.authorized` permits each repository and path; and
- every mapped repository and branch is available.

If the contract lacks a needed attribute or work order, implementation stops and sends
the gap back to analysis. It does not improve the contract in passing.

### Behavior

One invocation executes one unified work order. A business transaction, workflow, or
end-to-end use case may cross separate frontend, SSR, Node, GraphQL, backend, Collector,
or configuration repositories. The run opens at most one linked PR per repository plus a
coordination PR in the artifact repository. Every PR names the work-order id and links its
siblings. Agents never merge them.

For Splunk APM Business Transactions, implementation emits bounded `<org>.bt` as a global
span tag, propagated and stamped across repository boundaries. The TAM separately
configures the tenant's Global tag include rule. `workflow.name` remains finer-grained
intent; one BT can group many workflows. Raw URLs never become BT values.

Typical runtime dependency order is:

1. shared OpenTelemetry helper library and validation;
2. exactly one provider initialization point;
3. identity and composite propagation;
4. route tracking when a client router exists;
5. one message bus boundary at a time;
6. first-journey workflow spans and events;
7. bounded custom meters;
8. Collector derivation and redaction;
9. deterministic contract checks; then
10. remaining accepted work orders.

The run works on the branch under review and does not merge it. It does not touch paths
outside authorized scope, add names outside the schema, enable every automatic
instrumentation, embed credentials, remediate unrelated findings, or arm detectors.

### Required proof

Each linked change states its work order, repository leg, contract sections, sibling PRs,
files, refusals, and runnable verification. Depending on the target, proof includes:

- a single initialization and session identity;
- one trace across browser and backend;
- propagated cross-cutting keys;
- producer and consumer continuity across a bus;
- a bounded workflow in APM;
- a registered `<org>.bt` / `workflow.name` pair visible across all repository legs;
- meters with only approved dimensions; or
- Collector-derived dimensions appearing before span metrics.

The implementation eventually adds deterministic CI checks for schema agreement,
workflow-name validity, one provider initialization, baggage allowlisting, classifier
coverage, and deny-list enforcement.

Jira is used only when the human named it and a Jira MCP is connected. A unified work
order can create one linked issue per mapped Jira project when engineering requests it.
Otherwise the wiki work order is the queue and provides copy/paste-ready issue text for the
team's chosen tool.

## Run 4: generate observability Terraform

```text
/ob-terraform
```

This run is independent of implementation after contract acceptance.

### Preconditions

- accepted analysis;
- `attribute-schema.json`;
- engagement inputs;
- the target application and environment.

Tenant inventory or exports are strongly recommended so existing resources can be
identified. Without them, import IDs remain `TODO` and the handoff must warn that a future
apply could duplicate existing objects.

### What it writes

```text
terraform/apps/<app>/
    providers.tf
    variables.tf
    data.tf
    imports.tf
    modules/
        executive/
        sre/
        engineer/
        platform/       # when required
    environments/
        <environment>/
```

The run uses separate providers for Observability Cloud, Synthetics, and Splunk
Platform. It generates dashboards, detectors, SLOs, metric rulesets, links, checks, and
platform configuration supported by the verified provider schemas.

### Safety and refusal behavior

- Identified existing tenant objects receive import blocks. Unresolved objects retain
  `TODO` import IDs and an explicit duplication warning.
- A `group by` is refused when the key is not dimension-eligible.
- Unsupported contract features are listed for manual configuration.
- Detector resources start disabled.
- Placeholder thresholds are labeled.
- Sensitive variables have no defaults; no token is written to `.tf` or `.tfvars`.
- Remote encrypted state is required before generating resources that place secrets in
  Terraform state.
- The command never runs `terraform apply`.

### Validation and handoff

The run executes `terraform fmt`, `terraform validate`, and `terraform plan` when
credentials permit. Without credentials it can use `terraform providers schema -json`
to validate provider resource names, but must report the result as schema-checked rather
than planned.

The handoff lists planned resource counts, imports, unresolved IDs, refused items,
unsupported items, placeholder thresholds, and run-cost implications.

## Run 5: verify outcomes read-only

Run after instrumentation deployment and the human-reviewed Terraform apply:

```text
/ob-verify
```

The run verifies the exact accepted commit, provenance ledger, actionable verification
plan, and optional human-approved exclusions. It performs read-only tenant queries and
writes JSON plus a Markdown human report under `docs/observability/verification/`.

- `met`, `unmet`, and `unmeasurable` remain machine-visible.
- Every unmet criterion notifies the human with owner, exact remediation, next command,
  and recheck instructions.
- The verifier never declares a criterion unremediable. A human-approved exclusion is
  recorded separately and omitted from machine result rows and metric denominators.
- Verification never applies, deploys, merges, arms/disarms, rotates, or changes tenant
  state.
- Reusable anonymized outcomes are previewed for `cfallwell/obengineer`. Existing `gh`
  authentication is reused; otherwise the run provides `gh auth login --web` and the
  GitHub device-login URL.

Outcome rates always include numerator, denominator, and measurement coverage. Detailed
evidence and run state live only in `provenance-ledger.json`.

## Independent review

```text
/ob-review
/ob-review docs/observability/analysis-<app>-<date>.md
```

Review reads the canonical rubric and the engagement inputs, then reports all defects
with rubric row, file, line, and smallest fix. It checks document structure, schema
agreement, baggage consumers, cardinality arithmetic, detector thresholds, objective
error budgets, join types, stable IDs, business-value provenance, entitlement
separation, credential leakage, and rendered-artifact consistency.

Review is read-only. It does not repair the document; separation between author and
grader is intentional.

## Render and verify

```text
/ob-render
/ob-render docs/observability/analysis-<app>-<date>.md
```

The command turns Markdown into a house-style Word document and runs the render
verifier. Markdown is the source of truth. Never hand-edit the `.docx`; make changes in
Markdown and render again.

Equivalent toolkit command:

```bash
export OB_PROJECT=/path/to/project-repo
make render FILE=docs/observability/analysis-<app>-<date>.md \
  OUT=docs/observability/<Customer>-<App>-Analysis-<date>.docx
```

The low-level renderer also supports document-format options documented in
[`customer-doc-render`](../skills/customer-doc-render/SKILL.md), including section
heading level, footer text, TOC presence and depth, banner display, and alternate
approved format specifications.

## Repeat and re-baseline runs

When `wiki/apps/<app>/services/<service>/index.md` and `meta/run-log.md` exist,
`/ob-analyze` runs in delta mode:

- accepted workflow names, attribute keys, finding IDs, and SLI names remain stable;
- changes, removals, drift, and version movement are reported;
- new catalogue entries are additive;
- old findings become fixed, open, regressed, or risk-accepted rather than disappearing; and
- only notes actually reconsidered receive new `updated` and `run` values.

When an application has been rewritten beyond a meaningful delta, declare a re-baseline
and archive the prior wiki. Do not silently convert a delta into a new first run.

## Output map

```text
<artifact-repository>/
├── .env                              local, ignored
├── docs/observability/
│   ├── engagement-inputs.yaml
│   ├── analysis-<app>-<date>.md
│   ├── <Customer>-<App>-Analysis-<date>.docx
│   ├── attribute-schema.json
│   ├── implementation-map.json
│   ├── provenance-ledger.json
│   ├── verification-plan.json
│   ├── analysis-<app>-<date>.acceptance.yaml
│   ├── entitlement-exposure-<app>-<date>.md   conditional
│   └── verification/                          # read-only outcome results
├── wiki/apps/<app>/
│   ├── implementation/work-orders/
│   └── services/<service>/
└── terraform/apps/<app>/
```

Application-code changes land in the authorized application repository, not
necessarily in the artifact repository. Terraform may also be moved to a dedicated
configuration repository with separate reviewers and state.
