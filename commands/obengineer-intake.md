---
description: Collect the engagement inputs — artifacts, diagrams, tenancy, entitlement, constraints — into engagement-inputs.yaml
---

Run the obengineer intake.

Read `{{OBENGINEER_ROOT}}/skills/engagement-intake/SKILL.md` and follow it, using
`{{OBENGINEER_ROOT}}/inputs/engagement-inputs.template.yaml` as the template and
`{{OBENGINEER_ROOT}}/skills/references/engagement-inputs.md` for what each field decides.

Write the result to `docs/observability/engagement-inputs.yaml` in this workspace unless
the user names another path.

Ask for everything missing in **one** numbered message, and do not ask for anything a
scan can measure. Never request or store a credential value — record who holds it.

$ARGUMENTS
