---
name: ob-implement
description: >-
  Implement — execute one Ready work order from the accepted analysis version. Explicit workflow wrapper for $ob-implement in Codex CLI and
  @ob-implement in ChatGPT Desktop; do not invoke implicitly.
---

# ob-implement

Follow the matching obengineer command contract below as the authoritative workflow.
Preserve all user-supplied text accompanying the explicit invocation exactly and make
it available wherever the contract refers to `$ARGUMENTS`; do not drop, summarize, or
reinterpret those arguments before dispatch.

If the contract still contains the literal `{{OBENGINEER_ROOT}}` placeholder, resolve it to
the obengineer toolkit root associated with this skill before following any referenced
file or command.


## Command contract

Run one bounded implementation work order.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-implementer.agent.md`.
2. Resolve the accepted version from `wiki/apps/<app>/index.md`, then verify its
   `acceptance.yaml` with:
   `python3 "{{OBENGINEER_ROOT}}/skills/instrumentation-wiki/scripts/verify_analysis_acceptance.py" --record <acceptance-path> --repo .`.
3. Load only the selected version's analysis intent, schema, implementation map,
   relevant object notes, work order, and its latest revision. Never load every version
   or the whole wiki.
4. Follow `{{OBENGINEER_ROOT}}/prompts/03-implement-instrumentation.md` and use
   `$instrumentation-implement`.

Accept one selector: `work-order:<id>`, `business-transaction:<id>`,
`workflow:<name>`, `use-case:<id>`, `detector:<id>`, `alert-condition:<id>`,
`dashboard:<id>`, `custom-code:<id>`, `objective:<id>`, or `config:<id>`. Resolve it to
exactly one Ready work order. `use-case:<id>` runs the gate's `next_subordinate`.
Proposed, Blocked, Superseded, or older-version orders cannot run.

Before any work, gate the order with the state ledger
(`S="{{OBENGINEER_ROOT}}/skills/instrumentation-wiki/scripts/work_order_state.py"`):

- If `wiki/apps/<app>/implementation/V<N>/state.yaml` is missing, run `python3 "$S" init`.
- Run `python3 "$S" gate --work-order <id>`. Non-foundation orders run only when every
  foundation order is complete (implemented or verified).
- An implemented, verified, or changed order runs again only when the arguments include
  `reimplement`; then pass `--reimplement` to `gate`.

One invocation executes one work order. It may open one linked PR per mapped repository
plus a coordination PR. Stop at authorized repository/path boundaries. Never widen the
accepted schema or commit a credential.

After PR review and deployment proof, record status with
`python3 "$S" set-status --work-order <id> --status <status> --pr <url>`. Never edit
digest-bound wiki notes. Return to the work-order queue and state which order has become
Ready.

$ARGUMENTS
