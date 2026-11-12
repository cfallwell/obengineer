---
name: ob-verify
description: >-
  Verify — run accepted exit criteria read-only and route remediation. Explicit workflow wrapper for $ob-verify in Codex CLI and
  @ob-verify in ChatGPT Desktop; do not invoke implicitly.
---

# ob-verify

Follow the matching obengineer command contract below as the authoritative workflow.
Preserve all user-supplied text accompanying the explicit invocation exactly and make
it available wherever the contract refers to `$ARGUMENTS`; do not drop, summarize, or
reinterpret those arguments before dispatch.

If the contract still contains the literal `{{OBENGINEER_ROOT}}` placeholder, resolve it to
the obengineer toolkit root associated with this skill before following any referenced
file or command.


## Command contract

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
