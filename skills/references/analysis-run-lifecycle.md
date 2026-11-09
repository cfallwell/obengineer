# Analysis branch, commit, pull request, and acceptance lifecycle

This reference owns git and review behavior for intake, analysis, and generation.
Analysis artifacts are reviewable repository changes, not files left in an agent
workspace.

## Intake does not create git history

`/ob-intake` writes or updates `docs/observability/engagement-inputs.yaml`. It does not
create or switch branches, commit, push, or open a pull request. The file remains an
uncommitted input until `/ob-analyze` validates it and includes it in the analysis PR.

## One branch and PR per analysis run

Normalize `engagement.application` to a lowercase kebab-case slug.

| Run | Branch |
|---|---|
| First analysis, interactive or CI | `initial-<app>-analysis` |
| Later analysis started by CI | `ci-initiated-<app>-analysis` |

These names intentionally use lowercase kebab-case. A CI run does not use the CI name
when it is the application's first analysis. A later interactive delta must be queued
through the same CI analysis workflow so branch ownership and collision handling remain
single-sourced.

Fetch the current default branch, require a clean working tree except for validated
intake artifacts, and create the analysis branch from that default branch. If the branch
or an open PR with that analysis identity already exists, stop and report the collision;
do not overwrite, force-push, or append two runs to one PR.

In CI, the workflow runner owns branch creation and passes
`--branch-owned-by-runner` to each analysis phase; the agent must not create a second
branch. The runner materializes the validated intake artifact from the prior intake run.

## Phase commits

Commit each completed analysis phase on the same new branch:

1. `analysis(<app>): capture evidence and security findings`
   - validated `engagement-inputs.yaml`;
   - generated production diagram and evidence files;
   - security coverage matrix and Critical Findings working artifact.
2. `analysis(<app>): add instrumentation contract`
   - analysis Markdown;
   - `attribute-schema.json`;
   - `implementation-map.json`;
   - `provenance-ledger.json`, with analysis-owned entries sealed;
   - `verification-plan.json`;
   - conditional entitlement exposure.
3. `analysis(<app>): render and verify deliverables`
   - rendered `.docx`;
   - review corrections and verification metadata.

Create the pull request after the first commit, then update the same PR after later phase
commits. Only analysis-owned paths may be staged. Unrelated changes block the commit until
the owner separates them.

The PR is docs-only. Its body states run type, evidence sources and limitations, security
assessment mode, findings by severity and P0 priority, generated artifacts, unresolved
repository/Jira mappings, and verification results. The run never merges its own PR.

The human reviews and merges the analysis PR before generation. Merge alone is not
acceptance; after merge, the human invokes `/ob-generate accept … at <analysis-commit-sha>`.
Generation fetches the updated default branch, verifies that the accepted SHA is an ancestor
of it, and creates `generate-<app>-wiki` from that default branch. This prevents a generation
PR from duplicating or stacking unmerged analysis commits.

## Acceptance is explicit and commit-bound

File existence, successful rendering, a generic PR approval, and merging are not contract
acceptance.

After reviewing the analysis PR, a human accepts by invoking:

```text
/ob-generate accept docs/observability/analysis-<app>-<date>.md at <analysis-commit-sha>
```

The SHA must contain the Markdown, schema, and implementation map being accepted.
`/ob-generate` confirms those files match that commit and writes:

```text
docs/observability/analysis-<app>-<date>.acceptance.yaml
```

Required fields:

```yaml
status: accepted
analysis: docs/observability/analysis-<app>-<date>.md
analysis_commit: <full-sha>
analysis_pr: <url-or-number>
accepted_by: <reviewer identity>
accepted_at: <RFC3339 timestamp>
qualifications: []
rejected_decisions: []
provenance_seal_digest: <sha256-of-sealed-ledger-projection>
```

If the invocation omits the path or exact SHA, `/ob-generate` stops and prints the exact
acceptance command. If the files differ from the named commit, it stops and asks for a
new review. The acceptance record is contract acceptance; a finding with
`status: risk-accepted` is a different decision.

Generation commits the acceptance record and wiki on that separate branch and opens a
documentation PR. It never modifies the accepted analysis content in that PR.

## CI analysis

A CI-triggered analysis follows the same artifact allowlist, phase commits, review, and
human acceptance. CI may open the PR; it may not create the acceptance record, approve,
or merge it. Credentials come from the CI secret store and never enter artifacts or logs.
