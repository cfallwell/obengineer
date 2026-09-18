---
description: Write the full instrumentation contract plus the customer .docx and attribute schema (run 2 of 3)
---

Run obengineer run 2 — the instrumentation guide.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-architect.agent.md` as your operating
   contract for this run.
2. Load `docs/observability/engagement-inputs.yaml`. Run the intake first if it is absent.
3. Load the accepted analysis memo from run 1. If the human has not accepted one, say so
   and stop — this run deepens an accepted analysis, it does not replace it.
4. Follow `{{OBENGINEER_ROOT}}/prompts/02-develop-instrumentation-guide.md`.
5. Skills: `$instrumentation-guide`, `$baggage-propagation`, `$cardinality-budget`,
   `$customer-doc-render`.

Not complete until all three artifacts exist and the render verifier exits 0:

- `docs/observability/INSTRUMENTATION-GUIDE.md`
- `docs/observability/<Customer>-<Scope>-<Date>.docx`, rendered from that Markdown
- `docs/observability/attribute-schema.json`

The guide must contain the **Cross-Cutting Attributes and Baggage Propagation** section
with all five code subsections. A guide without it is a failed run.

Documentation only. No application code, no token values, no dashboard JSON unless the
human asked for stubs.

$ARGUMENTS
