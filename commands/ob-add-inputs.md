---
description: Add inputs — rerun from a changed local obconfig
---

Inputs are managed in local `obconfig.yaml`.

1. Read `{{OBENGINEER_ROOT}}/prompts/00-load-obconfig.md`.
2. Run `manage_obconfig.py --project-root . changed`. If unchanged, print exactly
   `Edit obconfig.yaml, then rerun this command.` and stop.
3. Validate, hash the full artifact tree, and show the common redacted summary.
4. Ask exactly `Proceed with analysis using this configuration? (yes/no)`. Exact `no`
   stops. Exact `yes` authorizes `ob-add-inputs` for the next immutable `V<N>` and
   follows `ob-analyze.md`; any other answer repeats the gate.

Do not edit YAML, ask field-by-field or numbered questions, or expose current values.

$ARGUMENTS
