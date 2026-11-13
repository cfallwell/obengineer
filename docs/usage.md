# End-to-end usage

This page walks through one complete engagement: install, configure, analyze, review
and accept, implement, revise, plan Terraform, verify, and start the next version. The
[command reference](#command-reference) at the end lists every command with its
arguments and outputs.

Examples use the Cursor and Claude Code form, `/ob-start`. In Codex CLI type
`$ob-start`; in ChatGPT Desktop (with local execution) type `@ob-start`. Arguments are
the same on every host. Run every command from the artifact repository, not the toolkit
checkout.

## 1. Install

```bash
git clone https://github.com/cfallwell/obengineer.git
cd obengineer
python3 -m pip install PyYAML==6.0.3
./install.sh --cursor --project /path/to/memory-repo
```

Restart the host and open `/path/to/memory-repo`. See [Installation](installation.md)
for other hosts, user-scoped installs, and troubleshooting.

## 2. Configure `obconfig.yaml`

Run `/ob-start` once. On a fresh repository it creates the local config and stops:

```text
Created local obconfig.yaml. Edit it and rerun /ob-start.
```

Open `obconfig.yaml` and fill in at least `engagement.application`,
`engagement.deployment_environment`, and `surfaces.production_urls` (or
`surfaces.no_browser_reason`). The sections you will most often set are:

| Section | Set it when |
|---|---|
| `engagement` | Always: the application id appears in every generated path. |
| `surfaces` | Always: production URLs for the live read-only scan. |
| `artifacts` | You have diagrams, prior guides, or exports; drop them in `artifacts/`. |
| `splunk` | You want measured tenant evidence: read-only Observability Cloud and Platform tokens. |
| `initial_scope` | Before implementation: which repositories or folders may be changed. |
| `security_assessment` | You want `safe-active` checks or to opt out with `none`. |
| `constraints` | Privacy regimes, data residency, consent, PII additions, change windows. |
| `developer_tools` | You want Jira tickets alongside work orders. |

Field meanings and defaults are in [`obconfig.yaml.template`](../obconfig.yaml.template);
[Configuration](configuration.md) explains each section with examples.

## 3. Run `/ob-start` and read the summary

```text
/ob-start
```

The command validates the file. If something is wrong it names the position and asks:

```text
obconfig.yaml is invalid at line 12, column 3: <redacted reason>. Repair it now? (yes/no)
```

Reply `yes` to apply a safe repair (a backup is written first) or `no` to fix it
yourself. When the file is valid, it hashes every file in `artifacts/` and prints a
redacted summary, for example:

```text
Configuration summary (redacted)
Application: storefront
Deployment environment: production
Production URLs: 1
Artifacts: artifacts — 4 files, tree 3f1c9a0b7d2e, delta +4 ~0 -0
Security: passive; 0 authorized origins
Observability Cloud: realm us1; token configured
Splunk Platform: host not configured; token not configured; 0 indexes
Dummy login: not configured
Constraints: 1 privacy, 0 PII additions, 0 competing agents
Percentile: p90
First journey: evidence-ranked
Direct APIs: Observability available, Platform not configured

Proceed with analysis using this configuration? (yes/no)
```

Check that the application, URL count, artifact count, and tenant access match what you
intended. Only the exact replies `yes` and `no` are accepted; anything else repeats the
question. `no` stops with no network activity.

## 4. Proceed: the analysis runs

Reply `yes`. The agent then, without further questions:

1. collects evidence in six parallel workstreams: the live production pages, source and
   dependencies, supplied artifacts, Observability Cloud, Splunk Platform with cloud and
   messaging boundaries, and public research plus authorized security checks;
2. writes analysis version `V<N>` (V1 on the first run) and its wiki, including every
   work order;
3. validates links, schema, mapping, ledger, and work-order structure; and
4. commits on branch `analysis-<app>-v<n>` and opens one pull request.

A standard run targets about 20 minutes and posts progress at least once a minute. If
evidence is limited or quality checks still fail after one repair, the PR stays a draft
and is labelled a degraded draft.

Files written:

```text
docs/observability/analysis/<app>/V<N>/index.md      landing page and linked detail pages
docs/observability/analysis-contract.json            canonical analysis contract
docs/observability/attribute-schema.json             allowed attributes and dimensions
docs/observability/implementation-map.json           work order → repositories and paths
docs/observability/provenance-ledger.json            every fact's source and label
docs/observability/verification-plan.json            read-only exit criteria
wiki/apps/<app>/versions/V<N>/                       agent wiki and all work orders
```

`obconfig.yaml` and `.obengineer/` are never committed.

## 5. Review the PR in the side panel

The agent replies with one documentation link and next steps, not the analysis itself:

```text
Please review PR #42.

When it is ready, reply `yes` to accept V1 and merge this PR.
Reply `no` to leave it open. Add review comments for changes.
```

Open `docs/observability/analysis/<app>/V<N>/index.md` in the host's Markdown side panel.
Every page uses relative links and a breadcrumb; no browser or local server is needed.
Review in this order:

1. **Architecture summary** on the landing page: does it match the real system?
2. **Findings**: each has evidence, confidence, impact, and its remediation work orders.
3. **Implementation path** and **Work orders**: foundation orders first, then each use
   case with its subordinate orders.
4. **Use cases**, then their **workflows** and **business transactions**.

Leave review comments on the PR for corrections. When the PR is marked ready for review,
the agent reads unresolved comments, commits supported corrections, reports what it
changed, and asks for acceptance again.

If the analysis is wrong because an input was wrong, do not accept it. Edit
`obconfig.yaml` or `artifacts/` and run `/ob-analyze` to produce the next version (see
[Start the next version](#13-start-the-next-version)).

## 6. Accept with `yes`

```text
Do you accept V1 and want me to merge this PR?
yes
```

An explicit `yes` makes the agent:

1. mark dependency-free foundation work orders `ready`;
2. compute a SHA-256 content digest over the version's analysis pages, contract, schema,
   map, sealed ledger, verification plan, and wiki snapshot;
3. write `docs/observability/analysis/<app>/V<N>/acceptance.yaml`, commit it to the PR,
   and merge using the repository's merge strategy.

You never copy a commit SHA or provide a name. `no` leaves the PR open. The handoff then
names the first Ready work order and the exact command, for example
`/ob-implement work-order:WO-001`.

## 7. Implement foundation work orders first

Foundation work orders are prerequisites taken from findings and recommendations, not
from use cases: for example, the deterministic contract checks that keep the accepted
schema enforced in CI, fixing the RUM agent so it loads and initializes before the
front-end framework (Angular, React, Vue, Next.js) bootstraps, and moving RUM snippet
injection to the CDN edge. When the application has a web front-end, the foundation
section of the analysis links the CDN-specific injection reference for the CDN it found
(Fastly today, in [`cdn/fastly.md`](../skills/references/cdn/fastly.md); other CDNs are
pending and fall back to the [CDN index](../skills/references/cdn/README.md)). There are
at most about ten foundation orders, and they have no subordinate work orders.

Before running implementation, set `initial_scope.authorized` in `obconfig.yaml`; with
the default `unknown`, `/ob-implement` stops and asks engineering for scope.

```text
/ob-implement work-order:WO-001
```

The agent verifies `acceptance.yaml` against the digest, creates
`wiki/apps/<app>/implementation/V<N>/state.yaml` on first use, and runs the gate. It then
opens one PR per mapped application repository, limited to authorized paths, plus one
coordination PR in the artifact repository. Each PR is titled
`obs(<work-order-id>): <target> — <imperative>` and links its siblings. Review, merge,
and deploy those PRs; once you give deployment proof, the agent records the status
(`in-progress`, `implemented`, or `verified`) and the PR URLs in `state.yaml` and names
the next Ready order.

### Foundation gate

Every non-foundation order stays blocked until all foundation work orders are
implemented or verified. Running one too early returns, for example:

```text
"runnable": false,
"reason": "foundation work orders incomplete: ['WO-002', 'WO-003']"
```

A foundation order that depends on another foundation order waits for that one.

## 8. Implement use cases, workflows, business transactions, and custom code in any order

Once the foundation is complete, every other order is released. Pick whatever the team
needs next:

```text
/ob-implement use-case:checkout                    # runs the use case's next unimplemented subordinate
/ob-implement workflow:web.cart.submit
/ob-implement business-transaction:checkout
/ob-implement detector:checkout-silent-outage
/ob-implement alert-condition:checkout-error-burn
/ob-implement dashboard:checkout-sre
/ob-implement custom-code:<id>
```

Each selector must resolve to exactly one Ready work order in the accepted version;
zero or several matches stop with the candidates listed. With no selector, the first
Ready order in display order runs. One invocation implements one work order.
`use-case:<id>` picks the next unimplemented subordinate in the order workflow, business
transaction, detector, alert condition, dashboard, custom code.

## 9. Revise a work order without a new version

SREs and engineers can change a subordinate work order after acceptance: rename spans
or attributes, add or remove attributes, add spans, or adjust a detector or alert
condition.

```text
/ob-revise work-order:WO-014
```

The agent asks what should change, the reason, and the requester's role (SRE,
engineering, or other; never a name). It writes a change file like:

```yaml
reason: Align with the team's span naming convention.
requested_by_role: sre
changes:
  attributes:
    add: [checkout.payment_method]
    rename:
      - {from: cart.total, to: checkout.cart_total}
  spans:
    add: [web.checkout.validate]
```

It records revision R2 (then R3, and so on) at
`wiki/apps/<app>/implementation/V<N>/revisions/<WO-id>/R<k>.md`, chained by SHA-256 to the
previous revision, updates `state.yaml`, and opens one PR in the artifact repository.
Reply `yes` to merge it. The accepted analysis and its digest are untouched, so no new
version is created. Attribute additions that appear in the schema's deny list are
rejected.

Foundation and use-case orders cannot be revised. To change those, edit
`obconfig.yaml` or `artifacts/` and run `/ob-analyze` for a new version. A use case
changes through its subordinate orders, which are revisable.

## 10. Re-implement a changed order

Revising an `implemented` or `verified` order sets it to `changed`. Implemented,
verified, and changed orders run again only with the explicit override:

```text
/ob-implement work-order:WO-014 reimplement
```

Without `reimplement` the gate refuses with
`work order is changed; pass --reimplement to run it again`.

## 11. Plan Terraform with `/ob-terraform`

```text
/ob-terraform
```

This can run in parallel with implementation. The agent verifies acceptance, imports
existing tenant objects rather than duplicating them, and writes:

```text
terraform/apps/<app>/modules/executive/     application rollup: SLOs, KPI tiles, one dashboard group
terraform/apps/<app>/modules/sre/           golden signals, detectors, muting rules, uptime checks
terraform/apps/<app>/modules/engineer/      step latency, Tag Spotlight, log views, data links
terraform/apps/<app>/modules/platform/      indexes, HEC, trace_id extraction, saved searches
terraform/apps/<app>/environments/<env>/    one workspace per environment
terraform/portfolio/                        leadership dashboard across every application
```

It runs `terraform fmt`, `validate`, and `plan` (or reports "schema-checked" when no
credentials are available) and hands over the plan. It never runs `apply`. Detectors are
generated with `disabled = true` until their signals are verified, and tokens are
sensitive variables, never literals in `.tf` or `.tfvars`. A human applies from
`terraform/apps/<app>/environments/<env>/`.

## 12. Verify with `/ob-verify`

After implementation is deployed and Terraform is applied:

```text
/ob-verify
```

The agent checks the acceptance record, `verification-plan.json`, and the ledger, then
runs each criterion read-only against the tenant. It writes:

```text
docs/observability/verification/verification-<app>-<timestamp>.json
docs/observability/verification/verification-<app>-<timestamp>.md
```

Each criterion is `met`, `unmet`, or `unmeasurable`. Every `unmet` row gives the
expected and observed values, the remediation route (an implementation work order, a
Terraform change, a contract amendment, or a human owner), the exact next command, and
how to recheck. In CI, an `unmet` result fails the job and is reported in the job
summary (see [Continuous integration](ci.md#scheduled-runs)). Verification never changes
the tenant.

## 13. Start the next version

`/ob-start` is the first-run command: it creates `obconfig.yaml` and runs the first
analysis. Every later analysis starts with `/ob-analyze`. When evidence or inputs change
(new artifacts, tenant access added, a new constraint, a new feature shipped), edit
`obconfig.yaml` or `artifacts/` and run:

```text
/ob-analyze
```

`/ob-analyze` validates the file, prints the same redacted summary with the artifact
delta, and asks `Proceed with analysis using this configuration? (yes/no)` itself. `yes`
produces `V<N+1>` in its own directory and PR; `no` stops with no network activity.
Accepted names and finding ids are reused, and the new version opens with
`Changes in this version`. Earlier versions stay readable and unchanged; only the
accepted version's work orders can be implemented.

To run this loop for every feature release, with contract checks on each pull request,
see [Continuous integration](ci.md).

## Command reference

| Command | Arguments | What it does | Writes |
|---|---|---|---|
| `/ob-start` | none | First run only. Creates `obconfig.yaml`, then validates it, shows the redacted summary, asks to proceed, and runs the first analysis. | `obconfig.yaml` on the first invocation; then everything `/ob-analyze` writes. |
| `/ob-analyze` | none | Every later analysis. Validates `obconfig.yaml` and `artifacts/`, shows the redacted summary, asks `Proceed with analysis using this configuration? (yes/no)`, and on `yes` runs the next version. | `docs/observability/analysis/<app>/V<N>/`, `docs/observability/*.json`, `wiki/apps/<app>/versions/V<N>/`, one PR; `acceptance.yaml` after `yes`. |
| `/ob-implement` | `<selector> [reimplement]`. Selectors: `work-order:`, `use-case:`, `workflow:`, `business-transaction:`, `detector:`, `alert-condition:`, `dashboard:`, `custom-code:`, `objective:`, `config:` | Implements one Ready work order after the foundation gate. | One PR per mapped repository plus a coordination PR; `wiki/apps/<app>/implementation/V<N>/state.yaml`. |
| `/ob-revise` | `work-order:<id>` (or `workflow:`, `business-transaction:`, `detector:`, `alert-condition:`, `dashboard:`, `custom-code:`) | Revises one subordinate work order in the accepted version. | `wiki/apps/<app>/implementation/V<N>/revisions/<WO-id>/R<k>.md`, `state.yaml`, one PR. |
| `/ob-terraform` | none | Generates a Terraform plan from the accepted version. Never applies. | `terraform/apps/<app>/`, `terraform/portfolio/`, a plan and handover. |
| `/ob-verify` | none | Runs the accepted exit criteria read-only and routes remediation. | `docs/observability/verification/verification-<app>-<timestamp>.{json,md}`, ledger entries. |
| `/ob-review` | optional version, default latest | Grades an analysis version and its wiki: links, breadcrumbs, schema, map, ledger, verification plan, work orders, credential safety. | A defect report in chat (rule, file, line, consequence, smallest repair). Changes nothing. |
| `/ob-render` | optional version | Renders the optional Word summary under 20 pages. | `docs/observability/analysis/<app>/V<N>/<App>-Summary.docx` |

## Common failures

| Symptom | Fix |
|---|---|
| `/ob-start` or `/ob-analyze` keeps repeating the proceed question. | Only `yes` or `no` is accepted, exactly. |
| `/ob-analyze` tells you to run `/ob-start` first. | `obconfig.yaml` does not exist yet. Run `/ob-start` once to create it and produce `V1`. |
| `/ob-implement` says the acceptance digest does not match. | An accepted file changed after acceptance. Revert it, or run `/ob-analyze` for a new version. |
| `/ob-implement` stops and asks for scope. | Set `initial_scope.authorized` to `full`, `repositories`, or `parent_folders`. |
| `/ob-implement` reports `foundation work orders incomplete`. | Implement the listed foundation orders first, or record their status once deployed. |
| A selector matches zero or several work orders. | Use `work-order:<id>` from the work-order queue in the wiki. |
| A work order is `blocked` with an unresolved repository mapping. | Add the repository remote and authorized paths (listed on the Intake recommendations page) to `obconfig.yaml` and run `/ob-analyze`. |
| `/ob-revise` refuses the order. | Foundation and use-case orders, and orders in a version accepted before work-order kinds existed, are not revisable; change `obconfig.yaml` or `artifacts/` and run `/ob-analyze` instead. |
| `/ob-terraform` refuses a chart grouping. | The key is attribute-only in the schema. Use a dimension-eligible key, or change the schema in a new version. |
| `/ob-verify` reports `unmeasurable`. | Access or evidence is missing; the row names what to configure. |
