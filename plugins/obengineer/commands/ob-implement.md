---
description: Implement — execute one Ready work order from the accepted analysis version
---

Run one bounded implementation work order.

1. Adopt `${CLAUDE_PLUGIN_ROOT}/agents/instrumentation-implementer.agent.md`.
2. Resolve the accepted version from `wiki/apps/<app>/index.md`, then verify its
   `acceptance.yaml` with:
   `python3 "${CLAUDE_PLUGIN_ROOT}/skills/instrumentation-wiki/scripts/verify_analysis_acceptance.py" --record <acceptance-path> --repo .`.
3. Load only the selected version's analysis intent, schema, implementation map,
   relevant object notes, and work order. Never load every version or the whole wiki.
4. Follow `${CLAUDE_PLUGIN_ROOT}/prompts/03-implement-instrumentation.md` and use
   `$instrumentation-implement`.

Accept one selector: `work-order:<id>`, `business-transaction:<id>`,
`workflow:<name>`, `use-case:<id>`, `detector:<id>`, `objective:<id>`, or
`config:<id>`. Resolve it to exactly one Ready work order. Proposed, Blocked, Superseded,
or older-version orders cannot run.

One invocation executes one work order. It may open one linked PR per mapped repository
plus a coordination PR. Stop at authorized repository/path boundaries. Never widen the
accepted schema or commit a credential.

After PR review and deployment proof, update the touched wiki notes and work-order status
in the same change. Return to the work-order queue and state which dependency has become
Ready.

$ARGUMENTS
