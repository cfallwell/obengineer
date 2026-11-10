---
description: Terraform — generate one application directory, plan only, no apply
---

Run obengineer run 4 — observability as code.

1. Adopt `{{OBENGINEER_ROOT}}/agents/observability-as-code.agent.md` as your operating
   contract for this run.
2. Load `docs/observability/analysis-<app>-<date>.md`,
   `docs/observability/attribute-schema.json`, and
   `docs/observability/engagement-inputs.yaml`, plus the exact-commit acceptance record.
   Run `python3 "{{OBENGINEER_ROOT}}/skills/instrumentation-wiki/scripts/verify_analysis_acceptance.py" --record docs/observability/analysis-<app>-<date>.acceptance.yaml --repo .`.
   **Stop if acceptance is absent or does not match** — this run configures a contract,
   it does not invent one.
   Validate `provenance-ledger.json`, then append inventory, import, plan/schema-check,
   refusal, and artifact records without altering sealed analysis entries.
3. Follow `{{OBENGINEER_ROOT}}/prompts/04-generate-observability-as-code.md`.
4. Skills: `$observability-as-code`, `$cardinality-budget`. Use only the resource names in
   `{{OBENGINEER_ROOT}}/skills/references/splunk-terraform-providers.md`.

You produce `terraform fmt`/`validate`/`plan`-clean code and a handover. **Never run
`apply`**, and never create anything in a tenant.

Import what the tenant already has rather than duplicating it. Refuse any `group by` on a
key the schema marks attribute-only, and name the gap instead. Ship detectors disabled
until the signal is trusted. No token in any `.tf` or `.tfvars` file.

$ARGUMENTS
