# Suggested prompts

Use these **in order**. Attach the matching agent file as the system prompt. The same prompts apply to any customer, environment, and stack.

| Order | Prompt | Agent | Skills | Output |
|---|---|---|---|---|
| 1 | [Analyze the application](01-analyze-application.md) | Architect | `instrumentation-analyze` | Findings memo (not yet the full guide) |
| 2 | [Develop the instrumentation guide](02-develop-instrumentation-guide.md) | Architect | `instrumentation-guide`, `baggage-propagation`, `customer-doc-render` | Guide **plus** a customer `.docx` **plus** `attribute-schema.json` (PR 0, docs only) |
| 3 | [Implement instrumentation](03-implement-instrumentation.md) | Implementer | `instrumentation-implement` | Code PRs, one contract slice (or Phase 0) at a time |

Do not skip 1→2. Do not run 3 against a guide the human has not accepted.

If your host has the skills loaded (see [`../README.md`](../README.md)), `$<skill-name>`
is enough and the prompt below is the long form for a host that does not. Either way
the agent file is the authority on what must be produced.

Run 2 is not complete until **both** the Markdown and the rendered `.docx` exist and
`verify_render.py` passes on them, and the guide contains the
**Cross-Cutting Attributes and Baggage Propagation** section.

Fill bracketed fields. Attach diagrams, URLs, and any **existing** in-repo schema in the chat — do not bake customer names or document paths into the agent files or into these templates.

## Attachments

- Architecture diagrams (export or screenshot)
- Production / non-prod URLs when a front end exists
- Collector values / Helm **with tokens redacted**
- The two `*.agent.md` files as rules

## Secrets

Strip tokens from HAR files, HTML dumps, and env examples. If a crawl artifact contains a RUM access token, redact it.

## After each implementation PR

Run the **audit** prompt at the bottom of `03-implement-instrumentation.md` (read-only). Fail closed on PII or missing `traceparent`.
