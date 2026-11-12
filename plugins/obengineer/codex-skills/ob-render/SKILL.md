---
name: ob-render
description: >-
  Render — build and verify an optional Word summary under 20 pages. Explicit workflow wrapper for $ob-render in Codex CLI and
  @ob-render in ChatGPT Desktop; do not invoke implicitly.
---

# ob-render

Follow the matching obengineer command contract below as the authoritative workflow.
Preserve all user-supplied text accompanying the explicit invocation exactly and make
it available wherever the contract refers to `$ARGUMENTS`; do not drop, summarize, or
reinterpret those arguments before dispatch.


## Command contract

Render the optional Word summary for an analysis version.

Read `${PLUGIN_ROOT}/skills/customer-doc-render/SKILL.md` and
`${PLUGIN_ROOT}/skills/references/document-template.md`.

Resolve the selected version, generate its temporary summary Markdown from the analysis
index, findings, path, work-order summary, and use-case summaries, then render and verify
the `.docx`. It must remain under 20 pages. Do not include deep contracts, code, complete
catalogues, or raw evidence. Never edit Word directly.

$ARGUMENTS
