---
description: Start — create local obconfig and run the first analysis; later runs use /ob-analyze
---

Start an obengineer engagement: create local project-root `obconfig.yaml` and run the
first analysis. After that, edit `obconfig.yaml` or `artifacts/` and rerun `/ob-analyze`.

1. Read `${CLAUDE_PLUGIN_ROOT}/prompts/00-load-obconfig.md` and follow its two exact gates.
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
   `${CLAUDE_PLUGIN_ROOT}/commands/ob-analyze.md`. Any other answer repeats the gate.

Never print config values outside the redacted summary, start discovery before
authorization, or use a browser/localhost review surface.

$ARGUMENTS
