---
description: Edit inputs — select existing values to change and automatically run the next analysis version
---

Edit inputs already supplied to an obengineer engagement.

1. Reopen the deterministic input review:
   `python3 "{{OBENGINEER_ROOT}}/skills/engagement-intake/scripts/manage_run_context.py" reopen --project-root .`
   This clears prior analysis authorization without discarding supplied values.
2. Read `{{OBENGINEER_ROOT}}/prompts/00-manage-analysis-inputs.md` in `edit`
   mode and follow it.
3. Load the current inputs and latest analysis version.
4. Show a numbered list of set, human-editable inputs and their redacted current
   values. Secret references display only `configured`; never display a secret.
5. Ask:
   `These inputs are already set. Would you like to edit them?`
   Accept `yes 1 3 4` or `no`.
6. For each selection, show the current value and request the replacement.
   `clear` removes it and returns it to the intake-recommendations page.
   Persist replacements through `prefill_engagement_inputs.py --json - --overwrite-existing`;
   this flag is reserved for explicit edit mode.
   Then show the checked list and ask whether to edit more. A `yes` response never
   starts analysis; only a response exactly equal to `no` authorizes it.
7. Save and validate the edits, then follow
   `{{OBENGINEER_ROOT}}/commands/ob-analyze.md` as the next immutable `V<N>` run.

The new version records each edited field and every resulting change. Open one analysis
PR and use the review/acceptance lifecycle in
`{{OBENGINEER_ROOT}}/skills/references/analysis-run-lifecycle.md`.
Never start a web server, open a browser, or use a localhost URL.

$ARGUMENTS
