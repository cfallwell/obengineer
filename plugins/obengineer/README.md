# obengineer

Guided instrumentation analysis for Claude Code and Codex.

## Start

```text
/ob-start
```

The command discovers measurable facts, asks for the minimum, offers numbered optional
inputs, then creates analysis V1. Use `/ob-add-inputs` or `/ob-edit-inputs` at any time;
each automatically creates the next immutable version.

The analysis PR includes:

- linked Markdown for the host-native side panel;
- architecture, findings, strategy, and implementation path;
- use cases, workflows, business transactions, and signal contracts;
- schema, implementation map, provenance ledger, and verification plan;
- versioned wiki; and
- the complete proposed work-order queue.

After review, reply `yes` to accept and merge. Eligible work orders become Ready. No manual
SHA or named accepter is required.

## Data sources

obengineer combines direct Observability Cloud and Splunk Platform APIs with relevant MCP
tools already connected to the host. MCP is not the only source.

For read-only API credentials, run the toolkit's
`scripts/setup-splunk-access.sh` in the artifact repository. It writes local `.env` and
never prints tokens.

## Continue

```text
/ob-implement work-order:<id>
/ob-terraform
/ob-verify
```

Terraform never applies. Verification is read-only.

## Review experience

Navigation remains inside the host side panel or native document view. No browser,
localhost server, or high port is required. Versions use `[V1] [V2] ...`; every page has
breadcrumbs. Word is optional and, when requested, is a summary under 20 pages.

## Requirements

Python 3.10+ and `PyYAML==6.0.3`. Optional Word rendering additionally uses
`python-docx` and `markdown-it-py==4.2.0`.

Never put token values in committed MCP or environment templates.
