---
name: ob-add-inputs
description: >-
  Add inputs — select unanswered suggestions and automatically run the next analysis version. Explicit workflow wrapper for $ob-add-inputs in Codex CLI and
  @ob-add-inputs in ChatGPT Desktop; do not invoke implicitly.
---

# ob-add-inputs

Follow the matching obengineer command contract below as the authoritative workflow.
Preserve all user-supplied text accompanying the explicit invocation exactly and make
it available wherever the contract refers to `$ARGUMENTS`; do not drop, summarize, or
reinterpret those arguments before dispatch.

If the contract still contains the literal `{{OBENGINEER_ROOT}}` placeholder, resolve it to
the obengineer toolkit root associated with this skill before following any referenced
file or command.


## Command contract

Add inputs to an existing obengineer engagement.

1. Reopen the deterministic input review:
   `python3 "{{OBENGINEER_ROOT}}/skills/engagement-intake/scripts/manage_run_context.py" reopen --project-root .`
   This clears prior analysis authorization, retains `[x]` supplied items, and returns
   prior `[-]` items to `[ ]`.
2. Read `{{OBENGINEER_ROOT}}/prompts/00-manage-analysis-inputs.md` in `add`
   mode and follow it.
3. Load the current inputs and latest analysis version. Discover measurable facts
   first; do not offer them as questions.
4. Ask:
   `Would you like to add more inputs to the analysis phase?`
   Under `Suggested inputs include`, show only unanswered items that could
   materially improve the analysis, retaining their canonical numbers 1–10 even
   when the filtered list has gaps. Accept `yes 1 3 4` or `no`.
5. Prompt once for each selected item, in order. A blank skips that item and keeps
   it on the intake-recommendations page. Never ask the human to type `unknown`.
   Show the checked `[x]`, `[ ]`, and `[-]` list, then ask the review question again.
   A `yes` response never starts analysis; only a response exactly equal to `no`
   authorizes it.
6. Save and validate the added inputs, then follow
   `{{OBENGINEER_ROOT}}/commands/ob-analyze.md` as the next immutable `V<N>` run.

The new version records the added inputs and every resulting change. Open one analysis
PR and use the review/acceptance lifecycle in
`{{OBENGINEER_ROOT}}/skills/references/analysis-run-lifecycle.md`.
Never start a web server, open a browser, or use a localhost URL.

$ARGUMENTS
