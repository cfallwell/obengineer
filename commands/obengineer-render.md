---
description: Render a Markdown deliverable to a customer-review .docx and prove the render matches its source
---

Render a deliverable for customer review.

Read `{{OBENGINEER_ROOT}}/skills/customer-doc-render/SKILL.md` and follow it.

The source Markdown is the argument below; default to
`docs/observability/INSTRUMENTATION-GUIDE.md` if none was given.

The render is not done until `verify_render.py` exits 0. Never hand-edit the `.docx` —
it is a build artifact, and an edited one is a second source of truth that will disagree
with the Markdown within a week.

$ARGUMENTS
