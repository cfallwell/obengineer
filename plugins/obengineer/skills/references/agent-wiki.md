# Versioned agent wiki

The analysis site is the human index. The wiki is small addressable detail that agents
retrieve by subject. Analysis creates both in the same version and PR.

## Layout

```text
wiki/
  README.md
  apps/
    <app>/
      index.md                         # [V1] [V2] ... and accepted-version pointer
      versions/
        V<N>/
          index.md                     # version map and analysis breadcrumb
          meta/
            obconfig-provenance.json       # sanitized statuses/tree metadata; never actual config
            versions.md
            run-log.md
            decisions.md
          implementation/
            work-orders/
              index.md
              <id>.md
          services/
            <service>/
              index.md
              architecture/
              findings/
              contract/
              business-transactions/
              workflows/
              use-cases/
              metrics/
              detectors/
              slos/
              business/
              implementation/
              as-code/
```

An app is the website and its participating backend services. A shared service is
represented under each app that uses it and cross-linked. A human does not create these
directories first.

Versions are immutable snapshots. The app index marks one accepted version as active.
Host pointers resolve the app index and then the active version. An older `[V<N>]` never
links into a newer wiki snapshot.

Version metadata exists once under `versions/V<N>/meta/`. Service trees do not duplicate
`meta/versions.md`, `meta/run-log.md`, `meta/decisions.md`, or
`contract/attribute-schema.json`; they link the version metadata and the canonical
`docs/observability/attribute-schema.json`.

## Breadcrumbs and links

Every versioned note opens with:

```markdown
[Analysis](<version analysis index>) / [<Object index>](index.md) / **<Object>**
```

Use relative Markdown links from the wiki to analysis pages. Use `[[wikilinks]]` between
wiki notes. Link every direction:

- findings ↔ use cases;
- use cases ↔ workflows and business transactions;
- objects ↔ attributes, metrics, propagation, collector, and operations;
- objects ↔ work orders; and
- work orders ↔ findings, use cases, workflows, transactions, repository legs, and
  verification criteria.

## A note earns its file

One note per subject does not mean one note per name. A workflow, detector, or objective
earns a file when it carries spans, attributes, a threshold, an objective, or a work order.
Until then it remains a line in its parent BT or catalogue. The service index reports total
names and promoted notes.

## Frontmatter

```yaml
---
title: checkout.order.submit
type: workflow
app: <app>
version: V3
status: proposed
updated: 2026-11-10
tags: [checkout, payment]
sources: [F-01]
work_orders: [WO-004]
---
```

Every note has the matching `app` and `version`; `sources` and `work_orders` are YAML
lists, including when empty. Types include `index`, `architecture`, `catalog`,
`contract`, `decision`, `run-log`, `finding`, `use-case`, `workflow`, `bt`, `metric`,
`business-transaction`, `dashboard`, `operation`, `service`, `detector`, `sli`, `slo`,
`objective`, `reference`, and `work-order`. General statuses
include `proposed`, `ready`, `blocked`, `observed`, `designed`, `accepted`, `active`,
`deferred`, `implemented`, `verified`, `resolved`, `not-applicable`, `retained`,
`changed`, `superseded`, and `retired`; finding and work-order statuses use their
applicable subsets.

Do not require customer, engineer, owner, or accepter names.

## Index notes

An index is a map, not a second authority. It stays under roughly 200 lines and contains:

- breadcrumb;
- selected version and status;
- short target description;
- counts;
- task-oriented entry links; and
- next step.

The human-facing analysis landing page may summarize conclusions. Wiki indexes link the
canonical object detail rather than repeating it.

## Work orders

Work orders are app-level because end-to-end changes cross services and repositories.
They live under the matching version:

```text
wiki/apps/<app>/versions/V<N>/implementation/work-orders/
```

The queue index contains:

| ID | Outcome | Depends on | Status | Unlocks | Detail |
|---|---|---|---|---|---|

Each order carries:

- reason and outcome;
- findings addressed;
- use cases enabled;
- workflows and business transactions affected;
- target selectors;
- repository ids and authorized paths;
- dependencies;
- shared contracts consumed;
- allowed and forbidden changes;
- linked PR coordination;
- acceptance evidence;
- verification criteria; and
- copy-ready issue text when an external tracker was requested.

Before acceptance, dependency-free orders are `proposed`; dependent orders are `blocked`.
Acceptance changes eligible orders to `ready`. A later version compares the prior queue
and marks each order retained, changed, superseded, implemented, or verified.

Canonical work-order frontmatter carries `work_order_id`, `selectors`, `depends_on`, and
structured `repository_legs`; the body carries the required reverse-link sections.
Verification rejects unsupported selectors, unknown or cyclic dependencies, repository
IDs absent from the implementation map, absolute or traversal paths, paths outside
`authorized_paths`, meaningless changes/tests, and a `ready` status whose acceptance or
dependencies do not authorize execution.

The first work order installs deterministic schema agreement, single-init,
workflow-registry, baggage-allowlist, and deny-list checks.

## Authorities

| Fact | Authority |
|---|---|
| Review narrative and strategy | Versioned analysis Markdown |
| Per-object spans, events, thresholds, and work orders | Matching versioned wiki note |
| Attribute keys and dimension eligibility | `attribute-schema.json` |
| Repository and path mapping | `implementation-map.json` |
| Evidence and run state | `provenance-ledger.json` |
| Accepted content | Version acceptance digest |

Do not duplicate a document section verbatim into a note.

## Host pointers

Create or update:

- `.cursor/rules/obengineer-wiki.mdc`;
- `CLAUDE.md`; and
- `AGENTS.md`.

Each points to `wiki/apps/<app>/index.md` and carries:

> Before changing instrumentation, read `wiki/apps/<app>/index.md`, resolve the accepted
> version, then load only the service, object, contract, and work-order notes in scope.
> Do not load every version or the whole wiki. Update touched note status in the same
> implementation commit.

No browser or localhost server is required.

## Verification

Run `verify_wiki.py wiki/apps/<app>/versions/V<N>`. It iterates every directory under
`services/` and checks:

- required paths and frontmatter;
- version and analysis breadcrumbs;
- relative links and unambiguous wikilinks;
- index counts;
- work-order dependency ids and reverse links;
- accepted-version pointer;
- schema and provenance references;
- host pointers; and
- credential-shaped values.

Warning signs include a mutable old-version link, an index that restates every object,
a work order with no reverse links, stale statuses, a note without `updated`, and any
credential value.
