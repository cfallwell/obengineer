# End-to-end usage

Run `/ob-start` (Cursor/Claude), `$ob-start` (Codex CLI), or `@ob-start` (ChatGPT
Desktop with local execution) from the artifact repository.

## Configure and authorize

On first run, obengineer creates ignored mode-0600 root `obconfig.yaml` from the
committed template and stops. Edit it and rerun. The canonical template explains every
field; docs do not duplicate that contract.

The rerun:

1. rejects unsafe, tracked, non-ignored, permissive, duplicate-key, or invalid config;
2. offers only catalogued safe repair through an exact `yes/no` gate;
3. hashes the complete artifact directory and calculates deterministic delta;
4. displays a condensed redacted summary; and
5. asks `Proceed with analysis using this configuration? (yes/no)`.

Exact `no` performs no network or analysis action. Exact `yes` binds one-shot
authorization to the config and artifact bytes and starts the next immutable analysis.
Changing either input before dispatch returns to a new summary.

## Analysis and review

Analysis rereads added/changed artifacts, removes deleted context, preserves accepted
historical versions, and runs six bounded evidence workstreams. Configured Splunk
products receive mandatory direct read attempts; MCP sources supplement them. Failures
are explicit redacted dispositions, never fabricated success.

The result is one reviewed PR containing linked Markdown analysis, canonical contract,
sanitized provenance, verification plan, versioned wiki, and all work orders. Review in
the host side panel; no browser or localhost server is used.

Reply `yes` only when asked whether to accept the finished version and merge its PR.
That acceptance is separate from the pre-analysis proceed gate.

## Add or edit inputs

Edit local `obconfig.yaml`, then run `/ob-add-inputs` or `/ob-edit-inputs`. Both are
compatibility entry points with identical behavior:

- unchanged config prints `Edit obconfig.yaml, then rerun this command.` and stops;
- changed config validates, rehashes artifacts, shows the common redacted summary, and
  uses the common proceed gate for the next immutable version.

Neither command edits YAML, asks field questions, or displays current values.

After acceptance, use `/ob-implement work-order:<id>`, `/ob-terraform`, and `/ob-verify`.
Implementation requires a Ready work order, Terraform remains plan-only, and
verification is read-only with the same secure config loader and mandatory configured
direct API attempts.
