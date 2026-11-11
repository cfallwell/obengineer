---
name: instrumentation-wiki
description: >-
  Materialize one analysis version as an addressable agent wiki: architecture,
  findings, use cases, workflows, business transactions, signal contracts,
  operations, and the complete dependency-ordered work-order queue. Used inside
  analysis and directly as $instrumentation-wiki when repairing or validating
  a generated wiki.
metadata:
  author: obengineer
  version: 0.3.0
  category: observability
---

# Versioned instrumentation wiki

Analysis and wiki generation are one run. The landing page is the human index; this wiki
is the canonical object detail and execution queue.

Read:

- [`../references/agent-wiki.md`](../references/agent-wiki.md)
- [`../references/analysis-site.md`](../references/analysis-site.md)
- [`../references/implementation-work-orders.md`](../references/implementation-work-orders.md)
- [`../references/provenance-ledger.md`](../references/provenance-ledger.md)

## Input

Use the current analysis version, `attribute-schema.json`, `implementation-map.json`,
ledger evidence ids, verification plan, and prior version when present. Do not redesign
accepted names while materializing notes.

## Output

```text
wiki/apps/<app>/
  index.md
  versions/
    V<N>/
      index.md
      meta/
      services/<service>/
      implementation/work-orders/
```

The app index links `[V1] [V2] ...`, marks the accepted version, and tells agents to load
only that version unless comparing history. Host pointers target the app index.

## Notes

Create one substantive note per:

- architecture surface and bus;
- finding;
- use case;
- promoted workflow;
- business transaction;
- detector;
- objective;
- shared contract; and
- work order.

A note earns a file when it carries spans, attributes, a threshold, an objective, a work
order, or another implementation decision. Unpromoted names remain in their parent
catalogue. Every note has frontmatter:

```yaml
title: <title>
type: workflow
app: <app>
version: V<N>
status: proposed
updated: <date>
tags: []
sources: []
work_orders: []
```

Do not require customer, engineer, owner, or accepter names.

## Links and breadcrumbs

Every note opens with links back to:

```markdown
[Analysis](<analysis index>) / [<Object index>](index.md) / **<Current object>**
```

Use relative Markdown links for the human analysis site and `[[wikilinks]]` within the
wiki. Link every direction:

- findings ↔ use cases;
- use cases ↔ workflows and business transactions;
- objects ↔ shared contracts;
- objects ↔ work orders; and
- work orders ↔ findings, use cases, workflows, transactions, repository legs, and
  verification criteria.

## Work orders

Create the complete queue during analysis. Each work order contains:

- outcome and reason;
- findings addressed;
- use cases enabled;
- workflows and business transactions affected;
- selectors;
- repository ids and authorized paths, or an explicit unresolved mapping with no invented
  leg and blocked status;
- dependencies;
- shared contracts consumed;
- allowed and forbidden changes;
- linked-PR coordination;
- acceptance evidence;
- verification criteria; and
- copy-ready issue text when an external tracker was explicitly requested.

Before acceptance, dependency-free work orders are `proposed`; dependent orders are
`blocked`. Acceptance changes eligible orders to `ready`. A later version compares the
prior queue and marks orders retained, changed, superseded, implemented, or verified.

The first order establishes schema agreement, single initialization, workflow registry,
baggage allowlist, and deny-list checks.

## Run metadata

Each version carries one shared `meta/` directory (never a copy under each service):

- inputs snapshot;
- component versions with provenance;
- run log;
- decisions;
- value-model workings;
- public evidence with read dates; and
- useful unanswered inputs.

The provenance ledger remains the machine authority. Notes link ledger ids instead of
copying evidence.

## Verification

Run:

```bash
python3 scripts/verify_wiki.py wiki/apps/<app>/versions/V<N> \
  --repo-root <artifact-repository>
```

The verifier iterates every service. Verify paths, frontmatter, breadcrumbs, relative
links, wikilinks, index counts, work-order
dependencies and reverse links, host pointers, acceptance binding, provenance, and
credential-shaped values. The analysis PR cannot become ready while verification fails.

## Boundaries

- No application code or Terraform.
- No duplicate narrative document.
- No browser server or localhost URL.
- No secret values.
- No mutable link from an older analysis version into a newer wiki snapshot.
