---
description: Revise — change one subordinate work order in the accepted analysis version
---

Revise one subordinate work order without creating a new analysis version.

1. Adopt `{{OBENGINEER_ROOT}}/agents/instrumentation-implementer.agent.md`.
2. Resolve the accepted version from `wiki/apps/<app>/index.md`, then verify its
   `acceptance.yaml` with:
   `python3 "{{OBENGINEER_ROOT}}/skills/instrumentation-wiki/scripts/verify_analysis_acceptance.py" --record <acceptance-path> --repo .`.
3. Load only the selected version's work-order note, every revision under
   `wiki/apps/<app>/implementation/V<N>/revisions/<id>/` in order, and the object notes it
   names.

Accept one selector: `work-order:<id>`, `workflow:<name>`, `business-transaction:<id>`,
`detector:<id>`, `alert-condition:<id>`, `dashboard:<id>`, or `custom-code:<id>`.
Resolve it to exactly one subordinate work order. Refuse foundation and use-case orders:
foundation changes need a new analysis version (edit `obconfig.yaml` or `artifacts/`, then
rerun `/ob-analyze`), and a use case is revised through its subordinate orders.

Collect the requested changes: naming conventions, attributes to add, remove, or rename,
additional spans, and detector or alert-condition changes. Record the reason and the
requester's role (for example SRE or engineer). Never ask for or record a person's name.

Write the change file, then run, where `<app>` and `V<N>` are the resolved accepted
application and version:

`python3 "{{OBENGINEER_ROOT}}/skills/instrumentation-wiki/scripts/work_order_state.py" revise --repo . --app <app> --version V<N> --work-order <id> --file <change-file>`

`python3 "{{OBENGINEER_ROOT}}/skills/instrumentation-wiki/scripts/work_order_state.py" verify --repo . --app <app> --version V<N>`

A version accepted before work-order kinds existed has a `legacy` ledger and cannot be
revised; `revise` refuses it, and the change needs a new analysis version: edit
`obconfig.yaml` or `artifacts/`, then rerun `/ob-analyze`.

Create a branch in the memory repository, commit the revision and ledger change, push, and
open one PR. Never create a new analysis version or edit digest-bound wiki notes. Merge
only after an explicit human `yes`.

Tell the user the order is now `changed` when it was implemented or verified, and that it
can be re-implemented with `/ob-implement work-order:<id> reimplement`.

$ARGUMENTS
