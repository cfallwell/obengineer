---
name: instrumentation-verify
description: >-
  Verify an accepted obengineer contract against read-only tenant evidence,
  notify humans about unmet criteria with exact remediation and recheck steps,
  honor human-approved unremediable exclusions, append provenance and outcome
  metrics, and publish anonymized reusable defects as GitHub issues. Use when
  the user types $instrumentation-verify or /ob-verify, asks to verify outcomes, close the observability
  loop, validate exit criteria, or measure contract quality.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Instrumentation Verify

## Preconditions

1. Verify the exact-commit acceptance record.
2. Validate `verification-plan.json`, `provenance-ledger.json`, and optional
   human-approved `verification-exclusions.json`.
3. Load only the read integrations named by eligible criteria.
4. Refuse every tenant mutation operation.

Authorities:

- [`../references/verification-run.md`](../references/verification-run.md)
- [`../references/provenance-ledger.md`](../references/provenance-ledger.md)
- [`../references/outcome-metrics.md`](../references/outcome-metrics.md)
- [`../references/outcome-issues.md`](../references/outcome-issues.md)
- [`../references/mcp-servers.md`](../references/mcp-servers.md)

## Process

1. Reconcile accepted criteria with human-approved exclusions. The verifier never marks a
   criterion unremediable.
2. Execute each eligible query through read-only list/get/search/query operations.
3. Record `met`, `unmet`, or `unmeasurable`.
4. For every unmet criterion, notify the human with expected/observed evidence, owner,
   exact remediation command/instructions, and recheck steps.
5. Keep human-approved unremediable criteria out of machine result rows and metric
   denominators, while retaining them in the Markdown report, exclusion file, and ledger.
6. Validate results and append ledger checks/metric opportunities.
7. Preview an anonymized outcome issue. Publish only through existing authenticated `gh`;
   otherwise provide the web-login handoff and rerun instructions.

## Outputs

- JSON and Markdown results under `docs/observability/verification/`;
- updated provenance ledger;
- local/CI human notification;
- anonymized GitHub issue create/update when previewed and authenticated.

CI exits nonzero for unmet criteria. `unmeasurable` lowers coverage and stays visible.

## Prohibitions

No apply, deploy, merge, detector arm/disarm, credential rotation, tenant write, or
auto-remediation. Remediation routes to `/ob-implement`, `/ob-terraform`, contract
amendment, or a named human owner.
