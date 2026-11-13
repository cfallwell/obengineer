# Versioned analysis documentation site

The analysis review surface is linked Markdown, not a monolithic customer document.
It opens in the host's native side panel. No run starts a web server, opens a browser,
or publishes a localhost URL.

## Location and versions

Each run creates an immutable version:

```text
docs/observability/analysis/<app>/
  index.md                         # version chooser; latest accepted version first
  V1/
    index.md                       # landing page
    overview/
    findings/
    strategy/
    implementation/
    use-cases/
    workflows/
    business-transactions/
    contracts/
    operations/
    reference/
  V2/
    ...
```

Use uppercase visible labels exactly: `[V1] [V2] [V3]`. Prior labels are relative links;
the selected label is bold plain text. Every selected version is self-contained
and links only to its matching wiki snapshot under
`wiki/apps/<app>/versions/V<N>/`. Earlier versions never resolve through a mutable
“current” page.

At the top of every version:

1. the version selector;
2. a breadcrumb beginning at `Analysis`;
3. title and status: analysis complete, awaiting acceptance, accepted, or superseded;
4. a **Side-panel navigation** notice;
5. the contextual next-step callout; and
6. `Changes in this version`: inputs added or edited and the resulting changes to
   findings, strategy, use cases, workflows, business transactions, schema, and work
   orders.

## Host-native navigation

All links are relative Markdown links or host-native document actions. Commands return
the root `index.md` as the single documentation link. The host opens it in its own side
view when that surface exists; otherwise it renders the same Markdown in its native
document view.

Forbidden:

- `python -m http.server`, Vite, or another preview server;
- a localhost or loopback URL;
- opening a system browser;
- JavaScript routing that requires a live process; and
- pasting the analysis into chat as a substitute for the documentation link.

Every detail page opens with:

```markdown
[Analysis](../index.md) / [<Parent>](index.md) / **<Current page>**
```

Adjust relative paths for depth. Detail pages end with related pages and the next
recommended review step.

## Landing page

The approved landing page is a long linked index. It does not duplicate every object
detail, but it gives a substantive summary of every review area before linking the
canonical detail view. A reviewer can understand the observed architecture and choose
the next subject without opening pages blindly. **Architecture is summarized on the
landing page itself**; it is never hidden behind the first link.

Use this exact order:

1. `[V1] [V2] [V3]`;
2. breadcrumb: `Analysis`;
3. title and substantive scope;
4. `## Status`;
5. one contextual `## Next steps` section:
   - **Next steps** while awaiting acceptance; or
   - **V<N> accepted — implementation can start** after acceptance;
6. `## Changes in this version`;
7. `## Table of contents and section summaries`, as a three-column table:
   `Section | Substantive summary | Open`;
8. `## Architecture summary`, with the observed storefront/client composition,
   backends, accounts, buses, downstreams, third-party consequences, initialization
   owner, SPA route behavior, and failure path;
9. `## Priority review map`, a two-column table whose headers are `Priority findings`
   and `Primary use cases`, with names and review links; and
10. `## Side-panel navigation`, stating that the site uses only relative Markdown.

The Contents table rows, in order, are:

1. Architecture
2. Technology
3. Current telemetry
4. Findings
5. Instrumentation strategy
6. Implementation path
7. Work orders
8. Use cases
9. Workflows
10. Business transactions
11. Shared signal contracts
12. Operations and verification
13. Reference

Every summary is at least one substantive sentence grounded in the matching detail.
Every `Open` cell links the matching detail index, which must be nonempty. The local Work orders view
summarizes and links the complete versioned queue; there are no unlinked content rows.

## Next steps

Before acceptance, the landing callout reads:

```markdown
1. Review [Architecture](overview/index.md), [Findings](findings/index.md), and the
   [Recommended path](implementation/index.md).
2. Review [Use cases](use-cases/index.md) and [Work orders](<wiki path>).
3. Run `/ob-add-inputs` or `/ob-edit-inputs` if evidence should change.
4. Reply `yes` in chat to accept V<N> and merge its reviewed analysis PR.
```

After acceptance, replace that callout with:

```markdown
1. Review [WO-001](<versioned wiki path>).
2. Confirm its repository paths are authorized.
3. Run `/ob-implement work-order:<id>` using the Ready id shown above.
4. Review and merge the linked implementation PRs, deploy, and return to the
   [work-order queue](<versioned wiki path>) for the next Ready order.
5. Generate and review Terraform independently; a human applies it.
6. Run `/ob-verify` after deployment and apply.
```

Use the actual first Ready id rather than assuming `WO-001`.

## Findings

The landing preview carries only priority finding names and one link. The Findings index
carries id, conclusion, impact, affected use cases, decision, and a detail link. A finding
page carries:

- why it matters;
- observed evidence and confidence;
- exposure and risk;
- decision and remediation;
- affected use cases, workflows, transactions, contracts, and work orders; and
- verification.

Security findings follow `security-assessment.md`. A mode that did not authorize a check
does not create an empty chapter; the limitation belongs on the evidence page and, when
material, in a finding.

## Strategy and implementation path

The strategy index covers only layers in evidence:

- foundation and deterministic contract checks;
- browser/RUM;
- bounded context and identity;
- backend HTTP propagation;
- messaging propagation;
- collector derivation and redaction;
- metrics and cardinality;
- logs and trace correlation; and
- dashboards, detectors, objectives, release events, and verification.

The implementation path orders outcomes by dependency. Each phase links the exact work
orders that realize it.

## Work orders

Analysis creates every work order before review. The landing queue contains:

| ID | Kind | Outcome | Depends on | Status | Unlocks | Detail |
|---|---|---|---|---|---|---|

Rows link the canonical versioned wiki pages. Do not copy repository legs, code detail,
or acceptance criteria onto the landing page. Foundation rows come first. Then each
use-case row is followed by its subordinates grouped workflow, business transaction,
detector, alert condition, dashboard, and custom code. Before acceptance, dependency-free
foundation rows are `proposed`; acceptance makes them `ready`. Dependent rows and all
non-foundation rows remain `blocked` until every foundation order is implemented or
verified. Live status and revisions come from
`wiki/apps/<app>/implementation/V<N>/state.yaml`; see
[implementation-work-orders.md](implementation-work-orders.md#state-ledger-and-revisions).

## Use cases, workflows, and business transactions

Review in that order. A use case maps to one or more business transactions; each business
transaction is made up of one or more workflows, and each workflow belongs to exactly one
business transaction.

A use-case summary states why it matters, the question answered, what is created, its
workflows, business transactions, full span and event design, bounded metrics, dashboards,
thresholded detectors, objective and error budget, acceptance proof, and work orders.

A workflow page carries boundaries, span tree, events, captured context, meters with
three to six bounded dimensions, every join labelled `continue-trace`, `span-link`, or
`attribute-pivot`, detectors, objective, code locations, verification, and work orders.

A business-transaction page carries the bounded grouping value, included workflows,
where it is set, propagation, tenant rule, verification query, and work orders.

Each direction is linked. A reviewer can move from a finding to a use case to a workflow
to a transaction to a work order and back without searching.

## Canonical JSON, orchestration, and deterministic rendering

Every new version is rendered from a canonical schema-v3 `analysis-contract.json` that
conforms to `instrumentation-analyze/schemas/analysis-contract-v3.schema.json`.
Historical accepted schema-v2 contracts continue to validate against the frozen
`analysis-contract-v2.schema.json` and render through an in-memory compatibility
projection without rewriting their files. For measured v2 budgets, legacy `inUse`,
`entitlement`, and `headroomAfter` map losslessly to v3 `usage`,
`enforcedSystemLimit`, and `systemHeadroomAfter`. The contract contains
the architecture, technology, current telemetry, findings, strategy, implementation
phases, work orders, use cases, workflows, business transactions, cross-cutting
contracts, operations, and reference evidence. The renderer is deterministic: the same
validated JSON produces byte-identical Markdown.

Evidence collection uses `analysis-job-manifest.schema.json`. A manifest contains at
most six fixed workstreams: production; source and technology; diagrams and prior
artifacts; Observability Cloud; platform, cloud, and messaging; and public evidence plus
authorized security review. The host owns worker creation. The repository **does not
claim it can spawn agents**; it validates worker results and their recorded intervals.
One host concurrency slot is always reserved for the coordinator. When two or more jobs
are runnable, audited intervals must show overlap without exceeding the remaining host
capacity.

The semantic gate rejects unresolved placeholders, empty pages, missing required object
fields, unbounded meter designs, detectors without thresholds, objectives without error
budgets, incorrect Collector order, inconsistent cardinality arithmetic, broken links,
and missing breadcrumbs.

## Conditional summaries

Always create:

- architecture and evidence;
- attributes; and
- metrics.

Create and link only when applicable:

- messaging;
- ad attribution;
- collector processing;
- Log Observer Connect;
- Synthetics;
- ThousandEyes; and
- optional portfolio products.

Do not create `Not in evidence` pages. Put plausible future additions on one
`reference/suggested-additions.md` page. Put useful unanswered human inputs on
`reference/intake-recommendations.md`; no human must type `unknown`.

## Optional Word summary

Word is opt-in. When requested, render only:

- analysis summary;
- architecture readout;
- findings;
- recommended path;
- work-order summary; and
- use-case summaries.

It must remain under 20 pages. Deep technical detail stays in linked Markdown. Rendering
or Word verification is not an analysis completion condition when Word was not requested.

## Chat handoff

After an analysis PR merges, the final response has this exact shape:

```markdown
[Open <app> analysis V<N>](<host-native artifact link>)

Next steps:
1. Review Architecture, Findings, Strategy, Use Cases, and Work Orders.
2. Use `/ob-add-inputs` or `/ob-edit-inputs` if evidence should change.
3. Reply `yes` to accept this version.
```

Do not paste findings or detail below the link. After acceptance, replace step 3 with
the Ready work order, exact `/ob-implement` command, PR/deploy sequence, Terraform
boundary, and `/ob-verify`.
