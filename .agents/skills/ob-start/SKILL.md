---
name: ob-start
description: >-
  Start — create local obconfig and run the first analysis; later runs use /ob-analyze. Explicit workflow wrapper for $ob-start in Codex CLI and
  @ob-start in ChatGPT Desktop; do not invoke implicitly.
---

# ob-start

Follow the matching obengineer command contract below as the authoritative workflow.
Preserve all user-supplied text accompanying the explicit invocation exactly and make
it available wherever the contract refers to `$ARGUMENTS`; do not drop, summarize, or
reinterpret those arguments before dispatch.

If the contract still contains the literal `{{OBENGINEER_ROOT}}` placeholder, resolve it to
the obengineer toolkit root associated with this skill before following any referenced
file or command.


## Command contract

Start an obengineer engagement: create local project-root `obconfig.yaml` and run the
first analysis. After that, edit `obconfig.yaml` or `artifacts/` and rerun `/ob-analyze`.

1. Read `{{OBENGINEER_ROOT}}/prompts/00-load-obconfig.md` and follow its two exact gates.
2. Before discovery, run `manage_obconfig.py --project-root . init`. If it creates the
   file, print its instruction and stop. If no config exists but a legacy `.env`,
   `.env.template`, or `docs/observability/engagement-inputs.yaml` exists, list only
   those paths and destination key paths, ask the repair gate, and run
   `migrate-legacy` only after exact `yes`; legacy files are preserved.
3. Run `validate`. On failure, repeat exactly the emitted repair question. Exact `no`
   stops without mutation. Exact `yes` runs `repair --answer yes`; an unsafe or
   ambiguous document blocks without analysis.
4. Run `summary`. Show it unchanged and ask exactly:
   `Proceed with analysis using this configuration? (yes/no)`.
5. Exact `no` stops. Exact `yes` runs `authorize --answer yes --command ob-start
   --intended-version V<N>`, where `V<N>` is the next immutable version, then follows
   `{{OBENGINEER_ROOT}}/commands/ob-analyze.md`. Any other answer repeats the gate.

Never print config values outside the redacted summary, start discovery before
authorization, or use a browser/localhost review surface.

$ARGUMENTS
