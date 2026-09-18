# Security

## Reporting

Report a vulnerability in this plugin through your organisation's normal security
channel. Do not open a public issue containing a credential, a customer identifier, or
a production URL with a session in it.

## Design constraints

- **No credential values anywhere.** Tokens in generated guides are placeholders
  (`window.__<ORG>_RUM_TOKEN__`, `${SPLUNK_ACCESS_TOKEN}`). MCP configuration uses
  `${VAR}` references. `verify_render.py` fails a document that contains a
  credential-shaped value, and a repository test fails a commit that does.
- **The SessionStart hook is read-only.** It checks for `python-docx` and probes
  `127.0.0.1` for the optional local MCP server. It installs nothing, contacts no
  external host, and always exits 0.
- **Optional MCP servers ship disabled.** No command is guessed on your behalf.
- **Generated guidance is deny-list aware.** The instrumentation contract's PII deny
  list covers credentials, tokens, and card data, and the same list is emitted into
  `attribute-schema.json` so CI can enforce it.

## Scanning production

`$instrumentation-analyze` reads production surfaces. It is read-only by design: it
does not submit forms destructively, run load, or modify state. Provide a test account
for authenticated scans, and rotate its credential afterwards.
