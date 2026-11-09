---
description: Render — rebuild the Word file from Markdown and verify it
---

Render a deliverable for customer review.

Read `{{OBENGINEER_ROOT}}/skills/customer-doc-render/SKILL.md` and follow it.

The source Markdown is the argument below; default to
the analysis document under `docs/observability/` if none was given.

The render is not done until `verify_render.py` exits 0. Never hand-edit the `.docx` —
it is a build artifact, and an edited one is a second source of truth that will disagree
with the Markdown within a week.

$ARGUMENTS
