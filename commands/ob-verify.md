---
description: Verify — run accepted exit criteria read-only and route remediation
---

Run obengineer run 5 — verify outcomes.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-verifier.agent.md`.
2. Follow `{{OBENGINEER_ROOT}}/prompts/05-verify-accepted-contract.md`.
3. Use `$instrumentation-verify`.
4. Verify the acceptance record, `verification-plan.json`, optional exclusions, and
   `provenance-ledger.json` before querying.
5. Execute read-only checks, notify the human about every unmet criterion with remediation
   and recheck instructions, then validate the output.

Human-approved unremediable criteria stay in the human exclusion report and ledger but are
not machine result rows. Never remediate or mutate the tenant.

$ARGUMENTS
