---
description: Intake — collect artifacts, tenancy, entitlement, and business context into engagement-inputs.yaml
---

Run the obengineer intake.

Read `{{OBENGINEER_ROOT}}/skills/engagement-intake/SKILL.md` and follow it, using
`{{OBENGINEER_ROOT}}/inputs/engagement-inputs.template.yaml` as the template and
`{{OBENGINEER_ROOT}}/skills/references/engagement-inputs.md` for what each field decides.

Write the result to `docs/observability/engagement-inputs.yaml` in this workspace unless
the user names another path.
Validate it with
`python3 "{{OBENGINEER_ROOT}}/skills/engagement-intake/scripts/verify_engagement_inputs.py" <path> --migrate`;
report every migration before saving.

Intake creates no branch, commit, or PR; `/ob-analyze` includes the validated artifact
in its analysis PR.

Create or extend `docs/observability/provenance-ledger.json` with stated inputs and any
read-first measured entitlement facts. Never create `evidence.json` or `run-state.json`.

Ask for everything missing in **one** numbered message, and do not ask for anything a
scan can measure. A token, an API key, or a dummy test login may be submitted as a
reference so the scan can see authenticated surfaces. Never store the secret. Rotate
it through its owner after analysis.

Open that message by telling the human what helps. The design runs against any site.
Scan the current production site. Test and QA are not the scan. Optional traffic
baselines tighten the consumption expectation; `unknown` and an empty list are
unsupplied and widen the range. Splunk Observability Cloud and Splunk Enterprise
MCP servers are mandatory. Ask which developer tools they use and match them to
MCP servers and environment variable names already present. Previous scans of this
site are inputs; a different site is not. Instrumentation scope is not an intake
question. Server classes: `skills/references/mcp-servers.md`.

Two inputs materially change the result:

- **Entitlement:** read measurable tenant usage first, then ask only for order-form gaps.
  It prices rather than caps the recommendation; `unknown` is valid.
- **Business context:** ask *in your own words, what hurts today?*, then the available MTTx,
  incident, response-cost, tooling, revenue, and peak-event facts. Never substitute an
  industry benchmark. Ask whether twelve-month public-record research is permitted.

$ARGUMENTS
