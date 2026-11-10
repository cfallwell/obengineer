# Read-only verification run

`/ob-verify` closes the loop after implementation and manual Terraform apply. It reads the
accepted contract and tenant; it never creates, updates, deletes, enables, arms, applies,
deploys, or remediates.

## Accepted inputs

- content-bound acceptance record for the selected version and verified artifacts;
- `verification-plan.json`;
- `verification-exclusions.json` when a human has approved exclusions;
- `provenance-ledger.json`;
- implementation coordination/work-order proof;
- Terraform plan/apply evidence supplied by the human; and
- read-only MCP/API access named by the plan.

## Verification plan

Analysis emits `docs/observability/verification-plan.json`:

```json
{
  "schema_version": 1,
  "criteria": [{
    "id": "VC-001",
    "source_section": 17,
    "system": "splunk-observability",
    "query": {
      "kind": "signalflow",
      "operation": "query",
      "method": "POST",
      "endpoint": "https://stream.<realm>.observability.splunkcloud.com/v2/signalflow/execute",
      "reference": "SRC-signalflow-criterion"
    },
    "expected": {"operator": "equals", "value": true},
    "observation_window": "PT30M",
    "owner": "platform",
    "remediation": {
      "route": "implementation",
      "selector": "work-order:WO-001",
      "instructions": "Run the linked work order, deploy, then rerun VC-001."
    }
  }]
}
```

Criteria IDs are stable. Allowed remediation routes are `implementation`, `terraform`,
`contract-amendment`, and `human-owner`. Every criterion needs actionable instructions
before it is eligible for the machine results schema.

## Human-approved exclusions

Read-only checks will encounter criteria that cannot be remediated. The verifier notifies
the human with evidence, reason, and recommended next decision. It does not decide that a
criterion is unremediable.

A human may approve `verification-exclusions.json`, bound to the exact analysis commit,
with criterion id, `decision: unremediable`, reason code, rationale, approver, RFC3339
timestamp, review date, and ledger evidence IDs.

Approved exclusions do not appear in machine result rows or metric denominators. They
remain visible in:

- the human Markdown report;
- the exclusions file;
- the provenance ledger decision and notification entries.

## Results

Machine results contain only eligible criteria with `met`, `unmet`, or `unmeasurable`.
Excluded criteria are forbidden.

Every `unmet` row includes expected and observed values, ledger evidence IDs, owner,
remediation route, exact next command/instructions, and recheck instructions. The human is
notified in chat and, in CI, in the job summary. CI exits nonzero on `unmet`.

`unmeasurable` remains visible and lowers measurement coverage. It names the missing access
or evidence and the human action required.

The summary is recomputed:

```text
eligible = accepted criteria - approved exclusions
eligible = met + unmet + unmeasurable
```

Output:

- `docs/observability/verification/verification-<app>-<timestamp>.json`
- same basename `.md` for human notification/remediation;
- appended ledger checks, notifications, decisions, and metric opportunities.

## Read-only capability boundary

Allowed operations are list/get/search/query/plan-read. Forbidden operations include
POST/PUT/PATCH/DELETE that mutate tenant state, Terraform apply, detector enable/disable,
credential rotation, deploy, and repository merge.

Publishing a previewed anonymized outcome issue is a separate GitHub write governed by
[`outcome-issues.md`](outcome-issues.md); it is not tenant remediation.
