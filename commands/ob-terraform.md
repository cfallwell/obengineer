---
description: Terraform — generate one accepted application plan, never apply
---

Generate observability configuration from the accepted analysis version.

1. Adopt `{{OBENGINEER_ROOT}}/agents/observability-as-code.agent.md`.
2. Resolve the accepted version from `wiki/apps/<app>/index.md`. Load its analysis,
   schema, implementation map, inputs, and acceptance record.
3. Verify acceptance with:
   `python3 "{{OBENGINEER_ROOT}}/skills/instrumentation-wiki/scripts/verify_analysis_acceptance.py" --record docs/observability/analysis/<app>/V<N>/acceptance.yaml --repo .`.
   Stop if the content digest does not match.
4. Validate the provenance ledger and append inventory, import, plan/schema-check,
   refusal, and artifact records without altering sealed analysis entries.
5. Follow `{{OBENGINEER_ROOT}}/prompts/04-generate-observability-as-code.md`.
6. Use `$observability-as-code` and `$cardinality-budget`; resource names come only
   from `splunk-terraform-providers.md`.

Produce format/validate/plan-clean code and a handoff. Never apply or mutate the tenant.
Import existing resources, refuse groupings on attribute-only keys, keep detectors
disabled until signals are verified, and put no token in `.tf` or `.tfvars`.

$ARGUMENTS
