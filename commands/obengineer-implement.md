---
description: Land one slice of an accepted instrumentation contract as a reviewable PR (run 3 of 3)
---

Run obengineer run 3 — implement one slice.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-implementer.agent.md` as your
   operating contract for this run.
2. Load `docs/observability/INSTRUMENTATION-GUIDE.md` and
   `docs/observability/attribute-schema.json`. **Stop if the human has not accepted the
   guide.** This run implements a contract; it does not invent one.
3. Follow `{{OBENGINEER_ROOT}}/prompts/03-implement-instrumentation.md`.
4. Use the `$instrumentation-implement` skill.

One slice per PR, single concern, with the CI check that keeps it enforced. Name the slice
you are implementing before you start, and stop at its boundary.

Never commit a token value. Never widen the attribute set beyond the schema — if the
contract is wrong, say so and stop rather than improving it in passing.

$ARGUMENTS
