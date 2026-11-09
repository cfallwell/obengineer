# Existing telemetry

The analyze pass that reads telemetry already in the tenant. The analyze run uses the `splunk-observability` and `splunk-platform` MCP servers and the Splunk API endpoints (Observability and Enterprise). MCP server names, and which servers are mandatory, live in [`mcp-servers.md`](mcp-servers.md). This file is the procedure. Do not copy it into an agent file.

## Credentials

Read the memory repository `.env` (copied from `templates/memory-repo/.env.template`) or the process environment. Never print a value into the document, the wiki, a log, or an example. Record the variable **name** when a value is missing.

| Variable | What it is |
|---|---|
| `SPLUNK_REALM` | Observability Cloud realm. The API base is `https://api.<realm>.signalfx.com`. There is no second base-URL variable. |
| `SPLUNK_ACCESS_TOKEN` | Admin-level Observability Cloud API key. `Splunk_O11y_API_Key` is the same secret. |
| `SPLUNK_HOST` | Splunk Enterprise base URL. The same fact as `tenancy.splunk_platform_host`. |
| `SPLUNK_TOKEN` | Splunk Enterprise API token for search and introspection. `SPLUNK_ENTERPRISE_TOKEN` is the same secret. |
| `SPLUNK_ENTERPRISE_INDEXES` | Comma-separated Enterprise indexes the log search may use. |
| `TE_OAUTH_BEARER_TOKEN` | ThousandEyes token, and only when that server is enabled. |

`SPLUNK_REALM`, `SPLUNK_ACCESS_TOKEN`, `SPLUNK_HOST`, `SPLUNK_TOKEN`, and `TE_OAUTH_BEARER_TOKEN` are the `env` keys in `plugins/obengineer/.mcp.optional.json`. `SPLUNK_ENTERPRISE_INDEXES` is not an MCP process variable. The run reads it and puts the index names into the search.

The org id stays `tenancy.o11y_org_id` in `engagement-inputs.yaml`.

`analysis_access` does not grow a second secret. When the ref is one of these API credentials, `api_key_ref` is `${SPLUNK_ACCESS_TOKEN}` and `token_ref` is `${SPLUNK_TOKEN}`. The rules for a dummy test login stay in [`engagement-inputs.md`](engagement-inputs.md).

If a variable is empty, an MCP server cannot be reached, or an API endpoint cannot be reached, write **Not in evidence** for the rows that source would have filled, and label those tenant facts `stated`. Do not invent a volume.

## Servers and API endpoints

Both products are required before a figure from the tenant is labelled `measured`. Each one is read through its MCP server and its API endpoint:

- `splunk-observability` and the Observability Cloud API at `https://api.<realm>.signalfx.com` — MetricSets and SignalFlow
- `splunk-platform` and the Splunk Enterprise API at `SPLUNK_HOST` — search and introspection, limited to `SPLUNK_ENTERPRISE_INDEXES`

Copy the MCP entries from `.mcp.optional.json`. Do not guess a command. Enabling one product is not enough: Observability Cloud does not see Enterprise indexes, and Enterprise does not see spans.

## What to collect

State the time range on every figure. Attribute a figure to `<app>` only when a returned dimension, sourcetype, source, or host matches evidence for that application. Otherwise say the figure is org-level or index-level.

### Log volume

Through the `splunk-platform` MCP and the Enterprise API, search only the indexes in `SPLUNK_ENTERPRISE_INDEXES`. When the source scan or a diagram names a sourcetype, source, or host for `<app>`, add that constraint. Report the event count and the byte sum when the search returns them.

Example of shape. Replace the index list from the environment. Do not add indexes that are not in it.

```
index IN (<indexes from SPLUNK_ENTERPRISE_INDEXES>)
| stats count AS events, sum(eval(len(_raw))) AS bytes
```

An empty `SPLUNK_ENTERPRISE_INDEXES` means log volume is **Not in evidence**.

### Span volume

The APM Monitoring MetricSet `spans` is the count of spans. SignalFlow of the documented shape:

```
histogram('spans').count().publish(label='spans')
```

Filter on `sf_service` or `service.name` when that service is in evidence. A tenant that still emits the older non-histogram metric may return `spans.count`; record that name only when the tenant returns it.

No `sf.org` metric for span count was verified for this procedure. Do not invent one. If the MCP or the API returns a span-count series under some other name, record the name it returned.

### Trace volume

Record these separately. They are not the same number.

| Fact | Metric | Scope |
|---|---|---|
| Traces received | `sf.org.apm.numTracesReceived` | Org-level. Per service only when the tenant returns `sf.org.apm.numTracesReceivedByService`. That series is not on by default. |
| Trace volume, bytes | `sf.org.apm.numSpanBytesReceived` | Bytes APM accepted after decompression, with invalid and throttled spans discarded. Org-level. |
| Traces for one service | `histogram('traces').count()` | The `traces` Monitoring MetricSet, filtered by `sf_service` or `service.name` when the service is in evidence. |

### MetricSets

From the `splunk-observability` MCP and the Observability API, list the Monitoring MetricSets and Troubleshooting MetricSets the tenant already has. Do not guess names beyond the defaults below, which Splunk documents as default Monitoring MetricSets: `service.request`, `inferred.services`, `spans`, `traces`, `business.transactions`.

Org cardinality, from the APM subscription-usage metrics:

- `sf.org.apm.numMonitoringMetricSets` — Monitoring MetricSet cardinality (histogram MMS)
- `sf.org.apm.numTroubleshootingMetricSets` — Troubleshooting MetricSet cardinality

Both are org-level unless a returned dimension matches `<app>`.

### Current and max MTS

Verified organization metrics for Infrastructure Monitoring system limits:

| Fact | Metric |
|---|---|
| Active MTS now | `sf.org.numActiveTimeSeries` |
| Active MTS ceiling | `sf.org.limit.activeTimeSeries` |
| Custom MTS now | `sf.org.numCustomMetrics` |
| Custom MTS ceiling, 60-minute window | `sf.org.limit.customMetricMaxLimit` |
| Custom MTS ceiling | `sf.org.limit.customMetricTimeSeries` |

These are org-level. Say so unless the series is broken down by a dimension that matches `<app>`. Record both custom-MTS ceilings when both are present. They are different limits.

### `sf.org` usage, entitlement, and overages

Query the metrics named in this file. Where a current metric and a limit metric both return, record the difference as the overage or the headroom. A human-typed entitlement stays `stated` until the same fact comes back from one of these metrics; then it is `measured`.

Do not add an `sf.org.*` name that is not in this file and was not returned by the query. Extra series the MCP or the API returns are recorded under the name that source used.

Checked against Splunk's organization-metrics page and the APM subscription-usage page when this procedure was written:

- `sf.org.numActiveTimeSeries`, `sf.org.limit.activeTimeSeries`
- `sf.org.numCustomMetrics`, `sf.org.limit.customMetricMaxLimit`, `sf.org.limit.customMetricTimeSeries`
- `sf.org.apm.numTracesReceived`, `sf.org.apm.numSpanBytesReceived`
- `sf.org.apm.numMonitoringMetricSets`, `sf.org.apm.numTroubleshootingMetricSets`
- `sf.org.apm.numTracesReceivedByService` only when the tenant already emits it

### SignalFlow cross-check

Through the `splunk-observability` MCP and the Observability API, run SignalFlow against telemetry the tenant already has.

- Custom metrics: names that are not `sf.*` defaults and not the default MetricSet names listed above. Record the names the query returns.
- Span attributes already indexed: dimensions on Troubleshooting MetricSets and Tag Spotlight, and attributes trace search returns for the services in evidence.
- Compare that set with the source scan. Two columns: found in telemetry, found in source. A name only in telemetry is instrumentation the scan did not see. A name only in source is code that is not arriving. A name in both is already collected.

Example of shape for one metric the tenant already emits:

```
data('<metric>', filter=filter('sf_service', '<service>')).sum().publish(label='existing')
```

Use `<metric>`, `<service>`, and `<app>` in anything that is written down. Do not paste an index list, a token, or a real service name from the tenant into an example.

## Where the numbers go

Section 3, **Existing portfolio footprint**, gets the operational measurements: log volume, span volume, trace volume, the MetricSets that exist, and the SignalFlow cross-check. Each figure is `measured` or **Not in evidence**.

Current and max MTS, `sf.org` entitlement, and overages are licensing figures. Write them into the entitlement exposure document's position-today table when that document is already required, and label the source `measured`. They do not appear in the customer document. Whether that document exists is decided in [`entitlement-exposure.md`](entitlement-exposure.md). A measured series does not by itself create it. When the document is out of scope, section 3 says the org-usage query ran or that it was **Not in evidence**, and it does not print the counts.

## What this pass does not do

It does not change the tenant, create a detector, or edit application code. It does not store a secret value in `engagement-inputs.yaml`, the wiki, or a log.
