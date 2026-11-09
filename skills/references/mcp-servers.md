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
| A cloud inventory MCP for the cloud this site actually runs on | Diagram generation for QA, pre-production, or production. Any vendor. The run uses a server that is already connected; it does not install one and it does not assume a provider |

## If present

Use a server only when the developer environment already has it connected.
Do not add a `jira`, `github`, or `gitlab` entry to `.mcp.json` from this
repository, and do not guess a command.

### Jira

At intake, if a Jira server is already connected, read issue keys that match
`outcomes.known_pain` and record the keys. If none is connected, say that a
Jira MCP would supply those keys, and stop. Do not ask for a token.

After the human accepts the contract, each accepted work order becomes **one
Jira issue**. The work-order file stays the instruction. The issue is the
queue. The issue names the work-order path, the developer's initial scope
(repositories, services, and the QA or test environment), and the acceptance
evidence. It is created in the backlog. Creating it does not start coding.

**Moving that issue into a sprint is the trigger.** The engineering agent
then queues that work order with the developer. It does not push to the
default branch. It works on the branch the developer already has, or on the
pull-request branch CI is checking. One issue per work order. A ticket per
file is not a queue.

Without a Jira server, the work-order file is the queue. Do not invent a
project key.

### Repository hosts

GitHub, GitLab, and any other repository MCP already connected are how a run
learns which projects and codebases the developer can see. List them. The
developer chooses `initial_scope`. The run does not adopt every repository
the server can reach.

CI checks out the pull-request branch with the forge's own credentials. It
does not shell out to a guessed host command. A codebase outside
`initial_scope` stays out of scope until the developer adds it.

## Simple setup

The developer environment is the configuration. Connected MCP servers are the
inventory. Splunk Observability Cloud and Splunk Enterprise remain mandatory
for a tenant fact to be labelled `measured`. Everything else is used when it
is already there. The only new thing the developer must name is the initial
scope: which repositories and services to start with, and the QA or test
environment those slices are proven in.
