# obengineer

obengineer analyzes a production application and publishes a versioned, linked
instrumentation strategy for Splunk Observability Cloud and OpenTelemetry. The result
opens in the agent host's native side panel: architecture, findings, recommended path,
use cases, workflows, business transactions, shared signal contracts, operations, and the
complete proposed work-order queue.

Generated artifacts belong in a separate memory or application repository. This
repository remains the toolkit.

## Requirements

- Git
- Python 3.10+
- `python-docx` and `markdown-it-py==4.2.0` only when rendering the optional Word summary
- `PyYAML==6.0.3` for input validation
- Terraform CLI for `/ob-terraform`

```bash
python3 -m pip install python-docx markdown-it-py==4.2.0 PyYAML==6.0.3
```

## Install

```bash
git clone https://github.com/cfallwell/obengineer.git
cd obengineer
mkdir -p /path/to/memory-repo
git -C /path/to/memory-repo init
./install.sh --cursor --project /path/to/memory-repo
```

Use `--claude`, `--codex`, or `--all` for other hosts. Restart the host after
installation. A project install creates only missing `.gitignore`, `.env.template`, and
`artifacts/README.md`; it never overwrites existing root content.

Optional read-only Splunk API access is configured interactively without printing
credentials:

```bash
cd /path/to/memory-repo
/path/to/obengineer/scripts/setup-splunk-access.sh
```

obengineer also uses relevant MCP tools already connected to the host. MCP supplements
direct APIs; it is not the only tenant data source.

## Use

Open the artifact repository and run:

```text
Cursor / Claude Code: /ob-start
Codex CLI:           $ob-start
ChatGPT Desktop:     @ob-start
```

ChatGPT Desktop requires its local executor for these Python-backed workflows. ChatGPT
web/cloud and Work surfaces without local execution are not supported.

Before any discovery, the guided start immediately asks for the application, an explicit
production URL or no-browser reason, and what hurts. It then offers numbered optional
inputs. Reply with, for example, `yes 1 3 4`; after those answers it shows `[x]`, `[ ]`,
and `[-]` status and asks again. Only explicit `no` authorizes analysis. Missing optional
answers do not block analysis.

At any time:

```text
Cursor / Claude Code: /ob-add-inputs, /ob-edit-inputs
Codex CLI:           $ob-add-inputs, $ob-edit-inputs
ChatGPT Desktop:     @ob-add-inputs, @ob-edit-inputs
```

Each addition or edit automatically creates the next immutable `[V<N>]` analysis and one
review PR. The PR contains the linked Markdown site, schema, ledger, verification plan,
versioned wiki, and every proposed work order.

When review is complete, reply `yes` to accept the version and merge the PR. The agent
resolves commits and content digests internally; no SHA or named accepter is required.
Eligible work orders become Ready.

Continue with:

```text
Cursor / Claude Code: /ob-implement work-order:<id>, /ob-terraform, /ob-verify
Codex CLI:           $ob-implement work-order:<id>, $ob-terraform, $ob-verify
ChatGPT Desktop:     @ob-implement work-order:<id>, @ob-terraform, @ob-verify
```

Terraform is plan-only and a human applies it. Verification is read-only.

## Analysis experience

- No browser or localhost server.
- One host-native documentation link in chat; detail stays in the side panel.
- `[V1] [V2] [V3]` selects immutable versions.
- Breadcrumbs return every detail page to the analysis index.
- The landing page represents the full strategy and links all detail.
- Use cases lead to workflows, business transactions, signal contracts, and work orders.
- Topics absent from evidence have no empty pages; suggestions share one reference page.
- Word is optional and, when requested, is a summary under 20 pages.

## Documentation

- [Documentation index](docs/README.md)
- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [End-to-end usage](docs/usage.md)
- [How it works](docs/how-it-works.md)
- [Design rationale](docs/design.md)

## Development

```bash
make deps
make test
make check
```

Canonical skills live in `skills/`. Run `make sync-plugin-skills` after changing them.

## License

[MIT](LICENSE)
