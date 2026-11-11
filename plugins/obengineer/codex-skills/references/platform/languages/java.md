# Java

Load only when Java is in `backends.languages`. Bootstrap with the Splunk OpenTelemetry
Java agent, then use the OTel Java SDK for accepted custom spans, baggage stamping, meters,
and propagators. Shared library shape: `<org>-otel-common`. Kubernetes injection is
bootstrap, not completion.
