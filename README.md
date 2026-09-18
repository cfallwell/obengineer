# obengineer

Agents, skills, and plugins that turn an application into an **instrumentation
contract** — one a team can implement, CI can enforce, and a TAM can configure in
Splunk Observability Cloud.

Structured after [signalfx/obstudio](https://github.com/signalfx/obstudio): canonical
skills under `skills/`, a self-contained bundle under `plugins/`, host wiring for
Cursor, Codex, and Claude Code, and deterministic tests over the agentry itself.

## What this produces

Three runs, each with a prompt and an agent definition:

| Run | Prompt | Output |
|---|---|---|
| Analyze | [`prompts/01-analyze-application.md`](prompts/01-analyze-application.md) | `analysis-<app>-<date>.md` — what the target actually is, measured |
| Guide | [`prompts/02-develop-instrumentation-guide.md`](prompts/02-develop-instrumentation-guide.md) | `INSTRUMENTATION-GUIDE.md`, a customer `.docx`, and `attribute-schema.json` |
| Implement | [`prompts/03-implement-instrumentation.md`](prompts/03-implement-instrumentation.md) | Small reviewable PRs, one contract slice each |

Every guide ships **twice** — Markdown for the engineers working the PRs, and a Word
document for customer architecture review, rendered from the same Markdown so the two
cannot disagree.

## Skills

| Skill | Purpose |
|---|---|
| `$instrumentation-analyze` | Deep-scan the front end (script order, competing agents, where the agent initialises, router, CSP, consent, status-versus-content), map backends and buses, inventory the existing portfolio footprint, enumerate business transactions from evidence |
| `$instrumentation-guide` | Write the full contract in canonical template order and emit all three artifacts |
| `$baggage-propagation` | The cross-cutting attribute set and W3C Baggage contract: set once, propagate, stamp on every span via `SpanProcessor.onStart` |
| `$customer-doc-render` | Render Markdown to a customer-review `.docx` — Table of Contents, one section per page, `Confidential` footer — then prove the render matches its source |
| `$instrumentation-implement` | Land the contract as ordered PRs, with the CI checks that keep it enforced |

## Quick start

```bash
pip install python-docx

# Render any Markdown deliverable for customer review, and prove it matches.
make render FILE=../docs/observability/INSTRUMENTATION-GUIDE.md

# Run the contract tests over the agentry.
make test
```

To use the skills, point your agent at this directory:

| Host | Wiring |
|---|---|
| **Cursor** | `.cursor/skills/` symlinks the canonical skills; open this directory as a workspace folder |
| **Codex** | `.agents/skills/` for repo-scoped use, or install the plugin from `.agents/plugins/marketplace.json` |
| **Claude Code** | Add the marketplace at `.claude-plugin/marketplace.json`, then install the `obengineer` plugin |

## Two references do the heavy lifting

Both are self-contained, so the format is reproducible in a fresh session with no
prior customer document to copy from:

- **[`skills/references/document-template.md`](skills/references/document-template.md)** — the canonical customer document: section order, every table's columns, the front matter, and the pre-delivery checklist.
- **[`skills/references/cross-cutting-attributes.md`](skills/references/cross-cutting-attributes.md)** — the mandatory baggage section, with the attribute-set table and all five code subsections.

## MCP servers

`plugins/obengineer/.mcp.json` declares the local
[obstudio](https://github.com/signalfx/obstudio) MCP server, which pairs with these
skills for the OTel audit and verify loop.

Splunk Observability Cloud, Splunk platform, and ThousandEyes servers are described in
`.mcp.optional.json` rather than enabled by default: each needs an endpoint or command
only your organisation can supply, and a server that fails to start is worse than one
that was never declared. Copy the entry you want into `.mcp.json`, supply the command,
and export the listed environment variables. **Never** put a token value in either
file — `${VAR}` references only.

## Contributing

`skills/` is the single source. The plugin carries copies so an installed bundle is
self-contained; refresh them with `make sync-plugin-skills` and never edit them
directly. See [`AGENTS.md`](AGENTS.md) for the review rules and
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow.
