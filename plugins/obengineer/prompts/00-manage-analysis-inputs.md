# Prompt 00 — Manage analysis inputs

**Skill:** `engagement-intake`  
**Modes:** `start` | `add` | `edit`  
**State:** `docs/observability/engagement-inputs.yaml` and the latest analysis version

This prompt owns the guided input conversation. Commands point here instead of carrying
three copies.

## Shared rules

- In `start` mode, the first response is the required-input question emitted by
  `manage_run_context.py start`. Ask it before source inspection, network access,
  production browsing, MCP discovery, or API discovery. Do not substitute a URL found
  elsewhere: the human must provide or confirm an explicit production URL, or provide
  `no browser: <reason>`.
- After that answer, inspect source, the production surface, connected tools,
  environment-variable names, and readable Splunk APIs before offering optional inputs.
  Do not ask for another measurable fact.
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
- On every start-mode turn, update `.obengineer/run-context.json` with
  `manage_run_context.py`. Show its checklist markers: `[x]` answered, `[ ]` pending,
  and `[-]` skipped or explicitly declined. The file is local, ignored, and written
  atomically.
- `yes 1 3` selects questions; it never starts analysis. After selected answers,
  return to the optional-review question. Only a response that is exactly `no`, recorded
  by the state machine while in `optional-review`, authorizes analysis.

## Start mode

The command runs this before loading or discovering anything else:

```bash
python3 <obengineer-root>/skills/engagement-intake/scripts/manage_run_context.py \
  start --project-root .
```

Ask the emitted question immediately. It requests, together:

- application name;
- an explicit production URL, or `no browser: <reason>`; and
- “In your own words, what hurts today?”

Persist the answer through the allowlisted prefill script using JSON on stdin. It may
read local `.env` and `.env.template`; it never copies raw token values. Then advance
`required -> optional-review`:

```bash
python3 <obengineer-root>/skills/engagement-intake/scripts/prefill_engagement_inputs.py \
  --project-root . --json -
python3 <obengineer-root>/skills/engagement-intake/scripts/manage_run_context.py \
  required --project-root .
```

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

Pass each optional-review response to `manage_run_context.py review` as JSON containing
`response` and the currently `offered` numbers. For each selected answer, persist the
answer, then pass its number and `answered` or `skipped` to
`manage_run_context.py answer`. Process the pending numbers in ascending order. When the
script returns to `optional-review`, show the checked list and ask again. Dispatch
analysis only when the script reports `Analysis authorized: yes (explicit no recorded)`.

## Add mode

Use the same question and reply grammar, but list only useful items that remain absent.
Do not renumber against an old run; number the current list from one.
After selected answers, show the checked list and ask again. Only an exact `no`
authorizes the next analysis version; `yes` never does.

## Edit mode

List set, human-editable values with redacted current values. Ask:

> These inputs are already set. Would you like to edit them?

For every selected item, show the current value and request a replacement. `clear`
removes it. Do not offer measured facts as editable human inputs; a later measurement
supersedes them through evidence precedence.

## Completion

Validate the input artifact and update the provenance ledger. Before dispatching any
analysis, read `.obengineer/run-context.json` and require
`analysis_authorized: true` with `last_event: review-no`. `start` then runs analysis V1;
`add` and `edit` run the next immutable version only after their explicit final `no`.
No input-management mode creates a standalone PR: the analysis PR includes the validated
input changes.
