---
description: Review — grade a deliverable against the completeness bar
---

Review a deliverable.

Read `${CLAUDE_PLUGIN_ROOT}/skills/deliverable-review/SKILL.md` and follow it. The rubric is
`${CLAUDE_PLUGIN_ROOT}/skills/references/document-template.md` — its section list, completeness
bar, and pre-delivery checklist. If this skill and the rubric disagree, the rubric wins.

Grade the file named below, defaulting to the analysis document under `docs/observability/`.
Use `docs/observability/engagement-inputs.yaml` to decide which conditional sections apply.
Validate `docs/observability/provenance-ledger.json`; evidence and outcome issue fields
must cite ledger IDs and remain anonymized.

Report every defect with the rubric row, the file, the line, and the smallest fix. Do not
stop at the first one, and **do not rewrite the document** — grading and authoring stay
separate, or there is no independent check.

$ARGUMENTS
