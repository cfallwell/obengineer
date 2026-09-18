# Prompt 02 — Build the instrumentation wiki

**Agent:** [`../agents/instrumentation-architect.agent.md`](../agents/instrumentation-architect.agent.md)  
**Skills:** `instrumentation-wiki`, `baggage-propagation`, `cardinality-budget`  
**Inputs:** `docs/observability/engagement-inputs.yaml` + the accepted Prompt 01 analysis document  
**Depends on:** the Prompt 01 analysis, accepted by the human.  
**Output:** PR 0 — documentation only. The wiki under `wiki/<Customer>/<app>/`, `attribute-schema.json`, and the host memory pointers.

**Invoke it, do not paste it.** `/obengineer-wiki` reads this file in place. Inputs come
from `engagement-inputs.yaml`, so nothing is re-attached and nothing is re-typed; the
analysis document and diagram paths are already in that file from run 1.

---

## System reminder

Follow `instrumentation-architect.agent.md`. This run builds the **agent layer**, not a
document. There is one customer-facing document and Prompt 01 produced it; your job is the
structured wiki the coding agents, the Terraform run, and the next delta run read.

**Do not produce a second document.** No `.docx`, no `INSTRUMENTATION-GUIDE.md`, nothing a
customer would read cover to cover. That artifact existed, was a near-duplicate of the
analysis, and failed in both directions: no customer read it, and no agent could load it
without spending its whole context on material irrelevant to the task in hand.

**One note per subject.** A business transaction, a workflow, a use case, a finding, a
detector, an objective — each is a file with frontmatter and `[[wikilinks]]`, retrievable
without loading its neighbours. Layout, frontmatter fields, the index-note rule, and the host
memory pointers: [`../skills/references/agent-wiki.md`](../skills/references/agent-wiki.md).
That file owns the tree; do not invent a different one.

**Lift the accepted analysis; do not re-derive it.** Reuse the BT names, `workflow.name`
strings, attribute keys, and finding ids from the document exactly. Extend from new evidence;
never rename for taste. Renaming an accepted `workflow.name` breaks every dashboard, detector,
and MetricSet built on it.

## Inputs

| Field | Used for |
|---|---|
| `engagement.customer`, `.application` | The wiki path — `wiki/<Customer>/<app>/`. Customer first, then application, because tenancy and entitlement are customer-level facts that must not be duplicated per app |
| `artifacts.prior_contract`, `.prior_schema` | The naming authority when one exists |
| `backends.languages`, `.buses` | Which language ports and bus notes must exist |
| `entitlement.*` | The arithmetic behind `contract/mpm.md`, and — only when supplied — `business/entitlement-exposure.md` |
| `business_context.*`, `public_evidence.*` | `business/value-model.md`, `business/public-evidence.md`, and `business/asks.md` |
| `standards.*` | The percentile and naming conventions the notes state once |

## First: is this a first run or a delta?

If `wiki/<Customer>/<app>/index.md` already exists with entries in `meta/run-log.md`, read
`meta/`, the accepted note names, and the finding frontmatter **before** writing. Update notes
in place; refresh `updated` and `run` only on the notes this run actually reconsidered.
Bumping every note tells the next delta that everything changed, which is the same as telling
it nothing. Rules: [`../skills/references/incremental-runs.md`](../skills/references/incremental-runs.md).

## Task

1. **The tree**, exactly as `agent-wiki.md` specifies: `meta/`, `architecture/`, `findings/`, `contract/`, `business-transactions/`, `workflows/`, `use-cases/`, `metrics/`, `detectors/`, `slos/`, `business/`, `implementation/`, `as-code/`.

2. **`index.md` as a map of content, not a summary.** The one note an agent may load unconditionally, so it stays short: the application in a paragraph, counts, the current run version, and a table of entry points by task. A summary in the index is a fact with two homes.

3. **One note per business transaction and one per workflow.** The workflow note is where the depth lives: the span tree with its bounded `workflow.step` values, span events, attributes with dimension eligibility, meters, the governing SLI, the detectors, and the join to the next flow labelled **continue trace** | **span link** | **attribute pivot**.

4. **`contract/`** — `cross-cutting.md` with all five code patterns from [`../skills/references/cross-cutting-attributes.md`](../skills/references/cross-cutting-attributes.md); `baggage.md` with the budget and **each key's named consumer**; `collector.md` with the config and why each processor sits where it does; `mpm.md` with the dimension-eligible and attribute-only lists **and their arithmetic**.

5. **`findings/`** — one note per finding from section 4 of the document, same ids, with `status: open | fixed | regressed | accepted`. This is what lets the next run report on a finding instead of rediscovering it as new.

6. **`detectors/` and `slos/`** — one note each. A detector note carries its threshold **and that threshold's provenance**: measured baseline, agreed target, or labelled placeholder with the query that will replace it. An SLI note carries the user-facing statement, the good and total event queries, the objective, the window, the error budget, and the burn-rate rules.

7. **`business/`** — `value-model.md` with the value arithmetic and every coefficient labelled `stated` | `measured` | `public` | `derived`, the unfilled ones left visibly unfilled; `public-evidence.md` with each cited source, its class, and **the date it was read**; `asks.md` with the inputs that would make the case quantitative. Add `entitlement-exposure.md` only when the customer supplied entitlement numbers — written without them it is invented, and the next run inherits the invention as fact. This directory is why a later run updates a coefficient instead of re-researching a quarter.

8. **`implementation/work-orders/<nn>-<slice>.md`** — one per pull-request-sized slice, ordered so each is independently reviewable and independently revertible. Each names the contract sections it implements, the files and packages it touches, new dependencies, the CI checks it adds, the acceptance evidence, and what it must not do without a human decision. These are what Prompt 03 executes.

9. **`implementation/enforcement.md`** — the layer-1 contract checks, from [`../skills/references/ci-integration.md`](../skills/references/ci-integration.md). Schema agreement and single-init first; they catch real defects and need no model.

10. **`meta/versions.md`** — a row per component with a **provenance** column, and an `## Upgrade path` entry for every breaking change since the last run, naming the affected notes, the code action, the configuration action, their ordering, and the verification. Spec: [`../skills/references/version-currency.md`](../skills/references/version-currency.md). `unknown` is acceptable; an absent row is not.

11. **`docs/observability/attribute-schema.json`** — every attribute, its type, dimension eligibility, and the deny list. This is the file the CI checks read, so it is why those checks can exist. It and the document's Appendix A are generated from each other and may not disagree.

12. **The host memory pointers** — `.cursor/rules/obengineer-wiki.mdc`, `CLAUDE.md`, `AGENTS.md` — each a **pointer** to the index note carrying the retrieval rule verbatim, never a copy of the wiki. A copy is a second authority that drifts.

13. **Close the run** — `meta/run-log.md` gains a row; `meta/decisions.md` gains what the human accepted **and what they rejected**, because that diff is the only preference data this project generates and it is otherwise lost when the session ends.

## Acceptance

A coding agent asked to implement one workflow can find what it needs by loading `index.md`
and two notes, and does not need the analysis document at all. A reviewer can see from the
frontmatter which notes this run reconsidered. Every `workflow.name` in the wiki appears in the
document's section 20 and nowhere disagrees with it. No `.docx` was produced, no note
reproduces a document section verbatim, and no note contains a credential value.
