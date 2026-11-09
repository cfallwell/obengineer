# obengineer

obengineer is a toolkit for a Splunk OpenTelemetry instrumentation contract. It installs skills and commands for Cursor, Claude Code, and Codex. Give it application source, diagrams, a live URL, existing telemetry, and the inputs a scan cannot measure. It writes one document a coding agent can implement. That document names the attributes a dashboard variable, a detector grouping, and a Related Content link all need, and it is the contract for shortening MTTx (mean time to detect, acknowledge, and resolve).

Canonical skills live under `skills/`. `plugins/obengineer/` is the bundle a marketplace install gets. This repository stays the toolkit. The wiki and the deliverables are written in a repository you choose. [`skills/references/ci-integration.md`](skills/references/ci-integration.md) allows three placements: the application repository, so checks and notes stay in one checkout; a separate memory repository, so several application repositories can share it; or a submodule. Record the choice in `meta/decisions.md`. Do not keep a second copy. The steps below use a separate memory repository.

## Get the toolkit, then create the memory repository

Do these two steps in this order.

1. Get a checkout of this repository.

   First time:

   ```bash
   git clone https://github.com/cfallwell/obengineer.git
   cd obengineer
   ```

   A checkout you already have:

   ```bash
   cd /path/to/obengineer
   git pull
   ```

2. Create the memory repository, then install into it.

   `--project` does not create a Git repository. It installs skills and commands into a directory that already exists. `git init` that directory, or clone a memory repository that already exists, before you install.

   New repository:

   ```bash
   mkdir -p /path/to/memory-repo
   cd /path/to/memory-repo
   git init
   git commit --allow-empty -m "Initial commit"
   ```

   Existing repository:

   ```bash
   git clone <memory-repo-url> /path/to/memory-repo
   ```

   From the toolkit checkout, install into that repository. The flag writes skills and commands there. Cursor and Claude Code use `.cursor/` and `.claude/` inside it. Codex uses `.agents/` for skills and `prompts/` for commands.

   ```bash
   cd /path/to/obengineer
   ./install.sh --cursor --project /path/to/memory-repo
   ```

   Pass `--claude`, `--codex`, or `--all` in place of `--cursor` when those hosts should receive the same install. Restart the host so it loads the new skills and commands. Open the memory repository in the host and run the commands there. They write `docs/observability/`, the wiki, and `terraform/apps/<app>/` into that repository.

   When your checkout contains `templates/memory-repo/`, copy its `.gitignore` and `.env.template` into the memory repository. Then copy `.env.template` to `.env` and fill it. `.env` is gitignored. That directory is not on this branch. It is added on `memory-repo-env-template`.

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
| `--project PATH` | Install into one repository. Point this at the memory repository, the application repository, or the submodule checkout you chose above. |
| `--copy` | Copy skills. The default is a symlink, so an edit to a canonical skill takes effect on the next run. |
| `--list` | Show what is installed and the exact paths, then exit |
| `--dry-run` | Print every action and take none |
| `--uninstall` | Remove exactly what a previous install created, tracked by a manifest |

Commands are files under `commands/`. Each file carries this bundle's resolved path, so `/ob-analyze` reads the prompt in this checkout. Host skill and command directories move between versions. `--list` prints the resolved paths:

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

Seven commands are installed from `commands/`. In Cursor, Claude Code, and Codex, type `/ob`. The host lists the seven names below. Each command tells the agent to read one file under `prompts/` in this checkout. The file the agent runs is the file in the checkout, so a review of that file is a review of the run.

Run them from the repository you installed into. Intake, analyze, and wiki run in that order. Wiki waits until a person has accepted the analysis. After that, implement and build-terraform can run at the same time: implement changes application repositories, and build-terraform writes configuration for the tenant. Review grades a deliverable and does not rewrite it. Render rebuilds the Word file from the Markdown.

You can also name a skill when you want one piece of a run: `$baggage-propagation`, `$cardinality-budget`, `$customer-doc-render`.

Bring source and a live URL when you have them. A diagram is more reliable than a description from memory. Existing dashboards and detectors are inventory of what the tenant already has. Anything you leave out is recorded as an open item.

Intake writes `docs/observability/engagement-inputs.yaml` once. Later runs read that file, so the realm, the percentile standard, the diagram paths, and the entitlement numbers stay in one place.

### `/ob-intake`

Run this first, in the memory repository (or the other placement you chose).

It asks, in one numbered message, for what a scan cannot measure: diagram and URL paths, Splunk realm and tenancy, entitlement, privacy constraints, and the business context (current MTTD, MTTA, MTTR, incident volume, and a paragraph in your own words). `unknown` is a valid answer. Do not invent an industry number to fill a blank. Do not put a token or a password in the file. A reference to a secret is enough for the scan to reach an authenticated page, and that secret is rotated when the analysis is finished.

It writes `docs/observability/engagement-inputs.yaml` from [`inputs/engagement-inputs.template.yaml`](inputs/engagement-inputs.template.yaml). What each field decides is [`skills/references/engagement-inputs.md`](skills/references/engagement-inputs.md).

Have the diagrams and the production URL ready before you start. Test and QA environments are not the scan. Optional traffic numbers tighten the consumption range. Leave a number `unknown` when you do not have it.

### `/ob-analyze`

Run this after intake. The inputs file must already exist.

The run reads the front end (script order, other RUM agents, where the agent starts, the router, content security policy, consent), maps backends and buses from the diagrams, and writes the recommendation catalogue. It does not change application source. Critical findings are section 4. The cross-cutting attribute section is required.

It writes three files under `docs/observability/`:

- `analysis-<app>-<date>.md`
- a `.docx` rendered from that Markdown
- `attribute-schema.json`

When entitlement or a supplied traffic baseline is present, it also writes `entitlement-exposure-<app>-<date>.md` for the account team. That file is Markdown only.

Inventory of telemetry the tenant already collects is specified in `skills/references/existing-telemetry.md`, using `.env` and the `splunk-observability` and `splunk-platform` MCP servers. That file is not on this branch. It is added with the env template on `memory-repo-env-template`.

### `/ob-wiki`

Run this after a person has accepted the analysis. If the analysis is not accepted, the command stops.

It writes one note per business transaction, workflow, use case, finding, detector, and objective under `wiki/<Customer>/<app>/`, plus work orders and tracked versions. It does not write a second customer document. Hosts get a short pointer at the index note (`.cursor/rules/obengineer-wiki.mdc`, `CLAUDE.md`, `AGENTS.md`), not a copy of the wiki.

A later analyze run reads those notes and reports what changed. See [`skills/references/agent-wiki.md`](skills/references/agent-wiki.md).

### `/ob-implement`

Run this after the analysis is accepted. Name one slice. Example:

```
/ob-implement workflow: checkout.payment.authorize
```

It opens one pull request in the application repository for that slice, with the CI check that keeps the contract enforced. It stops at the slice boundary. It does not add attributes that are not in `attribute-schema.json`.

Work through the phase plan in the analysis: trust the signal first, then the highest-ranked journey. One concern per pull request.

### `/ob-build-terraform`

Run this after the analysis is accepted. It can run while implement is in progress. It configures the contract. It does not invent one, and it does not run `terraform apply`.

It writes `terraform/apps/<app>/`: persona modules (executive, SRE, engineer, and platform when the contract needs it) and one workspace per environment under `environments/`. A later apply is run from `terraform/apps/<app>/environments/<env>`, so another application's directory is not in that plan. The directory shape is Step 3 of [`skills/observability-as-code/SKILL.md`](skills/observability-as-code/SKILL.md).

The command produces `terraform fmt`, `validate`, and `plan` output, plus a handover. Detectors are generated disabled. Tokens stay in variables, not in `.tf` files. Objects the tenant already has are imported. A grouping the schema marks attribute-only is refused.

### `/ob-review`

Run this on a finished analysis, or on any other deliverable, before a person reads it for acceptance.

It grades the file against the section list and the pre-delivery checklist in [`skills/references/document-template.md`](skills/references/document-template.md). It reports each defect with the rubric row, the file, and the line. It does not rewrite the document. Grading and authoring stay separate.

### `/ob-render`

Run this when the Markdown analysis changed and the Word file must be rebuilt.

It renders the `.docx` from the Markdown and runs `verify_render.py`. The Word file is a build artifact. Do not edit it by hand. The default source is the analysis document under `docs/observability/`. Pass another Markdown path when you need one.

## Where the files go

```
obengineer/                         # toolkit repository
<memory-repo>/                      # chosen repository (memory repo, application repo, or submodule)
    ├── .env.template               # copied from templates/memory-repo/ when that directory exists
    ├── .env                        # local only; gitignored
    ├── docs/observability/         # the customer document and its .docx
    ├── wiki/<Customer>/<app>/      # the agent wiki
    ├── AGENTS.md · CLAUDE.md       # host pointers into that wiki
    └── terraform/apps/<app>/       # one Terraform directory per application
```

Paths in the skills — `docs/observability/…`, `wiki/<Customer>/<app>/…` — are relative to that repository. The wiki path on this branch is `wiki/<Customer>/<app>/`.

## Environment file

`templates/memory-repo/` holds `.env.template` and a `.gitignore` for a new memory repository. That directory is not on this branch. Copy both into the memory repository when your checkout has them, then:

```bash
cp .env.template .env
```

Fill `.env`. Do not commit it. The copied `.gitignore` ignores `.env` and does not ignore `.env.template`.

The analyze run reads those variables from `.env` or from the process environment. Install does not write `.env`.

## Inputs

One file, `engagement-inputs.yaml`, from
[`inputs/engagement-inputs.template.yaml`](inputs/engagement-inputs.template.yaml).
The intake writes it under `docs/observability/` in the repository you installed into. What each field decides:
[`skills/references/engagement-inputs.md`](skills/references/engagement-inputs.md).

**Entitlement prices the recommendation.** Given licensed and consumed custom metric time series (MTS), remaining Monitoring MetricSet slots, and the agreed per-tag ceiling, every proposed dimension has a computable cost. That cost, any overage, and the options go to the account team in `entitlement-exposure-<app>-<date>.md`. The recommendation stays what the application needs. This phase ensures computed changes to instrumentation can be evaluated with your Splunk account team. The account team can buy more capacity, phase the work, or promote fewer dimensions. The recommendation is trimmed to the current license only when `fit_to_entitlement` is set, because that was requested.

When entitlement is unknown and every traffic baseline factor is unsupplied, there is no exposure document. The run recommends as though licensing is sufficient. A factor is supplied when its value is neither `unknown` nor an empty collection (`[]` or `{}`). A scalar such as `traffic_baseline.rum.sessions_per_day_avg` or `traffic_baseline.apm.requests_per_minute_avg` counts. `infra_integrations: []` does not. A supplied baseline with no entitlement still produces the exposure document. That document is an expectation range, with no claim that a license was exceeded.

**Business context fills the value section.** Current MTTD, MTTA, and MTTR, incidents a month, how many people join a bridge, what an engineering hour costs, what fraction of incidents customers report first, tooling spend, revenue per hour online, and a paragraph in the customer's own words. The paragraph is quoted. Every number may be `unknown`. Fill none of them with an industry benchmark. The analysis then reads the last twelve months of the public record — outage coverage, status history, complaints, field performance — and closes the document with **Business Value Realization**. Every figure is labelled `stated`, `measured`, `public`, or `derived`. See
[`skills/references/business-value.md`](skills/references/business-value.md) and
[`skills/references/entitlement-exposure.md`](skills/references/entitlement-exposure.md).

Composition, router, load order, competing agents, content security policy, and consent gating are evidence the scan records. Leave them out of the inputs file.

## What the runs write

Four runs, each with a prompt and an agent definition:

| Run | Prompt | Command | Output |
|---|---|---|---|
| Analyze | [`prompts/01-analyze-application.md`](prompts/01-analyze-application.md) | `/ob-analyze` | The customer document — architecture observed, critical findings, the recommendation catalogue, and Business Value Realization — plus its `.docx`, `attribute-schema.json`, and, when entitlement or a supplied traffic baseline exists, the account team's entitlement exposure document |
| Wiki | [`prompts/02-build-instrumentation-wiki.md`](prompts/02-build-instrumentation-wiki.md) | `/ob-wiki` | `wiki/<Customer>/<app>/`: one note per business transaction, workflow, use case, finding, detector, and objective, plus work orders, the value workings, and tracked versions |
| Implement | [`prompts/03-implement-instrumentation.md`](prompts/03-implement-instrumentation.md) | `/ob-implement` | Small reviewable pull requests, one contract slice each |
| Configure | [`prompts/04-generate-observability-as-code.md`](prompts/04-generate-observability-as-code.md) | `/ob-build-terraform` | `terraform/apps/<app>/` and a plan, in executive, SRE, and engineer modules. No `apply`. |

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
| `$observability-as-code` | Emit the contract as Terraform across the three Splunk providers, one directory per application, in executive, SRE, and engineer modules. Import what the tenant already has. Refuse a grouping the schema cannot support |
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

`plugins/obengineer/.mcp.json` ships with an empty `mcpServers` object. Copy an entry from `.mcp.optional.json` and supply your own command. Splunk Observability Cloud (`splunk-observability`) and Splunk Enterprise (`splunk-platform`) are mandatory. ThousandEyes, a local OpenTelemetry tools server, and a cloud inventory server for the cloud the site runs on are recommended. A Jira server is used when the host already has one connected. The classification lives in [`skills/references/mcp-servers.md`](skills/references/mcp-servers.md).

Keep token values out of both files. Use `${VAR}` references. Both files are committed. The design runs against any site. Put the current site's endpoint in the copied entry.

## Rebuild deliverables from the toolkit checkout

The `/ob-*` commands write the document and the wiki into the repository you installed into. These `make` targets rebuild or check those artifacts from this checkout, where the renderer and the wiki verifier live. `ENGAGEMENT` is the path to that repository. Substitute the real analysis filename and wiki directory. `<app>`, `<date>`, and `<Customer>` are placeholders.

```bash
export ENGAGEMENT=/path/to/memory-repo
make render FILE=docs/observability/analysis-<app>-<date>.md
make verify-wiki WIKI="wiki/<Customer>/<app>"
```

`make render` rebuilds the customer `.docx` from the Markdown analysis and proves the Word file matches its source. `make verify-wiki` checks that wikilinks resolve, frontmatter is complete, index counts match the tree, host pointers exist, and no credential-shaped values are present. An absolute path is used as given. With `ENGAGEMENT` unset, a relative path is resolved from the current directory.

## License

This repository is licensed under the [MIT License](LICENSE).
