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

1. **Measure before asking.** Inspect the workspace, production surface, connected MCP
   tools, environment-variable names, and direct Splunk APIs. MCP is one source, not the
   only source. Use every readable source and preserve provenance.
2. **No required `unknown`.** A blank remains absent. The validator may materialize a
   schema-compatible null/empty representation, but the human never types `unknown`.
3. **Ask by selection.** Present applicable suggestions as a numbered list. Accept
   `yes 1 3 4` or `no`, then prompt for selected items one at a time.
4. **Do not ask for names of engineers or owners.** Repository review policy supplies
   reviewers. Roles appear only where routing behavior requires them.
5. **Secrets never enter chat or committed YAML.** Use references. Direct the human to
   `scripts/obengineer/setup-splunk-access.sh` when local API access is useful.
6. **A missing optional input does not block analysis.** Put useful omissions and their
   consequences on `reference/intake-recommendations.md`.

## Modes

The commands invoke [`../../prompts/00-manage-analysis-inputs.md`](../../prompts/00-manage-analysis-inputs.md)
in one of three modes.

### Start

Read existing workspace facts first. Ask only for:

- application name;
- a current production URL when it cannot be discovered; and
- “In your own words, what hurts today?”

Then ask:

> Would you like to add more inputs to the analysis phase?
>
> Suggested inputs include:

Number only applicable suggestions. The canonical suggestion families are:

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

After the selected answers are validated, `/ob-start` runs analysis V1.

### Add

List only useful absent inputs, renumbered from one for the current prompt. Prompt for
selected items in ascending order. A blank skips the item. Save additions and
automatically run the next immutable analysis version.

### Edit

List supplied, human-editable inputs with their current values. Show secret-backed values
only as `configured`. Do not offer measured facts as human-editable opinions.

For each selection:

1. show the current redacted value;
2. request the replacement;
3. accept `clear` to remove it; and
4. state the immediate consequence.

Save edits and automatically run the next immutable version.

## Discovery

Before displaying suggestions:

- inspect repository source and supplied diagrams;
- discover the production URL from existing inputs or configuration;
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

For each absent but useful input, write one row to the version's
`reference/intake-recommendations.md`:

| Input | What it would improve | How to add it |
|---|---|---|

The action is `/ob-add-inputs`, not manual YAML editing. A cleared value returns to this
page. When the page has no useful rows, omit its landing-page link.
