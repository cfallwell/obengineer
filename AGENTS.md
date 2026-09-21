# AGENTS.md

Repo instructions for coding and reviewing agents working on this agentry. Keep
changes small, evidence-based, and aligned with the existing structure. This
repository is the home of the instrumentation architecture agents, skills, and
plugins. It belongs to no engagement: the deliverables it produces land in the
engagement's own repository, under `docs/observability/` and `wiki/<Customer>/<app>/`
there. Paths in the skills are relative to that repository, not to this one.

## Project Map

- `agents/` — agent definitions used as system prompts. Each is doctrine plus a routing table, capped at 2,500 words and tested; depth belongs in `skills/references/`. `instrumentation-architect.agent.md` owns the design doctrine, `instrumentation-implementer.agent.md` the PR rules, `observability-as-code.agent.md` the Terraform rules.
- `prompts/` — the run contracts: analyze, guide, implement, configure. Read in place by the installed commands, never pasted into a chat.
- `commands/` — installable host commands (`/obengineer-*`). Each is a short invocation carrying `{{OBENGINEER_ROOT}}`; the run contract stays in `prompts/`.
- `inputs/` — the engagement inputs template. One file per engagement, written only by `$engagement-intake`.
- `skills/` — canonical skill sources. One directory per skill with `SKILL.md`, plus `references/`, `scripts/`, `tests/` as needed.
- `skills/references/` — shared references loaded by more than one skill. `document-template.md` and `cross-cutting-attributes.md` are load-bearing; see below.
- `scripts/install.py`, `install.sh` — install skills and commands into Cursor, Claude Code, or Codex.
- `plugins/obengineer/` — the distributable bundle for Claude Code and Codex. Contains its own copy of `skills/`, `agents/`, and `prompts/` so an installed plugin is self-contained.
- `.cursor/skills/`, `.agents/skills/` — symlinks to canonical skills for Cursor and repo-scoped Codex use.
- `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json` — marketplace manifests pointing at the plugin.
- `scripts/` — repo maintenance. `sync_plugin_skills.py` is the only way plugin copies get updated.
- `tests/` — deterministic contract tests over the agentry itself.
- `docs/` — design notes and standing architecture reviews for this agentry, not customer deliverables.

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

## One authority per fact

Every fact has exactly one home, and everything else points at it. This is not tidiness;
it is the only way a disagreement becomes visible.

| Fact | Sole authority |
|---|---|
| The document section list, the completeness bar, the pre-delivery checklist | `skills/references/document-template.md` |
| Which platform answers which question, the course-of-action algorithm, the pitfalls | `skills/references/portfolio-decision-engine.md` |
| SDKs per language, front-end routers, clouds, platform log contract, ThousandEyes design | `skills/references/platform-expertise.md` |
| The cross-cutting section and its five code subsections | `skills/references/cross-cutting-attributes.md` |
| Baggage byte and key budget | `skills/references/baggage-budget.md` |
| Terraform resource names across the three Splunk providers | `skills/references/splunk-terraform-providers.md` |
| The `.docx` layout | `skills/customer-doc-render/references/document-format.json` |
| What the human must supply | `inputs/engagement-inputs.template.yaml` |

The architect agent once carried the decision engine, the platform expertise, and a full
output template inline — 7,214 words loaded on every run — while also linking to the
references that held the same material. That duplication hid a real defect: the agent
required 23 document sections and the template listed 16, and nobody noticed because
nobody diffs two long prescriptive files.

`test_section_list_has_exactly_one_authority` and
`test_agent_files_route_rather_than_duplicate` exist to stop it regrowing. Do not
summarize a reference into an agent file for convenience; that is how the 7,214 words
accumulated, one convenience at a time.

## The section that must never be dropped

`Cross-Cutting Attributes and Baggage Propagation` was once missing from the
architect agent and from a generated guide. The result was a contract that could
not drive a single dashboard variable, detector grouping, or Related-Content link,
because the keys those depend on existed only on the span where they were
discovered.

It is now mandatory in four places, and
`tests/test_skill_contracts.py::test_cross_cutting_section_is_mandatory_everywhere`
fails if any of them stops requiring it:

- `agents/instrumentation-architect.agent.md` — doctrine 16
- `prompts/01-analyze-application.md`
- `skills/references/document-template.md`
- `skills/instrumentation-analyze/SKILL.md`

Do not weaken that test. If the section genuinely does not apply to a target, the
guide keeps the heading and writes **Not in evidence**; the requirement to emit the
heading does not move.

## One customer document, and a wiki underneath it

The analyze run emits Markdown **and** a `.docx` rendered from that Markdown by
`customer-doc-render`, plus `attribute-schema.json`. The Word file is a build
artifact: never hand-maintained, always regenerated, and verified with
`verify_render.py` before delivery. A `.docx` with a modification time newer than
its source means somebody edited the wrong file.

There is exactly **one** customer-facing document. A second one existed —
`INSTRUMENTATION-GUIDE.md`, nominally for the implementers — and it failed in both
directions: it duplicated the analysis so the two disagreed, no customer read it, and no
agent could load it without spending its whole context on material irrelevant to the task
in hand. The lower layer is now a wiki of one note per subject under
`wiki/<Customer>/<app>/`; see `skills/references/agent-wiki.md`. If a change would
reintroduce a second document, it is the wrong change.

## Two placements that are load-bearing

**Critical findings are section 4.** Immediately after the architecture, ordered by
severity, each with the files involved, the exposure, the risk, the remediation, and the
verification. They were once written into whichever section discovered them, which put a
reachable credential on page 180 of a document nobody read to the end. See
`skills/references/critical-findings.md`.

**Nothing in the body sits under an appendix heading.** An earlier revision nested the
whole analysis under "Appendix A — Target breakdown", which put the substance of the
document behind a heading that reads as optional. Appendices are the attribute dictionary,
long code variants, the agent work-order plan, supplementary evidence, and open items.

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
| `$instrumentation-analyze` | Deep-scan a target and write the single customer document: architecture observed, critical findings, and the full recommendation catalogue |
| `$instrumentation-wiki` | Turn the accepted analysis into the agent wiki: one note per BT, workflow, use case, finding, detector, and objective, plus work orders and tracked versions |
| `$baggage-propagation` | Design the cross-cutting attribute set and the baggage propagation contract |
| `$customer-doc-render` | Render a Markdown deliverable as a verified customer-review Word document |
| `$instrumentation-implement` | Land an accepted analysis as small reviewable PRs from the wiki work orders, with the CI checks that keep it enforced |
| `$engagement-intake` | Collect the inputs no scan can measure into one `engagement-inputs.yaml`, asking only for what is missing |
| `$cardinality-budget` | Decide dimension versus attribute-only as arithmetic against the customer's entitlement |
| `$observability-as-code` | Emit the accepted contract as Terraform across the three Splunk providers, at three persona levels |
| `$deliverable-review` | Grade a finished deliverable against the completeness bar, separately from whoever wrote it |
