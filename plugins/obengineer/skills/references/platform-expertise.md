# Platform expertise router

Read [`context-loading.md`](context-loading.md) first. Load only references whose evidence
predicate is true and record each load in `provenance-ledger.json`.

## Conditional references

- Browser/WebView: [`platform/browser.md`](platform/browser.md)
- Cloud/runtime placement: [`platform/clouds.md`](platform/clouds.md)
- Splunk platform/log correlation: [`platform/splunk-platform.md`](platform/splunk-platform.md)
- ThousandEyes/off-box paths: [`platform/thousandeyes.md`](platform/thousandeyes.md)

Languages—load exactly those in `backends.languages`:

- [`java`](platform/languages/java.md)
- [`node`, `javascript`, `typescript`](platform/languages/node.md)
- [`dotnet`](platform/languages/dotnet.md)
- [`go`](platform/languages/go.md)
- [`python`](platform/languages/python.md)
- [`php`](platform/languages/php.md)
- [`ruby`](platform/languages/ruby.md)
- [`cpp`](platform/languages/cpp.md)

Buses—load exactly those in `backends.buses`:

- [`kafka`, `msk`](platform/buses/kafka.md)
- [`sqs`, `sns`, `eventbridge`](platform/buses/aws-messaging.md)
- [`rabbitmq`](platform/buses/rabbitmq.md)

An observed language or bus with no reference becomes an unresolved ledger item and a human
question. It never causes every platform reference to load.
