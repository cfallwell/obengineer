# CI/CD integration — the contract as a pipeline, not a document

A contract enforced by review decays. Someone ships a workflow name that is not in the
registry, a dimension that was never budgeted, a service with no `service.version`, and it is
caught two quarters later by an analysis run. The whole value of having written the contract
down is that a machine can check it.

Three layers, deliberately separate, because they fail for different reasons and should be
adopted in this order:

| Layer | Runs | Needs a model? | Fails the build? |
|---|---|---|---|
| **1. Contract checks** | Every pull request | No | Yes |
| **2. Agent instrumentation** | On a schedule, or on a label | Yes | No — it opens a pull request |
| **3. Configuration delivery** | On merge to the default branch | No | Yes, on `plan` failure |

Adopt layer 1 first and alone. It is deterministic, cheap, and it produces the signal the
other two layers depend on. An organisation that starts with layer 2 gets pull requests
nobody trusts, because nothing was measuring whether the contract held in the first place.

## Layer 1 — contract checks

Deterministic scripts, no model, run on every pull request. Each one exists because it caught
something a human review did not.

| Check | Fails when |
|---|---|
| **Schema agreement** | An attribute is emitted in code that is absent from `contract/attribute-schema.json`, or the document appendix and the schema disagree |
| **Workflow registry** | A `workflow.name` literal appears in code and is not in the wiki's workflow list |
| **Dimension budget** | A metric is created with a dimension the schema marks attribute-only, or the promoted set exceeds the recorded MTS budget |
| **Single init** | More than one artifact calls the provider `init`, which is the defect that silently halves RUM data |
| **Baggage allowlist** | `SpanProcessor.onStart` iterates baggage entries generically instead of the allowlist, or a key not in the budget is written |
| **No credential in telemetry** | A literal matching a credential shape reaches an attribute, a span name, or a log field |
| **Wiki freshness** | Code changed a workflow's spans and the corresponding note's `status`/`updated` did not move in the same commit |

The last one is the one people leave out and the one that keeps everything else true. Without
it the wiki is documentation, and documentation is wrong within a week.

These belong in the target repository, not here — they check the customer's code against the
customer's contract. What this project supplies is their definition and the reasons; the
implementer agent writes them as part of the slice that introduces the thing being checked, so
a check never lands before the contract it enforces.

## Layer 2 — the agent opens pull requests

The instrumentation agent runs against the repository and proposes code. Bounded to keep it
reviewable and to keep it from becoming the thing everyone disables:

**It opens a pull request. It never pushes to the default branch.** No exception. The value is
a reviewable proposal, and a bot with merge rights is a bot nobody reads.

**One work order per pull request**, from
`wiki/<Customer>/<app>/implementation/work-orders/`. A pull request that instruments four
workflows is a pull request that gets approved without being read.

**Scoped to what the contract already names.** It implements accepted design; it does not
invent a workflow, a meter, or a dimension. If the diff needs something not in the contract,
it stops and says which section is missing rather than filling the gap with a guess — that is
an analysis run's job, and the boundary is what makes the pull requests trustworthy.

**Refuses a set of paths outright**, and this list is configuration a human owns: payment and
identity code, anything that changes a public API, CSP allowlists, and any file matching the
repository's own protected-paths list. It may *propose* a change to these in the pull request
description; it may not make one.

**Triggers**, in increasing order of ambition:

- **Label** — a human adds `obengineer:instrument` to a pull request. Start here; the human chooses when.
- **Schedule** — weekly, against the default branch, one work order per run, and it opens nothing if the previous pull request is still unmerged. Queueing bot pull requests is how a repository ends up with nine of them and a policy against them.
- **On merge to a watched path** — a new route file or service directory appears, so the agent opens a pull request adding it to the registry and emitting its spans. This is the one that keeps new code from shipping uninstrumented, and it is the reason the periodic cadence exists at all.

**Every pull request body states**: the work order, the contract sections implemented, the
files touched, what was refused and why, and the verification steps. A reviewer must not have
to reconstruct intent from a diff.

## Layer 3 — configuration delivery

Terraform for dashboards, detectors, SLOs, metric rulesets, and Synthetics, applied
incrementally as the contract grows. See
[`../observability-as-code/SKILL.md`](../observability-as-code/SKILL.md).

**Put it in its own repository.** The application repository and the observability
configuration repository have different reviewers, different blast radius, and different
cadence: an application revert should not revert a dashboard, and a detector threshold change
should not need an application reviewer. One repository for all of a customer's applications,
one Terraform workspace per environment.

The flow, and each step exists to prevent a specific failure:

1. **The application pull request merges**, having added the instrumentation.
2. **The as-code agent opens a pull request** in the configuration repository for the panels, detectors, and objectives that new telemetry now supports. Separate pull request, separate review.
3. **CI runs `fmt`, `validate`, and `plan`** and posts the plan. Where there are no credentials, `terraform providers schema -json` still proves every resource name and argument exists — report it as schema-checked, not as planned.
4. **A human approves the plan.** Every time, at least until the estate has been stable for a quarter. A dashboard applied without review is recoverable; a detector applied without review pages someone at 03:00 on a threshold nobody agreed.
5. **`apply` on merge**, with remote encrypted state, and only for the environment the branch targets.

Two ordering rules, both learned the expensive way:

**Configuration follows telemetry, never leads it.** A dashboard applied before the attribute
exists renders empty, and an empty panel is indistinguishable from an outage to the person
looking at it. Gate step 2 on the telemetry being visible — a Tag Spotlight check or a schema
check against the tenant, not a guess about deploy timing.

**Detectors arrive disabled.** They are armed by a separate, deliberate change once the signal
has been clean for the agreed window. Both facts belong in the pull request description, or
the reviewer assumes they are live.

## Wiring the three together

The wiki is the integration point, which is why it is a repository directory and not a
hosted service:

```
application repo
  ├─ layer 1 checks ──────────── read contract/attribute-schema.json + workflow list
  ├─ layer 2 agent ───────────── reads implementation/work-orders/, writes code + updates notes
  └─ wiki/ (committed here, or a submodule)
                │
                └─ read by the as-code agent in the configuration repo
                                  └─ layer 3: plan on PR, apply on merge
```

Where the wiki lives is a real decision with no universally right answer. In the application
repository it stays in step with the code and layer 1 can check freshness in one checkout;
in its own repository it can serve several application repositories and matches the
configuration repository's cadence. A submodule gets both and costs contributors a
checkout step they will forget. Pick one, write down which and why in
`meta/decisions.md`, and do not let a second copy appear.

## Secrets

Ingest tokens, API tokens, and provider credentials come from the CI platform's secret store
and are referenced as environment variables. Never in a workflow file, never in a `.tfvars`,
never in a wiki note, never echoed into a log. `signalfx_org_token` and
`splunk_inputs_http_event_collector` write secrets into Terraform state, so remote encrypted
state with access control is a prerequisite for layer 3 rather than a later improvement.

Agent credentials get the minimum scope that works: contents write plus pull requests for
layer 2, and no access to the configuration repository. An agent that can both write code and
apply configuration can turn one bad inference into a production alerting change.

## Working examples

[`../../examples/ci/`](../../examples/ci/) carries a starting point per layer:
`contract-checks.yml`, `agent-instrument.yml`, and `terraform-plan-apply.yml`. They are
examples to copy and edit, not a framework to depend on — a workflow nobody read is a
workflow nobody can debug.

## Adoption order

1. **Layer 1, two checks**: schema agreement and single init. Both catch real defects immediately and neither needs a model.
2. **Wiki freshness check**, once notes exist and are being updated. This is what keeps layer 2 honest later.
3. **Layer 3 with manual `apply`**, on one persona module. Prove the review loop before widening it.
4. **Layer 2 on a label**, one work order. Let a human choose when for the first month.
5. **Layer 2 on a schedule or on watched paths**, once the pull requests are being merged roughly as-is. If they are being heavily edited, the contract is the thing to fix, not the trigger.

## Warning signs

- **Layer 2 before layer 1.** Pull requests against an unenforced contract, so nothing knows whether they helped.
- **The agent has write access to the default branch.** It will use it, and the day it is wrong is the day nobody was reading.
- **`terraform apply` with no plan review.** Working until it pages someone.
- **A bot pull request older than two weeks.** The trigger is producing work nobody wants; change what it proposes, not the reminder cadence.
- **Terraform in the application repository.** Ties an alerting change to an application reviewer and an application revert to a dashboard.
- **Wiki notes updated by a separate job after the code merged.** The window between them is when the contract is a lie, and CI cannot tell that window from a permanent drift.
- **Checks that warn instead of failing.** A warning is a check that has been turned off politely.
