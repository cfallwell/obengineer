# AGENTS.md

Repository instructions for agents working on obengineer. Generated engagement artifacts
belong in the artifact repository, not this toolkit.

## Project map

- `commands/` — short `/ob-*` host entry points.
- `prompts/` — ordered run contracts.
- `agents/` — operating doctrine and routing.
- `skills/` — canonical skill sources.
- `skills/references/` — one authority per cross-skill fact.
- `obconfig.yaml.template` — canonical local engagement configuration contract.
- `scripts/` — installer and mirror synchronization.
- `plugins/obengineer/` — generated self-contained plugin mirror.
- `.cursor/skills/`, `.agents/skills/` — generated links to canonical skills.
- `tests/` — deterministic contracts over the agentry.
- `docs/` — user and maintainer documentation.

## Current workflow

```text
/ob-start
  → local obconfig validation + digest-bound proceed gate + atomic claim
  → configured direct API and authorized safe-active attempts
  → analysis V<N> + versioned wiki + all work orders
  → one reviewed PR
  → explicit yes: content-bound acceptance and merge
  → Ready work orders / Terraform plan / read-only verification
```

`/ob-add-inputs` and `/ob-edit-inputs` validate a user-edited local `obconfig.yaml` and
automatically create the next version after the common proceed gate. There is no separate
generate command and no manual acceptance SHA.

The analysis is linked Markdown opened in the host's side panel. Never require a browser,
localhost server, or high port. Word is optional and under 20 pages.

## One authority per fact

| Fact | Authority |
|---|---|
| Linked analysis layout, versions, breadcrumbs, handoff, optional Word | `skills/references/analysis-site.md` |
| Config lifecycle and gates | `prompts/00-load-obconfig.md` |
| Input fields, defaults, consequences, and secret handling | `obconfig.yaml.template` |
| Findings | `skills/references/critical-findings.md` |
| Security coverage | `skills/references/security-assessment.md` |
| Branch, PR, acceptance, and merge | `skills/references/analysis-run-lifecycle.md` |
| Versioned wiki | `skills/references/agent-wiki.md` |
| Work orders and repository mapping | `skills/references/implementation-work-orders.md` |
| Evidence and run state | `skills/references/provenance-ledger.md` |
| Direct API and connected integration inventory | `skills/references/existing-telemetry.md` |
| Context predicates | `skills/references/context-loading.md` |
| Baggage | `skills/references/baggage-budget.md` |
| Optional Word format | `skills/references/document-template.md` and renderer format JSON |
| Terraform resources | `skills/references/splunk-terraform-providers.md` |
| Verification | `skills/references/verification-run.md` |

Agent files and commands route to these authorities; they do not restate them.

## Working rules

- Read surrounding files before editing.
- `skills/` is canonical. Never hand-edit `plugins/*/skills/**`; run
  `make sync-plugin-skills`.
- Prefer updating an existing authority over adding a competing one.
- Use `python3`, `pytest`, and `rg`.
- Keep examples generic unless source evidence names a target.
- Never commit credentials, tokens, customer PII, or personal paths.
- MCP is one data source; direct APIs remain first-class.
- Analysis claims the gate before invoking
  `manage_obconfig.py direct-api --phase analysis --command <command> --intended-version <Vn>`
  or `manage_obconfig.py safe-active`. After analysis/render/validation it stages
  intended paths, finalizes explicit output roots, commits exactly that index tree, and
  runs `dispatch` plus `verify-dispatch` before push/PR work. It consumes only after
  successful publication and aborts on every decline/failure. Verification invokes
  `direct-api --phase verification`. Only centralized-redacted network output feeds
  provenance.
- Do not require humans to type `unknown`, copy a SHA, or provide names of engineers,
  owners, or accepters. Engagement inputs are edited only in local `obconfig.yaml`.

## Analysis invariants

- `[V1] [V2] ...` are immutable and link only matching wiki snapshots.
- Every detail page has a breadcrumb to Analysis and its parent.
- Every landing-page object has a detail link.
- The landing page represents architecture, findings, strategy, path, work orders, use
  cases, workflows, transactions, contracts, operations, and reference.
- Use cases lead workflows; workflows lead business transactions.
- Analysis creates all work orders. Acceptance activates eligible orders.
- Work order 1 installs deterministic guardrails.
- Conditional subjects have no empty pages; suggestions share one page.
- Chat handoff is one documentation link plus concise next steps.
- Optional Word is a generated summary under 20 pages.

## Definition of done

- Requested scope only.
- `make test` passes.
- `make check` passes.
- Skill changes are synchronized.
- Renderer or verifier behavior changes have regression tests.
- No secret or customer-specific value appears in the diff.
