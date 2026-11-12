---
name: ob-edit-inputs
description: >-
  Edit inputs — rerun from a changed local obconfig. Explicit workflow wrapper for $ob-edit-inputs in Codex CLI and
  @ob-edit-inputs in ChatGPT Desktop; do not invoke implicitly.
---

# ob-edit-inputs

Follow the matching obengineer command contract below as the authoritative workflow.
Preserve all user-supplied text accompanying the explicit invocation exactly and make
it available wherever the contract refers to `$ARGUMENTS`; do not drop, summarize, or
reinterpret those arguments before dispatch.

If the contract still contains the literal `{{OBENGINEER_ROOT}}` placeholder, resolve it to
the obengineer toolkit root associated with this skill before following any referenced
file or command.


## Command contract

Inputs are managed in local `obconfig.yaml`.

1. Read `{{OBENGINEER_ROOT}}/prompts/00-load-obconfig.md`.
2. Run `manage_obconfig.py --project-root . changed`. If unchanged, print exactly
   `Edit obconfig.yaml, then rerun this command.` and stop.
3. Validate, hash the full artifact tree, and show the common redacted summary.
4. Ask exactly `Proceed with analysis using this configuration? (yes/no)`. Exact `no`
   stops. Exact `yes` authorizes `ob-edit-inputs` for the next immutable `V<N>` and
   follows `ob-analyze.md`; any other answer repeats the gate.

Do not edit YAML, list existing values, ask numbered questions, or expose secrets.

$ARGUMENTS
