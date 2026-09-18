---
description: Analyze a target application and produce the measured analysis memo (run 1 of 3)
---

Run obengineer run 1 — analyze.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-architect.agent.md` as your operating
   contract for this run. It is the authority on what must be produced.
2. Load the engagement inputs from `docs/observability/engagement-inputs.yaml`. If the file
   is absent or incomplete, run the intake first
   (`{{OBENGINEER_ROOT}}/skills/engagement-intake/SKILL.md`) — do not proceed on guesses,
   and do not re-ask for anything the file already answers.
3. Follow `{{OBENGINEER_ROOT}}/prompts/01-analyze-application.md`. That file is the run
   contract; read it rather than waiting for it to be pasted.
4. Use the `$instrumentation-analyze` skill for the scan and the inventory.

Docs only. Do not modify application source. Do not display ingest tokens.

$ARGUMENTS
