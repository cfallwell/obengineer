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

The approved landing page is a compact index, not the whole analysis stacked into one
view. It represents the full strategy through one summary, linked contents, and two
previews. Architecture, findings, strategy, path, work orders, use cases, workflows,
transactions, contracts, operations, and reference open as separate side-panel views.

Use this exact order:

1. `[V1] [V2] [V3]`;
2. breadcrumb: `Analysis`;
3. title and one-line scope/status;
4. **Side-panel navigation** notice: all controls remain in this panel; no browser,
   localhost server, or high port;
5. one contextual callout:
   - **Next steps** while awaiting acceptance; or
   - **V<N> accepted — implementation can start** after acceptance;
6. `## Changes in this version`;
7. `## Contents`, as a three-column table: `Section | What it contains | Open`;
8. `## Analysis summary`, one substantive paragraph;
9. a compact two-column table whose headers are `Priority findings` and
   `Primary use cases`, with names in the first row and **Review findings** /
   **Review use cases** links in the second.

Nothing else is expanded on the landing page.

The Contents table rows, in order, are:

1. Architecture
2. Findings
3. Instrumentation strategy
4. Implementation path
5. Work orders
6. Use cases
7. Workflows
8. Business transactions
9. Shared signal contracts
10. Operations and verification
11. Reference

Every `Open` cell links the matching detail index. Work orders link the complete
versioned queue. There are no unlinked content rows.

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

| ID | Outcome | Depends on | Status | Unlocks | Detail |
|---|---|---|---|---|---|

Rows link the canonical versioned wiki pages. Do not copy repository legs, code detail,
or acceptance criteria onto the landing page. Before acceptance, dependency-free rows
are `proposed`; acceptance makes them `ready`. Dependent rows remain `blocked`.

## Use cases, workflows, and business transactions

Review in that order.

A use-case summary states why it matters, the question answered, what is created, its
workflows, business transactions, signals, dashboards, detectors, acceptance proof, and
work orders.

A workflow page carries boundaries, span tree, events, captured context, meters, joins,
detectors, objective, code locations, verification, and work orders.

A business-transaction page carries the bounded grouping value, included workflows,
where it is set, propagation, tenant rule, verification query, and work orders.

Each direction is linked. A reviewer can move from a finding to a use case to a workflow
to a transaction to a work order and back without searching.

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
