# The agent wiki — memory that survives the session

The customer document is prose for humans, read front to back, once. Agents need the
opposite: small addressable notes, retrieved by subject, updated in place, diffable in a pull
request. Using one artifact for both jobs is what produced a 300-kilobyte "instrumentation
recommendations" document that no customer read and no agent could load without spending its
whole context on material irrelevant to the task in hand.

So the lower layer is a **wiki**: one note per subject, cross-linked, with frontmatter that
both a human tool (Obsidian, Foam, Dendron, a Git-backed wiki) and an agent memory feature
can read.

## Where it lives

```
wiki/
  README.md                       # entry point: customers, conventions, how to read this
  <Customer>/
    README.md                     # customer-level: tenancy, entitlement, contacts, applications
    <app>/
      index.md                    # map of content for this application — the note an agent loads first
      meta/
        engagement-inputs.yaml    # the run's inputs, copied here on completion
        versions.md               # tool, SDK, semconv, and provider versions this app is designed against
        run-log.md                # one row per architect or implementer run, newest first
        decisions.md              # accepted decisions with their date and rationale (an ADR log)
      architecture/
        observed.md               # the composition, as of the last run
        surfaces.md               # bundles, routes, chunk map
        buses.md                  # one section per bus: topics, accounts crossed, inject/extract state
        third-parties.md          # every third party, its purpose, and its telemetry consequence
      findings/
        F-01-<slug>.md            # one note per finding, with status: open | fixed | regressed | accepted
      contract/
        cross-cutting.md          # the attribute set and the five code patterns
        baggage.md               # the budget, the allowlist, and each key's named consumer
        collector.md              # the config and why each processor is where it is
        mpm.md                    # dimension-eligible and attribute-only, with the arithmetic
        attribute-schema.json     # the machine form — the same file the document appendix generates
      business-transactions/
        <bt>.md                   # one note per BT: surface, owning artifact, flag, workflows
      workflows/
        <workflow>.md             # one note per workflow: intent, spans, attributes, metrics, SLI, detectors
      use-cases/
        <flow>.md                 # the composite: narrative, identity, dashboard, joins
      metrics/
        custom-meters.md
      detectors/
        <detector>.md             # condition, threshold and its provenance, arm state, runbook
      slos/
        <sli>.md                  # user-facing statement, queries, objective, budget, burn rate
      implementation/
        work-orders/<nn>-<slice>.md   # what the implementer agent will do, one note per PR-sized slice
        enforcement.md            # the CI checks that keep the contract true
      as-code/
        inventory.md              # what exists in the tenant, what Terraform owns, what was imported
        refusals.md               # what could not be generated and the missing key for each
```

Two rules about the path, and they are the load-bearing ones:

**Customer first, then application.** A customer has more than one application and the
things that are true at the customer level — realm, entitlement, privacy regime, who holds a
credential — are true for all of them and must not be duplicated per application, because
duplicated facts drift and then two applications disagree about the same MTS budget.

**The application directory name is the `<app>` identifier used everywhere else**: in
`service.name`, in the document filename, in the `<org>.bt` prefix. One string, so a grep
finds everything.

## Note shape

Every note opens with YAML frontmatter, then a single H1, then content. The frontmatter is
what makes the wiki machine-usable:

```markdown
---
title: checkout.order.submit
type: workflow            # workflow | bt | use-case | finding | detector | sli | reference | work-order
customer: <Customer>
app: <app>
status: designed          # proposed | designed | implemented | verified | retired
updated: 2026-09-18
run: v3
tags: [checkout, payment, cross-account]
bt: [checkout, express-checkout]
sli: [checkout-success, checkout-latency]
sources: [F-01, "analysis-<app>-2026-09-18.md#use-case-checkout"]
---

# checkout.order.submit

...
```

`status` is the field the CI and the delta run read, so it is not decoration: a workflow at
`designed` with code in the repository that emits it is a wiki that has gone stale, and that
is a detectable condition rather than a matter of opinion.

Link between notes with `[[wikilinks]]` — `[[checkout.order.submit]]`,
`[[F-01-boot-bundle-api-key]]`. They resolve in Obsidian and every compatible tool, they
survive a file move, and an agent can follow them without a path. Use a relative Markdown
link only when pointing **out** of the wiki, at a real file in the repository.

## Making the hosts read it

An agent that has to be told to read the wiki will not read it. Each host has a place that
is loaded automatically, and the wiki install writes a short pointer into it — a pointer,
never a copy, because a copy is a second authority that drifts:

| Host | File | Contents |
|---|---|---|
| Cursor | `.cursor/rules/obengineer-wiki.mdc` | `alwaysApply: true`, and the path to `wiki/<Customer>/<app>/index.md` plus the retrieval rule below |
| Claude Code | `CLAUDE.md` (or an `@import` from it) | the same pointer |
| Codex / generic | `AGENTS.md` | the same pointer |

The retrieval rule those pointers carry, verbatim, because it is the whole discipline:

> Before changing instrumentation, read `wiki/<Customer>/<app>/index.md`, then only the notes
> for the BTs and workflows in scope. Do not load the whole wiki. After a change lands,
> update the `status` and `updated` fields of the notes you touched in the same commit.

"Do not load the whole wiki" is the point of having a wiki. A run that reads all of it has
rebuilt the 300-kilobyte document with extra steps.

## The index note

`index.md` is a map of content, not a summary. It is the one note an agent may load
unconditionally, so it stays under roughly 200 lines and contains links plus the few facts
needed to choose what to load next: the application in one paragraph, counts (BTs,
workflows, use cases, open findings), the current run version, and a table of entry points by
task — "implementing a workflow: start at `[[<workflow>]]` and `[[cross-cutting]]`";
"adding a dashboard: start at `[[mpm]]` and the use-case note".

A summary in the index is a fact with two homes. Link instead.

## Relationship to the customer document

The document and the wiki share content but not authority, and every fact has exactly one
owner:

| Fact | Authority | The other one |
|---|---|---|
| Narrative, findings, phasing, portfolio mapping | The document | Wiki notes link to the document section |
| Attribute keys and dimension eligibility | `contract/attribute-schema.json` | The document appendix is generated from it |
| Per-workflow spans, events, thresholds | The wiki note | The document use case summarises it |
| Run history, versions, decisions | `meta/` | Document control cites it |

The document is regenerated per run and versioned by filename. The wiki is **updated in
place** and versioned by Git. That difference is deliberate: a customer wants to see what
changed between two documents, and an agent wants the current state without reconstructing it
from a changelog.

## Reinforcement path

The wiki is what makes learning across engagements possible, because it is the only place
where a prediction and its outcome sit next to each other:

- **`meta/decisions.md`** records what was proposed and what the human accepted. The diff between them is preference data — the highest-value signal the project generates, and it is otherwise thrown away at the end of every session.
- **`findings/`** with a `status` field turns findings into an outcome series: how many were fixed, how long they stayed open, which classes recur across customers. A finding class that recurs points at a reference that failed to prevent it.
- **`detectors/`** with threshold provenance shows which placeholder thresholds were replaced and by how much, which is the only honest measure of whether the invented numbers were any good.
- **`run-log.md`** gives the denominator for all of it.

None of that requires a training loop to be useful, and all of it is a prerequisite for one.
See [`incremental-runs.md`](incremental-runs.md) for how a later run consumes it.

## Warning signs

- **A note that duplicates a document section verbatim.** Two authorities, and the wiki will lose because nobody re-renders it.
- **The wiki updated in a separate commit from the code.** Then it is documentation, and it is wrong within a week. Same commit, or a CI check that fails the pull request.
- **`status: designed` everywhere, months in.** Nobody is closing the loop, and the delta run has nothing to work from.
- **An index note that has grown a summary of every workflow.** It is now the document again. Cut it back to links.
- **Notes with no `updated` field.** The delta run cannot tell stale from current, so it will re-derive everything and produce a full rewrite.
- **A credential in the wiki.** The same rule as the document, and more dangerous here because a wiki is loaded into agent context by default. Record who holds it, never the value.
