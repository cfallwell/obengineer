---
description: Start — collect the minimum inputs, offer optional additions, and run analysis V<N>
---

Start or resume an obengineer engagement.

1. Read `${CLAUDE_PLUGIN_ROOT}/prompts/00-manage-analysis-inputs.md` in `start`
   mode and follow it.
2. Use `${CLAUDE_PLUGIN_ROOT}/skills/engagement-intake/SKILL.md` to discover
   measurable facts before asking the human. Never require the word `unknown`;
   unanswered suggestions go to the intake-recommendations page.
3. Ask only for the application name, current production URL when it is not
   discoverable, and “what hurts today?” before offering the numbered optional
   inputs.
4. Ask:
   `Would you like to add more inputs to the analysis phase?`
   Then show only useful, unanswered items under `Suggested inputs include`.
   Accept `yes 1 3 4` or `no`. Prompt once for each selected item, in order.
5. Validate and save the inputs, then follow
   `${CLAUDE_PLUGIN_ROOT}/commands/ob-analyze.md`. This command starts analysis;
   the human does not invoke `/ob-analyze` separately.

The completed run opens one analysis PR. Its final chat response contains only the
host-native side-panel documentation link followed by review, add/edit-input,
acceptance, and implementation instructions. Never start a web server, open a browser,
or use a localhost URL.

$ARGUMENTS
