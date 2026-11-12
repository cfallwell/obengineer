# Design rationale

## The problem

Instrumentation engagements fail when:

1. the design assumes an architecture the target does not have;
2. findings and recommendations are buried in a long document;
3. use cases, workflows, transactions, and code disagree;
4. implementation starts without a bounded dependency graph; or
5. nobody verifies the tenant after deployment.

obengineer therefore measures first, publishes one linked strategy, creates every work
order before acceptance, and verifies accepted outcomes read-only.

## Why linked Markdown

A 40–150 page Word document is a poor navigation surface and an expensive context load.
The analysis is a versioned Markdown site whose landing page represents the full strategy
and links the detail. Review starts with findings and the recommended path, then use cases,
workflows, and business transactions.

The same content opens in the host's native side panel. Relative links and breadcrumbs
require no browser, localhost server, or live process.

Word remains available when explicitly requested. It is a generated summary under 20
pages rather than the complete technical contract.

## Why versions

Adding or editing inputs reruns analysis. `[V1] [V2] [V3]` keeps each result reviewable.
The top of each version states the input changes and resulting contract changes. An old
version never resolves to newer mutable wiki detail.

Git still records diffs. Immutable version directories make comparison available from the
review surface without asking a human to inspect commits.

## Why analysis creates the wiki and work orders

The old handoff required a separate generation run after document acceptance. It added a
manual SHA step and delayed the artifact implementation actually consumes.

The analysis now creates:

- the human-facing linked strategy;
- the agent-facing versioned wiki;
- schema and implementation mapping;
- verification criteria; and
- the complete proposed work-order queue.

Acceptance activates the queue; it does not generate it. This lets reviewers assess not
only what is recommended, but exactly how it will be implemented.

## Why use cases lead

Attributes and platform features are mechanisms. A use case states the question the
instrumentation must answer. It links the workflows that emit evidence and the business
transactions that group those workflows. Shared attributes, metrics, propagation,
collector, and operations pages support them.

This order keeps the strategy legible:

```text
finding → use case → workflow → business transaction → work order → verification
```

Every direction is linked.

## Why acceptance is content-bound

The human should not copy a commit SHA. They review one PR and explicitly reply `yes`.
obengineer hashes the accepted analysis, schema, map, ledger seal, verification plan, and
wiki, writes the acceptance record, marks eligible work orders Ready, and merges only with
that authorization.

A content digest survives merge, squash, and rebase. Any accepted-file change produces a
new version.

## Why APIs and MCP coexist

MCP servers expose useful host-integrated tools but may not cover every product endpoint.
Direct Observability Cloud and Splunk Platform APIs are first-class evidence sources.
Connected MCP tools supplement them. Missing one source limits only the conclusions that
depend on it.

Credentials remain only in ignored mode-0600 local `obconfig.yaml`, are sent only in
validated HTTPS request headers, and never enter chat or committed/generated files.

## Safety boundaries

- no production mutation during analysis;
- no credential values in context or artifacts;
- no application change before accepted Ready work order and path authorization;
- no schema widening during implementation;
- no Terraform apply;
- no detector arming before signal validation;
- no automatic remediation during verification; and
- no inferred named engineer, owner, or accepter.
