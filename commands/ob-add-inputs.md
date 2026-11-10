---
description: Add inputs — select unanswered suggestions and automatically run the next analysis version
---

Add inputs to an existing obengineer engagement.

1. Read `{{OBENGINEER_ROOT}}/prompts/00-manage-analysis-inputs.md` in `add`
   mode and follow it.
2. Load the current inputs and latest analysis version. Discover measurable facts
   first; do not offer them as questions.
3. Ask:
   `Would you like to add more inputs to the analysis phase?`
   Under `Suggested inputs include`, number only unanswered items that could
   materially improve the analysis. Accept `yes 1 3 4` or `no`.
4. Prompt once for each selected item, in order. A blank skips that item and keeps
   it on the intake-recommendations page. Never ask the human to type `unknown`.
5. Save and validate the added inputs, then automatically follow
   `{{OBENGINEER_ROOT}}/commands/ob-analyze.md` as the next immutable `V<N>` run.

The new version records the added inputs and every resulting change. Open one analysis
PR and use the review/acceptance lifecycle in
`{{OBENGINEER_ROOT}}/skills/references/analysis-run-lifecycle.md`.
Never start a web server, open a browser, or use a localhost URL.

$ARGUMENTS
