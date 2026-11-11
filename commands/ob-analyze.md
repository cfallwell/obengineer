---
description: Analyze — publish a versioned linked analysis with its wiki and work orders
---

Run an obengineer analysis version. `/ob-start`, `/ob-add-inputs`, and
`/ob-edit-inputs` normally dispatch here. Direct invocation does not bypass intake
authorization.

1. Run
   `python3 "{{OBENGINEER_ROOT}}/skills/engagement-intake/scripts/manage_run_context.py" show --project-root .`.
   Continue only when it reports `Analysis authorized: yes (explicit no recorded)` and
   the context contains `analysis_authorized: true` and `last_event: review-no`.
   Otherwise follow
   `{{OBENGINEER_ROOT}}/commands/ob-start.md`. Neither direct invocation nor a
   `yes <numbers>` response authorizes analysis.
2. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-architect.agent.md`.
3. Load `docs/observability/engagement-inputs.yaml`. If absent, follow
   `{{OBENGINEER_ROOT}}/commands/ob-start.md`. Missing optional answers never block
   analysis; put useful gaps on the intake-recommendations page.
4. Determine the next immutable `V<N>`. Read accepted names and finding ids from the
   latest version before scanning. Reuse them and report changes under
   `{{OBENGINEER_ROOT}}/skills/references/incremental-runs.md`.
5. Follow `{{OBENGINEER_ROOT}}/prompts/01-analyze-application.md`.
6. During the same run, follow
   `{{OBENGINEER_ROOT}}/prompts/02-build-instrumentation-wiki.md` to create the
   versioned wiki and every proposed work order.
7. Use `$instrumentation-analyze`, `$instrumentation-wiki`,
   `$baggage-propagation`, `$cardinality-budget`, and `$deliverable-review`.
   Use `$customer-doc-render` only when the human requested the optional short Word
   summary.
8. Follow `{{OBENGINEER_ROOT}}/skills/references/analysis-run-lifecycle.md`: include
   inputs, the analysis site, wiki, and work orders in one PR and process review
   comments.
9. Validate the provenance ledger and schema version 2 read-only verification plan.

The review surface is owned by
`{{OBENGINEER_ROOT}}/skills/references/analysis-site.md`: linked Markdown opened in
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
- conditional entitlement exposure and optional short `.docx`.

Open one analysis PR. When it becomes ready for review, read its comments and commit
the requested corrections. Ask the human to review the linked PR and whether to accept
and merge it. An explicit `yes` authorizes the acceptance commit and merge; resolve the
accepted commit internally and never ask for a SHA or a person's name.

After merge, provide only the host-native documentation link followed by concise next
steps. After acceptance, name the Ready work order and the exact
`/ob-implement work-order:<id>` command. Do not paste the analysis into chat.

$ARGUMENTS
