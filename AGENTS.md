# AGENTS.md

Repo instructions for coding and reviewing agents working on this agentry. Keep
changes small, evidence-based, and aligned with the existing structure. This
directory is the home of the instrumentation architecture agents, skills, and
plugins; the customer deliverables they produce live under `../docs/observability/`.

## Project Map

- `agents/` — agent definitions used as system prompts. `instrumentation-architect.agent.md` owns the doctrine and the mandatory section list; `instrumentation-implementer.agent.md` owns the PR rules.
- `prompts/` — the three-run workflow: analyze, guide, implement. Copy-paste blocks for a human to hand to an agent.
- `skills/` — canonical skill sources. One directory per skill with `SKILL.md`, plus `references/`, `scripts/`, `tests/` as needed.
- `skills/references/` — shared references loaded by more than one skill. `document-template.md` and `cross-cutting-attributes.md` are load-bearing; see below.
- `plugins/obengineer/` — the distributable bundle for Claude Code and Codex. Contains its own copy of `skills/`, `agents/`, and `prompts/` so an installed plugin is self-contained.
- `.cursor/skills/`, `.agents/skills/` — symlinks to canonical skills for Cursor and repo-scoped Codex use.
- `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json` — marketplace manifests pointing at the plugin.
- `scripts/` — repo maintenance. `sync_plugin_skills.py` is the only way plugin copies get updated.
- `tests/` — deterministic contract tests over the agentry itself.
- `docs/` — design notes for this agentry, not customer deliverables.

## Working Rules

- Read the surrounding file before editing. These documents are prescriptive; a
  contradiction between two sections is a defect.
- Prefer editing an existing file over adding one.
- `skills/` is the single source for skill content. **Never hand-edit
  `plugins/*/skills/`** — change the canonical file, then run
  `make sync-plugin-skills`.
- Use `rg` for search.
- Use `python3` and `pytest`; the only runtime dependency is `python-docx`.
- Avoid drive-by refactors and narration comments.

## The section that must never be dropped

`Cross-Cutting Attributes and Baggage Propagation` was once missing from the
architect agent and from a generated guide. The result was a contract that could
not drive a single dashboard variable, detector grouping, or Related-Content link,
because the keys those depend on existed only on the span where they were
discovered.

It is now mandatory in four places, and
`tests/test_skill_contracts.py::test_cross_cutting_section_is_mandatory_everywhere`
fails if any of them stops requiring it:

- `agents/instrumentation-architect.agent.md` — doctrine 12a and the contract table
- `prompts/02-develop-instrumentation-guide.md`
- `skills/references/document-template.md`
- `skills/instrumentation-guide/SKILL.md`

Do not weaken that test. If the section genuinely does not apply to a target, the
guide keeps the heading and writes **Not in evidence**; the requirement to emit the
heading does not move.

## Deliverables are produced in pairs

Every guide run emits Markdown **and** a `.docx` rendered from that Markdown by
`customer-doc-render`, plus `attribute-schema.json`. The Word file is a build
artifact: never hand-maintained, always regenerated, and verified with
`verify_render.py` before delivery. A `.docx` with a modification time newer than
its source means somebody edited the wrong file.

## Coding Agent Definition of Done

Before handing work back:

- Keep the diff within the requested scope. Re-read the request.
- `make test` passes, including the credential scan.
- `make check` passes — plugin copies match canonical skills and manifest versions agree.
- If a skill changed, `make sync-plugin-skills` has been run and the result committed.
- If a reference that defines the customer template changed, re-render an existing
  deliverable and run `verify_render.py` to prove the template still renders.
- No credential, token, key, or customer PII anywhere in the diff. Placeholders and
  `${ENV_VAR}` references only, including in `.mcp.json`.

## Code Review Rules

### OE-SOURCE — canonical skills are the source
A diff that edits `plugins/*/skills/**` without the matching change under `skills/**`
is wrong even if the content is good; the next sync will silently revert it.

### OE-TEMPLATE — the template is a contract, not a preference
Reordering sections in `document-template.md`, retitling
`<Frontend> and Backend Architecture (Observed)`, moving it into an appendix, or
moving the attribute dictionary to the front all change what a customer review
opens on. Those changes need an explicit request, not a tidy-up.

### OE-EVIDENCE — no invented taxonomy
Skills and agents must not name a customer's journeys, business transactions, metric
names, or industry. Every example is generic (`<org>`, `<app>`, `<bus>`) or is
labelled as an example of shape.

### OE-SECRETS — placeholders only
Tokens are `window.__<ORG>_RUM_TOKEN__`, `${SPLUNK_ACCESS_TOKEN}`, or a named secret
store. Any literal that looks like a credential fails review and the credential
scan. Optional MCP servers stay in `.mcp.optional.json` with `${VAR}` references
rather than being wired with a guessed command.

### OE-TEST — prove changed behaviour
A change to the renderer or verifier needs a test that fails without it. The
existing tests encode real defects (bold wrapping a code span, ordered lists
continuing across the document, headings miscounted inside code fences); do not
delete one to make a change pass.

## Testing

```bash
make test                    # contract tests + renderer round-trip
make check                   # plugin sync + manifest agreement
make render FILE=<path.md>   # render one Markdown deliverable
```

`python-docx` is required for the renderer tests; they skip cleanly without it, so
run `pip install python-docx` before trusting a green run.

## Available Skills

| Skill | Purpose |
|---|---|
| `$instrumentation-analyze` | Deep-scan a target and inventory what is actually there before designing anything |
| `$instrumentation-guide` | Write the full instrumentation contract; emits Markdown, `.docx`, and the attribute schema |
| `$baggage-propagation` | Design the cross-cutting attribute set and the baggage propagation contract |
| `$customer-doc-render` | Render a Markdown deliverable as a verified customer-review Word document |
| `$instrumentation-implement` | Land an accepted guide as small reviewable PRs, with the CI checks that keep it enforced |
