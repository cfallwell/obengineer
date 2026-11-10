# MCP servers — which ones a run requires

Authoring reference for [`engagement-intake`](../engagement-intake/SKILL.md),
[`instrumentation-analyze`](../instrumentation-analyze/SKILL.md), and the plugin
files `plugins/obengineer/.mcp.json` and `.mcp.optional.json`.

The design runs against **any site**. These servers read the observability
tenant and, when a cloud inventory server is already connected, the environment
that site runs in. They do not select a customer, and a server configured for
a previously scanned site is not evidence for this one.

## Why `.mcp.json` ships with an empty `mcpServers` object

Every server needs a command or URL that only the operator's organisation can
supply. A placeholder command fails at session start, and a plugin that fails
at session start gets uninstalled. Tokens are `${VAR}` references. No command
is guessed.

Mandatory means the operator copies that entry from `.mcp.optional.json` into
`.mcp.json` and supplies their own command before a run treats tenant facts as
measured. It does not mean this repository hardcodes an endpoint.

## Mandatory

Both are required. A run that cannot see them still proceeds on the site scan
and on what the human typed, and it labels those tenant rows `stated`.

| Server key | Product | What a run reads through it |
|---|---|---|
| `splunk-observability` | Splunk Observability Cloud | MetricSets, APM workflows, Tag Spotlight cardinality, RUM and Synthetics configuration, Subscription Usage |
| `splunk-platform` | Splunk Enterprise | Indexes, sourcetypes, `trace_id` extraction, the SPL behind a Log Observer Connect panel, ITSI services when that app is present |

Copy both entries. Enabling one of them is not enough: Observability Cloud does
not see Enterprise indexes, and Enterprise does not see RUM sessions.

## Recommended

Enable when the engagement has the matching surface. Absence is an open item,
not a startup failure.

| Server | When it earns its place |
|---|---|
| `local-otel-tools` | The team runs a local server that reads a Collector config or SDK setup and reports what it would emit |
| `thousandeyes` | The evidence shows an off-box hop: CDN, DNS, SaaS, or a path APM cannot see |
| A cloud inventory MCP for the cloud this site actually runs on | Diagram generation for production. Test and QA inventories vary from production and are not the diagram. Any vendor. The run uses a server that is already connected; it does not install one and it does not assume a provider |

## If present

Use a server only when the developer environment already has it connected.
Do not add a `jira`, `github`, or `gitlab` entry to `.mcp.json` from this
repository, and do not guess a command.

### Developer tools already in the environment

Intake asks the human which tools they use. Examples of shape: Jira, GitHub,
GitLab, Artifactory. Match that list to MCP servers already connected and to
environment variable names already present. Record each match as
`{tool: "<named tool>", via: "mcp" | "env", key: "<server or variable name>"}` in
`developer_tools.matched`. Do not read the value, do not write it into
`engagement-inputs.yaml`, and do not ask the human to paste it. A credential
stays in the user environment or in the MCP server that already holds it.

A named tool with no match is not installed by the run.

### Jira

Jira is enabled only when the human named Jira under `developer_tools.named`
**and** `developer_tools.matched` contains
`{tool: "jira", via: "mcp", key: "<connected server key>"}`. At intake, only
then read issue keys that match `outcomes.known_pain`. Connected-but-unnamed
Jira and named-but-unavailable Jira are not used. Do not ask for a token.

After the human accepts the contract, engineering has the **option** of
generating backlog issues, and only when Jira is enabled by the predicate above.
Create at most one linked issue per mapped project, and only when engineering asks.
The run does not create issues on its own. The work-order file stays the
instruction. The issue, when created, names the work-order path, the
authorized `initial_scope`, and the acceptance evidence. It is created in
the backlog. Creating it does not start coding.

**Moving that issue into a sprint is the trigger.** The engineering agent
then queues that work order with the developer. It does not push to the
default branch. It works on the branch the developer already has, or on the
pull-request branch CI is checking. One issue per mapped project is the maximum;
a ticket per file is not a queue.

Without enabled Jira, the app-level work-order file is the queue. It carries
copy/paste-ready issue text for whatever engineering tool the team uses. Do not
attempt Jira, invent a project key, or treat Jira as the default.

For a unified multi-repository work order, create at most one requested issue per
mapped Jira project. Link sibling issues and repository pull requests to the work-order
id. The wiki work order remains authoritative.

### Repository hosts

GitHub, GitLab, and any other repository MCP already connected are how a run
learns which projects and codebases the developer can see. At intake, matching
them to `developer_tools` is the whole use. Choosing what to instrument is not
an intake question.

After the contract exists, engineering authorizes `initial_scope`: the full
scope, a subset of repositories, or a subset of a repository by parent folder.
A connected host may list candidates. The run does not adopt every repository
the server can reach, and it does not write instrumentation code until
`initial_scope.authorized` is `full`, `repositories`, or `parent_folders`.

CI checks out the pull-request branch with the forge's own credentials. It
does not shell out to a guessed host command. A path outside the authorized
scope stays out until engineering adds it.

## Existing telemetry

The analyze inventory of logs, spans, traces, MetricSets, MTS, and `sf.org` usage is
[`existing-telemetry.md`](existing-telemetry.md). The analyze run uses the
`splunk-observability` and `splunk-platform` MCP servers and the Splunk API endpoints
(Observability and Enterprise). Server keys stay the ones in the
tables above. The environment variable names are in that procedure and in
`plugins/obengineer/.mcp.optional.json`. This file does not repeat the queries.

## Verification access

`/ob-verify` uses only list/get/search/query tools required by accepted criteria. It may
read Observability Cloud, approved Enterprise indexes, ThousandEyes tests/results,
repository checks, and Terraform plan/state evidence supplied by the human.

It must refuse create/update/delete, detector enable/disable, Terraform apply, deploy,
credential rotation, issue publication before preview, and repository merge. Outcome issue
publication is a separate sanitized GitHub write governed by `outcome-issues.md`, not a
tenant permission.

## Simple setup

The developer environment is the configuration. Connected MCP servers are the
inventory. Each product can independently produce measured facts; both are required only
for conclusions joining Observability and Enterprise. Everything else is used when it
is already there. At intake the human names the developer tools they use.
Instrumentation scope is authorized later, by engineering, against the
accepted contract.
