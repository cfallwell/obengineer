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


## Command contract

Run one obengineer analysis version. Direct invocation never bypasses the one-shot authorization.

1. Determine the intended next immutable `V<N>` and originating command. Run
   `python3 "${PLUGIN_ROOT}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . claim --command <origin> --intended-version V<N>`.
   Continue only when this atomic one-winner claim matches schema/config, full artifact
   manifest/delta and artifact-tree digest, command, and version. Feed its sanitized
   delta to collection.
2. After step 1, run the non-secret projection exactly:
   `python3 "${PLUGIN_ROOT}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . config-projection --command <origin>
   --intended-version V<N>`. Its redacted JSON is analysis's only configuration input;
   never read raw `obconfig.yaml`, environment, or legacy inputs.
3. Adopt `${PLUGIN_ROOT}/agents/instrumentation-architect.agent.md`.
4. Invoke the supported direct evidence path exactly:
   `python3 "${PLUGIN_ROOT}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . direct-api --phase analysis --command <origin>
   --intended-version V<N>`. Feed its redacted JSON into provenance; never import the
   adapter or pass credentials.
5. Invoke the supported safe-active path exactly:
   `python3 "${PLUGIN_ROOT}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . safe-active --command <origin> --intended-version V<N>`.
   Append its redacted outcomes; passive/none makes zero requests.
6. Reuse accepted names/finding ids per `skills/references/incremental-runs.md`.
7. Rehash artifacts, apply the claimed delta, preserve accepted history, and follow
   Prompt 01.
8. During the same run, follow
   `${PLUGIN_ROOT}/prompts/02-build-instrumentation-wiki.md` to create the
   versioned wiki and every proposed work order.
9. Use the skills routed by Prompt 01; render Word only when requested.
10. Follow `skills/references/analysis-run-lifecycle.md` for the one PR and review.
11. Validate all Prompt 01 outputs, then stage every intended analysis-owned path. Never
   stage `obconfig.yaml` or `.obengineer`. With the generated outputs in the Git index,
   run
   `python3 "${PLUGIN_ROOT}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . finalize --command <origin> --intended-version V<N>
   --output docs/observability --output wiki/apps/<app>/versions/V<N>`.
   It binds the complete Git index tree and exact contained output blobs. Commit that
   index without staging anything else; the commit tree must match exactly.
12. Before push or PR creation, run `manage_obconfig.py dispatch` with the same
   command/version. It records only an exact matching HEAD commit/tree. Immediately
   before each push/PR operation run `manage_obconfig.py verify-dispatch`; dispatch
   nothing unless it succeeds.
13. After successful analysis push and PR dispatch, run `consume` with the same
   command/version. Input changes after finalize belong to the next run and do not
   alter the immutable dispatched tree. On decline or any pre-dispatch/dispatch failure,
   run
   `python3 "${PLUGIN_ROOT}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . abort --command <origin> --intended-version V<N>` instead. Abort
   releases the claim without changing artifact baseline/history.

The review surface is owned by
`${PLUGIN_ROOT}/skills/references/analysis-site.md`: linked Markdown opened in
the host's native side panel. Never start a web server, open a browser, or emit a
localhost URL.

Produce every Prompt 01 output, including `wiki/apps/<app>/versions/V<N>/`. After review,
explicit `yes` authorizes acceptance and merge. Return the host-native documentation
link and next Ready work-order command. Do not paste the analysis into chat.
Use the exact `/ob-implement work-order:<id>` handoff.

$ARGUMENTS
