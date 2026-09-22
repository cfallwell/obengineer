# Copilot instructions

This repository holds instrumentation architecture agentry: agent definitions,
prompts, canonical skills, and a plugin bundle. Read `AGENTS.md` before making a
change; it owns the review rules.

Key constraints:

- `skills/` is the single source. Never edit `plugins/*/skills/**`, `plugins/*/agents/**`,
  or `plugins/*/prompts/**` — run `make sync-plugin-skills` instead.
- `Cross-Cutting Attributes and Baggage Propagation` is a mandatory section of every
  instrumentation guide. It is required in the architect agent, prompt 02, the document
  template, and the guide skill, and a test asserts all four. Do not weaken it.
- Every guide ships as Markdown plus a `.docx` rendered from that Markdown. The Word
  file is a build artifact, never hand-edited.
- No credential values anywhere, including `.mcp.json`. Use `${ENV_VAR}` references and
  `window.__<ORG>_RUM_TOKEN__` style placeholders.
- Do not name a customer's journeys, business transactions, or metric names in a skill
  or agent. Examples are generic or labelled as examples of shape.

Run `make test` and `make check` before handing work back. `.github/workflows/ci.yml`
runs both on every pull request, along with an install and uninstall round-trip.
