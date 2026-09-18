# Run contracts

One file per run, and **one copy of each**. These are read in place by the installed
commands, not pasted into a chat — a prompt that gets copied is a prompt that drifts
from the version under review, and the copy in someone's clipboard is the one that
actually ran.

| Order | Command | Run contract | Agent | Output |
|---|---|---|---|---|
| 0 | `/obengineer-intake` | [`engagement-intake`](../skills/engagement-intake/SKILL.md) | — | `engagement-inputs.yaml` |
| 1 | `/obengineer-analyze` | [01](01-analyze-application.md) | Architect | **The customer document** — analysis and recommendations in one file — plus its `.docx` and `attribute-schema.json` (PR 0, docs only) |
| 2 | `/obengineer-wiki` | [02](02-build-instrumentation-wiki.md) | Architect | The agent wiki under `wiki/<Customer>/<app>/`, work orders, tracked versions. **No second document.** |
| 3 | `/obengineer-implement` | [03](03-implement-instrumentation.md) | Implementer | Code PRs, one contract slice (or Phase 0) at a time |
| 4 | `/obengineer-as-code` | [04](04-generate-observability-as-code.md) | Observability as Code | Terraform for three persona levels, plus a plan. No `apply`. |

Do not skip 1→2. Do not run 3 or 4 against an analysis the human has not accepted.

**One customer document, one agent layer.** Run 1 produces the single customer-facing
artifact; run 2 produces the notes the coding agents retrieve by subject. An earlier design
had run 2 emit a second document that duplicated run 1, which no customer read and no agent
could load without spending its context on irrelevant material.

Runs 3 and 4 are independent of each other: instrumentation lands in application repos and
configuration lands in a tenant, so neither blocks the other. Run 4 will refuse whatever
run 3 has not yet delivered, by name.

Install the commands with [`../install.sh`](../install.sh). Without them, tell the agent
to read the run contract and the agent file — the content is identical, only the
invocation differs. Either way the agent file is the authority on what must be produced.

Run 1 is not complete until **both** the Markdown and the rendered `.docx` exist,
`verify_render.py` passes on them, and the document contains **Critical Findings** as section
4 and **Cross-Cutting Attributes and Baggage Propagation** with all five code subsections.

Run 2 is not complete until every business transaction, workflow, use case, finding, detector,
and objective has a note, `meta/versions.md` records what the design was built against, and
the host memory pointers point at the index note rather than copying it.

## Running again

The architect is expected to run periodically. Where a wiki already exists for the customer
and application, run 1 is a **delta**: it reads the accepted names and finding ids before
scanning, reuses them, and reports what changed — with newly shipped uninstrumented code
first, because that is what the cadence exists to catch. See
[`../skills/references/incremental-runs.md`](../skills/references/incremental-runs.md), and
[`../skills/references/ci-integration.md`](../skills/references/ci-integration.md) for running
all of this from a pipeline.

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
