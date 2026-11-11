# Memory repository scaffold

A project-scoped install creates missing `.gitignore`, `.env.template`, and
`artifacts/README.md` at the repository root. Existing files are never overwritten.
Reinstall is safe, and uninstall removes only unchanged files whose scaffold manifest
proves the installer created them; files placed in `artifacts/` are never removed.

Copy the generated environment template locally and fill only the inputs you have:

```bash
cp .env.template .env
```

`.env` is gitignored. Do not commit it. `.env.template` stays in git with empty values.
`PASSWORD_REF` must contain a `${VAR}` reference, never a password.

The intake prefill reads allowlisted names from `.env` or the process environment. It
maps onboarding values into `docs/observability/engagement-inputs.yaml` without
overwriting supplied fields. Raw Splunk tokens stay in `.env`; only `${VAR}` references
enter the committed input artifact.

The analyze run uses relevant MCP servers and direct Splunk API endpoints when it
inventories existing telemetry. The procedure is
`skills/references/existing-telemetry.md` in the toolkit.
