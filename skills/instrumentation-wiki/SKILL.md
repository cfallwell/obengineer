---
name: instrumentation-wiki
description: >-
  Turn an accepted analysis into the structured wiki the agents work from: one
  note per business transaction, workflow, use case, finding, detector, and
  objective under wiki/<Customer>/<app>/, with frontmatter and wikilinks that
  Obsidian and the Cursor, Claude, and Codex memory features can read. Also
  emits attribute-schema.json, the tracked-versions note, the run log, and the
  work orders the implementer agent executes. Use when the user types
  $instrumentation-wiki, asks for the agent wiki or memory layer, "Prompt 02",
  a business-transaction and workflow registry as notes, work orders for the
  coding agent, or asks where the lower-layer detail behind the customer
  document lives. Writes notes and schema; no application runtime code, and no
  second customer-facing document.
metadata:
  author: obengineer
  version: 0.2.0
  category: observability
---

# Instrumentation Wiki — the layer the agents read

## Overview

There is **one** customer-facing document, and `instrumentation-analyze` produces it. This
skill produces the layer underneath: the notes an agent retrieves by subject when it is about
to change code, sized so a run loads three notes rather than three hundred kilobytes.

This used to be a second document — `INSTRUMENTATION-GUIDE.md`, a near-duplicate of the
analysis. It failed in both directions: no customer read it, and no agent could load it
without spending its entire context on material irrelevant to the task in hand. Notes are the
right shape because retrieval is per subject and updates are in place.

Agent definition: [`../../agents/instrumentation-architect.agent.md`](../../agents/instrumentation-architect.agent.md).
Prompt: [`../../prompts/02-build-instrumentation-wiki.md`](../../prompts/02-build-instrumentation-wiki.md).

## Read these first

| Reference | Owns |
|---|---|
| [`../references/agent-wiki.md`](../references/agent-wiki.md) | The directory layout, note frontmatter, the index note, and the host memory pointers. |
| [`../references/document-template.md`](../references/document-template.md) | The customer document this wiki sits beneath. Sections 19–25 are the catalogue the notes expand. |
| [`../references/cross-cutting-attributes.md`](../references/cross-cutting-attributes.md) | The five code patterns `contract/cross-cutting.md` carries. |
| [`../references/version-currency.md`](../references/version-currency.md) | What `meta/versions.md` records and how a later run diffs it. |
| [`../references/incremental-runs.md`](../references/incremental-runs.md) | Whether this is a first run, a repeat, or a re-baseline. |

## Output

```
wiki/<Customer>/<app>/          # notes — see agent-wiki.md for the full tree
docs/observability/attribute-schema.json
```

Plus the host memory pointers — `.cursor/rules/obengineer-wiki.mdc`, `CLAUDE.md`,
`AGENTS.md` — each a pointer to the index note, never a copy of it.

**No `.docx`, and no second Markdown document.** If this run produces something a customer
would read cover to cover, it has recreated the artifact this design removed.

## Process

### Step 1 — Establish the run type before writing anything

Does `wiki/<Customer>/<app>/index.md` exist? No wiki means a first run. A wiki with run-log
entries means a **delta**: read `meta/`, the accepted names, and the finding frontmatter
*before* scanning, or the run will invent names that already exist and rename things that
have dashboards built on them. Rules: [`../references/incremental-runs.md`](../references/incremental-runs.md).

### Step 2 — Lift the accepted analysis; do not re-derive it

The analysis document is the source. Reuse its BT names, `workflow.name` strings, attribute
keys, and finding ids exactly. Extend from new evidence; never rename for taste. If a prior
`attribute-schema.json` exists, it is the naming authority and this run extends it.

### Step 3 — One note per subject, and a note earns its file

| Note | Carries |
|---|---|
| `business-transactions/<bt>.md` | Surface, owning artifact, feature flag, the workflows it hosts as wikilinks, evidence |
| `workflows/<workflow>.md` | Intent, the span tree with `workflow.step` values, span events, attributes with dimension eligibility, meters, the SLI, the detectors, and the labelled join to the next flow |
| `use-cases/<flow>.md` | The composite: narrative, workflow identity, dashboard panels, joins, and links to the notes above |
| `findings/F-nn-<slug>.md` | The finding with `status: open \| fixed \| regressed \| accepted`, so the next run reports rather than rediscovers |
| `detectors/<detector>.md` | Condition, threshold **and its provenance**, arm state, group-by, runbook |
| `slos/<sli>.md` | User-facing statement, good and total event queries, objective, window, error budget, burn-rate rules |
| `contract/*.md` | Cross-cutting attributes, baggage budget with each key's named consumer, collector config, MPM lists with their arithmetic |
| `meta/*` | Versions, run log, decisions, and the engagement inputs as run |

Every note gets the frontmatter from `agent-wiki.md`: `type`, `customer`, `app`, `status`,
`updated`, `run`, `tags`, and `sources`. `status` is read by CI and by the delta run, so it
is load-bearing rather than descriptive.

**One note per subject is not one note per name.** A workflow or a detector earns a file when
it carries something beyond its name — spans, a threshold with a provenance, an objective, a
work order. Until then it is a line in its BT note or the detector catalogue note, and it is
promoted the moment there is something to record. An application with four hundred workflows
would otherwise open with four hundred frontmatter stubs, which is a retrieval surface where
every search returns names. Put the counts in `index.md` — named versus noted — so the gap is
visible rather than looking like an omission.

Link with `[[wikilinks]]`. Use a relative Markdown link only when pointing out of the wiki at
a real repository file. Check that every link resolves before closing the run — `verify_wiki.py`
in Step 9 does it mechanically — because a link that goes nowhere is worse than no link: an
agent follows it, finds nothing, and infers the subject was never analysed.

### Step 4 — Keep the index a map, not a summary

`index.md` is the one note an agent may load unconditionally, so it stays short: the
application in a paragraph, counts, the current run version, and a table of entry points by
task. A summary in the index is a fact with two homes — link instead.

### Step 5 — Write the work orders

`implementation/work-orders/<nn>-<slice>.md`, one per pull-request-sized slice, ordered so
each is independently reviewable and independently revertible. Each names the contract
sections it implements, the files and packages it touches, new dependencies, the CI checks it
adds, the acceptance evidence, and what it must **not** do without a human decision.

These are what [`../instrumentation-implement/SKILL.md`](../instrumentation-implement/SKILL.md)
executes and what Appendix C of the customer document summarises. Appendix C is the plan; the
work order is the instruction.

### Step 6 — Record versions and the upgrade path

`meta/versions.md` gets a row per component with a **provenance** column, and any breaking
change since the last run becomes an `## Upgrade path` entry naming the affected notes, the
code action, the configuration action, their ordering, and the verification.
[`../references/version-currency.md`](../references/version-currency.md) has the shape.
`unknown` is acceptable; an absent row is not, because nobody checks a component that is not
listed.

### Step 7 — Emit the schema, and make the checks possible

`attribute-schema.json` carries every attribute, its type, dimension eligibility, and the
deny list. It is the file the layer-1 CI checks read, so it is the reason those checks can
exist at all — see [`../references/ci-integration.md`](../references/ci-integration.md).
It and the document's Appendix A are generated from each other and may not disagree.

### Step 8 — Point the hosts at it

An agent that has to be told to read the wiki will not read it. Write a **pointer** — never a
copy — into each host's automatically loaded file: `.cursor/rules/obengineer-wiki.mdc` with
`alwaysApply: true`, `CLAUDE.md`, and `AGENTS.md`. Each carries the path to `index.md`, the
retrieval rule ("read the index, then only the notes in scope, do not load the whole wiki"),
the same-commit update rule, and the two or three prohibitions specific to this target that
have already gone wrong — a single `init`, names from the registry, no credential values.

Keep it short. A pointer that grows into a summary is a second authority, and the copy is the
one that will be wrong.

### Step 9 — Verify the wiki, then close the run

```bash
python3 scripts/verify_wiki.py "wiki/<Customer>/<app>"
```

It checks what a reader will not: the notes every wiki must have, `type` / `status` / `updated`
on every note from the allowed sets, every wikilink resolving and no bare name ambiguous, the
index short with its counts matching the tree, a promoted note carrying more than its name, a
provenance column in `meta/versions.md`, the host pointers carrying the retrieval and
same-commit rules, and no credential-shaped value anywhere. A failure is the run's, not the
reviewer's — fix it before handing over.

`meta/run-log.md` gains a row: date, run version, document filename, counts of new and
changed items, findings opened and closed. `meta/decisions.md` gains what the human accepted,
**including what they rejected** — that diff is the only preference data this project
generates, and it is otherwise lost when the session ends.

Refresh `updated` and `run` only on notes this run actually reconsidered. Bumping every note
tells the next delta that everything changed, which is the same as telling it nothing.

## Warning signs

- **A note that reproduces a document section verbatim.** Two authorities, and the wiki loses, because nobody re-renders it.
- **An index note that has grown a summary per workflow.** It is the old guide again. Cut it to links.
- **Notes with no `status` or no `updated`.** The delta run cannot tell stale from current and will rewrite everything.
- **A workflow renamed with no migration note.** Dashboards, detectors, and MetricSets are built on that string.
- **Finding ids renumbered.** Every ticket referencing them is now wrong.
- **A `.docx` in the output.** That is `instrumentation-analyze`'s job, once, for the customer.
- **A credential in a note.** More dangerous here than in the document, because wikis get loaded into agent context by default. Who holds it, never the value.

## Non-goals

- No application runtime code. That is [`../instrumentation-implement/SKILL.md`](../instrumentation-implement/SKILL.md), working from the work orders.
- No second customer-facing document, and no `.docx`.
- No new journeys, meters, or dimensions. The analysis decides those; this skill structures them.
- No Terraform. That is [`../observability-as-code/SKILL.md`](../observability-as-code/SKILL.md).
