# Versioned analysis pull request and acceptance lifecycle

This reference owns branches, commits, review, acceptance, and the host-native handoff.
An analysis version is one reviewed pull request containing its inputs, linked Markdown
site, schema, ledger, verification plan, versioned wiki, and complete work-order queue.

## Input management creates no standalone history

`/ob-start`, `/ob-add-inputs`, and `/ob-edit-inputs` validate the ignored local
`obconfig.yaml`, hash its artifact directory, and dispatch analysis only after the exact
proceed gate. They do not open an input-only PR and never commit local config/state.

Exact `yes` creates one-shot authorization bound to config, complete artifact manifest
and delta, command, and intended version. Analysis atomically claims it before network
or analysis work. After analysis, rendering, and validation, `finalize` revalidates the
claimed inputs and hashes explicit generated-output roots immediately before the initial
commit/push/PR dispatch. Failed or declined work calls `abort`; only successful dispatch
calls `consume`, which records the finalized snapshot and advances the artifact baseline.

## One branch and PR per version

Normalize the application to lowercase kebab-case. Determine the next immutable uppercase
version label, then create:

```text
analysis-<app>-v<n>
```

Create it from the current default branch. An existing branch or open PR with that identity
is resumed only when its ledger says the same run owns it; otherwise stop and report the
collision. Never overwrite or force-push another run.

CI follows the same version and artifact rules. A runner-owned branch is reused rather
than creating another.

## Parallel analysis, serialized naming

Use the six fixed evidence jobs from the analysis manifest: production; source and
technology; diagrams and prior artifacts; Observability Cloud; platform, cloud, and
messaging; and public plus authorized security review. Reserve one host concurrency slot
for the coordinator. The host launches workers; repository tooling audits result shape,
recorded intervals, overlap, and capacity but never claims to spawn agents. Naming,
schema reconciliation, and the dependency graph remain serialized after evidence returns.

Naming and schema reconciliation remain serial.

## Performance budget and degradation

For a standard run:

- first required question: 5 seconds, before network or source discovery;
- manifest and worker scheduling after explicit authorization: 20 seconds;
- evidence collection: 10 minutes;
- reconciliation and schema freeze: 4 minutes;
- deterministic rendering: 3 minutes;
- validation and one repair cycle: 2 minutes; and
- total analysis: 20 minutes, excluding human review, forge operations, and CI.

Emit a progress update at least every 60 seconds while workers are active. A timed-out
worker returns a limited result with exact missing evidence; do not rerun it serially.
Authentication denial is recorded once and not retried indefinitely. If the total budget
expires or semantic QA still fails after one repair cycle, keep the PR draft and label the
result a degraded draft. Never run past 30 minutes and call a shallow result complete.

## Phase commits

Commit completed phases on the same branch:

1. `analysis(<app> V<n>): capture evidence and findings`
2. `analysis(<app> V<n>): publish strategy and contracts`
3. `analysis(<app> V<n>): add wiki and work orders`
4. `analysis(<app> V<n>): verify linked documentation`
5. optional `analysis(<app> V<n>): render Word summary`

Complete and validate every phase before dispatch. Then invoke the runtime `finalize`
gate with all generated output roots and, without intervening analysis/network/render
work, create the phase commits, push them together, and open the PR. Stage only
analysis-owned paths. The PR body states the version, inputs added or edited, evidence
and limitations, findings, strategy, artifacts, work-order count, verification results,
and the host-native analysis index path. Any mutation after finalize but before dispatch
requires `abort` followed by a fresh proceed/claim/finalize flow.

## Review loop

When the PR is ready, tell the human:

```markdown
Please review [PR #<number>](<url>).

When it is ready, reply `yes` to accept V<N> and merge this PR.
Reply `no` to leave it open. Add review comments for changes.
```

When the PR state becomes ready for review, read unresolved review comments, make only
supported corrections, commit them, and report what changed. Ask the acceptance question
again. Do not merge, accept, or infer approval without an explicit `yes`.

## Acceptance is content-bound without a manual SHA

The human never copies a path or commit SHA. An explicit `yes` after review authorizes:

1. change dependency-free work orders from `proposed` to `ready`;
2. compute a deterministic SHA-256 digest over the version's analysis index, linked pages,
   analysis contract, schema, implementation map, ledger seal, verification plan, and
   final versioned wiki;
3. verify that the same artifact paths and bytes exist in the Git tree named by
   `analysis_content_commit`;
4. write `docs/observability/analysis/<app>/V<N>/acceptance.yaml`;
5. commit and push that acceptance change to the same PR; and
6. merge the PR using the repository's configured merge strategy.

The record is:

```yaml
schema_version: 2
status: accepted
version: V<N>
analysis: docs/observability/analysis/<app>/V<N>/index.md
analysis_content_commit: <full branch commit before the acceptance commit>
analysis_content_digest: <sha256 of the accepted artifact set>
analysis_pr: <url>
accepted_via: explicit-human-confirmation
accepted_at: <RFC3339 timestamp>
qualifications: []
rejected_decisions: []
provenance_seal_digest: <sha256 of the sealed ledger projection>
```

Schema version 1 records that use `analysis_commit` remain readable for migration.
New records are schema version 2 and use only `analysis_content_commit` plus
`analysis_content_digest`; `analysis-contract.json` is required in their accepted
artifact set. Legacy accepted versions do not gain that requirement retroactively.

No accepter name, engineer name, or named owner is required. The digest survives merge,
squash, and rebase strategies because commit ancestry is not part of content identity.
Verification reads the recorded commit's Git tree and requires both its digest and the
current selected version to match. A content-equivalent rewritten commit is valid, but the
commit object named by the record must remain available; repositories that delete PR
objects after squash or rebase must preserve that object through an archival ref.
Changing any accepted file requires a new version and a new explicit acceptance.

When more than one immutable acceptance record exists, the app wiki index explicitly
marks one version accepted and active. Discovery follows that pointer rather than treating
normal `[V1] [V2] ...` history as ambiguous. Historical verification reads unversioned
companions such as the schema, implementation map, ledger, and verification plan from
that version's accepted commit tree; it never substitutes the newer mutable companions.

Finding risk acceptance is separate and may require the organization's own decision
record; it does not imply analysis acceptance.

## Post-merge handoff

Do not start a server or browser. Return one host-native link to:

```text
docs/observability/analysis/<app>/V<N>/index.md
```

Do not paste the analysis into chat. Immediately below the link provide concise review,
add/edit-input, and acceptance instructions. Once accepted, provide:

- the first Ready work order and its link;
- `/ob-implement work-order:<id>`;
- the implementation PR review and deployment sequence;
- the independent `/ob-terraform` plan and human-apply boundary; and
- `/ob-verify` after deployment and apply.

Earlier `[V1] [V2] ...` versions remain selectable and read-only. The accepted version is
the only executable work-order queue.
