# obengineer documentation

This documentation explains how to install, configure, and operate obengineer. The
root [README](../README.md) is intentionally limited to a quick start.

## Start here

1. [Installation and upgrades](installation.md) — choose a host and artifact
   repository, install or remove the toolkit, and configure renderer dependencies.
2. [Configuration and behavior controls](configuration.md) — configure credentials by
   reference, MCP integrations, engagement inputs, scope, licensing behavior, and
   output constraints.
3. [End-to-end usage and command reference](usage.md) — run intake, analysis, wiki
   generation, implementation, Terraform generation, review, and rendering.
4. [How obengineer operates](how-it-works.md) — understand dispatch, sources of truth,
   state, evidence precedence, output flow, repeat runs, and safety boundaries.

## Maintainer references

- [Design rationale](design.md)
- [Architecture review](reviews/2026-09-18-architecture-review.md)
- [Contributing guide](../CONTRIBUTING.md)
- [Agent instructions](../AGENTS.md)

## Canonical specifications

The files below are executable contracts used by the agents. They take precedence
over explanatory documentation if behavior changes:

- [`inputs/engagement-inputs.template.yaml`](../inputs/engagement-inputs.template.yaml)
  defines every accepted engagement input.
- [`skills/references/document-template.md`](../skills/references/document-template.md)
  defines the analysis structure and completion checks.
- [`skills/references/agent-wiki.md`](../skills/references/agent-wiki.md) defines the
  wiki layout and metadata.
- [`skills/references/ci-integration.md`](../skills/references/ci-integration.md)
  defines contract enforcement and implementation automation.
- [`skills/observability-as-code/SKILL.md`](../skills/observability-as-code/SKILL.md)
  defines Terraform generation.
- [`commands/`](../commands/) contains the installed command entry points.
