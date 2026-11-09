# C++

Load only when C++ is in `backends.languages`. There is no honest general zero-code
solution; use the OpenTelemetry C++ SDK for accepted instrumentation. Shared library shape:
`<org>_otel_common`. OBI/eBPF may provide protocol visibility for third-party binaries but
does not replace business instrumentation.
