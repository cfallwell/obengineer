# obengineer

Agents, skills, and plugins that turn an application into an **instrumentation
contract** — one a team can implement, CI can enforce, and a TAM can configure in
Splunk Observability Cloud.

Canonical skills under `skills/`, a self-contained bundle under `plugins/obengineer/`,
installable commands under `commands/`, host wiring for Cursor, Codex, and Claude Code,
and deterministic tests over the agentry itself.

## Install

```bash
git clone <this repo> && cd obengineer

./install.sh --cursor            # this user, Cursor
./install.sh --claude --codex    # this user, two hosts
./install.sh --all               # every supported host
```

Then restart your agent host so it picks up the new skills and commands.

| Flag | Effect |
|---|---|
| `--cursor`, `--claude`, `--codex`, `--all` | Which hosts to install for |
| `--project PATH` | Scope to one repository (`.cursor/`, `.claude/`, `.agents/` inside it) instead of this user |
| `--copy` | Copy skills instead of symlinking, for a host that cannot follow links |
| `--list` | Show what is installed and the exact paths, then exit |
| `--dry-run` | Print every action without taking it |
| `--uninstall` | Remove exactly what a previous install created, tracked by a manifest |

Skills are symlinked by default, so editing a canonical skill takes effect without
reinstalling. Commands are written as files because each one carries this bundle's
resolved path.

Host skill and command directories are conventions rather than standards and they move
between versions. `--list` prints the resolved paths so a wrong guess is a visible
inconvenience rather than a silent no-op:

```
$ ./install.sh --list
obengineer at /Users/you/src/obengineer
scope: user /Users/you

  Cursor       installed
    skills   /Users/you/.cursor/skills
    commands /Users/you/.cursor/commands
  Claude Code  host present, not installed
    ...
```

The only runtime dependency is the document renderer's:

```bash
pip install python-docx      # or: make deps
```

Claude Code can also take the whole bundle as a plugin, which brings the hooks and the
MCP declarations along with the skills:

```bash
claude plugin marketplace add /path/to/obengineer
# then install the obengineer plugin
```

## Invoke

Seven commands; the first five run in order. They read the prompt files in place, so the run
contract has exactly one copy and it is the copy under review — nothing is pasted into a chat.

| Command | Does | Produces |
|---|---|---|
| `/obengineer-intake` | Asks for the inputs no scan can measure, in one round | `engagement-inputs.yaml` |
| `/obengineer-analyze` | Deep-scans the front end, maps the backends from diagrams, raises the findings, and writes the full recommendation set | `analysis-<app>-<date>.md`, a customer `.docx`, `attribute-schema.json` |
| `/obengineer-wiki` | Turns the accepted analysis into the notes the agents retrieve by subject | `wiki/<Customer>/<app>/`, work orders, tracked versions |
| `/obengineer-implement` | Lands one contract slice with the CI check that keeps it enforced | A single-concern PR |
| `/obengineer-as-code` | Generates Terraform for the contract at three persona levels | A `terraform/` tree and a plan |
| `/obengineer-review` | Grades a deliverable against the completeness bar before a human sees it | A pass, or numbered defects with lines |
| `/obengineer-render` | Re-renders any deliverable and proves the render matches its source | A verified `.docx` |

```
/obengineer-intake
/obengineer-analyze
/obengineer-wiki
/obengineer-implement workflow: checkout.payment.authorize
/obengineer-as-code
```

`/obengineer-implement` and `/obengineer-as-code` are independent — instrumentation lands in
application repos, configuration lands in a tenant — so they can run in parallel once the
analysis is accepted.

Or name a skill directly when you want one piece rather than a whole run:
`$baggage-propagation`, `$cardinality-budget`, `$customer-doc-render`.

Nothing needs to be attached twice. The intake writes `engagement-inputs.yaml`, and
every later run reads it — so the realm, the percentile standard, the diagram paths, and
the entitlement numbers are given once and cannot drift between runs.

## Inputs

One file, `engagement-inputs.yaml`, from
[`inputs/engagement-inputs.template.yaml`](inputs/engagement-inputs.template.yaml).
Filled once, visible, diffable, and reviewable. What each field decides:
[`skills/references/engagement-inputs.md`](skills/references/engagement-inputs.md).

The section worth filling carefully is **entitlement**. Cardinality is a budget rather
than a preference: given licensed and consumed custom MTS, remaining Monitoring
MetricSet slots, and the agreed per-tag ceiling, a proposed dimension has a cost that
either fits or does not. Given nothing, the guide can only advise, and advice loses
every argument with a team that wants to group a chart by order identifier.

Everything a scan can measure is *not* an input. Composition, router, load order,
competing agents, CSP, and consent gating are evidence, and asking about them converts
evidence into opinion.

## What this produces

Four runs, each with a run contract and an agent definition:

| Run | Prompt | Output |
|---|---|---|
| Analyze | [`prompts/01-analyze-application.md`](prompts/01-analyze-application.md) | **The customer document** — architecture observed, critical findings, and the full recommendation set — plus its `.docx` and `attribute-schema.json` |
| Wiki | [`prompts/02-build-instrumentation-wiki.md`](prompts/02-build-instrumentation-wiki.md) | `wiki/<Customer>/<app>/` — one note per BT, workflow, use case, finding, detector, and objective, plus work orders and tracked versions |
| Implement | [`prompts/03-implement-instrumentation.md`](prompts/03-implement-instrumentation.md) | Small reviewable PRs, one contract slice each |
| Configure | [`prompts/04-generate-observability-as-code.md`](prompts/04-generate-observability-as-code.md) | A `terraform/` tree and a plan — executive, SRE, and engineer modules |

**One customer document, two renderings.** Markdown as the source of record, and a Word
document for architecture review rendered from that same Markdown so the two cannot disagree.
There is no separate "instrumentation recommendations" deliverable: it duplicated the
analysis, no customer read it, and no agent could load it without spending its whole context
on material irrelevant to the task in hand.

The document leads with what a reader needs in the first six pages — the observed
architecture, then **critical findings** ordered by severity with remediation, files, and
exposure — and closes with the catalogue the build works from: business transactions,
workflows, custom metrics, the BT-to-workflow join, detectors with thresholds, indicators and
objectives in the customer's voice, then the composite use cases.

The lower layer is a **wiki**, one note per subject under `wiki/<Customer>/<app>/`, with
frontmatter and wikilinks that Obsidian and the Cursor, Claude, and Codex memory features can
read. It is what makes a periodic run a delta rather than a rewrite, and what makes a CI
pipeline possible at all. See
[`skills/references/agent-wiki.md`](skills/references/agent-wiki.md),
[`skills/references/incremental-runs.md`](skills/references/incremental-runs.md), and
[`skills/references/ci-integration.md`](skills/references/ci-integration.md).

## Skills

| Skill | Purpose |
|---|---|
| `$engagement-intake` | Collect and validate the inputs no scan can reach — artifacts, tenancy, entitlement, privacy regime, who deploys what — into one file, asking only for what is missing |
| `$instrumentation-analyze` | Deep-scan the front end (script order, competing agents, where the agent initialises, router, CSP, consent, status-versus-content), map backends and buses, inventory the existing portfolio footprint, enumerate business transactions from evidence — then write the customer document in canonical template order, findings at section 4 and the catalogue closing the body, and emit all three artifacts |
| `$instrumentation-wiki` | Turn the accepted analysis into one note per subject, with work orders, tracked versions, and the host memory pointers |
| `$baggage-propagation` | The cross-cutting attribute set and W3C Baggage contract: set once, propagate, stamp on every span via `SpanProcessor.onStart` — and the byte budget that decides which keys earn a place in the header |
| `$cardinality-budget` | Dimension versus attribute-only as arithmetic against entitlement: MTS cost per promotion, MMS and TMS sizing, and the classifiers that replace raw URLs and topic names |
| `$customer-doc-render` | Render Markdown to a customer-review `.docx` — simple title page, Table of Contents, one section per page, `Confidential` footer — then prove the render matches its source |
| `$instrumentation-implement` | Land the contract as ordered PRs, with the CI checks that keep it enforced |
| `$observability-as-code` | Emit the contract as Terraform across the three Splunk providers — executive, SRE, and engineer modules — importing what the tenant already has and refusing any grouping the schema cannot support |
| `$deliverable-review` | Grade a finished deliverable against the completeness bar, separately from whoever wrote it, and report defects by rubric row with line numbers |

## Working on this repo

```bash
make test                # contract tests over the agentry and the renderer round-trip
make check               # packaging consistency: plugin mirror, manifest versions
make sync-plugin-skills  # refresh plugin copies and host links from canonical skills
make render FILE=../docs/observability/analysis-<app>-<date>.md
```

`skills/` is the single source. The plugin carries copies so an installed bundle is
self-contained; refresh them with `make sync-plugin-skills` and never edit them
directly. See [`AGENTS.md`](AGENTS.md) for the review rules,
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow,
[`docs/design.md`](docs/design.md) for why the layout is shaped this way, and
[`docs/reviews/`](docs/reviews/) for the standing architecture reviews — including what
is deliberately not built yet and why.

One rule underpins the rest: **one authority per fact.** The section list lives only in
`skills/references/document-template.md`, the platform decision rules only in
`portfolio-decision-engine.md`, the layout only in `document-format.json`. Agent files
route to them and never restate them, capped at 2,500 words and tested. A second copy
drifts, and then two files both claim to say what a deliverable contains.

## Three references do the heavy lifting

Self-contained, so each is reproducible in a fresh session with no prior customer
document to copy from:

- **[`skills/references/document-template.md`](skills/references/document-template.md)** — the canonical customer document: section order, every table's columns, the title page, and the pre-delivery checklist.
- **[`skills/references/cross-cutting-attributes.md`](skills/references/cross-cutting-attributes.md)** — the mandatory baggage section, with the attribute-set table and all five code subsections.
- **[`skills/references/baggage-budget.md`](skills/references/baggage-budget.md)** — which keys are worth carrying, the five tests each must pass, and where the rejected ones go instead.

## MCP servers

`plugins/obengineer/.mcp.json` declares **no servers by default**, and every skill works
without any. Each server they can use needs an endpoint, command, or token only your
organisation can supply, and a server that fails to start is worse than one that was
never declared.

`.mcp.optional.json` describes the four that pair with these skills — a local
OpenTelemetry audit-and-verify server, Splunk Observability Cloud, the Splunk platform,
and ThousandEyes — with what each is for and the environment variables it needs. Copy an
entry into `.mcp.json` to enable it. **Never** put a token value in either file;
`${VAR}` references only, since both are committed.
