---
description: Collect the engagement inputs — artifacts, diagrams, tenancy, entitlement, constraints, and the business context behind the engagement — into engagement-inputs.yaml
---

Run the obengineer intake.

Read `{{OBENGINEER_ROOT}}/skills/engagement-intake/SKILL.md` and follow it, using
`{{OBENGINEER_ROOT}}/inputs/engagement-inputs.template.yaml` as the template and
`{{OBENGINEER_ROOT}}/skills/references/engagement-inputs.md` for what each field decides.

Write the result to `docs/observability/engagement-inputs.yaml` in this workspace unless
the user names another path.

Ask for everything missing in **one** numbered message, and do not ask for anything a
scan can measure. Never request or store a credential value — record who holds it.

Two asks are easy to skip and both change what the deliverable can say:

- **Entitlement**, and say what it is for: these numbers **price** the recommendation rather than cap it. What implementing it consumes, and any overage, goes to the account team in a separate document; the recommendation itself is what the application needs either way. `unknown` is fine — then there is simply no exposure document.
- **Business context**, starting with prose: *in your own words, what hurts today — what breaks, who finds out first, and what it costs you when it does?* Then current MTTD/MTTA/MTTR, incidents per month, how many people join a bridge, what an engineering hour costs, what fraction of incidents customers report first, tooling in use and annual spend, revenue per hour online, orders per day, average order value, conversion rate, and any named peak events. Every one of them may be `unknown`; none of them may be filled with an industry benchmark. Finally, whether reading the last twelve months of the **public record** is permitted, and which brand terms to search.

$ARGUMENTS
