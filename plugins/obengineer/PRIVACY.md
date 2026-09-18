# Privacy

## What this plugin reads

- Files in your workspace, to inventory the application and to read a guide it is asked to render.
- URLs you explicitly provide for a front-end scan.
- Any MCP server you enable in `.mcp.json`. None are enabled by default.

## What it writes

Files under `docs/observability/` in your workspace: the analysis memo, the
instrumentation guide, the attribute schema, and the rendered `.docx`. It writes
application code only through `$instrumentation-implement`, and only against a guide
you have accepted.

## What it does not do

- No telemetry about your usage is collected or transmitted by this plugin.
- No data is sent to Splunk, Cisco, or any third party. The optional MCP servers you
  enable yourself talk to your own tenants with your own credentials.
- No credential is stored. Tokens are referenced as `${ENV_VAR}` or placeholders, never
  captured into a deliverable.

## Sensitive data in deliverables

The analysis skill scans production surfaces and may encounter exposed keys, customer
identifiers, or PII in payloads. Its rules require that such a finding is recorded as a
finding and referenced as `<redacted>`, never reproduced. The document renderer also
scans its own output and fails the render if a credential-shaped value reached the
document.

If you scan an authenticated session, the account you use will appear in your workspace
artifacts. Use a test account.
