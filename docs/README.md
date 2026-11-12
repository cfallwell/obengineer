# obengineer documentation

This documentation explains how to install, configure, and operate obengineer. The
root [README](../README.md) is intentionally limited to a quick start.

## Start here

1. [Installation and upgrades](installation.md) — choose a host and artifact
   repository, install or remove the toolkit, and configure renderer dependencies.
2. [Configuration and behavior controls](configuration.md) — configure local obconfig,
   direct APIs, connected MCP integrations, scope, artifact hashing, and output gates.
3. [End-to-end usage and command reference](usage.md) — start, add or edit inputs,
   review and accept a version, implement work orders, generate Terraform, and verify.
4. [How obengineer operates](how-it-works.md) — understand dispatch, sources of truth,
   state, evidence precedence, output flow, repeat runs, and safety boundaries.

## Canonical specifications

The files below are executable contracts used by the agents. They take precedence
over explanatory documentation if behavior changes:

- [`obconfig.yaml.template`](../obconfig.yaml.template) defines every accepted input,
  default, consequence, and secret annotation.
- [`skills/references/analysis-site.md`](../skills/references/analysis-site.md)
  defines the linked analysis layout, versioning, breadcrumbs, side-panel handoff,
  and optional short Word summary.
- [`skills/references/agent-wiki.md`](../skills/references/agent-wiki.md) defines the
  wiki layout and metadata.
- [`skills/references/ci-integration.md`](../skills/references/ci-integration.md)
  defines contract enforcement and implementation automation.
- [`skills/references/security-assessment.md`](../skills/references/security-assessment.md)
  defines credential/API checks, OWASP coverage, confidence, and P0 routing.
- [`skills/references/analysis-run-lifecycle.md`](../skills/references/analysis-run-lifecycle.md)
  defines analysis branches, commits, review, content-bound acceptance, and merge.
- [`skills/references/implementation-work-orders.md`](../skills/references/implementation-work-orders.md)
  defines bounded targets, repository mapping, linked PRs, and Jira fallback.
- [`skills/references/provenance-ledger.md`](../skills/references/provenance-ledger.md)
  defines the single evidence and run-state authority.
- [`skills/references/context-loading.md`](../skills/references/context-loading.md)
  defines evidence-gated reference loading.
- [`skills/references/verification-run.md`](../skills/references/verification-run.md)
  defines read-only outcome verification and remediation routing.
- [`skills/references/outcome-metrics.md`](../skills/references/outcome-metrics.md) and
  [`outcome-issues.md`](../skills/references/outcome-issues.md) define measured outcomes
  and anonymized project issues.
- [`skills/observability-as-code/SKILL.md`](../skills/observability-as-code/SKILL.md)
  defines Terraform generation.
- [`commands/`](../commands/) contains the installed command entry points.

## Maintainer references

- [Design rationale](design.md)
- [Architecture review — 9 Nov 2026](reviews/architecture-review.md)
- [Archived architecture review — 18 Sep 2026](reviews/2026-09-18-architecture-review.md)
- [Contributing guide](../CONTRIBUTING.md)
- [Agent instructions](../AGENTS.md)
