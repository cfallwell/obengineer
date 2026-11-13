# obengineer

obengineer is an agent toolkit for Splunk Observability Cloud and OpenTelemetry. It
analyzes a production application, writes a versioned instrumentation strategy, and
then delivers that strategy: pull requests for the code changes, Terraform for the Splunk
resources, and checks against your tenant to confirm the result. It runs in Cursor,
Claude Code, Codex CLI, and ChatGPT Desktop.

## Analysis

One command, `/ob-start`, produces a complete strategy in a single pull request for you
to review. The analysis draws on several sources at once: the application's source code,
the running application, read-only Splunk Observability and Splunk Platform APIs,
connected MCP tools, and any documents you supply. Each fact is labeled as measured,
stated, public, or derived, and a measured fact always overrides a stated one.

Each analysis includes:

- **Architecture.** Services, dependencies, entry points, and how requests and messages
  move between them.
- **Current telemetry.** What the tenant already receives: services, traces, metrics,
  MetricSets, detectors, dashboards, and usage against enforced system limits.
- **Critical findings.** Gaps such as broken trace propagation, missing signals,
  high-cardinality risks, and exposed credentials, each with its severity, evidence, and
  fix.
- **Security assessment.** Checks for exposed credentials and APIs, plus versioned OWASP
  Web and API coverage, within the boundary you authorize.
- **Use cases, workflows, and business transactions.** Use cases are derived from the
  application itself and lead to the workflows and business transactions they depend
  on.
- **Signal contracts.** Shared attributes, W3C Baggage propagation, span and metric
  naming, and a cardinality budget that decides which tags become metric dimensions.
- **Operations.** Detectors with thresholds, SLOs with error budgets, and dashboards
  built for executives, SREs, and engineers.
- **Work orders.** The complete set of implementation steps, ordered by dependency and
  linked to the findings and use cases they address.
- **Verification plan.** The telemetry and resources that must exist before the work
  counts as done.

The analysis is published as linked Markdown that opens in the host's side panel, with
a matching wiki for agents. Each run is a new version, labeled `[V1]`, `[V2]`, and so
on. Earlier versions are never modified. A Word summary of under 20 pages is available
on request.

## Delivery

After you reply `yes` to accept a version, obengineer carries it out:

- **`/ob-implement`** delivers the strategy in reviewable slices. You can target a
  single work order, a use case, a workflow, a business transaction, a detector, an
  objective, or a configuration change. A use case can span several workflows and
  business transactions across multiple repositories. obengineer delivers it as one
  unified change, with one pull request per repository and a coordination pull request
  that links them. You can limit the work to one repository or to specific folders
  within a repository. Typical changes include the shared OTel library, provider
  initialization, baggage propagation, message-bus inject and extract, workflow spans,
  custom meters, Collector configuration, and CI checks that keep the contract enforced.
- **`/ob-terraform`** generates Terraform for dashboards, detectors, SLOs, metric
  rulesets, Synthetics checks, and Splunk Platform indexes. It imports resources that
  already exist instead of duplicating them, and it stops at a plan that you apply.
- **`/ob-verify`** checks the tenant against the accepted strategy and reports each
  unmet criterion with the exact steps to fix it and recheck.

## Safety

- Production analysis and verification are read-only.
- Tokens and passwords stay in a local, Git-ignored `obconfig.yaml` and never appear in
  reports.
- Application code changes only through accepted work orders and reviewed pull
  requests.
- Terraform is never applied automatically.
- The [security assessment](docs/configuration.md#security-assessment-modes) is passive
  by default. Optional `safe-active` mode adds two `HEAD` requests to each HTTPS origin
  you authorize and never runs penetration-testing tools.

## Install

Requires Git and Python 3.10 or later. Terraform CLI is needed only for `/ob-terraform`.

```bash
python3 -m pip install PyYAML==6.0.3
git clone https://github.com/cfallwell/obengineer.git
cd obengineer
./install.sh --cursor --project /path/to/memory-repo
```

Use `--claude`, `--codex`, or `--all` to install for other hosts, then restart the host.
The memory repository is a separate Git repository that holds everything obengineer
generates.

## Usage

```text
/ob-start                     Validate obconfig.yaml and run the next analysis version
/ob-implement <target>        Deliver a work order, use case, workflow, or transaction
/ob-terraform                 Plan Splunk resources
/ob-verify                    Verify the deployed result
```

To update an analysis, edit `obconfig.yaml` or `artifacts/`, then run `/ob-start` again.

Use the `/` prefix in Cursor and Claude Code, `$` in Codex CLI, and `@` in ChatGPT
Desktop. ChatGPT Desktop needs its local executor enabled.

## Documentation

- [Installation and upgrades](docs/installation.md)
- [Configuration and behavior controls](docs/configuration.md)
- [End-to-end usage and command reference](docs/usage.md)
- [How obengineer operates](docs/how-it-works.md)
- [Design rationale](docs/design.md)

## Development

`make deps`, `make test`, and `make check`. Canonical skills live in `skills/`; run
`make sync-plugin-skills` after changing them.

## License

[MIT](LICENSE)
