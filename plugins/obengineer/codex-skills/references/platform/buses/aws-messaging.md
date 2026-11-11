# AWS messaging

Load only when SQS, SNS, or EventBridge is in `backends.buses`. Inject trace context and
approved baggage into message attributes within service limits; extract before consumer
work. Record queue/topic/event-bus templates as bounded values. DLQ redrive starts a new
trace with a link to the prior context when available.
