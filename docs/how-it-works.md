# How obengineer operates

obengineer is a versioned set of agent contracts, skills, references, validators, and
renderers. The host model investigates and authors; repository files constrain evidence,
outputs, changes, and verification.

## Runtime

```text
/ob-start
  → local obconfig validation, artifact hash, and proceed gate
  → parallel evidence collection
  → linked analysis V<N>
  → versioned wiki and all work orders
  → deterministic validation
  → one review PR
  → explicit yes: content-bound acceptance and merge
  → Ready work-order implementation / Terraform plan / read-only verification
```

`/ob-add-inputs` and `/ob-edit-inputs` repeat the same run as the next immutable version.

## Evidence

Facts are:

- **measured** from source, production, direct APIs, or connected tools;
- **stated** by the human;
- **public** from permitted cited research; or
- **derived** with visible arithmetic.

Measured evidence wins over stated descriptions. Splunk APIs and MCP integrations are
complementary. A missing MCP server does not disable direct API inventory. A missing
optional answer does not block analysis.

Independent sources run with maximum safe sub-agent parallelism. Naming and schema
reconciliation remain serial so concurrent workers do not create competing taxonomies.

## Versioned review surface

Each run creates:

```text
docs/observability/analysis/<app>/V<N>/
wiki/apps/<app>/versions/V<N>/
```

The analysis landing page represents the full strategy and links every detail:
architecture, findings, strategy, implementation path, work orders, use cases, workflows,
business transactions, shared contracts, operations, and reference.

Versions use `[V1] [V2] [V3]`. Every page carries a breadcrumb to Analysis and its parent.
Older versions are immutable and link only their matching wiki snapshot.

Navigation is host-native. No server, browser, localhost URL, or high port exists.

## Wiki and work orders

Analysis creates the wiki and complete work-order queue before review. The landing page
summarizes the queue and links canonical wiki files.

Before acceptance:

- dependency-free orders are Proposed;
- dependent orders are Blocked.

After explicit acceptance:

- eligible orders are Ready;
- the accepted version becomes the only executable queue.

Every object links its work orders. Every work order links its findings, use cases,
workflows, transactions, shared contracts, repository legs, dependencies, evidence, and
verification.

## Review and acceptance

One analysis PR contains inputs, linked Markdown, schema, implementation map, ledger,
verification plan, wiki, and work orders. When ready, the agent asks the human to review
the PR. Ready-for-review comments are processed as additional commits.

The human replies `yes` to accept and merge. The agent:

1. marks eligible work orders Ready;
2. computes a deterministic digest over the accepted artifacts;
3. writes the acceptance record;
4. commits and pushes it; and
5. merges using the repository strategy.

No manual SHA or named accepter is required. The digest survives squash and rebase.
Changing accepted content requires a new version.

## Handoff

After merge the chat contains one host-native analysis link, then concise next steps. It
does not reproduce the analysis.

After acceptance the handoff gives:

- the first Ready work order;
- the exact `/ob-implement work-order:<id>` command;
- PR review and deployment sequence;
- `/ob-terraform` with human apply; and
- `/ob-verify` after deployment and apply.

## Safety

- Production analysis is read-only.
- Secrets stay only in ignored mode-0600 `obconfig.yaml`, enter direct request headers
  only, and never enter generated artifacts.
- Application changes require a Ready work order and authorized paths.
- Implementation opens review PRs and does not silently widen the schema.
- Terraform plans and never applies.
- Verification reads and routes remediation; it does not fix the tenant.
- Word is optional, generated, and under 20 pages.
