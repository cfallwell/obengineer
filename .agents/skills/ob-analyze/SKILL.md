---
name: ob-analyze
description: >-
  Analyze — publish a versioned linked analysis with its wiki and work orders. Explicit workflow wrapper for $ob-analyze in Codex CLI and
  @ob-analyze in ChatGPT Desktop; do not invoke implicitly.
---

# ob-analyze

Follow the matching obengineer command contract below as the authoritative workflow.
Preserve all user-supplied text accompanying the explicit invocation exactly and make
it available wherever the contract refers to `$ARGUMENTS`; do not drop, summarize, or
reinterpret those arguments before dispatch.

If the contract still contains the literal `{{OBENGINEER_ROOT}}` placeholder, resolve it to
the obengineer toolkit root associated with this skill before following any referenced
file or command.


## Command contract

Run one obengineer analysis version. Direct invocation never bypasses the one-shot authorization.

1. Determine the intended next immutable `V<N>` and originating command. Run
   `python3 "{{OBENGINEER_ROOT}}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . claim --command <origin> --intended-version V<N>`.
   Continue only when this atomic one-winner claim matches schema/config, full artifact
   manifest/delta and artifact-tree digest, command, and version. Feed its sanitized
   delta to collection.
2. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-architect.agent.md`.
3. Only after step 1 passes, invoke the supported direct evidence path exactly:
   `python3 "{{OBENGINEER_ROOT}}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . direct-api --phase analysis --command <origin>
   --intended-version V<N>`. It securely loads local root
   `obconfig.yaml`; never read `.env`, process environment, or legacy engagement inputs.
   Feed its redacted JSON into provenance. Never import the adapter or pass credentials.
4. Invoke the supported safe-active path exactly:
   `python3 "{{OBENGINEER_ROOT}}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . safe-active --command <origin> --intended-version V<N>`.
   Append its redacted outcomes; passive/none makes zero requests.
5. Reuse accepted names/finding ids per `skills/references/incremental-runs.md`.
6. Rehash artifacts, apply the claimed delta, preserve accepted history, and follow
   Prompt 01.
7. During the same run, follow
   `{{OBENGINEER_ROOT}}/prompts/02-build-instrumentation-wiki.md` to create the
   versioned wiki and every proposed work order.
8. Use the skills routed by Prompt 01; render Word only when requested.
9. Follow `skills/references/analysis-run-lifecycle.md` for the one PR and review.
10. Validate all Prompt 01 outputs. After successful PR dispatch, run `consume` with the
   same command/version. Never consume on decline/failure; the baseline remains retryable.

The review surface is owned by
`{{OBENGINEER_ROOT}}/skills/references/analysis-site.md`: linked Markdown opened in
the host's native side panel. Never start a web server, open a browser, or emit a
localhost URL.

Produce every Prompt 01 output, including `wiki/apps/<app>/versions/V<N>/`. After review,
explicit `yes` authorizes acceptance and merge. Return the host-native documentation
link and next Ready work-order command. Do not paste the analysis into chat.
Use the exact `/ob-implement work-order:<id>` handoff.

$ARGUMENTS
