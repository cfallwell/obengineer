---
description: Analyze a target application and produce the customer analysis document (run 1 of 4)
---

Run obengineer run 1 — analyze.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-architect.agent.md` as your operating
   contract for this run. It is the authority on what must be produced.
2. Load the engagement inputs from `docs/observability/engagement-inputs.yaml`. If the file
   is absent or incomplete, run the intake first
   (`{{OBENGINEER_ROOT}}/skills/engagement-intake/SKILL.md`) — do not proceed on guesses,
   and do not re-ask for anything the file already answers.
3. Check for `wiki/<Customer>/<app>/index.md`. If it exists with entries in
   `meta/run-log.md`, this is a **delta run**: read `meta/` and the accepted names before
   scanning, reuse every accepted name and finding id, and report change rather than
   reproducing the previous document.
   Rules: `{{OBENGINEER_ROOT}}/skills/references/incremental-runs.md`.
4. Follow `{{OBENGINEER_ROOT}}/prompts/01-analyze-application.md`. That file is the run
   contract; read it rather than waiting for it to be pasted.
5. Skills: `$instrumentation-analyze`, `$baggage-propagation`, `$cardinality-budget`,
   `$customer-doc-render`, then `$deliverable-review` before you report.

This is the **only customer-facing document**. Section order is owned by
`{{OBENGINEER_ROOT}}/skills/references/document-template.md`; read it first.

Not complete until all three artifacts exist and the render verifier exits 0:

- `docs/observability/analysis-<app>-<date>.md`
- `docs/observability/<Customer>-<App>-Analysis-<date>.docx`, rendered from that Markdown
- `docs/observability/attribute-schema.json`

Plus a fourth, **only when `entitlement` was supplied**:
`docs/observability/entitlement-exposure-<app>-<date>.md`, addressed to the account team,
markdown only, never rendered. Spec:
`{{OBENGINEER_ROOT}}/skills/references/entitlement-exposure.md`.

Six things this run fails on if you are not deliberate:

- **Critical Findings is section 4**, immediately after the architecture, severity-ordered,
  each with files, exposure, risk, remediation, and verification. A credential is recorded by
  shape and location, never by value.
- **Nothing the argument depends on sits under an appendix heading.**
- **The catalogue is sections 19–25, contiguous**: business transactions, workflows, custom
  metrics, BT-aligned workflows, detectors with thresholds, SLIs and SLOs, composite use cases.
- **Cross-Cutting Attributes and Baggage Propagation** with all five code subsections.
- **Business Value Realization is section 26**, last in the body: the customer's own words,
  the last twelve months of the cited public record, the performance you measured, every
  figure labelled `stated` / `measured` / `public` / `derived`, every claim tied to a
  mechanism in this document, and no industry benchmark anywhere. Spec:
  `{{OBENGINEER_ROOT}}/skills/references/business-value.md`.
- **Entitlement prices the recommendation, it does not cap it.** No licensing, consumption,
  or overage number in the customer document; nothing trimmed to fit unless
  `fit_to_entitlement` is true.

Docs only. Do not modify application source. Do not display ingest tokens. Do not produce a
second customer-facing document.

$ARGUMENTS
