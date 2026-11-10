# Prompt 05 — Verify the accepted contract

**Agent:** [`../agents/instrumentation-verifier.agent.md`](../agents/instrumentation-verifier.agent.md)
**Skill:** `instrumentation-verify`
**Inputs:** `docs/observability/engagement-inputs.yaml`, exact acceptance, verification
plan, provenance ledger, and optional exclusions
**Output:** read-only verification JSON/Markdown, ledger append, outcome metrics/issues

**Invoke it, do not paste it.** `/ob-verify` reads this file in place.

Follow the verifier agent and the verification-run authority. Discover acceptance only at
`docs/observability/analysis/<app>/V<N>/acceptance.yaml` and reject ambiguous records.
Validate its accepted content commit and digest, the plan, exclusions, and ledger before
querying. New plans, results, and exclusions use schema version 2,
`analysis_content_commit`, and stable plan `source_ref` values; schema version 1 remains
readable only for migration. Use only read operations.

Human-approved unremediable criteria are omitted from machine result rows and denominators
but remain in the human report, exclusion record, and ledger. For each unmet eligible
criterion, notify the human and provide exact remediation and recheck instructions.

Preview every anonymized outcome issue. Publish through existing authenticated `gh`; when
authentication is absent, provide the web login handoff. Never ask for a token in chat.

No tenant mutation, apply, deploy, merge, detector state change, credential rotation, or
auto-remediation.

$ARGUMENTS
