---
name: ob-review
description: >-
  Review — grade a versioned analysis site and matching wiki. Explicit workflow wrapper for $ob-review in Codex CLI and
  @ob-review in ChatGPT Desktop; do not invoke implicitly.
---

# ob-review

Follow the matching obengineer command contract below as the authoritative workflow.
Preserve all user-supplied text accompanying the explicit invocation exactly and make
it available wherever the contract refers to `$ARGUMENTS`; do not drop, summarize, or
reinterpret those arguments before dispatch.

If the contract still contains the literal `{{OBENGINEER_ROOT}}` placeholder, resolve it to
the obengineer toolkit root associated with this skill before following any referenced
file or command.


## Command contract

Review the named analysis version, defaulting to the latest.

Read `{{OBENGINEER_ROOT}}/skills/deliverable-review/SKILL.md` and follow it.
The authorities are `analysis-site.md`, `agent-wiki.md`, and their linked contracts.

Grade the landing page and every reachable page, then the matching versioned wiki and
work-order queue. Validate the provenance ledger, schema, implementation map,
verification plan, breadcrumbs, relative links, version isolation, reverse work-order
links, and credential safety.

Report every defect with rule, file, line, consequence, and smallest repair. Do not
rewrite the analysis; grading remains independent.

$ARGUMENTS
