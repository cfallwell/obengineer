---
description: Implement — execute one bounded accepted work order across its repositories
---

Run obengineer run 3 — implement one bounded target.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-implementer.agent.md` as your
   operating contract for this run.
2. Load `docs/observability/analysis-<app>-<date>.md` and
   `docs/observability/attribute-schema.json`,
   `docs/observability/implementation-map.json`, and the acceptance record. **Stop if the human has not accepted the
   guide.** This run implements a contract; it does not invent one.
   Before editing, run:
   `python3 "{{OBENGINEER_ROOT}}/skills/instrumentation-wiki/scripts/verify_analysis_acceptance.py" --record docs/observability/analysis-<app>-<date>.acceptance.yaml --repo .`.
3. Follow `{{OBENGINEER_ROOT}}/prompts/03-implement-instrumentation.md`.
4. Use the `$instrumentation-implement` skill.

Accept one selector: `work-order:<id>`, `business-transaction:<id>`,
`workflow:<name>`, `use-case:<id>`, `detector:<id>`, `objective:<id>`, or
`config:<id>`. Resolve it to exactly one accepted app-level work order using
`{{OBENGINEER_ROOT}}/skills/references/implementation-work-orders.md`.

One invocation executes one unified work order. It may open one linked PR per mapped
repository plus a coordination PR, and every PR names the work-order id and sibling links.
Stop at the accepted repository/path boundaries.

Never commit a token value. Never widen the attribute set beyond the schema — if the
contract is wrong, say so and stop rather than improving it in passing.

$ARGUMENTS
