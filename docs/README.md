# obengineer documentation

The root [README](../README.md) is a quick start. These pages cover everything else.

## Guides

| Page | Answers |
|---|---|
| [Installation](installation.md) | How do I install obengineer into Cursor, Claude Code, Codex CLI, or ChatGPT Desktop, confirm it worked, upgrade it, and remove it? |
| [Configuration](configuration.md) | What does each `obconfig.yaml` section control, what do the repair and proceed gates ask, and how do security assessment modes behave? |
| [End-to-end usage](usage.md) | What exact commands and replies take me from install to an accepted analysis, implemented work orders, a Terraform plan, and verification? Includes the command reference. |
| [How it works](how-it-works.md) | What happens at each pipeline stage, which files are written where, how the foundation gate, acceptance digest, revisions, Terraform layout, and verification work? |
| [Design rationale](design.md) | Why does obengineer measure first, version every analysis, gate on foundation work orders, and bind acceptance to content? |

## Canonical specifications

These files are the contracts the agents execute. When they disagree with a guide, they
win.

| File | Defines |
|---|---|
| [`obconfig.yaml.template`](../obconfig.yaml.template) | Every configuration field, its default, and its effect. |
| [`commands/`](../commands/) | The installed `/ob-*` command entry points. |
| [`analysis-site.md`](../skills/references/analysis-site.md) | Analysis page layout, versions, breadcrumbs, side-panel handoff, optional Word summary. |
| [`agent-wiki.md`](../skills/references/agent-wiki.md) | Wiki layout and note frontmatter. |
| [`implementation-work-orders.md`](../skills/references/implementation-work-orders.md) | Work-order kinds, selectors, foundation gate, state ledger, revisions, repository mapping, linked PRs, Jira fallback. |
| [`analysis-run-lifecycle.md`](../skills/references/analysis-run-lifecycle.md) | Analysis branches, PR review, content-bound acceptance, and merge. |
| [`rum-delivery.md`](../skills/references/rum-delivery.md) | RUM load-order check and CDN delivery recommendation. |
| [`security-assessment.md`](../skills/references/security-assessment.md) | Credential and API checks, OWASP coverage, confidence, P0 routing. |
| [`provenance-ledger.md`](../skills/references/provenance-ledger.md) | Evidence records and run state. |
| [`verification-run.md`](../skills/references/verification-run.md) | Read-only verification and remediation routing. |
| [`outcome-metrics.md`](../skills/references/outcome-metrics.md), [`outcome-issues.md`](../skills/references/outcome-issues.md) | Measured outcomes and anonymized project issues. |
| [`context-loading.md`](../skills/references/context-loading.md) | Which references an agent loads, and when. |
| [`ci-integration.md`](../skills/references/ci-integration.md) | Contract enforcement in CI and artifact-repository placement. |
| [`observability-as-code/SKILL.md`](../skills/observability-as-code/SKILL.md) | Terraform generation and layout. |

## Maintainer references

- [Architecture review — 9 Nov 2026](reviews/architecture-review.md)
- [Archived architecture review — 18 Sep 2026](reviews/2026-09-18-architecture-review.md)
- [Contributing guide](../CONTRIBUTING.md)
- [Agent instructions](../AGENTS.md)
