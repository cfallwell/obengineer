---
name: deliverable-review
description: >-
  Review a versioned obengineer analysis site and its matching wiki before a
  human sees it: navigation, evidence, findings, strategy, use cases, workflows,
  transactions, signal contracts, work orders, verification, optional Word
  summary, and credential safety. Use for $deliverable-review, /ob-review, or a
  request to grade an analysis or wiki.
metadata:
  author: obengineer
  version: 0.3.0
  category: observability
---

# Analysis and wiki review

Review is read-only and independent from authoring. Report every defect with page, line,
rule, consequence, and the smallest repair. Do not silently fix it.

## Authorities

- [`../references/analysis-site.md`](../references/analysis-site.md)
- [`../references/agent-wiki.md`](../references/agent-wiki.md)
- [`../references/critical-findings.md`](../references/critical-findings.md)
- [`../references/security-assessment.md`](../references/security-assessment.md)
- [`../references/implementation-work-orders.md`](../references/implementation-work-orders.md)
- [`../references/provenance-ledger.md`](../references/provenance-ledger.md)

The authorities win over explanatory docs.

## Grade the analysis site

Fail when:

- `[V<N>]` labels are not uppercase or a selected old version links mutable current detail;
- a detail page lacks a breadcrumb to Analysis and its parent index;
- any landing-page object lacks a detail link;
- the landing page omits next steps, architecture, findings, strategy, path, work orders,
  use cases, workflows, transactions, contracts, operations, or reference;
- the summary does not represent the strategy;
- a finding lacks evidence, impact, decision, affected objects/work orders, or verification;
- use cases do not lead workflows, or workflows do not lead transactions;
- a conditional subject has an empty page instead of being absent;
- useful future items are scattered instead of listed on Suggested additions;
- missing human inputs are required as `unknown` instead of listed on Intake recommendations;
- a web server, browser action, localhost URL, or high-port preview is required;
- chat handoff pastes detail instead of linking the host-native side view; or
- a credential-shaped value appears.

## Grade the strategy

Check that applicable browser, backend, messaging, collector, metrics, logs, and operations
layers are complete. Cross-Cutting Attributes and Baggage Propagation has its applicable
provider, allowlisted `SpanProcessor.onStart`, identity write, backend propagator, and bus
inject/extract patterns. Every baggage key has a consumer. Every metric dimension has
cardinality arithmetic. Every detector has a threshold. Every objective has an error
budget. Every join is continue trace, span link, or attribute pivot.

## Grade the wiki and work orders

Run `instrumentation-wiki/scripts/verify_wiki.py` for each service. Then judge what the
script cannot:

- no analysis section is duplicated verbatim;
- current statuses agree with code and deployment evidence;
- every work order links findings, use cases, workflows, transactions, contracts,
  repository legs, dependencies, acceptance evidence, and verification criteria;
- every linked object points back to its work order;
- dependency-free orders are proposed before acceptance and Ready after it;
- dependent orders are Blocked until proof satisfies dependencies; and
- no named engineer, owner, or accepter is required.

## Optional Word summary

If no `.docx` was requested, absence passes. If requested, apply
[`../references/document-template.md`](../references/document-template.md): generated from
the current version, fewer than 20 pages, summary only, and verified. A long Word artifact
or one that carries deep detail fails.

## Result

Return `PASS` only when there are no defects. Otherwise return a numbered defect list.
Analysis cannot become ready for review until blocking defects are repaired.
