---
description: Build the structured agent wiki and attribute schema from the accepted analysis (run 2 of 4)
---

Run obengineer run 2 — the instrumentation wiki.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-architect.agent.md` as your operating
   contract for this run.
2. Load `docs/observability/engagement-inputs.yaml`. Run the intake first if it is absent.
3. Load the accepted analysis document from run 1. If the human has not accepted one, say so
   and stop — this run structures an accepted analysis, it does not replace it.
4. Follow `{{OBENGINEER_ROOT}}/prompts/02-build-instrumentation-wiki.md`.
5. Skills: `$instrumentation-wiki`, `$baggage-propagation`, `$cardinality-budget`.

This run builds the **agent layer**, not a document. **Do not produce a `.docx` and do not
write a second Markdown document** — that artifact existed, duplicated the analysis, and was
read by neither customers nor agents.

Layout, frontmatter, the index-note rule, and the host memory pointers are owned by
`{{OBENGINEER_ROOT}}/skills/references/agent-wiki.md`. Read it first; do not invent a
different tree.

Not complete until:

- `wiki/<Customer>/<app>/` exists with one note per business transaction, workflow, use case,
  finding, detector, and objective, each with frontmatter and `[[wikilinks]]`
- `index.md` is a map of content — links and counts, not a summary
- `contract/`, `meta/versions.md` with a provenance column, `meta/run-log.md`, and
  `implementation/work-orders/` are populated
- `docs/observability/attribute-schema.json` agrees with the document's Appendix A
- The host memory pointers exist and point at the index note rather than copying it

Reuse the accepted BT names, `workflow.name` strings, attribute keys, and finding ids exactly.
Renaming an accepted workflow breaks every dashboard, detector, and MetricSet built on it.

No application code. No credential value in any note.

$ARGUMENTS
