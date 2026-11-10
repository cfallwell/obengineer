---
description: Generate — accept the analysis and build the agent wiki
---

Run obengineer run 2 — accept the analysis and generate the instrumentation wiki.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-architect.agent.md` as your operating
   contract for this run.
2. Load `docs/observability/engagement-inputs.yaml`. Run the intake first if it is absent.
3. Require an explicit invocation in this form:
   `/ob-generate accept docs/observability/analysis-<app>-<date>.md at <analysis-commit-sha>`.
   Follow `{{OBENGINEER_ROOT}}/skills/references/analysis-run-lifecycle.md`, verify the
   Markdown, schema, and implementation map with
   `python3 "{{OBENGINEER_ROOT}}/skills/instrumentation-wiki/scripts/verify_analysis_acceptance.py" <analysis-path> <full-sha> --repo .`,
   then write the acceptance record. If either argument is missing, print the exact
   command and stop.
   The accepted artifact set includes `provenance-ledger.json` and
   `verification-plan.json`; verify the ledger seal before generating.
4. Follow `{{OBENGINEER_ROOT}}/prompts/02-build-instrumentation-wiki.md`.
5. Skills: `$instrumentation-wiki`, `$baggage-propagation`, `$cardinality-budget`.

This run builds the **agent layer**, not a document. **Do not produce a `.docx` and do not
write a second Markdown document** — that artifact existed, duplicated the analysis, and was
read by neither customers nor agents.

Layout, frontmatter, the index-note rule, and the host memory pointers are owned by
`{{OBENGINEER_ROOT}}/skills/references/agent-wiki.md`. Read it first; do not invent a
different tree.

Not complete until:

- `wiki/apps/<app>/services/<service>/` exists with one note per business transaction, workflow, use case,
  finding, detector, and objective, each with frontmatter and `[[wikilinks]]`
- `index.md` is a map of content — links and counts, not a summary
- `contract/`, `meta/versions.md` with a provenance column, `meta/run-log.md`, and
  app-level `wiki/apps/<app>/implementation/work-orders/` are populated from
  `docs/observability/implementation-map.json`
- `docs/observability/attribute-schema.json` agrees with the document's Appendix A
- The host memory pointers exist and point at the index note rather than copying it

Reuse the accepted `<org>.bt` values, `workflow.name` strings, attribute keys, and finding ids exactly.
Renaming an accepted workflow breaks every dashboard, detector, and MetricSet built on it.

No application code. No credential value in any note.

$ARGUMENTS
