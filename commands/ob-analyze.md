---
description: Analyze — scan the application and write the customer analysis document
---

Run obengineer run 1 — analyze.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-architect.agent.md` as your operating
   contract for this run. It is the authority on what must be produced.
2. Load the engagement inputs from `docs/observability/engagement-inputs.yaml`. If the file
   is absent or incomplete, run the intake first
   (`{{OBENGINEER_ROOT}}/skills/engagement-intake/SKILL.md`) — do not proceed on guesses,
   and do not re-ask for anything the file already answers.
3. Check for `wiki/apps/<app>/services/<service>/index.md`. If it exists with entries in
   `meta/run-log.md`, this is a **delta run**: read `meta/` and the accepted names before
   scanning, reuse every accepted name and finding id, and report change rather than
   reproducing the previous document.
   Rules: `{{OBENGINEER_ROOT}}/skills/references/incremental-runs.md`.
4. Follow `{{OBENGINEER_ROOT}}/prompts/01-analyze-application.md`. That file is the run
   contract; read it rather than waiting for it to be pasted.
5. Skills: `$instrumentation-analyze`, `$baggage-propagation`, `$cardinality-budget`,
   `$customer-doc-render`, then `$deliverable-review` before you report.
6. Follow `{{OBENGINEER_ROOT}}/skills/references/security-assessment.md` for exposed
   credentials, insecure/exposed APIs, OWASP coverage, confidence, and P0 routing.
7. Follow `{{OBENGINEER_ROOT}}/skills/references/analysis-run-lifecycle.md`: include the
   intake artifact, create the analysis branch, commit each phase, push, and open one
   docs-only PR.
8. Follow `provenance-ledger.md`, `context-loading.md`, and `verification-run.md`;
   validate the ledger and read-only verification plan before review.

This is the **only customer-facing document**. Section order is owned by
`{{OBENGINEER_ROOT}}/skills/references/document-template.md`; read it first.

Not complete until all six artifacts exist and the render verifier exits 0:

- `docs/observability/analysis-<app>-<date>.md`
- `docs/observability/<Customer>-<App>-Analysis-<date>.docx`, rendered from that Markdown
- `docs/observability/attribute-schema.json`
- `docs/observability/implementation-map.json`
- `docs/observability/provenance-ledger.json`
- `docs/observability/verification-plan.json`

Plus a seventh, when entitlement or a supplied traffic baseline exists:
`docs/observability/entitlement-exposure-<app>-<date>.md` for the account team,
markdown only, never rendered. Spec:
`{{OBENGINEER_ROOT}}/skills/references/entitlement-exposure.md`.

The prompt and references own the invariants: Critical Findings and OWASP coverage in
section 4; confirmed/high-confidence vulnerabilities in section 5 P0 fixes; contiguous
catalogue; mandatory cross-cutting code; provenance-labelled Business Value Realization;
and entitlement pricing without silent design cuts.

Docs-only analysis PR. Do not modify application source, merge the PR, display ingest
tokens, or produce a second customer-facing document.

$ARGUMENTS
