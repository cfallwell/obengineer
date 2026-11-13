---
description: Implement — execute one Ready work order from the accepted analysis version
---

Run one bounded implementation work order.

1. Adopt `${CLAUDE_PLUGIN_ROOT}/agents/instrumentation-implementer.agent.md`.
2. Resolve the accepted version from `wiki/apps/<app>/index.md`, then verify its
   `acceptance.yaml` with:
   `python3 "${CLAUDE_PLUGIN_ROOT}/skills/instrumentation-wiki/scripts/verify_analysis_acceptance.py" --record <acceptance-path> --repo .`.
3. Load only the selected version's analysis intent, schema, implementation map,
   relevant object notes, and the work order's full revision chain (see below). Never load
   every version or the whole wiki.
4. Follow `${CLAUDE_PLUGIN_ROOT}/prompts/03-implement-instrumentation.md` and use
   `$instrumentation-implement`.

Accept one selector: `work-order:<id>`, `business-transaction:<id>`,
`workflow:<name>`, `use-case:<id>`, `detector:<id>`, `alert-condition:<id>`,
`dashboard:<id>`, `custom-code:<id>`, `objective:<id>`, or `config:<id>`. Resolve it to
exactly one Ready work order. `use-case:<id>` runs the gate's `next_subordinate`.
Proposed, Blocked, Superseded, or older-version orders cannot run.

Before any work, gate the order with the state ledger
(`S="${CLAUDE_PLUGIN_ROOT}/skills/instrumentation-wiki/scripts/work_order_state.py"`).
`<app>` and `V<N>` are the resolved accepted application and version.

- If `wiki/apps/<app>/implementation/V<N>/state.yaml` is missing, run
  `python3 "$S" init --repo . --app <app> --version V<N>`. A version accepted before work-order
  kinds existed gets a `legacy` ledger: its Ready, In progress, or dependency-Blocked
  orders run once their `depends_on` orders are implemented, verified, or retired, with
  no foundation gate.
- Run `python3 "$S" gate --repo . --app <app> --version V<N> --work-order <id>`.
  Non-foundation orders run only when every foundation order is complete (implemented or
  verified at its current revision).
- An implemented, verified, or changed order runs again only when the arguments include
  `reimplement`; then pass `--reimplement` to `gate`.
- Load the accepted note, then every path in the gate's `revision_paths` in order (R2,
  R3, ...). Implement the cumulative `effective_changes` from
  `python3 "$S" show --repo . --app <app> --version V<N> --work-order <id>`, not only the
  latest revision.

One invocation executes one work order. It may open one linked PR per mapped repository
plus a coordination PR. Stop at authorized repository/path boundaries. Never widen the
accepted schema or commit a credential.

After PR review and deployment proof, record status with
`python3 "$S" set-status --repo . --app <app> --version V<N> --work-order <id> --status <status> --pr <url>`.
`verified` requires the current revision to be implemented. Never edit digest-bound wiki
notes. Return to the work-order queue and state which order has become
Ready.

$ARGUMENTS
