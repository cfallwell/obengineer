# Implementation mapping and unified work orders

This reference owns how versioned analysis subjects map to code, repositories, pull
requests, and optional engineering tickets.

## Work-order hierarchy

Work orders are implementation contracts. Each has one `kind`:

| Kind | Role |
|---|---|
| `foundation` | Prerequisite for everything else. A finding and recommendation, never a use case. No parents, no subordinates; depends only on other foundation orders. Expect at most about 10. |
| `use-case` | A complete unit for exactly one use case. Lists its subordinate work orders; has no `dependsOn`. |
| `workflow` | One workflow. May cross business-transaction boundaries. |
| `business-transaction` | One `<org>.bt` value. A shared business transaction may be listed under more than one use case. |
| `detector`, `alert-condition` | Detector IDs. |
| `dashboard` | Dashboard IDs. |
| `custom-code` | Custom instrumentation. May be atomic: one span or one attribute. |

A use case can map to several business transactions. Every subordinate names at least one
use-case parent, and each parent lists it in `subordinateIds` (reciprocal).

### Release rule

Implementation asks one question: **Are all foundation work orders complete?** Complete
means status `implemented` or `verified`. Until the answer is yes, every non-foundation
order stays blocked. Once it is yes, any non-foundation order may be implemented in any
order. An application with no foundation orders releases everything at acceptance.

Foundation orders include the RUM load-order check and the CDN delivery recommendation in
[rum-delivery.md](rum-delivery.md). An `incorrect` `rumLoadOrder` requires at least one
foundation order.

### Display order

Foundation orders come first. Then, per use case: the use-case order, followed by its
subordinates grouped workflow, business-transaction, detector, alert-condition, dashboard,
custom-code.

## Bounded target selectors

`/ob-implement` accepts one selector:

```text
work-order:<id>
business-transaction:<id>
workflow:<name>
use-case:<id>
detector:<id>
alert-condition:<id>
dashboard:<id>
custom-code:<id>
objective:<id>
config:<id>
```

The selector must resolve to exactly one Ready work order in the accepted version. Zero
matches stop with the missing mapping. Multiple matches stop and list candidates. If
omitted, the first Ready order in display order is selected. `use-case:<id>` runs that use
case's next unimplemented subordinate. One invocation executes one work order.

Before execution, run the foundation gate:

```bash
python3 skills/instrumentation-wiki/scripts/work_order_state.py gate --work-order <id> [--reimplement]
```

An `implemented`, `verified`, or `changed` order runs again only with the explicit
`reimplement` override (`--reimplement`).

## Business transactions in Splunk APM

Splunk Observability Cloud APM supports a Business Transaction include rule whose type is
**Global tag**. The tag must first be indexed; traces containing the selected global tag
are grouped and its value becomes the Business Transaction name:

- [Configure business transaction rules](https://help.splunk.com/en/splunk-observability-cloud/monitor-application-performance/correlate-traces-to-track-business-transactions/configure-business-transaction-rules)

The contract therefore defines `<org>.bt` as a bounded, stable global span tag and uses
it as the APM Business Transaction rule key. It is set at the earliest known business
surface, propagated across relevant process and repository boundaries, and stamped on
backend spans. Never derive it from a raw URL.

`workflow.name` remains the finer-grained intent. One `<org>.bt` value may contain several
workflows, and a workflow or end-to-end use case may cross several services and
repositories. The contract registers valid `<org>.bt` / `workflow.name` pairs.

## Implementation map

Analysis emits `docs/observability/implementation-map.json`. It maps every proposed
business transaction, workflow, use case, detector, objective, and configuration slice to
the repositories and optional Jira projects that own its implementation.
Every `evidence` value is a stable ID from `provenance-ledger.json`, never a free-form path.

Shape:

```json
{
  "schema_version": 1,
  "repositories": [
    {
      "id": "web",
      "remote": "owner/web",
      "authorized_paths": ["src/"],
      "jira_project": "WEB"
    }
  ],
  "targets": [
    {
      "selector": "use-case:account-update",
      "work_order": "WO-014",
      "repositories": ["web", "graphql", "identity"],
      "mapping_status": "complete",
      "evidence": ["SRC-c4-production", "SRC-web-account-route"]
    }
  ]
}
```

Repository IDs are stable within the application. `authorized_paths` must agree with
`initial_scope`; the map cannot grant scope. Jira project keys are recorded only from
engineering or a named-and-connected Jira integration.

List every `mapping_status: incomplete` row on Intake recommendations:

- the repository remote and authorized parent paths;
- the Jira project, only if Jira is the configured issue tool.

A missing repository mapping blocks generation of an executable work order. Analysis still
records the proposed outcome, dependencies, acceptance evidence, and verification with an
`unresolved` mapping, no repository legs, and `blocked` status; it never invents a
repository or path. A missing Jira mapping does not: the work order remains the manual
queue.

## Unified multi-repository work orders

Work orders live at:

```text
wiki/apps/<app>/versions/V<N>/implementation/work-orders/<id>.md
```

Their status is one of `proposed`, `ready`, `in-progress`, `blocked`, `retained`,
`changed`, `superseded`, `implemented`, `verified`, or `retired`. Only `ready` or
`in-progress` orders in the accepted version execute.
This status is work authorization, not analysis acceptance and not finding risk acceptance.

Before acceptance, foundation orders are `proposed` (`blocked` when they have `dependsOn`
or an unresolved mapping); non-foundation orders are `blocked` when any foundation order
exists, otherwise `proposed`. Acceptance makes eligible foundation orders `ready`.

## State ledger and revisions

The accepted wiki note is revision R1 and stays digest-bound. Live state lives outside the
acceptance digest:

```text
wiki/apps/<app>/implementation/V<N>/state.yaml
wiki/apps/<app>/implementation/V<N>/revisions/<WO-id>/R<k>.md
```

`skills/instrumentation-wiki/scripts/work_order_state.py` owns it: `init`, `gate`,
`set-status --work-order ID --status S [--pr URL]`, `revise --work-order ID --file
change.yaml`, and `verify`.

Subordinate orders are not frozen inside an accepted version. SREs and engineers may change
naming conventions, add, remove, or rename attributes, or add spans with
`/ob-revise work-order:<id>`. That writes revision R2, R3, ... in a commit and PR; it never
creates a new analysis version. Each revision chains to the SHA-256 of the previous one.
Revising an `implemented` or `verified` order sets it to `changed`. Foundation and
use-case orders cannot be revised; change them with a new analysis version.

## Contract schema v4

New analyses write `analysis-contract-v4.schema.json`; v3 stays frozen for historical
versions. Each `workOrders[]` entry adds:

| Field | Rule |
|---|---|
| `kind` | One of the kinds above. |
| `parentIds` | Use-case order IDs; empty for foundation and use-case orders. |
| `subordinateIds` | Non-empty for use-case orders; empty otherwise. |
| `subjectIds` | Contract objects implemented: one use case, one workflow, one business transaction, detector or dashboard IDs; may be empty for custom code. |
| `findingIds` | Non-empty for foundation orders. |
| `revision` | Always `1` in the contract; later revisions live in the state ledger. |

All foundation orders precede every other order in `workOrders`.

Service notes link to app-level work orders. Each work order contains:

- target selectors, accepted version, and content digest;
- repository legs with repository ID, paths, changes, tests, and dependency order;
- the registered `<org>.bt` / `workflow.name` pairs affected;
- one pull request per repository, at most;
- cross-repository sequencing and verification;
- optional Jira project mappings; and
- copy/paste-ready issue text for manual use.

The executable fields are canonical YAML frontmatter parsed with `safe_load`:

```yaml
work_order_id: WO-014
kind: workflow
parents: [WO-012]
subordinates: []
revision: 1
selectors: [workflow:account-update-submit]
depends_on: []
repository_mapping: mapped
repository_mapping_evidence: The accepted implementation map authorizes this repository and parent path.
repository_legs:
  - repository: web
    paths: [src/account/]
    changes: [Implement the accepted account-update signal contract.]
    tests: [Run the deterministic workflow and propagation contract tests.]
```

Selectors use only the grammar listed above. Repository IDs must exist in
`implementation-map.json`; every path is repository-relative, traversal-free, and under
one of that repository's `authorized_paths`. Changes and tests describe meaningful work.
Every dependency exists in the same version, and the dependency graph is acyclic.
An unresolved order uses `repository_mapping: unresolved`, meaningful
`repository_mapping_evidence`, `repository_legs: []`, and `status: blocked`.

One work order can produce several pull requests. Every PR title and body includes the
work-order ID and reciprocal links to the coordination PR and sibling PRs. The artifact
repository gets a coordination PR recording all legs and their states. No PR is merged
without explicit human authorization, and no repository leg is declared complete until its siblings and end-to-end
verification are visible.

## Jira and other issue tools

Jira is enabled only when both are true:

1. the human named Jira under `developer_tools.named`; and
2. `developer_tools.matched` contains
   `{tool: "jira", via: "mcp", key: "<connected server key>"}`.

Connected-but-unnamed Jira is not used. Named-but-unavailable Jira is not used. Never
guess a project key from a repository name.

When Jira is enabled and engineering requests tickets, create at most one issue per mapped
project for the unified work order, link sibling issues and repository PRs, and retain the
wiki work order as authority.

If Jira is unavailable or the team uses another tool, do not attempt Jira operations.
Provide the work-order path and copy/paste-ready issue text. A human transfers it into the
team's chosen system.
