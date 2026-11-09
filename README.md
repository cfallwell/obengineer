# obengineer

obengineer is a multi-host agent toolkit for designing and implementing a Splunk
OpenTelemetry instrumentation contract. It inspects an application and its existing
telemetry, produces a reviewable analysis and attribute schema, turns the accepted
contract into an agent-readable wiki, and can then implement one contract slice or
generate Terraform.

It supports Cursor, Claude Code, and Codex. Generated artifacts belong in a separate
memory or application repository; this repository remains the toolkit.

## Requirements

- Git
- Python 3
- `python-docx` for Word document rendering
- Terraform CLI when using `/ob-build-terraform`

```bash
python3 -m pip install python-docx
```

## Install

Clone the toolkit:

```bash
git clone https://github.com/cfallwell/obengineer.git
cd obengineer
```

Create or clone the repository that will hold the engagement artifacts, then install
obengineer into it:

```bash
mkdir -p /path/to/memory-repo
git -C /path/to/memory-repo init

./install.sh --cursor --project /path/to/memory-repo
```

Use `--claude`, `--codex`, or `--all` instead of `--cursor` for other hosts. Restart
the host after installation. Run `./install.sh --help` for all installer options.

For tenant inventory, copy `templates/memory-repo/.env.template` and
`templates/memory-repo/.gitignore` into the memory repository, create `.env` from the
template, and enable the required MCP servers using environment-variable references.
Never commit `.env` or place credential values in MCP configuration.

## Use

Open the memory repository in the installed host and run:

```text
/ob-intake
/ob-analyze
/ob-wiki
/ob-implement workflow: <accepted-workflow-name>
/ob-build-terraform
```

The first three commands are sequential. A person must accept the analysis before
`/ob-wiki`, `/ob-implement`, or `/ob-build-terraform` proceeds. After acceptance,
implementation and Terraform generation can run independently.

Use `/ob-review` to grade a deliverable and `/ob-render` to rebuild and verify its
Word rendering.

## Documentation

- [Documentation index](docs/README.md)
- [Installation and upgrades](docs/installation.md)
- [End-to-end usage and command reference](docs/usage.md)
- [Configuration and behavior controls](docs/configuration.md)
- [How obengineer operates](docs/how-it-works.md)
- [Design rationale](docs/design.md)
- [Contributing](CONTRIBUTING.md)

## Development

```bash
make deps
make test
make check
```

Canonical skills live in `skills/`. Do not edit generated copies under
`plugins/obengineer/skills/`; use `make sync-plugin-skills`.

## License

[MIT](LICENSE)
