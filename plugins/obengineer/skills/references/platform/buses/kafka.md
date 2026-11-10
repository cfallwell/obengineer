# Kafka

Load only when Kafka/MSK is in `backends.buses`. Inject W3C trace context and approved
baggage into record headers; extract before the consumer span. Use bounded destination
templates, not raw topic names, as dimensions. Batch/fan-in uses links only where one parent
would lie.
