# obengineer

obengineer is the toolkit for a Splunk OpenTelemetry instrumentation contract. It installs as skills and commands for Cursor, Claude Code, and Codex. Give it source, diagrams, a live URL, existing telemetry, and the inputs a scan cannot measure. It writes one customer document a coding agent can implement. Landed and enforced, that contract puts the same keys on the spans a dashboard variable, a detector grouping, and a Related Content link need, and it shortens MTTx (mean time to detect, acknowledge, and resolve).

Canonical skills live under `skills/`. `plugins/obengineer/` is the self-contained bundle a marketplace install gets. This repository stays the toolkit. The wiki and the deliverables are written in a separate memory repository.

## Pull the toolkit, then create the memory repository

Do these two steps in this order.

1. Pull the obengineer repository so this checkout matches the current toolkit.

   ```bash
   cd /path/to/obengineer
   git pull
   ```

2. Create a separate repository for obengineer to use for memory. From this toolkit checkout, run the install command with `--project` pointing at that memory repository. The flag installs skills and commands into the memory repository. Cursor and Claude Code use `.cursor/` and `.claude/` inside it. Codex uses `.agents/` for skills and `prompts/` for commands.

   ```bash
   ./install.sh --cursor --project /path/to/memory-repo
   ```

   Pass `--claude`, `--codex`, or `--all` in place of `--cursor` when those hosts should receive the same install. Restart the host so it loads the new skills and commands. Open the memory repository in the host and run the commands there. They write `docs/observability/`, the wiki, and `terraform/` into that repository.

   Copy `templates/memory-repo/.gitignore` and `templates/memory-repo/.env.template` into the memory repository. Then copy `.env.template` to `.env` and fill it. `.env` is gitignored. That template path is in this repository. It is not on every branch today.

## Install

`install.sh` is a thin wrapper around `scripts/install.py`.

```bash
./install.sh --cursor --project /path/to/memory-repo
./install.sh --claude --codex --project /path/to/memory-repo
./install.sh --all --project /path/to/memory-repo
```

| Flag | Effect |
|---|---|
| `--cursor`, `--claude`, `--codex`, `--all` | Which hosts to install for |
| `--project PATH` | Install into one repository. Point this at the memory repository. |
| `--copy` | Copy skills. The default is a symlink, so an edit to a canonical skill takes effect on the next run. |
| `--list` | Show what is installed and the exact paths, then exit |
| `--dry-run` | Print every action and take none |
| `--uninstall` | Remove exactly what a previous install created, tracked by a manifest |

Commands are written as files. Each file carries this bundle's resolved path, so `/obengineer-analyze` reads the prompt in this checkout. Host skill and command directories move between versions. `--list` prints the resolved paths:

```
$ ./install.sh --list --project /path/to/memory-repo
obengineer at /Users/you/src/obengineer
scope: project /path/to/memory-repo

  Cursor       installed
    skills   /path/to/memory-repo/.cursor/skills
    commands /path/to/memory-repo/.cursor/commands
  Claude Code  host present, not installed
    ...
```

The document renderer needs `python-docx`:

```bash
pip install python-docx      # or: make deps
```

Claude Code can take the whole bundle as a plugin. That install brings the hooks and the MCP declarations with the skills:

```bash
claude plugin marketplace add /path/to/obengineer
# then install the obengineer plugin
```

## Commands

Seven commands. Each one reads its prompt file in place under `prompts/`, so the run contract under review is the one that ran. Intake, analyze, and wiki run in that order. After you accept the analysis, implement and as-code can run in parallel: implement changes application repositories, and as-code configures the tenant. Review grades a deliverable. Render rebuilds the Word file.

| Command | Does | Produces |
|---|---|---|
| `/obengineer-intake` | Asks for the inputs a scan cannot measure, in one round | `docs/observability/engagement-inputs.yaml` |
| `/obengineer-analyze` | Deep-scans the front end, maps the backends from diagrams, reads existing telemetry through the `splunk-observability` and `splunk-platform` MCPs, raises the findings, and writes the full recommendation set | `analysis-<app>-<date>.md`, a customer `.docx`, `attribute-schema.json` |
| `/obengineer-wiki` | Turns the accepted analysis into the notes the agents retrieve by subject | `wiki/<Customer>/<app>/`, work orders, tracked versions |
| `/obengineer-implement` | Lands one contract slice with the CI check that keeps it enforced | A single-concern pull request |
| `/obengineer-as-code` | Generates Terraform for the contract at three persona levels | A `terraform/` tree and a plan |
| `/obengineer-review` | Grades a deliverable against the completeness bar before a human sees it | A pass, or numbered defects with lines |
| `/obengineer-render` | Re-renders a deliverable and proves the render matches its source | A verified `.docx` |

```
/obengineer-intake
/obengineer-analyze
/obengineer-wiki
/obengineer-implement workflow: checkout.payment.authorize
/obengineer-as-code
```

Name a skill directly when you want one piece of a run: `$baggage-propagation`, `$cardinality-budget`, `$customer-doc-render`.

Source and a live URL carry more weight than a narrative. A diagram carries more weight than a recollection. Existing dashboards and detectors are inventory. What you omit, the run records as an open item.

Intake writes `engagement-inputs.yaml` once. Later runs read that file, so the realm, the percentile standard, the diagram paths, and the entitlement numbers stay in one place.

## Where the files go

```
obengineer/                         # toolkit repository
<memory-repo>/                      # memory repository
    ├── .env.template               # copied from templates/memory-repo/
    ├── .env                        # local only; gitignored
    ├── docs/observability/         # the customer document and its .docx
    ├── wiki/<Customer>/<app>/      # the agent wiki
    ├── AGENTS.md · CLAUDE.md       # host pointers into that wiki
    └── terraform/                  # what observability-as-code emits
```

Paths in the skills — `docs/observability/…`, `wiki/<Customer>/<app>/…` — are relative to the memory repository.

## Environment file

`templates/memory-repo/` holds `.env.template` and a `.gitignore` for a new memory repository. Copy both into that repository, then:

```bash
cp .env.template .env
```

Fill `.env`. Do not commit it. The copied `.gitignore` ignores `.env` and does not ignore `.env.template`.

The analyze run reads those variables from `.env` or from the process environment. It uses the `splunk-observability` and `splunk-platform` MCP servers to inventory existing telemetry. The procedure is `skills/references/existing-telemetry.md`. That path is in this repository. It is not on every branch today. Install does not write `.env`.

## Inputs

One file, `engagement-inputs.yaml`, from
[`inputs/engagement-inputs.template.yaml`](inputs/engagement-inputs.template.yaml).
The intake writes it under `docs/observability/` in the memory repository. What each field decides:
[`skills/references/engagement-inputs.md`](skills/references/engagement-inputs.md).

**Entitlement prices the recommendation.** Given licensed and consumed custom metric time series (MTS), remaining Monitoring MetricSet slots, and the agreed per-tag ceiling, every proposed dimension has a computable cost. That cost, any overage, and the options go to the account team in `entitlement-exposure-<app>-<date>.md`. The recommendation stays what the application needs. A team that learns full checkout observability needs 40,000 more MTS can buy them, phase them, or promote fewer dimensions. Trimming to fit happens when `fit_to_entitlement` is set because they asked. When entitlement and a supplied traffic baseline are both absent, there is no exposure document and the run recommends as though licensing is sufficient. A supplied baseline is a list with values. An empty list leaves the range wide. A baseline with no entitlement is an expectation range.

**Business context fills the value section.** Current MTTD, MTTA, and MTTR, incidents a month, how many people join a bridge, what an engineering hour costs, what fraction of incidents customers report first, tooling spend, revenue per hour online, and a paragraph in the customer's own words. The paragraph is quoted. Every number may be `unknown`. Fill none of them with an industry benchmark. The analysis then reads the last twelve months of the public record — outage coverage, status history, complaints, field performance — and closes the document with **Business Value Realization**. Every figure is labelled `stated`, `measured`, `public`, or `derived`. See
[`skills/references/business-value.md`](skills/references/business-value.md) and
[`skills/references/entitlement-exposure.md`](skills/references/entitlement-exposure.md).

Composition, router, load order, competing agents, content security policy, and consent gating are evidence the scan records. Leave them out of the inputs file.

## What the runs write

Four runs, each with a prompt and an agent definition:

| Run | Prompt | Output |
|---|---|---|
| Analyze | [`prompts/01-analyze-application.md`](prompts/01-analyze-application.md) | The customer document — architecture observed, critical findings, the recommendation catalogue, and Business Value Realization — plus its `.docx`, `attribute-schema.json`, and, when entitlement or a supplied traffic baseline exists, the account team's entitlement exposure document |
| Wiki | [`prompts/02-build-instrumentation-wiki.md`](prompts/02-build-instrumentation-wiki.md) | `wiki/<Customer>/<app>/` in the memory repository: one note per business transaction, workflow, use case, finding, detector, and objective, plus work orders, the value workings, and tracked versions |
| Implement | [`prompts/03-implement-instrumentation.md`](prompts/03-implement-instrumentation.md) | Small reviewable pull requests, one contract slice each |
| Configure | [`prompts/04-generate-observability-as-code.md`](prompts/04-generate-observability-as-code.md) | A `terraform/` tree and a plan, in executive, SRE, and engineer modules |

The customer document has two renderings of one source. Markdown is the source of record. The Word file for architecture review is rendered from that Markdown. Critical findings are section 4, ordered by severity, with the files involved, the exposure, the remediation, and the verification. The body then carries business transactions, workflows, custom metrics, the business-transaction-to-workflow join, detectors with thresholds, indicators and objectives, and the composite use cases. It closes on Business Value Realization.

The wiki sits under that document: one note per subject at `wiki/<Customer>/<app>/`, with frontmatter and wikilinks that Obsidian and the Cursor, Claude, and Codex memory features can read. A later run reads those notes and reports the delta. See
[`skills/references/agent-wiki.md`](skills/references/agent-wiki.md),
[`skills/references/incremental-runs.md`](skills/references/incremental-runs.md), and
[`skills/references/ci-integration.md`](skills/references/ci-integration.md).

## Skills

| Skill | Purpose |
|---|---|
| `$engagement-intake` | Collect the inputs a scan cannot reach — artifacts, tenancy, entitlement, privacy regime, who deploys what, and the business context — into one file, asking only for what is missing |
| `$instrumentation-analyze` | Deep-scan the front end (script order, competing agents, where the agent initialises, router, content security policy, consent, status versus content), map backends and buses, inventory the existing Splunk and ThousandEyes footprint, enumerate business transactions from evidence, write the customer document in template order with findings at section 4, emit the three artifacts, read the last twelve months of the public record, and price the recommendation for the account team when entitlement or a supplied traffic baseline exists |
| `$instrumentation-wiki` | Turn the accepted analysis into one note per subject, with work orders, the value workings and their cited sources, tracked versions, and the host memory pointers |
| `$baggage-propagation` | The cross-cutting attribute set and the W3C Baggage contract: set once, propagate, stamp on every span with `SpanProcessor.onStart`, inside a byte and key-count budget |
| `$cardinality-budget` | Dimension versus attribute-only as arithmetic: MTS cost per promotion, Monitoring and Troubleshooting MetricSet sizing, the classifiers that replace raw URLs and topic names, and the priced overage the account team gets when the total exceeds the entitlement |
| `$customer-doc-render` | Render Markdown to a customer-review `.docx` — title page, table of contents, one section per page, clickable section and appendix references, `Confidential` footer — then prove the render matches its source |
| `$instrumentation-implement` | Land the contract as ordered pull requests, with the CI checks that keep it enforced |
| `$observability-as-code` | Emit the contract as Terraform across the three Splunk providers — executive, SRE, and engineer modules — importing what the tenant already has and refusing a grouping the schema cannot support |
| `$deliverable-review` | Grade a finished deliverable against the completeness bar, separately from whoever wrote it, and report defects by rubric row with line numbers |

## Working on this repository

```bash
make test                # contract tests over the toolkit and the renderer round-trip
make check               # plugin copies match canonical skills; manifest versions agree
make sync-plugin-skills  # refresh plugin copies and host links from canonical skills
```

`make test` and `make check` run on every pull request, with an install and uninstall round-trip into a scratch project. See `.github/workflows/ci.yml`.

`skills/` is the single source. The plugin carries copies so an installed bundle is self-contained. Refresh them with `make sync-plugin-skills`. See [`AGENTS.md`](AGENTS.md) for the review rules, [`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow, [`docs/design.md`](docs/design.md) for why the layout is shaped this way, and [`docs/reviews/`](docs/reviews/) for the standing architecture reviews.

Each fact has one home. The section list lives in `skills/references/document-template.md`. The platform decision rules live in `portfolio-decision-engine.md`. The `.docx` layout lives in `document-format.json`. Agent files route to those files and stay under 2,500 words. The tests fail when an agent file restates a reference.

## References

Each of these is enough to reproduce its part of a deliverable in a fresh session:

- [`skills/references/document-template.md`](skills/references/document-template.md) — the customer document: section order, every table's columns, the title page, and the pre-delivery checklist.
- [`skills/references/cross-cutting-attributes.md`](skills/references/cross-cutting-attributes.md) — the baggage section, with the attribute-set table and all five code subsections.
- [`skills/references/baggage-budget.md`](skills/references/baggage-budget.md) — which keys earn a place in the header, the five tests each must pass, and where the others go.

Two more govern money, and they stay separate. [`business-value.md`](skills/references/business-value.md) is the value the customer reads. [`entitlement-exposure.md`](skills/references/entitlement-exposure.md) is the cost the account team reads.

## MCP servers

`plugins/obengineer/.mcp.json` ships with an empty `mcpServers` object. Copy an entry from `.mcp.optional.json` and supply your own command. Splunk Observability Cloud (`splunk-observability`) and Splunk Enterprise (`splunk-platform`) are mandatory. The analyze run uses both, with the variables in the memory repository `.env`, when it inventories existing telemetry. ThousandEyes, a local OpenTelemetry tools server, and a cloud inventory server for the cloud the site runs on are recommended. A Jira server is used when the host already has one connected. The classification lives in [`skills/references/mcp-servers.md`](skills/references/mcp-servers.md).

Keep token values out of both files. Use `${VAR}` references. Both files are committed. The design runs against any site. Put the current site's endpoint in the copied entry.

## Rebuild deliverables from the toolkit checkout

The `/obengineer-*` commands write the document and the wiki into the memory repository. These `make` targets rebuild or check those artifacts from this checkout, where the renderer and the wiki verifier live. `ENGAGEMENT` is the path to the memory repository. Substitute the real analysis filename and wiki directory. `<app>`, `<date>`, and `<Customer>` are placeholders.

```bash
export ENGAGEMENT=/path/to/memory-repo
make render FILE=docs/observability/analysis-<app>-<date>.md
make verify-wiki WIKI="wiki/<Customer>/<app>"
```

`make render` rebuilds the customer `.docx` from the Markdown analysis and proves the Word file matches its source. `make verify-wiki` checks that wikilinks resolve, frontmatter is complete, index counts match the tree, host pointers exist, and no credential-shaped values are present. An absolute path is used as given. With `ENGAGEMENT` unset, a relative path is resolved from the current directory.

## License

This repository is licensed under the [MIT License](LICENSE).
