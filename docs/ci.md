# Continuous integration

This page explains how to run obengineer in CI so that every new feature ships with the
observability its accepted contract requires. It covers which jobs run where, the checks
that keep the contract enforced, the pre-merge job that refuses to write instrumentation
without authorization, scheduled runs, and how one feature release moves from code to
verified telemetry.

The authority for this design is
[`ci-integration.md`](../skills/references/ci-integration.md); repeat-run behavior is
owned by [`incremental-runs.md`](../skills/references/incremental-runs.md). Starting-point
workflows are in [`examples/ci/`](../examples/ci/). For the interactive commands, see
[End-to-end usage](usage.md); for the pipeline stages, see
[How it works](how-it-works.md).

## Why a pipeline

A contract enforced only by review decays. Someone ships a `workflow.name` that is not
registered, a metric dimension that was never budgeted, or a second RUM initialization,
and nobody notices until the next analysis months later. Writing the contract down is
valuable because a machine can then check it on every pull request, and because a repeat
analysis can find newly shipped code that nobody instrumented.

## What runs where

| Job | Repository | Trigger | Needs a model? | Fails the build? | Example |
|---|---|---|---|---|---|
| Analysis | Artifact (memory) repository | Manual dispatch with a protected configuration artifact | Yes | No; it opens one analysis PR for human review | [`agent-analysis.yml`](../examples/ci/agent-analysis.yml) |
| **Layer 1:** contract checks | Application repository | Every pull request and push to the default branch | No | Yes | [`contract-checks.yml`](../examples/ci/contract-checks.yml) |
| Pre-merge branch job | Application repository | Pull request opened or updated | Yes | Yes, when authorization is missing or checks fail | [`branch-before-merge.yml`](../examples/ci/branch-before-merge.yml) |
| **Layer 2:** agent instrumentation | Application repository | Label, schedule, or merge to a watched path | Yes | No; it opens a pull request | [`agent-instrument.yml`](../examples/ci/agent-instrument.yml) |
| **Layer 3:** configuration delivery | Observability configuration repository | Plan on pull request, apply on merge | No | Yes, when `plan` fails | [`terraform-plan-apply.yml`](../examples/ci/terraform-plan-apply.yml) |
| Verification | Artifact repository | After deployment and apply | Yes; the agent runs `/ob-verify`, and every tenant query is read-only | Yes, on any `unmet` criterion | — |

Adopt them in this order, one step at a time:

1. Layer 1 with two checks, schema agreement and single initialization. Both catch real
   defects immediately and neither needs a model or a credential.
2. The wiki freshness check, once wiki notes exist and are being updated.
3. Layer 3 with a manual `apply`, on one persona module, to prove the plan review loop.
4. Layer 2 on a label, one work order at a time, so a human chooses when it runs.
5. Layer 2 on a schedule or on watched paths, once its pull requests are merged roughly
   as written. If reviewers rewrite them heavily, fix the contract, not the trigger.

Starting with layer 2 produces pull requests nobody trusts, because nothing measures
whether the contract held in the first place.

## Contract checks on every pull request

Layer 1 is a set of deterministic scripts in the application repository. They read the
accepted contract (`docs/observability/attribute-schema.json` and the registered
workflow list) and fail the build when code disagrees with it. The first foundation work
order installs the core set before any journey code, and each later work order adds the
check for whatever it introduces, so a check never lands before the contract it enforces.

| Check | Fails when |
|---|---|
| **Single initialization** | The provider `init` symbol is imported or called outside the one boot package. A second initialization splits one browser session into two and silently halves RUM data. |
| **Workflow name validation** | A `workflow.name` literal in code is not registered in the schema, or `startWorkflow` accepts a value that is not bounded dotted-kebab within the length ceiling. In production an invalid name degrades to a sentinel value, and the sentinel's rate is alerted on. |
| **Baggage allowlist** | `setBaggageEntry` accepts a key outside the baggage budget or an over-long value, or the `SpanProcessor.onStart` stamp iterates baggage generically instead of using the allowlist. This is what stops a token from becoming a baggage value. |
| **Schema agreement** | An attribute emitted in code is absent from `attribute-schema.json`, the schema does not parse, or its deny list differs from the analysis. |
| **Classifier coverage** | A route registry generates the page-type classifier and the regenerated classifier differs from the committed one, so a new route would silently classify as `other`. |
| **Deny-list keys** | A key on the schema's deny list (for example `email`, `phone`, `full_name`, `card_*`, `password`) appears as a literal attribute key anywhere in the diff. |
| **Dimension budget** | A metric uses a dimension the schema marks attribute-only, or the promoted set exceeds the recorded budget. |
| **No credential in telemetry** | A credential-shaped literal reaches an attribute, a span name, or a log field. |
| **Wiki freshness** | Code changed a workflow's telemetry and the corresponding wiki note's `status` or `updated` field did not change in the same commit. |

The first six are the checks `$instrumentation-implement` lands when a work order
requires them; the last three come from
[`ci-integration.md`](../skills/references/ci-integration.md). Wiki freshness is the check
teams most often leave out, and it is the one that keeps the others true: without it the
wiki becomes ordinary documentation that drifts within weeks.

These checks belong to the target repository because they check that application's code
against that application's contract. obengineer defines them and the agent writes them;
they then run without a model.

Example, excerpted from
[`examples/ci/contract-checks.yml`](../examples/ci/contract-checks.yml) (adjust the
pattern and source path to your stack):

```yaml
- name: exactly one provider init
  run: |
    count=$(grep -rn --include='*.[jt]s' --include='*.[jt]sx' \
              -E '(SplunkRum|provider)\.init\(' src | grep -v '\.test\.' | wc -l)
    if [ "$count" -ne 1 ]; then
      echo "::error::expected exactly 1 provider init, found $count"
      exit 1
    fi
```

## Pre-merge job: no instrumentation without authorization

The pre-merge job runs on the pull-request branch, before merge, so contract updates and
instrumentation land in the same review as the feature. It never merges and never pushes
to the default branch.

It refuses to write code unless engineering has authorized the scope:

- `initial_scope.authorized` must be `full`, `repositories`, or `parent_folders`. With
  `unknown`, the job asks engineering to authorize a scope and exits without writing
  code. `unknown` is never permission to scan every repository a connected GitHub,
  GitLab, or other MCP server can see.
- The accepted `implementation-map.json` must map the repository, and every path the job
  touches must sit under that repository's `authorized_paths`. A diff outside the
  authorized scope is skipped.
- The implementation step applies the same checks as `/ob-implement`: the accepted
  version must pass `verify_analysis_acceptance.py`, and the work order must pass the
  foundation gate in `work_order_state.py`.

On each update of an in-scope pull request, the job:

1. checks out the pull-request head, not the default branch, and skips commits whose
   message starts with `obengineer:` (its own pushes), so it cannot loop;
2. runs the layer 1 checks against that checkout;
3. when the diff introduces code the contract does not yet cover, updates the contract on
   the same branch in delta mode: only the new paths, the notes they touch, and the
   schema keys they require, without inventing a workflow the evidence does not support;
4. implements one work order on the same branch, inside the protected-path refusals;
5. pushes to the head branch and leaves merging to a human. When the token cannot push
   (a fork pull request), it fails the check and posts the diff as a review comment
   instead of opening a second pull request.

Example, excerpted from
[`examples/ci/branch-before-merge.yml`](../examples/ci/branch-before-merge.yml):

```yaml
- name: require a developer scope
  if: steps.gate.outputs.skip != 'true'
  run: |
    python3 - <<'PY'
    import json, pathlib, sys
    path = pathlib.Path("docs/observability/implementation-map.json")
    data = json.loads(path.read_text()) if path.exists() else {}
    repositories = data.get("repositories", [])
    if not repositories:
        print("Accepted implementation-map authorization is required before this job writes code.")
        sys.exit(1)
    PY
```

Example, not shipped as a file: the acceptance and foundation-gate steps a CI job can run
before any agent step, using the same scripts `/ob-implement` uses. Replace `<app>`,
`V<N>`, `WO-014`, and the toolkit path. Both scripts exit nonzero when the order may not
run.

```yaml
- name: accepted version and foundation gate
  run: |
    TOOLKIT=.obengineer/toolkit
    python3 "$TOOLKIT/skills/instrumentation-wiki/scripts/verify_analysis_acceptance.py" \
      --record docs/observability/analysis/<app>/V<N>/acceptance.yaml --repo .
    python3 "$TOOLKIT/skills/instrumentation-wiki/scripts/work_order_state.py" \
      gate --repo . --app <app> --version V<N> --work-order WO-014
```

## Agent instrumentation (layer 2)

The instrumentation agent proposes code as a pull request. The rules that keep it
reviewable:

- It opens a pull request and never pushes to the default branch. A bot with merge
  rights is a bot nobody reads.
- It runs one work order per invocation from the accepted version's queue,
  `wiki/apps/<app>/versions/V<N>/implementation/work-orders/`, with live status from
  `wiki/apps/<app>/implementation/V<N>/state.yaml`. A work order that spans repositories
  produces at most one linked PR per repository plus a coordination PR in the artifact
  repository.
- It implements only what the contract already names. If the change needs a workflow,
  meter, or dimension the contract lacks, it stops and names the missing section; adding
  it is an analysis run's job.
- It refuses a human-owned list of protected paths (for example payment and identity
  code, public API changes, and CSP allowlists). It may propose changes to them in the
  pull-request description, never make them.
- Every pull-request body states the work order, the contract sections implemented, the
  files touched, what was refused and why, and how to verify the result.

## Configuration delivery (layer 3)

Terraform from `/ob-terraform` lives in its own observability configuration repository,
not the application repository: the two have different reviewers, blast radius, and
cadence, and an application revert should not revert a dashboard. The flow is:

1. the application pull request that adds instrumentation merges;
2. the as-code agent opens a separate pull request in the configuration repository for
   the dashboards, detectors, and objectives the new telemetry supports;
3. CI runs `terraform fmt`, `validate`, and `plan` and posts the plan; without
   credentials, `terraform providers schema -json` still proves every resource and
   argument exists, reported as schema-checked rather than planned;
4. a human approves the plan; and
5. `apply` runs on merge, using remote encrypted state, for the targeted environment only.

Configuration follows telemetry: a dashboard applied before its attribute exists renders
empty and looks like an outage, so gate the plan on the telemetry being visible in the
tenant. Detectors arrive disabled and are armed by a separate, deliberate change once the
signal has been clean for the agreed window.

## Scheduled runs

Three jobs can run on a schedule. None of them merges anything.

- **Layer 2, weekly.** Against the default branch, one work order per run, and nothing at
  all if the previous bot pull request is still open. Queued bot pull requests are how a
  repository ends up with nine of them and a policy against them.
- **Layer 2 on merge to a watched path.** When a new route file or service directory
  appears, the agent proposes registering it and emitting its spans. This is the trigger
  that keeps new code from shipping uninstrumented.
- **Repeat analysis.** obengineer is meant to run periodically against the same target,
  because routes, buses, and services keep appearing. A repeat analysis is a delta: it
  reuses accepted names and finding IDs and reports new surfaces, retired surfaces,
  drift, and the status of every prior finding. The analysis job still needs the
  one-shot proceed authorization, so the example is a manual dispatch that consumes a
  protected configuration artifact rather than an unattended cron job.

Verification runs after each deployment and apply. In CI, `/ob-verify` writes the
human report, lists every `unmet` criterion in the job summary, and exits nonzero on any
`unmet` result, so a release whose telemetry did not arrive fails visibly.

## How a new feature release flows

```text
 feature pull request
   │  layer 1 checks: unregistered key or workflow fails the build
   │  pre-merge job (if authorized): delta contract update + one slice on the same branch
   ▼
 merge ─▶ watched-path trigger or schedule notices new surfaces
   ▼
 edit artifacts/ or obconfig.yaml ─▶ /ob-analyze ─▶ V<N+1> with "Changes in this version"
   │                                                  new surfaces ─▶ new work orders
   │  small change to an existing subordinate order ─▶ /ob-revise ─▶ R2 ─▶ status changed
   ▼
 review and accept V<N+1>  (one PR, explicit yes)
   ▼
 /ob-implement <selector>  (or /ob-implement work-order:<id> reimplement)
   │  one PR per mapped repository + coordination PR; layer 1 checks must pass
   ▼
 deploy ─▶ /ob-terraform plan ─▶ human apply (detectors disabled)
   ▼
 /ob-verify  (read-only; CI fails on unmet)
```

1. **Add the feature.** A developer opens a pull request with the new route, service, or
   queue. Layer 1 runs immediately. If the feature emits an attribute or `workflow.name`
   the contract does not name, the build fails and tells the developer to either remove
   it or add it through analysis. If the pre-merge job is enabled and the scope is
   authorized, it can update the contract and implement one slice on the same branch.
2. **Analysis delta on rerun.** After the feature merges, add any new design material to
   `artifacts/` (or change `obconfig.yaml`) and run `/ob-analyze`. It shows the redacted
   summary with the artifact delta and asks
   `Proceed with analysis using this configuration? (yes/no)`. On `yes` it produces the
   next version. Because the run reads the prior version's accepted names and decisions
   before scanning, the new version keeps existing names, adds the new surfaces, and
   opens with `Changes in this version`. Newly shipped, uninstrumented code is the
   highest-value finding of a repeat run, and every such surface gets a work order.
3. **New or revised work orders.** A genuinely new business transaction, workflow, or
   foundation change arrives as a new work order in the next version. A small change to
   an existing subordinate order in the current accepted version (a span name, an added
   attribute, a detector threshold) does not need a new version: `/ob-revise` records
   revision R2, R3, and so on in the state ledger, and an implemented order becomes
   `changed`.
4. **Review and accept.** The new version is reviewed in one PR and accepted with an
   explicit `yes`. Each version has its own state ledger, created from that version's
   accepted notes, and its foundation orders must be recorded `implemented` or `verified`
   in that ledger (with `set-status` and the PR URLs) before its other orders release.
5. **Implement.** `/ob-implement` runs one Ready order at a time;
   `/ob-implement work-order:<id> reimplement` reruns a changed order with its cumulative
   revisions. Each repository pull request must pass layer 1, including any check the
   order itself adds.
6. **Configure.** After deployment, `/ob-terraform` plans the dashboards, detectors, and
   SLOs the new telemetry supports, including the application rollup and the leadership
   portfolio; a human applies the plan through layer 3.
7. **Verify.** `/ob-verify` checks the accepted criteria read-only against the tenant.
   Every `unmet` row names the remediation route and the exact recheck, and CI fails
   until the criterion is met or a human approves it as unremediable.

## Analysis in CI

An analysis run in CI follows the same rules as an interactive one
([`analysis-run-lifecycle.md`](../skills/references/analysis-run-lifecycle.md)): one
branch and one docs-only PR per version, named `analysis-<app>-v<n>`; the same
one-shot authorization, finalize, and dispatch checks; and no acceptance or merge by CI.
`obconfig.yaml` is never committed. A separate secure step provides it to the runner as
a protected workflow artifact, which the job installs with mode `0600` and never stages.

## Secrets and permissions

- Every token comes from the CI platform's secret store as an environment variable:
  never in a workflow file, a `.tfvars` file, a wiki note, or a log line.
- Give agent jobs the minimum scope that works: contents write and pull requests in the
  application repository, and no access to the configuration repository. An agent that
  can both write code and apply configuration can turn one bad inference into a
  production alerting change.
- `signalfx_org_token` and `splunk_inputs_http_event_collector` write secrets into
  Terraform state, so remote encrypted state with access control is a prerequisite for
  layer 3.

## Where the wiki lives

The wiki is the integration point between the three layers: layer 1 reads the schema and
workflow list, layer 2 reads work orders and updates notes, and the as-code agent in the
configuration repository reads the accepted contract. It can live in the application
repository (it stays in step with code, and layer 1 can check freshness in one
checkout), in a separate memory repository (it can serve several application
repositories), or as a submodule (both, at the cost of an extra checkout step). Pick one,
record the choice and the reason in `meta/decisions.md`, and never keep a second copy.

## About the examples

The files in [`examples/ci/`](../examples/ci/) are starting points to copy and edit, not
a framework to depend on. Replace every placeholder runner step with your organization's
approved agent runner. Before enabling them, align three details with the current design,
because the examples predate it:

- **Branch names.** `agent-analysis.yml` creates `initial-<app>-analysis` or
  `ci-initiated-<app>-analysis`; the current lifecycle uses one `analysis-<app>-v<n>`
  branch per version.
- **Work-order paths.** `agent-instrument.yml` picks orders from
  `wiki/apps/<app>/implementation/work-orders/` by note status; the queue now lives under
  `wiki/apps/<app>/versions/V<N>/implementation/work-orders/`, and live status comes from
  the state ledger and `work_order_state.py gate`, not from note frontmatter.
- **Acceptance.** References to a separate generate or accept command are obsolete.
  Acceptance is the explicit `yes` on the analysis PR, which writes `acceptance.yaml`.
