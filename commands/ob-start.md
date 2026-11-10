---
description: Start — collect the minimum inputs, offer optional additions, and run analysis V<N>
---

Start or resume an obengineer engagement.

1. Before reading source, using the network, browsing production, or discovering MCP/API
   tools, prefill supplied project context silently and emit the first turn:
   `python3 "{{OBENGINEER_ROOT}}/skills/engagement-intake/scripts/start_turn.py" --project-root .`
   Ask only the required fields still marked `[ ]`: application name, explicit production
   URL or `no browser: <reason>`, and what hurts today. When all three are `[x]`, do not
   ask them again; proceed immediately to optional review. Do not prepend discovery or
   setup narration.
2. Read `{{OBENGINEER_ROOT}}/prompts/00-manage-analysis-inputs.md` in `start`
   mode and follow it. Securely prefill the input artifact through
   `prefill_engagement_inputs.py`; never copy a raw password or token.
3. After the required answer, use the skill to discover measurable optional facts.
   Never require `unknown`; omissions go to the intake-recommendations page.
4. Ask:
   `Would you like to add more inputs to the analysis phase?`
   Then show only useful, unanswered items under `Suggested inputs include`.
   Send every review and answer turn through `manage_run_context.py`. Display its
   `[x]`, `[ ]`, and `[-]` checklist. Prompt once for each selected item, in order.
   After answers, return to optional review. `yes 1 3 4` never starts analysis.
5. Validate and save the inputs. Follow
   `{{OBENGINEER_ROOT}}/commands/ob-analyze.md`. This command starts analysis;
   the human does not invoke `/ob-analyze` separately. Dispatch only when an exact `no`
   has produced `analysis_authorized: true` and `last_event: review-no`.

The completed run opens one analysis PR. Its final chat response contains only the
host-native side-panel documentation link followed by review, add/edit-input,
acceptance, and implementation instructions. Never start a web server, open a browser,
or use a localhost URL.

$ARGUMENTS
