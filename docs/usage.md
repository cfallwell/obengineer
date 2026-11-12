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
authorization to the config and full artifact snapshot. Analysis atomically claims it;
changing either input prevents API/PR dispatch. Concurrent/repeated claims fail.

## Analysis and review

Analysis rereads added/changed artifacts, removes deleted context, preserves accepted
historical versions, and runs six bounded evidence workstreams. Configured Splunk
products receive mandatory direct read attempts; MCP sources supplement them. Failures
are explicit redacted dispositions, never fabricated success.

After claiming with the originating command and intended version, analysis runs:

```text
python3 <obengineer-root>/skills/engagement-intake/scripts/manage_obconfig.py --project-root . direct-api --phase analysis --command <origin> --intended-version V<N>
python3 <obengineer-root>/skills/engagement-intake/scripts/manage_obconfig.py --project-root . safe-active --command <origin> --intended-version V<N>
python3 <obengineer-root>/skills/engagement-intake/scripts/manage_obconfig.py --project-root . finalize --command <origin> --intended-version V<N> --output docs/observability --output wiki/apps/<app>/versions/V<N>
python3 <obengineer-root>/skills/engagement-intake/scripts/manage_obconfig.py --project-root . dispatch --command <origin> --intended-version V<N>
python3 <obengineer-root>/skills/engagement-intake/scripts/manage_obconfig.py --project-root . verify-dispatch --command <origin> --intended-version V<N>
```

Its centralized-redacted JSON feeds provenance. `/ob-verify` runs the same supported
path with `--phase verification` after acceptance/plan validation and feeds those rows
to verification evidence and provenance. Neither workflow imports the adapter directly
or puts credentials in command arguments. Passive/none makes zero safe-active requests.
After all analysis, network, render, and validation work, stage intended paths and run
finalize. It binds the full index tree and computes contained output digests itself.
Commit exactly that tree, record `dispatch`, and run `verify-dispatch` immediately before
push/PR operations. Only successful publication followed by final `consume` advances
the artifact baseline; consume re-verifies commit/tree/blob objects. Failure/decline invokes
`abort` with the same binding, releasing the claim while baseline/history stay unchanged.
Input edits after finalize belong to the next run and do not invalidate consumption of
the already published snapshot.

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
