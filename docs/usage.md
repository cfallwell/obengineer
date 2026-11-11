# Guided analysis and implementation

obengineer is a versioned workflow:

```text
start → analyze + wiki + work orders → review PR → accept and merge
                                                    ├─ implement Ready work orders
                                                    ├─ generate Terraform plan
                                                    └─ verify outcomes read-only
```

## Start

Run from the artifact repository:

```text
/ob-start
```

Within five seconds, before source, network, browser, API, or MCP discovery, the agent
asks one required question for the application name, an explicit production URL (or
`no browser: <reason>`), and what hurts today. Only after that answer does it discover
what source, the confirmed production surface, direct Splunk APIs, and connected MCP
tools can measure.

This five-second check covers the installed deterministic prefill/start executable
sequence and verifies output precedes instrumented network or process discovery.
Markdown slash-command parsing and the host model's first-token latency remain owned by
the host and cannot be guaranteed by repository code.

It then asks:

```text
Would you like to add more inputs to the analysis phase?

Suggested inputs include:

1. ...
2. ...

Reply yes and the numbers you want, with spaces between them.
Example: yes 1 3 4

Reply no to start with what I can already see.
```

Selected items are prompted one at a time. A blank skips one. The checked list uses
`[x]` for answered, `[ ]` for pending, and `[-]` for skipped. After selected answers the
agent returns to the optional-review question. `yes 1 3` never starts analysis; only an
explicit `no` at optional review authorizes it. The human never has to type `unknown` or
edit YAML. Filtered suggestions retain their canonical 1–10 numbers, so a list may show
`2` and `9` without renumbering them to `1` and `2`.

Every onboarding turn atomically updates ignored local state at
`.obengineer/run-context.json`. Allowlisted `.env` values prefill missing engagement
inputs. Raw token values and passwords are never copied; dummy access uses a
`${VAR}` password reference.

For optional read-only API access:

```bash
/path/to/obengineer/scripts/setup-splunk-access.sh
```

The script prompts in the terminal, writes local `.env`, and never prints the token.

## Analysis

After the explicit `no`, `/ob-start` automatically runs analysis V1. Independent
evidence sources run as six bounded jobs through the host with one concurrency slot
reserved for coordination. Repository tooling audits
result intervals but does not spawn workers. Naming and schema reconciliation happen
after evidence returns.

The analysis PR contains:

```text
docs/observability/analysis/<app>/V1/
docs/observability/analysis-contract.json
docs/observability/analysis-job-manifest.json
docs/observability/analysis-worker-results/
docs/observability/attribute-schema.json
docs/observability/implementation-map.json
docs/observability/provenance-ledger.json
docs/observability/verification-plan.json
wiki/apps/<app>/versions/V1/
```

The version wiki includes every proposed work order. The analysis landing page links all
detail and the work-order queue.

When ready:

```text
Please review PR #<number>.

When it is ready, reply yes to accept V1 and merge this PR.
Reply no to leave it open. Add review comments for changes.
```

When the PR becomes ready for review, the agent reads unresolved comments, commits
supported corrections, and asks again. It never accepts or merges without explicit `yes`.

Acceptance is bound to a deterministic content digest. The agent handles paths, commits,
and digests; the human does not copy a SHA. Acceptance makes dependency-free work orders
Ready and merges the reviewed PR.

## Review the result

After merge, the agent returns one host-native documentation link and concise next steps.
It does not paste the analysis into chat.

Navigation remains inside the host's side panel or native document surface:

- no browser;
- no localhost server;
- no high port;
- `[V1] [V2] ...` version links;
- breadcrumbs on every page; and
- relative links to all detail.

The long linked landing page includes version, status, next steps, changes, a substantive
summary for every linked review area, the observed architecture directly on the landing
page, and Priority Findings and Primary Use Cases previews. Its table of contents opens
separate side-panel views for:

1. changes in this version and next steps;
2. analysis summary;
3. architecture, technology, and current telemetry;
4. findings;
5. instrumentation strategy;
6. implementation path;
7. work-order queue;
8. use cases;
9. workflows;
10. business transactions;
11. shared signal contracts;
12. operations and verification; and
13. reference material.

Only applicable subjects receive pages. Suggested additions share one page. Useful missing
human inputs share one intake-recommendations page.

## Add or edit inputs

Run:

```text
/ob-add-inputs
```

The agent lists only useful unanswered inputs. Reply `yes 1 3`, answer each selected
prompt, review the checked list, then reply `no` to authorize V2 and its PR.

Run:

```text
/ob-edit-inputs
```

The agent lists supplied human-editable values with redacted current values. Reply
`yes 2 5`. Send a replacement or `clear`. Secret values display only as `configured`.
`clear` deterministically restores the template value and removes supplied provenance;
the literal word is never saved. Explicit default-valued answers remain checked across
restart. The edit automatically creates the next immutable version.

Earlier versions remain selectable and read-only. The accepted version is the only
executable work-order queue.

## Implement

After acceptance, the landing page identifies the first Ready work order:

```text
/ob-implement work-order:WO-001
```

Implementation verifies the accepted content digest and resolves the selected order from
the accepted version. It opens at most one linked PR per mapped repository plus a
coordination PR. It does not merge without explicit authorization.

Review, merge, and deploy the PRs. Evidence updates the work-order and touched wiki-note
statuses. Return to the queue for the next Ready order.

## Terraform

Run after acceptance:

```text
/ob-terraform
```

Terraform reads the same accepted schema and work-order strategy. It inventories and
imports existing objects where possible, formats, validates, and plans. Detectors begin
disabled. It never applies; a human reviews and applies.

## Verify

After application deployment and human Terraform apply:

```text
/ob-verify
```

Verification executes accepted criteria read-only. Results are met, unmet, or
unmeasurable. Unmet rows route to a work order, Terraform plan, contract amendment, or
human decision and give the exact next command.

## Optional Word summary

Word is not required. Request it explicitly or run `/ob-render` against the version's
summary source. It contains the analysis summary, architecture, findings, path, work-order
summary, and use cases and must remain under 20 pages. Deep detail remains in Markdown.
