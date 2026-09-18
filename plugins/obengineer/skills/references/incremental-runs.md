# Incremental runs — the second analysis is not the first one again

The architect is not a one-off engagement. It runs periodically against the same target,
because the target keeps changing: routes get added, a bus appears, a team ships a service
nobody instrumented, a finding gets fixed or does not.

The naive behaviour on a second run is to redo the first: scan everything, write the whole
document again, renumber the findings, invent the workflow names a second time. That produces
a document the customer cannot diff, a taxonomy that has drifted from the one in the code, and
a review meeting spent re-litigating decisions that were settled six months ago.

**A repeat run is a delta.** Same structure, same names, new content only where something
actually changed.

## Establishing which kind of run this is

One check, first, before any scanning: does `wiki/<Customer>/<app>/index.md` exist?

| Answer | Run type | Behaviour |
|---|---|---|
| No wiki | **First run** | Full analysis. Create the wiki. Record versions. Everything is new |
| Wiki exists, `meta/run-log.md` has entries | **Repeat run** | Delta. Read before scanning. Reuse every accepted name |
| Wiki exists but is stale beyond recognition — the application has been rewritten | **Re-baseline** | Full analysis, but the old wiki is archived rather than deleted, and the document says why the baseline was reset |

The third case is real and must be declared, not drifted into. A "delta" against an
application that has been rebuilt is a document full of phantom sections about code that no
longer exists.

## What a repeat run reads first

In this order, and only this, before touching the target:

1. **`meta/run-log.md`** — when the last run happened, what version it produced, what it left open.
2. **`meta/versions.md`** — what the design was built against, and any open upgrade path. See [`version-currency.md`](version-currency.md).
3. **`meta/decisions.md`** — what the human accepted, including the things they rejected. Re-proposing a rejected design is the fastest way to lose a reviewer's attention.
4. **`business-transactions/` and `workflows/` note names only** — the accepted vocabulary. Names, not bodies; loading every body is how the context budget disappears before the work starts.
5. **`findings/` frontmatter only** — id, severity, status. Enough to check each one.

Then scan. Reading after scanning means the scan invents names that already exist.

## What the delta document contains

Same section list as a first run — every heading stays, because a customer comparing two
versions must find the same shape — but the content of each is scoped to change.

**Section 3 gains `### Changes since v<N-1>`**, and it is the section the reader goes to
first on a repeat run. Four subsections, each of which may be "none":

- **New surfaces and services** — routes, bundles, endpoints, queues, and services that did not exist at the last run. For each, whether it is instrumented, and if not, which BT and workflow it needs. **This is the highest-value output of a repeat run**: newly shipped, uninstrumented code is what the periodic cadence exists to catch, and it is invisible to anyone reading the running system's dashboards, because code nobody instrumented produces no telemetry and therefore no gap in a chart.
- **Removed or retired** — surfaces that have gone. Their notes move to `status: retired` rather than being deleted, and their detectors and dashboards are named for removal, because an alert on a deleted service fires as a silent outage forever.
- **Drift** — where the implementation and the contract have diverged: a workflow name in code that is not in the registry, an attribute emitted that is not in the schema, a dimension promoted in the tenant that the budget never approved. Drift is not a finding about people; it is the normal consequence of shipping, and the run's job is to reconcile it — either the code changes or the contract does, named explicitly per item.
- **Version and upgrade status** — components that moved, breaking changes, and any upgrade-path entry still open with its age.

**Findings are carried forward, never renumbered.** `F-01` is `F-01` for the life of the
application. Each prior finding appears with its current state — `fixed` (with what verified
it), `open` (with how long, which is the number that creates urgency), `regressed` (which is
worse than new and must say so), or `accepted` (with who accepted the risk and when). New
findings continue the sequence. A finding that vanishes between two documents is the worst
available outcome: the reader cannot tell whether it was fixed or dropped.

**Sections with no change say so, briefly, and keep the heading.** "Unchanged since v2" with
a wikilink is correct and useful. Silently reproducing the previous text is not: the reader
cannot tell reviewed-and-unchanged from copied-forward-unread.

**The catalogue sections (19–25) are additive.** New BTs, new workflows, new meters, new
detectors, new objectives — appended, with new entries marked so a reviewer can find them
without diffing. Existing entries are not rewritten for taste. Renaming an accepted
`workflow.name` breaks every dashboard, detector, and MetricSet built on it, so it happens
only with a stated migration path and never because a later run preferred different wording.

## What must not change without saying so

These have downstream configuration built on them, so a change is a migration, not an edit:

| Thing | What breaks if it changes silently |
|---|---|
| `workflow.name` values | Dashboards, detectors, the APM Business Workflow, every MetricSet |
| `<org>.bt` values | Dashboard variables and filters |
| Attribute keys | MPM rules, detector `group by`, Related Content links |
| Finding ids | Tickets, the phased plan, the customer's own tracking |
| SLI names | SLO resources and their history, which does not survive a rename |

Where a change to one is genuinely right, the document says: the old value, the new value, why,
what has to be reconfigured, and in which order code and configuration cut over.

## After the run

The run is not finished when the document renders. In the same commit:

- Wiki notes updated in place, with `updated` and `run` refreshed on every note the run actually reconsidered — and *not* on notes it merely listed, or the next delta cannot tell reviewed from untouched.
- `meta/run-log.md` gains a row: date, run version, document filename, counts of new and changed items, findings opened and closed.
- `meta/decisions.md` gains any decision this run made or the human accepted.
- New notes for everything new, at `status: proposed` until a human accepts it.

## Warning signs

- **A second document the same length as the first with no delta section.** The run redid the analysis and learned nothing from having been here before.
- **Findings renumbered.** Every external reference to them is now wrong.
- **A workflow renamed with no migration note.** Something in the tenant is about to go blank, and it will be found by an on-call engineer.
- **`Changes since v<N-1>` listing only additions.** Nothing was retired and nothing drifted in six months of shipping? Look again, particularly for drift.
- **Every note's `updated` field bumped to today.** The run touched nothing and claimed everything.
- **New uninstrumented code found, but no work order for it.** The finding without the follow-through is the same as not having looked.
