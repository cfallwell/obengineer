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

One check, first, before scanning: does `wiki/apps/<app>/index.md` list a prior version?

| Answer | Run type | Behaviour |
|---|---|---|
| No version | **First run** | Full analysis. Create V1 and its wiki. Everything is new |
| Prior version exists | **Repeat run** | Create the next immutable version. Read prior accepted state before scanning |
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

## Previous scans of this site

A previous scan of **this** site is an input. Several previous scans are inputs.
Compare each of them with the current production scan. The comparison writes
three lists, and each changed surface is in exactly one:

- **Changes** — present in a previous scan and in the current scan, and the two disagree.
- **Merges** — the same surface recorded more than once. Keep the name already accepted.
- **Additions** — in the current scan and in no previous scan. This is how uninstrumented code that has already been released enters the contract.

A scan, diagram, or taxonomy from a **different** site is not an input. Do not
cite it. This comparison runs when `artifacts.prior_scans` is non-empty and on
every repeat run, whether or not a wiki already exists. The current scan is
production. Test and QA scans are not a substitute: those environments vary.

## What the next version contains

The landing page begins with `Changes in V<N>` and links immutable prior versions. It
states inputs added or edited and resulting changes to findings, strategy, use cases,
workflows, transactions, schema, and work orders. Unchanged detail remains available in
the prior version rather than being copied into empty pages.

The changes readout covers:

- **New surfaces and services** — routes, bundles, endpoints, queues, and services that did not exist at the last run. For each, whether it is instrumented, and if not, which BT and workflow it needs. **This is the highest-value output of a repeat run**: newly shipped, uninstrumented code is what the periodic cadence exists to catch, and it is invisible to anyone reading the running system's dashboards, because code nobody instrumented produces no telemetry and therefore no gap in a chart.
- **Removed or retired** — surfaces that have gone. Their notes move to `status: retired` rather than being deleted, and their detectors and dashboards are named for removal, because an alert on a deleted service fires as a silent outage forever.
- **Drift** — where the implementation and the contract have diverged: a workflow name in code that is not in the registry, an attribute emitted that is not in the schema, a dimension promoted in the tenant that the budget never approved. Drift is not a finding about people; it is the normal consequence of shipping, and the run's job is to reconcile it — either the code changes or the contract does, named explicitly per item.
- **Version and upgrade status** — components that moved, breaking changes, and any upgrade-path entry still open with its age.

**Findings are carried forward, never renumbered.** `F-01` is `F-01` for the life of the
application. Each prior finding appears with its current state — `fixed` (with what verified
it), `open` (with how long, which is the number that creates urgency), `regressed` (which is
worse than new and must say so), or `risk-accepted` (with the decision record, date,
and rationale). Contract acceptance is the separate content-bound acceptance record. New
findings continue the sequence. A finding that vanishes between two documents is the worst
available outcome: the reader cannot tell whether it was fixed or dropped.

Do not create empty pages. The landing-page change summary names unchanged catalogues when
that fact matters; otherwise the prior version remains the record.

**The catalogues are additive.** New BTs, new workflows, new meters, new
detectors, new objectives — appended, with new entries marked so a reviewer can find them
without diffing. Existing entries are not rewritten for taste. Renaming an accepted
`workflow.name` breaks every dashboard, detector, and MetricSet built on it, so it happens
only with a stated migration path and never because a later run preferred different wording.

## What must not change without saying so

These have downstream configuration built on them, so a change is a migration, not an edit:

| Thing | What breaks if it changes silently |
|---|---|
| `<org>.bt` and `workflow.name` values | APM Business Transaction rules, dashboards, detectors, and MetricSets |
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
