# Existing telemetry and direct API evidence

This is the tenant-read procedure for analysis and verification. Local credentials come
only from ignored mode-0600 root `obconfig.yaml`, loaded by `obconfig.py`. Never read
process environment or legacy files as fallback. Never print or persist credential
values.

## Mandatory direct attempts

When `splunk.observability` is configured, both analysis and verification directly call
the documented realm-derived SignalFlow endpoint. When `splunk.platform` is configured,
both directly call the exact validated HTTPS host and search only its validated index
allowlist. `direct_api.py` owns deterministic request construction and failure
dispositions.

Record one source-specific disposition for every product:

- `succeeded` — direct result may be labeled measured;
- `access-denied`, `unavailable`, or `unsupported-endpoint` — direct attempt occurred,
  but no fact is measured from it;
- `not-configured` — no direct request occurred.

MCP may add evidence but cannot replace, suppress, or relabel the direct attempt. MCP-only
facts are never called direct tenant measurement.

## Request safety

- HTTPS certificate verification is mandatory, with bounded timeout and response size.
- Tokens appear only in `X-SF-TOKEN` or `Authorization` request headers.
- No token enters a URL, query, body, exception, subprocess argument, MCP request,
  worker result, generated file, or provenance.
- Redirects are disabled. Credentials are never forwarded across origins.
- All requests are fixed read/introspection operations. There are no saved-object,
  configuration, detector-state, or other tenant mutations.
- Platform searches quote exact allowlisted indexes. `*`, `_all`, duplicates, empty
  names, and requested indexes outside the allowlist are rejected.

## Observability Cloud usage and enforced limits

Use `POST https://stream.<realm>.observability.splunkcloud.com/v2/signalflow/execute`
for the fixed approved organization-metric registry:

| Fact | Metric |
|---|---|
| Active MTS usage | `sf.org.numActiveTimeSeries` |
| Active MTS enforced system limit | `sf.org.limit.activeTimeSeries` |
| Custom MTS usage | `sf.org.numCustomMetrics` |
| Custom MTS 60-minute enforced limit | `sf.org.limit.customMetricMaxLimit` |
| Custom MTS enforced limit | `sf.org.limit.customMetricTimeSeries` |
| APM traces received | `sf.org.apm.numTracesReceived` |
| APM accepted bytes | `sf.org.apm.numSpanBytesReceived` |
| Monitoring MetricSet cardinality | `sf.org.apm.numMonitoringMetricSets` |
| Troubleshooting MetricSet cardinality | `sf.org.apm.numTroubleshootingMetricSets` |

Current usage and `sf.org.limit.*` are measured usage and enforced system limits.
Calculate their difference only as system headroom or exceedance. They are never
contractual entitlement. Contractual entitlement remains explicitly unavailable unless
a separate measured Billing/Subscription Usage API or approved export supports it.

Application attribution requires a returned service/dimension that matches source or
artifact evidence. Otherwise label the number organization-level.

## Splunk Platform

Use only read/introspection endpoints and search export. The bounded log-volume query is
equivalent to:

```text
search (index="<each exact allowlisted index>")
| stats count AS events, sum(eval(len(_raw))) AS bytes by index
```

The adapter constructs this expression; models do not interpolate config values.
Generated examples retain placeholders and never contain actual index names or raw
events. Add application constraints only from validated source evidence and escape them.

## Output contract

Each source records timestamp, endpoint class (not credential), direct disposition,
scope, observation window, limitations, and measured fact IDs. Sanitized provenance also
records artifact-tree algorithm/hash/count/bytes and redacted delta paths. Secret fields
are represented only as `configured` or `not configured`.
