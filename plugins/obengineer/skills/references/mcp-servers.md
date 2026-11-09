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

**Jira.** At the start of intake and analyze, look at the MCP servers already
connected in the session. If one is a Jira server, read issue keys that match
`outcomes.known_pain` and record the keys. If none is connected, do not declare
a Jira server, do not guess a command, and do not ask the human to paste a
token. Say that a Jira MCP, when the organisation already runs one, would
supply those keys.

Do not add a `jira` entry to `.mcp.json` from this repository. A guessed
command is worse than a missing server.
