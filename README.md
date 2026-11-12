# obengineer

obengineer is an agent toolkit that helps you plan and deliver OpenTelemetry
instrumentation for an application monitored in Splunk Observability Cloud. You point it
at an application, its source code, and your Splunk tenant. It studies what is already
there and writes a reviewable observability strategy. Once you accept that strategy, it
helps you carry it out.

The strategy covers the application's architecture, the gaps found in its current
telemetry, the user journeys and business transactions worth measuring, and the signals
each service should emit. It also includes a queue of small, ordered work orders. Each
work order describes one change, such as adding a shared tracing library, propagating
context across a message bus, or defining a detector. Your coding agent can then
implement those work orders as ordinary pull requests.

obengineer runs inside Cursor, Claude Code, Codex CLI, and ChatGPT Desktop.

## How it works

obengineer keeps the toolkit and your engagement separate. You install it into a
dedicated Git repository, called the memory repository, and everything it produces is
committed there. This repository contains only the toolkit itself.

A typical engagement has four stages:

1. **Configure.** You describe the application and how to reach it in a local
   `obconfig.yaml` file. This includes the application's name and environment, where its
   source lives, read-only Splunk tokens, and any supporting documents you want
   considered. obengineer checks the file and shows you a short summary before it does
   anything else.
2. **Analyze.** obengineer gathers evidence from the source code, the running
   application, the Splunk APIs, and any connected tools. It then writes the analysis as
   linked Markdown pages that open in your editor's side panel, along with a wiki and the
   full work-order queue. All of it arrives in a single pull request for you to review.
   Each run is saved as a new numbered version (V1, V2, and so on), so earlier analyses
   are never overwritten.
3. **Accept.** When you are satisfied with the analysis, reply `yes`. obengineer records
   your acceptance, merges the pull request, and marks the first work orders as ready to
   start.
4. **Deliver and verify.** You implement work orders one at a time. Each one becomes a
   pull request in the application's repository. obengineer can also generate Terraform
   for dashboards, detectors, and related Splunk resources. After the changes are
   deployed, it checks your tenant to confirm that the expected telemetry and resources
   are actually there.

obengineer only reads from production. It never changes your Splunk tenant directly:
generated Terraform is planned for you to apply yourself, and verification makes no
changes. Tokens and passwords stay in `obconfig.yaml`, which Git ignores, and they are
never copied into reports.

## Requirements

- Git
- Python 3.10 or later, with `PyYAML==6.0.3`
- `python-docx` and `markdown-it-py==4.2.0`, only if you want the optional Word summary
- Terraform CLI, only if you use `/ob-terraform`

```bash
python3 -m pip install PyYAML==6.0.3 python-docx markdown-it-py==4.2.0
```

## Installation

Clone the toolkit:

```bash
git clone https://github.com/cfallwell/obengineer.git
cd obengineer
```

Create the memory repository and install obengineer into it:

```bash
mkdir -p /path/to/memory-repo
git -C /path/to/memory-repo init
./install.sh --cursor --project /path/to/memory-repo
```

Replace `--cursor` with `--claude` or `--codex` to install for another host, or use
`--all` to install for every host. Restart the host when the installer finishes.

The installer adds three starter files to the memory repository if they are not already
present: a `.gitignore`, an `obconfig.yaml.template`, and an `artifacts/README.md`. It
never overwrites files that already exist. See [Installation](docs/installation.md) for
upgrades and uninstalling.

## Usage

Open the memory repository in your host. Commands use a different prefix in each host:

| Host                 | Prefix | Example     |
| -------------------- | ------ | ----------- |
| Cursor, Claude Code  | `/`    | `/ob-start` |
| Codex CLI            | `$`    | `$ob-start` |
| ChatGPT Desktop      | `@`    | `@ob-start` |

ChatGPT Desktop needs its local executor enabled, because these workflows run Python on
your machine. ChatGPT on the web and other cloud-only surfaces are not supported.

### Start an analysis

Run `/ob-start`. The first time, obengineer creates `obconfig.yaml` from the template
and asks you to fill it in. Place any supporting documents, such as architecture
diagrams or runbooks, in the `artifacts/` directory.

Run `/ob-start` again when the file is ready. obengineer validates the configuration,
reports any problems with the line number and the reason, and then shows a summary with
secrets hidden. Reply `yes` to begin the analysis. When it finishes, you receive one link
to the analysis and one pull request to review.

### Review and accept

Read the analysis in the side panel and comment on the pull request as you would on any
other change. When the analysis is ready, reply `yes` in chat. obengineer accepts that
version, merges the pull request, and tells you which work order to start with.

### Update the analysis

If you learn something new, edit `obconfig.yaml` or add files to `artifacts/`, then run
`/ob-add-inputs` or `/ob-edit-inputs`. obengineer shows the same summary and asks for
confirmation. It then produces the next version of the analysis in a new pull request.
If nothing has changed, it tells you so and stops.

### Implement and verify

| Command                          | What it does                                                         |
| -------------------------------- | -------------------------------------------------------------------- |
| `/ob-implement work-order:<id>`  | Implements one ready work order as a pull request for review.        |
| `/ob-terraform`                  | Generates Terraform for Splunk resources and stops at a plan.        |
| `/ob-verify`                     | Checks the tenant against the accepted strategy and reports any gaps. |

Run `/ob-verify` after your changes are deployed and the Terraform has been applied.

## Security assessment

As part of the analysis, obengineer reviews the application's security posture within
the boundary you authorize. By default this review is passive. It examines source code,
configuration, dependencies, and the artifacts you supply, and it sends no
security-specific requests of its own. You can opt into `safe-active` mode. In that mode,
obengineer also sends two read-only `HEAD` requests to each HTTPS origin you explicitly
list, one for `robots.txt` and one for `security.txt`. It never runs penetration-testing
tools. [Security assessment modes](docs/configuration.md#security-assessment-modes)
describes exactly what each mode does.

## Documentation

- [Documentation index](docs/README.md)
- [Installation and upgrades](docs/installation.md)
- [Configuration and behavior controls](docs/configuration.md)
- [End-to-end usage and command reference](docs/usage.md)
- [How obengineer operates](docs/how-it-works.md)
- [Design rationale](docs/design.md)

## Development

```bash
make deps
make test
make check
```

The canonical skills live in `skills/`. After you change a skill, run
`make sync-plugin-skills` to update the copies bundled with the plugin.

## License

[MIT](LICENSE)
