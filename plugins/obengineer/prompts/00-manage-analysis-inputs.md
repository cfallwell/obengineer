# Prompt 00 — Manage analysis inputs

**Skill:** `engagement-intake`  
**Modes:** `start` | `add` | `edit`  
**State:** `docs/observability/engagement-inputs.yaml` and the latest analysis version

This prompt owns the guided input conversation. Commands point here instead of carrying
three copies.

## Shared rules

- Inspect source, the production surface, connected tools, environment-variable names,
  and readable Splunk APIs before asking. Do not ask for a measurable fact.
- A missing answer is absent, not the literal string `unknown`. The human never types `unknown`. Preserve schema-compatible
  empty values in YAML and list useful gaps on
  `reference/intake-recommendations.md`.
- Never ask for a person's name, team name, or named owner.
- Never request a secret in chat. When access is useful, point to
  `<obengineer-root>/scripts/setup-splunk-access.sh`; display secret-backed values only
  as `configured`.
- Number the currently applicable choices. The reply grammar is `yes` followed by
  space-separated numbers, for example `yes 1 3 4 6 7`, or `no`.
- After `yes`, prompt once for each selected item in ascending order. A blank skips it.

## Start mode

Ask only for the application name, a production URL when none can be discovered, and:

> In your own words, what hurts today?

Then ask:

> Would you like to add more inputs to the analysis phase?
>
> Suggested inputs include:

Offer applicable items from:

1. diagrams or an earlier analysis of this application;
2. passive or safe-active security assessment authorization;
3. a dummy test login for authenticated surfaces;
4. tenant realm and environments not already measured;
5. order-form entitlement and optional traffic baselines;
6. privacy, residency, consent, and change constraints;
7. business context such as MTTx, incident volume, triage cost, and revenue exposure;
8. permission for twelve-month public-record research;
9. chart and detector percentile; and
10. a journey to rank first.

## Add mode

Use the same question and reply grammar, but list only useful items that remain absent.
Do not renumber against an old run; number the current list from one.

## Edit mode

List set, human-editable values with redacted current values. Ask:

> These inputs are already set. Would you like to edit them?

For every selected item, show the current value and request a replacement. `clear`
removes it. Do not offer measured facts as editable human inputs; a later measurement
supersedes them through evidence precedence.

## Completion

Validate the input artifact and update the provenance ledger. `start` runs analysis V1;
`add` and `edit` automatically run the next immutable version. No input-management mode
creates a standalone PR: the analysis PR includes the validated input changes.
