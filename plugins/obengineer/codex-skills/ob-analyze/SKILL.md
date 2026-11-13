---
name: ob-analyze
description: >-
  Analyze — rerun analysis after editing obconfig.yaml or artifacts/. Explicit workflow wrapper for $ob-analyze in Codex CLI and
  @ob-analyze in ChatGPT Desktop; do not invoke implicitly.
---

# ob-analyze

Follow the matching obengineer command contract below as the authoritative workflow.
Preserve all user-supplied text accompanying the explicit invocation exactly and make
it available wherever the contract refers to `$ARGUMENTS`; do not drop, summarize, or
reinterpret those arguments before dispatch.


## Command contract

Run one analysis version. After the first `/ob-start`, edit `obconfig.yaml` or
`artifacts/` and rerun `/ob-analyze`. Direct invocation never bypasses the
one-shot authorization. `manage_obconfig.py` means
`python3 "${PLUGIN_ROOT}/skills/engagement-intake/scripts/manage_obconfig.py" --project-root .`.

1. Determine the intended next immutable `V<N>` and `<origin>`. When `/ob-start`,
   `/ob-add-inputs`, or `/ob-edit-inputs` dispatched here after its exact `yes`,
   `<origin>` is that command; go to step 2 without asking again. Otherwise `<origin>`
   is `ob-analyze`: if `obconfig.yaml` is missing, tell the user to run `/ob-start`
   first and stop. Apply `${PLUGIN_ROOT}/prompts/00-load-obconfig.md` gates: run
   `manage_obconfig.py validate` (on failure, its exact repair gate), then `summary`,
   which rehashes artifacts. Show it unchanged and ask exactly
   `Proceed with analysis using this configuration? (yes/no)`. Exact `no` stops. Exact
   `yes` runs `manage_obconfig.py authorize --answer yes --command ob-analyze
   --intended-version V<N>`; any other answer repeats the gate.
2. Run `manage_obconfig.py claim --command <origin> --intended-version V<N>`. Continue
   only when this atomic one-winner claim matches schema/config, full artifact
   manifest/delta and artifact-tree digest, command, and version. Feed its sanitized
   delta to collection.
3. Run `manage_obconfig.py config-projection --command <origin>
   --intended-version V<N>`. Its redacted JSON is the only configuration input; never
   read raw `obconfig.yaml`, environment, or legacy inputs.
4. Adopt `${PLUGIN_ROOT}/agents/instrumentation-architect.agent.md`.
5. Run `manage_obconfig.py direct-api --phase analysis --command <origin>
   --intended-version V<N>`. Feed its redacted JSON into provenance; never pass
   credentials.
6. Run `manage_obconfig.py safe-active --command <origin> --intended-version V<N>`.
   Append redacted outcomes; passive/none makes zero requests.
7. Reuse accepted names/finding ids per `skills/references/incremental-runs.md`.
8. Apply the claimed delta, preserve accepted history, and follow Prompt 01 and its
   routed skills; render Word only when requested. In the same run, follow
   `${PLUGIN_ROOT}/prompts/02-build-instrumentation-wiki.md` for the versioned wiki
   and every proposed work order.
9. Follow `skills/references/analysis-run-lifecycle.md` for the one PR and review.
10. Validate all Prompt 01 outputs, then stage every intended analysis-owned path. Never
   stage `obconfig.yaml` or `.obengineer`. Then run
   `manage_obconfig.py finalize --command <origin> --intended-version V<N>
   --output docs/observability --output wiki/apps/<app>/versions/V<N>`.
   It binds the complete index tree and exact output blobs; commit exactly that tree.
11. Before push or PR creation, run `dispatch` with the same command/version; it records
   the exact HEAD commit/tree. Immediately before each push/PR operation
   run `verify-dispatch`; dispatch nothing unless it succeeds.
12. After successful push and PR dispatch, run `consume` with the same command/version.
   Later input changes belong to the next run. On decline or any dispatch failure, run
   `abort` with the same command/version instead; it preserves baseline/history.

Review linked Markdown in the host's native side panel per
`${PLUGIN_ROOT}/skills/references/analysis-site.md`. Never start a web server,
open a browser, or emit a localhost URL.

After review, explicit `yes` authorizes acceptance and merge. Return the host-native
documentation link and the exact `/ob-implement work-order:<id>` handoff. Do not paste
the analysis into chat.

$ARGUMENTS
