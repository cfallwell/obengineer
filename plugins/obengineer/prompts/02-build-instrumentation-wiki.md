# Prompt 02 — Materialize the versioned analysis wiki and work orders

**Agent:** [`../agents/instrumentation-architect.agent.md`](../agents/instrumentation-architect.agent.md)  
**Skills:** `instrumentation-wiki`, `baggage-propagation`, `cardinality-budget`  
**Inputs:** the current analysis evidence, schema, implementation map, and version
**Output:** the wiki and complete proposed work-order queue in the same analysis PR

This prompt runs inside `/ob-analyze`. There is no separate generation command.

## System reminder

Build the addressable detail behind the analysis landing page. The landing page is the
human index; the wiki is the canonical detail read by agents. Do not duplicate a wiki
note into the landing page. Summarize it and link it.

Use the current immutable version:

```text
wiki/apps/<app>/versions/V<N>/
```

Earlier versions remain read-only. The app-level `index.md` links every version and
marks exactly one accepted version as active.

## Required tree

Create:

- `index.md` with a breadcrumb back to the analysis landing page;
- `services/<service>/` notes for architecture, findings, contracts, business
  transactions, workflows, use cases, metrics, detectors, objectives, business
  workings, enforcement, and as-code inventory;
- `implementation/work-orders/index.md` with the dependency graph and status;
- one `implementation/work-orders/<id>.md` per bounded implementation slice; and
- host pointers that resolve the accepted version instead of loading every version.

Follow [`../skills/references/agent-wiki.md`](../skills/references/agent-wiki.md) and
[`../skills/references/implementation-work-orders.md`](../skills/references/implementation-work-orders.md).

## Work-order state

Analysis creates the full queue:

- dependency-free orders are `proposed` before acceptance;
- dependent orders are `blocked`;
- acceptance changes eligible `proposed` orders to `ready`;
- completion evidence changes an order to `implemented` or `verified`; and
- a later version marks changed prior orders `retained`, `superseded`, or `changed`
  rather than silently recreating them.

Every finding, use case, workflow, and business transaction links its work orders.
Every work order links back to the findings it addresses, use cases it enables,
workflows it implements, business transactions it affects, shared contracts it consumes,
repository legs, dependencies, acceptance evidence, and verification criteria.

Do not record a named engineer, named owner, or accepter. Repository review policy
decides who reviews implementation. A work order may name a role only when the product
requires routing behavior.

## One authority

- Narrative and review order: versioned analysis Markdown.
- Per-object implementation detail and work orders: versioned wiki.
- Attribute keys and dimensions: `attribute-schema.json`.
- Evidence and run state: `provenance-ledger.json`.

The landing page links these authorities; it does not restate them.

## Verification

Run `verify_wiki.py` against every service in the version. Verify links, frontmatter,
version breadcrumbs, work-order dependencies, reverse links, pointers, provenance, and
credential-shaped values. The analysis PR is incomplete until the wiki passes.
