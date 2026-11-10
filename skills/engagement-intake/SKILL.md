---
name: engagement-intake
description: >-
  Guide analysis inputs for /ob-start, /ob-add-inputs, and /ob-edit-inputs.
  Discover measurable facts before asking, present unanswered or editable inputs
  as a numbered selection, keep secrets out of chat, and persist only supplied
  values. Use when the user invokes $engagement-intake, starts an engagement,
  adds evidence, or corrects an existing input.
metadata:
  author: obengineer
  version: 0.2.0
  category: observability
---

# Guided analysis inputs

Inputs persist in `docs/observability/engagement-inputs.yaml`. This skill manages the
file; the analysis consumes it. It does not create a standalone branch, commit, or PR.

Field meaning and consequences live in
[`../references/engagement-inputs.md`](../references/engagement-inputs.md). Connected
systems and direct API behavior live in
[`../references/mcp-servers.md`](../references/mcp-servers.md) and
[`../references/existing-telemetry.md`](../references/existing-telemetry.md).

## Principles

1. **Ask the required question first.** In start mode, ask for the application, an
   explicit production URL or `no browser: <reason>`, and what hurts before any source,
   network, browser, MCP, or API discovery. After that answer, measure before asking any
   optional question.
2. **No required `unknown`.** A blank remains absent. The validator may materialize a
   schema-compatible null/empty representation, but the human never types `unknown`.
3. **Ask by selection.** Present applicable suggestions as a numbered list. Accept
   `yes 1 3 4` or `no`, then prompt for selected items one at a time. `yes` never starts
   analysis. Return to the review list after the answers; only an exact `no` authorizes
   analysis.
4. **Do not ask for names of engineers or owners.** Repository review policy supplies
   reviewers. Roles appear only where routing behavior requires them.
5. **Secrets never enter chat or committed YAML.** Use references. Direct the human to
   `scripts/obengineer/setup-splunk-access.sh` when local API access is useful.
6. **A missing optional input does not block analysis.** Put useful omissions and their
   consequences on `reference/intake-recommendations.md`.
7. **Persist every turn deterministically.** Use
   `scripts/manage_run_context.py` for the state transition and checked list. Use
   `scripts/prefill_engagement_inputs.py` for allowlisted `.env` or JSON prefill. Never
   hand-set the analysis authorization flag.

## Modes

The commands invoke [`../../prompts/00-manage-analysis-inputs.md`](../../prompts/00-manage-analysis-inputs.md)
in one of three modes.

### Start

Run `scripts/manage_run_context.py start --project-root .` before reading the workspace
or contacting anything. Ask its emitted question immediately (target: five seconds or
less). It asks only for:

- application name;
- an explicit current production URL, or `no browser: <reason>`; and
- “In your own words, what hurts today?”

Securely persist allowlisted local environment values and the answer:

```bash
python3 <obengineer>/skills/engagement-intake/scripts/prefill_engagement_inputs.py \
  --project-root . --json -
python3 <obengineer>/skills/engagement-intake/scripts/manage_run_context.py \
  required --project-root .
```

The first command maps names through `schemas/env-prefill.schema.json`. Raw Splunk token
values are replaced with `${SPLUNK_ACCESS_TOKEN}` or `${SPLUNK_TOKEN}` references;
`PASSWORD_REF` must already be a `${VAR}` reference. It never overwrites a supplied YAML
value.

Then ask:

> Would you like to add more inputs to the analysis phase?
>
> Suggested inputs include:

Show only applicable suggestions while preserving these canonical numbers; filtered
lists may have gaps and must never be renumbered by display position:

1. diagrams or prior analysis for this application;
2. passive or safe-active security authorization;
3. dummy authenticated test access;
4. unmeasured tenant realm and environments;
5. order-form entitlement and optional traffic baselines;
6. privacy, residency, consent, and change constraints;
7. business context such as MTTx, incident volume, triage cost, and revenue exposure;
8. permission for bounded public-record research;
9. chart and detector percentile; and
10. a journey to rank first.

Send review and answer events to `manage_run_context.py` every turn. Its state sequence
is `new -> required -> optional-review -> optional-answers -> optional-review`.
Checklist markers are `[x]` answered, `[ ]` pending, and `[-]` skipped. After the
selected answers, ask the optional-review question again. `/ob-start` runs analysis V1
only after the exact response `no` produces `analysis_authorized: true` and
`last_event: review-no`. `yes 1 3` never starts analysis.

### Add

List only useful absent inputs with their canonical 1–10 numbers. Prompt for
selected items in ascending order. A blank skips the item. Save additions and
return to the checked optional-review list. Run the next immutable analysis version only
after an exact `no`.

### Edit

List supplied, human-editable inputs with their current values. Show secret-backed values
only as `configured`. Do not offer measured facts as human-editable opinions.

For each selection:

1. show the current redacted value;
2. request the replacement;
3. accept reserved value `clear` through
   `prefill_engagement_inputs.py --json - --overwrite-existing`; the script restores
   the template value, removes explicit-supply provenance, and never stores the literal;
   and
4. state the immediate consequence.

Save edits, show the checked list, and ask again. Run the next immutable version only
after an exact `no`.

`input_provenance.supplied_paths` records dotted paths explicitly supplied through the
allowlist. This is value-free metadata: it keeps intentional defaults such as `passive`,
`false`, `true`, and `p90` checked across restart while ordinary start/add prefills
continue to preserve existing human values.

## Discovery

After the required question has been answered and before displaying suggestions:

- inspect repository source and supplied diagrams;
- inspect the explicit production URL from the input (never substitute a discovered URL);
- list connected MCP tools and use relevant read tools;
- inspect only whether supported environment-variable names are present, never values;
- use Observability Cloud and Splunk Platform APIs directly when configured;
- use MCP results to supplement APIs, not replace them; and
- record each measured/stated source in `provenance-ledger.json`.

When neither direct APIs nor relevant MCP tools are available, analysis continues from
source and the production surface. The evidence page states the limitation. Do not make
the finished site look tenant-measured when it was not.

## Credential setup

Tell the human how to create least-privilege read credentials, then point to:

```bash
scripts/obengineer/setup-splunk-access.sh
```

The installed command may substitute the toolkit's absolute
`scripts/setup-splunk-access.sh` path. The script prompts in the terminal, writes `.env`
with mode `0600`, adds `.env` to `.gitignore`, and never prints token values.

Temporary dummy login access uses a login identifier plus a secret reference. Production
credentials are not inputs. Any temporary credential is rotated by its holder after the
analysis completes.

## Validation and recommendations

Run:

```bash
python3 <obengineer>/skills/engagement-intake/scripts/verify_engagement_inputs.py \
  docs/observability/engagement-inputs.yaml --migrate
```

Report deterministic migrations. Do not delete unknown extension fields.

Validation requires `engagement.application`, exactly one of an absolute production URL
or `no browser: <reason>`, and the required what-hurts commentary. A dummy login ID and
password reference must appear together; the password reference must match `${VAR}` and
access submission requires rotation.

For each absent but useful input, write one row to the version's
`reference/intake-recommendations.md`:

| Input | What it would improve | How to add it |
|---|---|---|

The action is `/ob-add-inputs`, not manual YAML editing. A cleared value returns to this
page. When the page has no useful rows, omit its landing-page link.
