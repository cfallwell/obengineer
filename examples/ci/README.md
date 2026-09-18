# CI examples

Working starting points for the three layers in
[`../../skills/references/ci-integration.md`](../../skills/references/ci-integration.md).
Copy them into the repository they belong in and edit the marked values — they are examples,
not a framework, and a workflow nobody read is a workflow nobody can debug.

| File | Repository | Layer |
|---|---|---|
| [`contract-checks.yml`](contract-checks.yml) | the application repo | 1 — deterministic checks on every pull request |
| [`agent-instrument.yml`](agent-instrument.yml) | the application repo | 2 — the agent proposes instrumentation as a pull request |
| [`terraform-plan-apply.yml`](terraform-plan-apply.yml) | the observability config repo | 3 — plan on pull request, apply on merge |

Adopt in that order. Layer 1 alone is worth having; layers 2 and 3 depend on it for the
signal that tells anyone whether they helped.

## Before you enable anything

**Secrets.** Every token comes from the CI platform's secret store as an environment
variable. Never in a workflow file, never in a `.tfvars`, never echoed into a log. Give the
agent job the minimum scope that works — contents write plus pull requests, and no access to
the configuration repository. An agent that can both write code and apply configuration turns
one bad inference into a production alerting change.

**Remote state.** `signalfx_org_token` and `splunk_inputs_http_event_collector` write secrets
into Terraform state. Remote encrypted state with access control is a prerequisite for layer
3, not a later improvement.

**Ordering.** Configuration follows telemetry, never leads it. A dashboard applied before the
attribute exists renders empty, and an empty panel is indistinguishable from an outage to the
person looking at it.
