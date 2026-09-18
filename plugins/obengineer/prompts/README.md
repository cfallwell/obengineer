# Run contracts

One file per run, and **one copy of each**. These are read in place by the installed
commands, not pasted into a chat — a prompt that gets copied is a prompt that drifts
from the version under review, and the copy in someone's clipboard is the one that
actually ran.

| Order | Command | Run contract | Agent | Output |
|---|---|---|---|---|
| 0 | `/obengineer-intake` | [`engagement-intake`](../skills/engagement-intake/SKILL.md) | — | `engagement-inputs.yaml` |
| 1 | `/obengineer-analyze` | [01](01-analyze-application.md) | Architect | Findings memo (not yet the full guide) |
| 2 | `/obengineer-guide` | [02](02-develop-instrumentation-guide.md) | Architect | Guide **plus** a customer `.docx` **plus** `attribute-schema.json` (PR 0, docs only) |
| 3 | `/obengineer-implement` | [03](03-implement-instrumentation.md) | Implementer | Code PRs, one contract slice (or Phase 0) at a time |
| 4 | `/obengineer-as-code` | [04](04-generate-observability-as-code.md) | Observability as Code | Terraform for three persona levels, plus a plan. No `apply`. |

Do not skip 1→2. Do not run 3 or 4 against a guide the human has not accepted.

Runs 3 and 4 are independent of each other: instrumentation lands in application repos and
configuration lands in a tenant, so neither blocks the other. Run 4 will refuse whatever
run 3 has not yet delivered, by name.

Install the commands with [`../install.sh`](../install.sh). Without them, tell the agent
to read the run contract and the agent file — the content is identical, only the
invocation differs. Either way the agent file is the authority on what must be produced.

Run 2 is not complete until **both** the Markdown and the rendered `.docx` exist and
`verify_render.py` passes on them, and the guide contains the
**Cross-Cutting Attributes and Baggage Propagation** section.

## Inputs

There are no bracketed fields to fill. Everything the human supplies lives in
`docs/observability/engagement-inputs.yaml`, written once by
[`$engagement-intake`](../skills/engagement-intake/SKILL.md) and read by every run. See
[`../skills/references/engagement-inputs.md`](../skills/references/engagement-inputs.md)
for what each field decides.

Diagrams, URLs, and an existing in-repo schema are referenced **by path** from that
file. Do not bake customer names or document paths into the agent files or into these
run contracts.

## Secrets

Strip tokens from HAR files, HTML dumps, and env examples. If a crawl artifact contains a
RUM access token, redact it. The inputs file records who holds a credential, never its
value.

## After each implementation PR

Run the **audit** prompt at the bottom of `03-implement-instrumentation.md` (read-only). Fail closed on PII or missing `traceparent`.
