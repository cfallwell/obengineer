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

Run an obengineer analysis version. `/ob-start`, `/ob-add-inputs`, and
`/ob-edit-inputs` normally dispatch here. Direct invocation does not bypass intake
authorization.

1. Determine the intended next immutable `V<N>` and originating command. Run
   `python3 "${PLUGIN_ROOT}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . show --command <origin> --intended-version V<N>`.
   Continue only when the one-shot authorization matches schema version, config digest,
   complete artifact-tree digest, command, and intended version. Otherwise return to the
   common redacted summary/proceed gate; direct invocation never bypasses it.
2. Adopt `${PLUGIN_ROOT}/agents/instrumentation-architect.agent.md`.
3. Only after step 1 passes, invoke the supported direct evidence path exactly:
   `python3 "${PLUGIN_ROOT}/skills/engagement-intake/scripts/manage_obconfig.py"
   --project-root . direct-api --phase analysis`. It securely loads local root
   `obconfig.yaml`; never read `.env`, process environment, or legacy engagement inputs.
   Feed its redacted JSON dispositions and measurements into the provenance ledger.
   Missing config produces explicit `not-configured` rows. Never invoke
   `direct_api.py` as an import-only substitute or put credentials in arguments.
4. Read accepted names and finding ids from the
   latest version before scanning. Reuse them and report changes under
   `${PLUGIN_ROOT}/skills/references/incremental-runs.md`.
5. Rehash the entire artifact directory. Reread every added/changed file, remove deleted
   context, and reuse only unchanged path/length/digest context. Preserve historical
   accepted analysis files without rewriting them. Follow Prompt 01.
6. During the same run, follow
   `${PLUGIN_ROOT}/prompts/02-build-instrumentation-wiki.md` to create the
   versioned wiki and every proposed work order.
7. Use `$instrumentation-analyze`, `$instrumentation-wiki`,
   `$baggage-propagation`, `$cardinality-budget`, and `$deliverable-review`.
   Use `$customer-doc-render` only when the human requested the optional short Word
   summary.
8. Follow `${PLUGIN_ROOT}/skills/references/analysis-run-lifecycle.md`: include
   inputs, the analysis site, wiki, and work orders in one PR and process review
   comments.
9. Validate the sanitized provenance ledger and schema version 2 read-only verification
   plan. In a success or failure cleanup, consume the one-shot authorization; successful
   consumption also records the local last-analysis binding for add/edit comparison.

The review surface is owned by
`${PLUGIN_ROOT}/skills/references/analysis-site.md`: linked Markdown opened in
the host's native side panel. Never start a web server, open a browser, or emit a
localhost URL.

Required outputs:

- `docs/observability/analysis/<app>/V<N>/index.md` and every linked page
- `docs/observability/analysis-contract.json`
- `docs/observability/attribute-schema.json`
- `docs/observability/implementation-map.json`
- `docs/observability/provenance-ledger.json`
- `docs/observability/verification-plan.json`
- `wiki/apps/<app>/versions/V<N>/` with subject notes and every work order
- measured usage/enforced-system-limit exposure and optional short `.docx`.

Open one analysis PR. When it becomes ready for review, read its comments and commit
the requested corrections. Ask the human to review the linked PR and whether to accept
and merge it. An explicit `yes` authorizes the acceptance commit and merge; resolve the
accepted commit internally and never ask for a SHA or a person's name.

After merge, provide only the host-native documentation link followed by concise next
steps. After acceptance, name the Ready work order and the exact
`/ob-implement work-order:<id>` command. Do not paste the analysis into chat.

$ARGUMENTS
