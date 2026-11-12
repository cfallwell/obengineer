# obengineer

Guided instrumentation analysis for Claude Code and Codex.

## Start

```text
Claude Code:     /ob-start
Codex CLI:       $ob-start
ChatGPT Desktop: @ob-start
```

ChatGPT Desktop requires its local executor for these Python-backed workflows. ChatGPT
web/cloud and Work surfaces without local execution are not supported.

The command creates local ignored mode-0600 `obconfig.yaml` when missing, then stops for
editing. On rerun it validates, hashes the complete artifact directory, shows a redacted
summary, and requires exact proceed authorization before analysis V1. Edit the same file
and use `/ob-add-inputs` or `/ob-edit-inputs` for the next immutable version.

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
Analysis and verification use the supported
`manage_obconfig.py direct-api --phase analysis|verification` command and feed its
centralized-redacted JSON dispositions/aggregates into provenance.

Read-only API credentials remain only in local `obconfig.yaml` and are sent only in
validated HTTPS request headers. The committed `obconfig.yaml.template` is the sole
field authority.

## Continue

```text
Claude Code:     /ob-implement work-order:<id>, /ob-terraform, /ob-verify
Codex CLI:       $ob-implement work-order:<id>, $ob-terraform, $ob-verify
ChatGPT Desktop: @ob-implement work-order:<id>, @ob-terraform, @ob-verify
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
