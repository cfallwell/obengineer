# obengineer

Instrumentation architecture workflows for Claude Code and Codex: analyze a target, write
the customer document, lay the wiki the agents retrieve from, land the contract in code,
and configure the tenant as Terraform.

## Skills

| Skill | Purpose |
|---|---|
| `$engagement-intake` | Collect the inputs no scan can reach — artifacts, tenancy, entitlement, privacy regime — into one file, asking only for what is missing |
| `$instrumentation-analyze` | Deep-scan the front end, map backends and buses, inventory the existing Splunk and ThousandEyes footprint, enumerate business transactions from evidence, and write the one customer document: Markdown, a `.docx`, and `attribute-schema.json` |
| `$instrumentation-wiki` | Turn the accepted analysis into one note per subject under `wiki/apps/<app>/services/<service>/`, with work orders, tracked versions, and the host memory pointers |
| `$baggage-propagation` | The cross-cutting attribute set and W3C Baggage contract: set once, propagate, stamp on every span |
| `$cardinality-budget` | Dimension versus attribute-only as arithmetic against entitlement, plus MMS and TMS sizing |
| `$customer-doc-render` | Render Markdown to a verified customer-review `.docx` — Table of Contents, one section per page |
| `$instrumentation-implement` | Land an accepted contract as ordered, single-concern pull requests |
| `$observability-as-code` | Emit the contract as Terraform across the three Splunk providers, at executive, SRE, and engineer levels |
| `$deliverable-review` | Grade a finished deliverable against the completeness bar and report defects by rubric row |

## Requirements

`python3` and `python-docx` for the document renderer:

```bash
pip install python-docx
```

The SessionStart hook checks for it and reports rather than installing anything. It
never fails a session.

## MCP servers

`.mcp.json` ships with an empty `mcpServers` object so a placeholder command cannot
fail plugin startup. **Splunk Observability Cloud and Splunk Enterprise are
mandatory:** copy those two entries from `.mcp.optional.json` and supply your
organisation's command. ThousandEyes and the local OpenTelemetry tools server are
recommended. A Jira MCP is used only when this host already has one. Classification:
the plugin copy of `skills/references/mcp-servers.md`.

**Never put a token value in either file.** Use `${VAR}` references only; both files
are committed.

## What it writes

Under `docs/observability/` in your workspace: one customer document as Markdown, the
`.docx` rendered from that same Markdown, and `attribute-schema.json`. Under
`wiki/apps/<app>/services/<service>/`: the notes the agents retrieve by subject. It does not modify
application code unless you run `$instrumentation-implement` against an analysis you
have accepted.
