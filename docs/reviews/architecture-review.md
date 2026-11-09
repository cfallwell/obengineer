# Architecture review — 9 Nov 2026

Current architecture review of obengineer. This review supersedes the
[18 Sep 2026 review](2026-09-18-architecture-review.md) without rewriting it. The
September document remains the point-in-time record; links below identify every conclusion
that has materially changed.

Companion reading:

- [Design notes](../design.md)
- [Canonical customer-document specification](../../skills/references/document-template.md)
- [CI/CD integration](../../skills/references/ci-integration.md)
- [Run contracts](../../prompts/README.md)

---

## Executive assessment

The architecture is materially more complete than it was on 18 September. The project has
moved from a set of long prompts and a document generator to an installable, multi-host
contract system with:

- one canonical analysis document and one subject-addressable wiki beneath it;
- explicit intake, analysis, acceptance, generation, implementation, Terraform, review,
  and rendering contracts;
- deterministic schema, wiki, render, acceptance, and implementation-map verification;
- security and OWASP analysis routed into Critical Findings and P0 fixes;
- repository-qualified, multi-repository implementation work orders;
- read-only tenant discovery, import-aware Terraform generation, reviewed plans, and
  manual apply;
- exact-commit human acceptance before implementation or configuration; and
- generated plugin mirrors checked against canonical sources.

The strongest September finding—two competing authorities for the document section
list—is resolved structurally. The most important remaining gap is also the same one
September identified: the pipeline still lacks a first-class verification run that checks
the accepted contract against telemetry after implementation and configuration.

## Section-count decision

Revises [The defect worth dwelling on](2026-09-18-architecture-review.md#the-defect-worth-dwelling-on).

The September defect was not that 23 was inherently correct and 16 inherently wrong. The
defect was that both counts claimed authority. That conflict is gone:
`skills/references/document-template.md` is the sole section authority, and tests prevent
agents and prompts from growing a second list.

The canonical document has since grown beyond both historical counts. It currently defines
26 body sections, five appendices, and one H1 per ranked use case. The growth is explained by
requirements that did not have an explicit home in September: security coverage, course of
action, route behavior, cardinality, portfolio mapping, implementation planning, the
catalogue, and Business Value Realization.

**Decision on 9 November: accept the current canonical structure.** Do not reduce it to 23
or return to 16 merely to satisfy a historical count. Future section changes happen only in
the canonical template, with render/review tests and an explicit architecture request.

## What changed since 18 September

| Change | Status now | Evidence |
|---|---|---|
| Repository hygiene and public portability | Resolved | [PR #1](https://github.com/cfallwell/obengineer/pull/1) removed customer/machine paths; source and generated-artifact credential scans are tested |
| Install and host command discovery | Resolved | Seven commands are installed for Cursor, Claude Code, and Codex; retired command names migrate safely |
| Project and memory-repository setup | Resolved | [PR #10](https://github.com/cfallwell/obengineer/pull/10), [PR #11](https://github.com/cfallwell/obengineer/pull/11), and [PR #12](https://github.com/cfallwell/obengineer/pull/12) established the memory repository, app/service wiki, environment template, and existing-telemetry pass |
| Entitlement and consumption arithmetic | Substantially resolved | [PR #8](https://github.com/cfallwell/obengineer/pull/8) added license prediction and pre-merge contracts; entitlement exposure is separate from the customer document |
| Exact contract acceptance | Resolved | Analysis artifacts are bound to a full commit SHA and verified before generation, implementation, or Terraform |
| Security discovery | Resolved as an analysis contract | Exposed credentials/APIs and OWASP Web/API categories are assessed within an authorized boundary; confirmed/high-confidence vulnerabilities route to section 4 and P0 |
| Multi-repository implementation | Resolved as a contract | `implementation-map.json`, app-level work orders, repository legs, coordination PRs, and optional Jira mappings define one end-to-end unit |
| Terraform ownership | Resolved | `/ob-terraform` inventories/imports when access exists and plans; without credentials it reports schema-checked output. A human applies |
| Documentation hierarchy | Resolved | [PR #13](https://github.com/cfallwell/obengineer/pull/13) and [PR #14](https://github.com/cfallwell/obengineer/pull/14) separated concise entry documentation from detailed operating contracts |
| Parser and MCP decisions | Resolved at design level | [PR #15](https://github.com/cfallwell/obengineer/pull/15) fixed the parser migration direction, operator-supplied MCP commands, and manual Terraform apply boundary |

## Reassessment of the defects worth dwelling on

### One authority per fact

Revises [The defect worth dwelling on](2026-09-18-architecture-review.md#the-defect-worth-dwelling-on).

**Resolved.** The section list, OWASP coverage, analysis lifecycle, implementation mapping,
persona behavior, Terraform resources, and Word format each have named authorities.
Canonical-to-plugin drift is checked. The remaining risk is not duplicate section lists;
it is allowing explanatory documentation to silently become prescriptive. The current tests
and `AGENTS.md` review rules are the correct control.

### Baggage and cardinality

Revises [Baggage: how to decide what to carry](2026-09-18-architecture-review.md#baggage-how-to-decide-what-to-carry).

**Resolved as a design contract.** The budget remains six keys, 512 bytes total, and
64 bytes per value. Carrying, stamping, and metric-dimension promotion remain separate
decisions. `<org>.bt` is now a bounded propagated global tag used for Splunk APM Business
Transaction grouping, while `workflow.name` remains subordinate intent.

What remains to assess is real-estate validation: measured header sizes at gateways and
buses, observed cardinality after deployment, and whether every carried key still has a
named consumer. That belongs in the future verification run, not another design document.

### Multi-agent operation and handoffs

Revises [Multi-agent: what to parallelize, and what must stay serial](2026-09-18-architecture-review.md#multi-agent-what-to-parallelize-and-what-must-stay-serial).

**Substantially resolved.** Naming remains serialized through the accepted schema.
Implementation can fan out by repository under one unified work order, with one linked PR
per repository and a coordination PR. Analysis, implementation, and Terraform have explicit
branch and PR lifecycles.

The September recommendation that analysis automatically proceed into generation is no
longer accepted. Exact-commit acceptance is intentionally human: review and merge the
analysis PR, then invoke `/ob-generate accept <analysis> at <sha>`. Mechanical completeness
is necessary but does not authorize engineering work.

### Context engineering

Revises [Context engineering](2026-09-18-architecture-review.md#context-engineering).

**Most high-value work is resolved.**

- Agent files route to references and remain capped.
- The second customer-facing guide was removed.
- The wiki stores one note per subject and app-level work orders.
- Implementation loads an accepted work order, schema, and implementation map rather than
  inventing ownership from a monolithic document.
- Inputs, acceptance, and repository mapping are structured artifacts.

Still open:

- a first-class `evidence.json` ledger;
- a single machine-readable run-state artifact joining evidence, checklist, outputs, and
  unresolved decisions;
- explicit conditional-reference loading for targets with no browser or bus; and
- the CommonMark parser migration described in [Resolved design decisions](../design.md#resolved-design-decisions).

### Outcome learning

Revises [Reinforcement learning: build the grader first](2026-09-18-architecture-review.md#reinforcement-learning-build-the-grader-first).

**The grader and deterministic inputs exist; the outcome system does not.** Reviews report
defects by rubric row, implementation maps bind targets to code, and verification scripts
can reject drift. There is still no repository-level outcome record that aggregates schema
misses, empty dimensions, detector disarms, or reversed “Not in evidence” findings.

Decision: each anonymized outcome record is opened or updated as a GitHub issue in
[`cfallwell/obengineer`](https://github.com/cfallwell/obengineer/issues). Issues must contain
no customer name, production URL, tenant identifier, credential, or customer-specific
taxonomy. The issue should identify the rubric row or reference, source commit, outcome
class, measured result, and proposed specification change. Repeated instances update one
defect-class issue rather than creating customer-per-issue leakage.

This policy is now part of the deliverable-review contract, including anonymization,
deduplication, and an issue-ready fallback when GitHub write access is unavailable. A
deterministic issue helper, authentication profile, and the point in the future verification
run that invokes it still need implementation.

### Closing the loop

Revises [Closing the loop: analysis → recommendation → implementation → verification](2026-09-18-architecture-review.md#closing-the-loop-analysis--recommendation--implementation--verification).

**Still open.** There are deterministic artifact verifiers, contract checks, Terraform
plans, and manual proof requirements, but there is no `/ob-verify` run that executes the
accepted exit criteria against the tenant and records met, unmet, or unmeasurable.

This is now the highest-value architectural addition. It is the only way to distinguish a
complete-looking contract from one that actually improved the tenant's ability to answer
incident questions.

## Resolutions to the September open questions

Revises [Open questions for the humans](2026-09-18-architecture-review.md#open-questions-for-the-humans).

### 1. Entitlement: read before asking

**Decision: it should read it.** When the required Splunk integrations and API access are
available, analysis reads subscription usage, current/max MTS, MetricSet counts, and other
measurable tenant facts before asking a human. Measured values outrank stated values.

Not every commercial term is exposed by an API. Intake may still ask for order-form limits,
contractual entitlements, or values whose endpoint is unavailable, but it asks only for the
remaining gaps and labels them `stated`. The intake contract is now explicitly read-first;
the remaining assessment is endpoint coverage, minimum scopes, and reconciliation with
order-form values.

### 2. Outcome records: GitHub issues

**Decision: use issues in `cfallwell/obengineer`.** The issue is an anonymized engineering
outcome record, not an engagement artifact. The customer repository retains the detailed
evidence; the public project issue retains only the reusable defect class and proposed
change. See [Outcome learning](#outcome-learning) for privacy and deduplication requirements.

### 3. Personas: add on product request, after discovery

**Decision: three personas are defaults, not a ceiling.** If a product manager or other
stakeholder requests another persona, it can be added. Before changing reporting outputs or
Terraform, ask one numbered round of up to seven questions, stopping early when sufficient:

1. Who is the audience, and which decision must this view support?
2. What must it include that the Executive, SRE, and Engineer views do not?
3. What must it exclude so it is not an existing view with a new title?
4. Which transactions, workflows, SLIs/SLOs, metrics, and time horizons matter?
5. Which filters/groupings are needed, and are those dimensions affordable and permitted?
6. Which reporting outputs and Terraform artifacts are expected, in which environments?
7. Who owns acceptance, thresholds, access, cost, and maintenance?

The answers update the accepted contract, dashboard specification, Terraform module layout,
tests, and handover together. This protocol is now canonical in
[`persona-levels.md`](../../skills/references/persona-levels.md#adding-a-persona-on-request).

### 4. Run 5 tenant access: still relevant, and read-only

**Yes, it remains relevant.** Run 5 does not exist yet, but its access boundary must be
settled before implementation because credential scope shapes the design.

The verification run needs read access to:

- query Observability Cloud for tags, spans, MetricSets, dashboards, detectors, and SLOs;
- query Splunk Enterprise only across approved indexes for trace/log correlation;
- inspect ThousandEyes tests and results when those paths are in scope; and
- compare observed state with the accepted analysis commit, schema, implementation map,
  Terraform plan, and exit criteria.

It does **not** need tenant write access. Write access would make verification
self-fulfilling: a verifier could create the object it was meant to prove already existed,
hide drift, or alter a detector while measuring it. Failed criteria instead produce:

- a linked implementation work order when telemetry is missing;
- a new `/ob-terraform` plan when configuration is missing;
- an amendment when the contract is wrong; or
- an anonymized GitHub outcome issue when the defect is reusable.

Tenant remediation remains separated by human review. `/ob-terraform` plans and a human
applies. `/ob-implement` opens linked PRs and humans merge. The verification identity should
therefore have read-only product scopes and no apply, deploy, or detector-arm permission.

## What now needs assessment

Ordered by architectural leverage:

1. **Verification run contract.** Define `/ob-verify`, its read-only credentials, accepted
   inputs, queries, result schema, and how unmet criteria dispatch work without remediating.
2. **Outcome issue workflow.** Define authentication, anonymization, deduplication, issue
   fields, failure behavior, and whether issue creation requires a final human preview.
3. **Read-first entitlement flow.** Identify which facts are available from each Splunk API,
   the minimum read scopes, the fallback questions, and how measured values reconcile with
   order-form values.
4. **Evidence and run-state schema.** Decide whether `evidence.json` and `run-state.json`
   remain separate or become one provenance ledger consumed by analysis, generation, and
   verification.
5. **Parser migration.** Replace line parsing with a maintained CommonMark AST while proving
   Word output parity and updating the dependency contract atomically.
6. **Outcome metrics.** Define exact denominators and collection points for schema miss,
   dimension miss, detector disarm, and “Not in evidence” reversal rates.
7. **Conditional context loading.** Measure whether explicit browser/bus/language gates
   reduce context without hiding cross-cutting requirements.

The section-count question is not on this list. The current canonical structure is accepted,
and one tested authority owns it.

## Conclusion

The September architecture review succeeded at its most important job: it found that
duplication concealed a real contract defect. The repository now enforces the remedy.
Since then, the project has added durable memory, exact acceptance, security assessment,
multi-repository implementation mapping, plan-only Terraform, and much stronger verification
of its own artifacts.

The next architecture milestone is not another authoring feature. It is closing the loop:
read the tenant after implementation, prove or disprove the accepted exit criteria, and turn
reusable failures into anonymized issues that improve the specification.
