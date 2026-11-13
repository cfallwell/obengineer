# Design rationale

This page explains why obengineer works the way it does. It is for maintainers and for
reviewers deciding whether to trust its output. For mechanics, see
[How it works](how-it-works.md).

## The problem

Observability is a cultural change, and most organizations struggle with that shift.
Today most engineering is outsourced, and even management, software architecture, and
design can be outsourced. How does an enterprise ensure that observability stays aligned
with the business? How does an organization that has outsourced its engineering drive a
culture of Observability-Driven Development (ODD) as a material shift in its engineering
processes? Those questions are why obengineer was developed.

Manual developer custom instrumentation engagements fail when:

1. the design assumes an architecture the application does not have;
2. findings and recommendations are buried in a long document nobody navigates;
3. use cases, workflows, business transactions, and code disagree about names;
4. implementation starts without a dependency order, so shared plumbing is built late
   or several times; or
5. nobody checks the tenant after deployment to see whether the signals arrived.

obengineer answers each one: it measures before it designs, publishes one linked and
versioned strategy, creates every work order before anyone approves it, releases those
orders in dependency order, and verifies outcomes against the tenant read-only.

## Measure first, label every fact

Each fact carries one of four labels: **measured** (source, production scan, tenant API,
connected tool), **stated** (from `obconfig.yaml` or the human), **public** (cited
research), or **derived** (visible arithmetic over the others). Measured evidence wins
when sources disagree, and the disagreement is recorded rather than hidden. A missing
source limits only the conclusions that depend on it; analysis never fills a gap with an
industry benchmark.

Direct Splunk APIs and MCP integrations coexist because neither is complete. When a
tenant block is configured, the direct API calls are mandatory; MCP tools add evidence
but cannot replace or relabel those results.

## Linked Markdown instead of a long document

A 40–150 page Word document is hard to navigate and expensive for an agent to load. The
analysis is a set of linked Markdown pages under
`docs/observability/analysis/<app>/V<N>/`. The landing page summarizes every area
(architecture, findings, strategy, work orders, use cases) and links its detail, and
every page has a breadcrumb back. It opens in the host's side panel with relative links,
so no browser, local web server, or port is involved. Word is available through
`/ob-render` as a summary under 20 pages, never as the contract.

## Immutable versions

The first `/ob-start` creates `V1`, and every later `/ob-analyze` creates the next
version, `V2`, `V3`, and so on, each in its own directory with a matching wiki snapshot.
A version never changes after it is published, and an older version never links to
newer content. Each version opens with what changed
in the inputs and what changed in the results, so reviewers compare versions without
reading Git history.

## Analysis creates the wiki and every work order

Reviewers approve the implementation plan, not just the recommendations. The same run
that writes the strategy also writes the agent-facing wiki, the attribute schema, the
repository mapping, the verification plan, and the complete work-order queue. Acceptance
then activates that queue; it does not generate anything new.

## Use cases lead

Attributes and platform features are mechanisms. A use case states the question the
instrumentation must answer, so it organizes everything else:

```text
finding → use case → workflow → business transaction → work order → verification
```

Every link in that chain is navigable in both directions.

## Foundation first, then any order

Shared prerequisites, such as deterministic contract checks in CI or a RUM agent that
initializes before the front-end framework bootstraps, undermine every later change if
they are fixed late. obengineer separates them into
at most about ten **foundation** work orders. They come from findings, not use cases,
and have no subordinates.

Implementation asks one question: *are all foundation work orders implemented or
verified?* Until the answer is yes, everything else is blocked. Once it is yes, any use
case, workflow, business transaction, detector, alert condition, dashboard, or
custom-code order can be implemented in any order. This avoids a long serial phase plan
while still guaranteeing the plumbing exists first.

RUM delivery is a foundation concern for the same reason. Injecting the RUM snippet at
the CDN edge places it first on every HTML response and lets the token or version change
without an application release, so analysis recommends it over in-code injection. Edge
configuration differs by CDN, so each CDN gets its own injection reference under
`skills/references/cdn/`, and the analysis links only the one that matches the site's
CDN, and only when the target has a web front-end.

## Acceptance is bound to content, not to a commit

A reviewer should not copy a commit SHA. They review one pull request and reply `yes`.
obengineer computes a SHA-256 digest over the accepted analysis pages, contract, schema,
implementation map, sealed ledger, verification plan, and wiki snapshot, and writes it to
`acceptance.yaml`. A digest survives merge, squash, and rebase; any later change to those
files is detectable and requires a new version.

## Revisions without new versions

Engineers and SREs legitimately refine an accepted plan: a span name, an extra
attribute, a renamed tag. Rerunning analysis for that would be slow and would discard
review history. So subordinate work orders can be revised with `/ob-revise`, which
records revision R2, R3, and so on in a separate state ledger outside the digest, chains
each revision to the previous one by hash, and opens a PR. Foundation and use-case
orders cannot be revised this way, because changing them changes the plan; that needs a
new analysis version.

## Safety boundaries

- Analysis never mutates production; the only active security checks are two fixed
  `HEAD` requests, and only when explicitly authorized.
- Credential values never enter chat, command arguments, logs, or generated files.
- No application code changes before a work order is Ready and its paths are authorized.
- Implementation never widens the accepted attribute schema.
- Terraform is planned, never applied; detectors ship disabled until signals are
  verified.
- Verification reads and reports; it never remediates.
- No step asks for or infers a named engineer, owner, or approver.
