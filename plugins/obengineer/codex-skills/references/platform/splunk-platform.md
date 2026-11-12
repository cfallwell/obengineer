# Splunk platform

Load when durable logs, audit, security search, ITSI, Enterprise Security, or trace/log
correlation is in evidence.

Design the log contract: existing sourcetypes/indexes, `trace_id`, `span_id`, session and
request identifiers, transport already deployed, retention, and redaction. Log Observer
Connect loads only when logs need trace correlation and direct tenant evidence confirms
that capability is available.

ITSI and Enterprise Security material loads only when tenant evidence shows those products.
Never reconstruct the user journey as an SPL transaction.
