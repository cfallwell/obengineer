# RabbitMQ

Load only when RabbitMQ is in `backends.buses`. Inject W3C context and approved baggage into
message headers and extract before the consumer span. Use bounded exchange/routing templates,
not raw high-cardinality names. Retries and dead-letter paths retain explicit causal links.
