# obengineer

Instrumentation architecture workflows for Claude Code and Codex: analyze a target,
write the full instrumentation contract, and render it for customer architecture
review.

## Skills

| Skill | Purpose |
|---|---|
| `$instrumentation-analyze` | Deep-scan the front end, map backends and buses, inventory the existing Splunk and ThousandEyes footprint, enumerate business transactions from evidence |
| `$instrumentation-guide` | Write the full contract; emits Markdown, a customer `.docx`, and `attribute-schema.json` |
| `$baggage-propagation` | The cross-cutting attribute set and W3C Baggage contract: set once, propagate, stamp on every span |
| `$customer-doc-render` | Render Markdown to a verified customer-review `.docx` — Table of Contents, one section per page |
| `$instrumentation-implement` | Land an accepted contract as ordered, single-concern pull requests |

## Requirements

`python3` and `python-docx` for the document renderer:

```bash
pip install python-docx
```

The SessionStart hook checks for it and reports rather than installing anything. It
never fails a session.

## MCP servers

`.mcp.json` declares **no servers by default**, and the skills work without any. Every
server they can use needs an endpoint, command, or token that only your organisation
can supply, and a server that fails to start is worse than one that was never
declared.

`.mcp.optional.json` describes the four that pair with these skills — a local
OpenTelemetry audit-and-verify server, Splunk Observability Cloud, the Splunk platform,
and ThousandEyes — with what each is used for and the environment variables it needs.
Copy the entry you want into `.mcp.json`, supply the command, and export those
variables.

**Never put a token value in either file.** Use `${VAR}` references only; both files
are committed.

## What it writes

Under `docs/observability/` in your workspace: the analysis memo, the instrumentation
guide, `attribute-schema.json`, and the rendered customer document. It does not modify
application code unless you run `$instrumentation-implement` against a guide you have
accepted.
