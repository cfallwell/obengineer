# Provenance ledger

`docs/observability/provenance-ledger.json` is the single machine authority for evidence
and run state. Do not create parallel `evidence.json` or `run-state.json` files.
Human-readable document control, wiki run logs, public-evidence notes, and checklist
summaries are projections from this ledger.

## Shape

```json
{
  "schema_version": 1,
  "engagement": {"application": "<app>"},
  "contract": {"sealed_ids": []},
  "context_profile": {"loaded_references": [], "predicates": {}},
  "sources": [],
  "facts": [],
  "runs": [],
  "checks": [],
  "artifacts": [],
  "decisions": [],
  "unresolved": [],
  "seals": {}
}
```

Every entry has a stable `id`. IDs are unique across the ledger. References between
entries use those IDs and must resolve.

## Provenance

Fact provenance is one of `measured`, `stated`, `public`, or `derived`.

- `measured` requires collection timestamp, tool or endpoint, method/query, scope,
  observation window, and limitations.
- `stated` requires source role and timestamp.
- `public` requires URL, publication, publication date, and read date.
- `derived` requires source fact IDs and the formula.
- `not_in_evidence` is an unresolved entry, not a fact. It requires attempted source,
  failure reason, fallback question, and owner.

Conflicting facts remain in the ledger. A measured fact outranks a stated fact for the
current recommendation but never deletes it.

## Artifacts and runs

Artifacts record repository-relative path, SHA-256, producing stage, run id, and git
commit. Runs are append-only events. Corrections add a superseding entry; they do not
rewrite history.

Analysis seals the IDs it owns when the exact commit is accepted. Generation,
implementation, Terraform, and verification may append records but may not alter sealed
entries. Acceptance records the digest of the sorted sealed projection.

## Stage behavior

- Intake appends stated inputs and read-first entitlement facts.
- Analysis appends sources, measured/public/derived facts, context decisions, checks,
  artifacts, unresolved questions, and the verification plan.
- Generation consumes sealed analysis entries and appends acceptance/wiki artifacts.
- Implementation loads only ledger IDs cited by its work order and appends repository-leg
  proof.
- Terraform appends tenant inventory, imports, plan or schema-check results, refusals,
  and artifact hashes.
- Verification appends criterion observations and outcome metric opportunities.

## Safety

Never store credential values, raw sensitive payloads, customer PII, or unrestricted
tenant exports. Store a redacted shape, digest, repository-relative evidence path, and
access-controlled source reference.

The validator is
`skills/instrumentation-wiki/scripts/verify_provenance_ledger.py`. Every run validates
the ledger before consuming it and after appending to it.
