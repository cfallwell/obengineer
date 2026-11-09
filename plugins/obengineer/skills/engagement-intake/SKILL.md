---
name: engagement-intake
description: >-
  Collect and validate the human-supplied inputs every other skill depends on —
  artifacts and diagrams, front-end URLs, backend languages and buses, Splunk
  realm and tenancy, entitlement for pricing the recommendation, privacy regime,
  percentile standard, and the business context behind the engagement — current
  MTTx, incident volume, triage and tooling cost, revenue exposure, and the
  customer's own commentary on what hurts — into a single engagement-inputs.yaml.
  Guides the human on suggested inputs first. A live production site scan is
  required for whatever site this engagement names. Test and QA environments
  are not the scan. Optional traffic baselines (daily sessions, hourly log
  volume, infrastructure integrations) tighten the consumption prediction;
  unknown widens it. Asks which developer tools they use and matches that list
  to MCP servers and environment variable names already present. Asks only for
  what is missing, one short round of questions, and records `unknown` rather
  than guessing. Does not collect instrumentation scope. Use when the user types $engagement-intake,
  starts an engagement, says they have diagrams or a URL to analyze, asks what
  information you need, or when any other skill finds the inputs file absent or
  incomplete. A token, API key, or dummy test login may be submitted as a
  reference so the scan can see authenticated surfaces. Never stores the secret.
  Whatever was submitted is rotated when the analysis completes.
metadata:
  author: obengineer
  version: 0.1.0
  category: observability
---

# Engagement Intake — ask once, reuse everywhere

## Overview

Every run in this bundle needs the same facts: what the application is called, where
the diagrams are, which realm, which percentile, and what the customer is licensed
for. Asking for them inside each prompt produced three copies that drifted, and a
human who pasted the third prompt with the second prompt's answers still in it.

So the inputs live in one file — `engagement-inputs.yaml`, from
[`../../inputs/engagement-inputs.template.yaml`](../../inputs/engagement-inputs.template.yaml) —
and this skill is the only thing that writes it. Field-by-field meaning and the
consequence of leaving each blank:
[`../references/engagement-inputs.md`](../references/engagement-inputs.md).
Which MCP servers are mandatory, recommended, or used only when already present:
[`../references/mcp-servers.md`](../references/mcp-servers.md).

The design runs against **any site**. This file is that site. A URL, diagram, or
schema from a **different** site is not an input; if one is in the file, remove
it and say so. Previous scans of this site are inputs. Comparing them with the
current production scan is [`../references/incremental-runs.md`](../references/incremental-runs.md).

## The rule that makes this worth having

**Ask for what is missing. Never re-ask for what the file already answers, and never
ask for anything a scan can measure.**

A run that asks the human which router the application uses has given up on the job it
was hired for. Router, bundle order, competing agents, CSP, consent gating, and the
existing Splunk footprint are all *discoverable*, and asking about them converts
evidence into opinion. The intake exists for the facts no scan can reach: commercial
entitlement, who deploys what, which privacy regime applies, and what the customer is
trying to fix.

| Category | Who answers | Why |
|---|---|---|
| Composition, router, load order, competing agents, CSP, consent | The scan | Measurable. Asking invites a stale answer from memory. |
| Existing MetricSets, workflows, dashboards, tests | The tenant, via MCP if enabled, otherwise the human | Measurable in principle, often gated by access. |
| Entitlement, for pricing the recommendation | The human, from Org Metrics and the order form | Not in the application, not in the tenant's data plane. |
| Privacy regime, residency, deny-list additions | The human | A legal position, not a technical one. |
| Who deploys the front end and the Collector | The human | Determines whether Phase 0 is possible at all. |
| First journey and known pain | The human, optionally | The run can rank candidates; the human breaks ties. |
| Current MTTx, incident volume, triage and tooling cost, revenue exposure | The human | Nobody outside the business knows what an outage costs it, and a benchmark in its place is a guess with a citation. |
| Outage coverage, complaints, field performance | The public record, if research is permitted | Cheaper and more credible from the open record than from recollection. |

## Process

### Step 1 — Find or create the file

Look for `engagement-inputs.yaml` beside the deliverables (conventionally
`docs/observability/engagement-inputs.yaml`), then at the workspace root. If none
exists, copy the template and say so — the human should be able to see and edit the
file, not only answer questions into a chat that ends.

If the human attached a filled file or pasted values, load those first and treat the
questions as gap-filling. If that file names a site other than the one this
engagement is for, drop those values and tell the human they were not kept.

Before asking, look at the MCP servers already connected in this session.

- **Splunk Observability Cloud and Splunk Enterprise are mandatory.** If either is absent, the gap report says so and points at copying that entry from `plugins/obengineer/.mcp.optional.json` with the organisation's own command. Do not invent a command. Tenant facts gathered without them are `stated`, not `measured`.
- **Memory repository `.env`.** API keys for those two servers live in `.env`, copied from `templates/memory-repo/.env.template` in the toolkit. Tell the human to fill that file. Do not read the values into the inputs file. The variable names and the analyze pass are [`existing-telemetry.md`](../references/existing-telemetry.md).
- **Developer tools.** Ask which tools they use — examples of shape: Jira, GitHub, GitLab, Artifactory — and match the list to MCP servers already connected and to environment variable names already present. Record the server key or the variable name in `developer_tools`. Never read or store a value. Do not add a server that is not already connected. The procedure is [`mcp-servers.md`](../references/mcp-servers.md).
- **Jira, if present.** When a Jira server is already connected, read issue keys that match `outcomes.known_pain` and record the keys. Generating backlog issues is engineering's option after the contract exists, and only when they ask. Intake does not create those issues and does not start coding. When Jira is not connected, do not add it. The rule is [`mcp-servers.md`](../references/mcp-servers.md).
- **Repository hosts, if present.** When a GitHub, GitLab, or other repository MCP is already connected, match it to the named tool list. Do not choose `initial_scope` here, and do not adopt every repository it can reach. Scope authorization is the instrumentation phase.
- **Recommend, do not require,** the other servers in [`mcp-servers.md`](../references/mcp-servers.md): local OpenTelemetry tools, ThousandEyes when an off-box hop is in scope, and a cloud inventory MCP for whatever cloud this site runs on so analyze can generate the production diagram.

### Step 2 — Tell them what to bring, then ask once for the gaps

The first message has two parts. The guidance comes first, then the numbered gaps.

**Guidance, in substance:**

The design runs against whatever site this engagement names. Bring as much as you have. A live **production site scan is required**: the current production URL. Test and QA environments vary from production and are not the scan. Previous scans of this site are welcome; a scan of a different site is not. Diagrams you already have of this site are welcome. If you can grant read-only access to the production cloud environment, the run can generate the architecture diagram from that inventory — any cloud, no credential stored in the file. The only way to skip the scan is to write `no browser` and the reason.

Then the optional numbers, with this notice: **the more accurate the data, the tighter the consumption expectation.** Every one of them may be `unknown`. Unknown widens the range. It does not block the design, and it does not cap it.

- Daily average and peak sessions (RUM).
- Requests per minute, average and peak, and a typical spans-per-trace if they know it (APM).
- Hourly log volume, average and peak.
- Infrastructure metrics already coming from integrations: which integration, how many entities, roughly how many metrics each. Name the integration this site runs. Do not invent a vendor.

**Then the gaps**, in one message, numbered, each with the consequence of skipping it. A drip of single questions across a session is the failure mode this skill exists to remove.

Ask in this order, because early answers make later questions unnecessary:

1. **Application, customer, and date.** Without the name there is no filename. Do not ask for instrumentation scope. Engineering authorizes that after the contract exists.
2. **Developer tools.** The list they use. Examples of shape: Jira, GitHub, GitLab, Artifactory. Then match it. A miss is an open item, not a prompt for a token.
3. **Artifacts.** Diagrams, prior contract, prior schema, earlier scans of this site, house-style `.docx`. Say explicitly that a prior schema will be *extended* and its key names reused, never renamed for taste. Previous scans of this site are compared with the current production scan.
4. **Surfaces.** The production site scan. An empty production URL list is a gap, not a default. A test or QA URL does not fill it. Analysis access, when they have it: a token, an API key, or a dummy test login, each as a reference, never the secret. `unknown` is acceptable. Anything submitted is rotated when the analysis completes. The rule is [`engagement-inputs.md`](../references/engagement-inputs.md).
5. **Backends and the production cloud diagram.** Languages, deploy targets, buses, account boundaries, what terminates TLS, and whether production can be inventoried for a generated diagram.
6. **Tenancy.** Realm, org, environments. Identifiers only.
7. **Entitlement, then the optional traffic baseline.** The entitlement numbers in the table below, then daily sessions, hourly log volume, request rate, and infrastructure integrations. Say the accuracy notice once, not once per field. An empty integration list is unsupplied, the same as `unknown`.
8. **Constraints.** Privacy regime, residency, consent platform, change windows, who deploys.
9. **Outcomes.** Known pain, and whether they want to nominate the first journey.
10. **Business context.** The commentary and the numbers in Step 4.
11. **Public-record research.** Whether it is permitted, the brand terms to search, and their own status or incident history pages.

### Step 3 — Ask for entitlement as pricing, not as a limit

Ask for it plainly and say what it is for, because the reason has changed and the old
framing made people defensive: these numbers do not constrain the recommendation, they
**price** it. What implementing the contract will consume, and any overage, goes into a
separate document for the account team —
[`../references/entitlement-exposure.md`](../references/entitlement-exposure.md) — and the
recommendation itself is what the application needs either way.

Say that in one sentence before asking. A customer who thinks the numbers will be used to
shrink their design has a reason to withhold them; one who understands they buy a costed
plan does not.

| Ask | What it prices |
|---|---|
| Custom MTS included, and current consumption | Every proposed dimension, charged against real headroom rather than against a guess. |
| MMS slots remaining | Monitoring MetricSets are bounded, and a slot shortage is a feature that cannot be created rather than a bill. |
| Observed Troubleshooting MetricSet distinct-value peak, if they have one | A baseline the prediction compares against. Not a cap. Identity keys stay attribute-only either way. |
| RUM sessions per month; replay entitled | Sampling, and whether replay may be discussed at all. |
| Synthetics run quota and private locations | Test frequency and which locations the plan may assume. |
| Platform GB/day and retention | What goes to Splunk platform versus what stays in Observability Cloud. |
| ThousandEyes agent units and test slots | How many off-box hops can actually be covered. |

Two answers remain hard vetoes rather than pricing inputs, and they do shape the
recommendation: `session_replay_accepted_in_writing` and `log_observer_connect_entitled`.

If the human does not have the numbers, record `unknown`, note who would, and move on.
There is **no exposure document** only when entitlement is `unknown` throughout and
every traffic-baseline factor is unsupplied — neither `unknown` nor an empty
collection counts as supplied. A supplied baseline with no entitlement is still
written, as an expectation range. The rule is
[`../references/entitlement-exposure.md`](../references/entitlement-exposure.md).
The recommendation is written as though there is enough licensing, and the
deliverable says the budget was not supplied. Do not stall the run on a
procurement question, and do not invent a limit so that there is something to
design around.

Ask one more thing, once: **has the customer asked for a recommendation that fits inside
what they already own?** Only a yes sets `fit_to_entitlement: true`, and then cutting to fit
becomes the job and every cut is recorded.

### Step 4 — Ask for the business context, and take the prose

The section that makes a Business Value Realization section possible. Nobody outside the
business knows what an outage costs it, and an industry benchmark in place of their number
is a guess with a citation attached.

**Ask for the commentary first, and ask for it as prose.** "In your own words, what hurts
today — what breaks, who finds out first, and what it costs you when it does?" The answer
gets quoted in the deliverable, attributed to the role that gave it, and it is the one input
that cannot be reconstructed later.

Then the numbers, `unknown` freely accepted:

| Ask | What the value section can then say |
|---|---|
| MTTD / MTTA / MTTR, however they measure them | Where the incident time actually goes, and which instrumentation slice touches that stage |
| Incidents per month, Sev1s per quarter | The multiplier. A twenty-minute detection improvement is a rounding error at one incident a quarter |
| Responders per incident, fully loaded hourly cost | Triage cost per incident as arithmetic instead of assertion |
| Percentage of incidents customers report first | The number executives react to fastest, and the one a customer-facing SLI moves directly |
| Tools in use and annual tooling spend | Consolidation value, checked against the agents the scan actually found on the page |
| Revenue per hour online, orders per day, average order value, conversion rate | Exposure per outage minute, and the value of catching a checkout regression before a release |
| Named peak events and their dates | When the value is concentrated, which is what a phase plan should be aimed at |
| OpEx and revenue challenges, in prose | Which audience the section leads with, and the language the executive already uses |

Finally, **public-record research**: is it permitted, which brand terms and sub-brands to
search, and do they publish a status or incident history page. Say what it is for — the last
twelve months of outage coverage, complaints, and field performance make the value case rest
on something other than recollection — and accept `allowed: false` without argument.

Full field-by-field meaning:
[`../references/business-value.md`](../references/business-value.md).

### Step 5 — Validate before handing off

Refuse to proceed, and say which check failed, when:

- **A value looks like a credential.** Long random strings, anything matching a known token shape, `-----BEGIN`. Strip it, tell the human it was not stored, and ask for a `${ENV_VAR}` or a secret name. A login that is not a dummy test account is refused. When a reference was accepted, rotation on completion is required. The rule is [`engagement-inputs.md`](../references/engagement-inputs.md).
- **A referenced path does not exist.** A diagram in the file but not on disk becomes a phantom citation in the deliverable.
- **`standards.percentile` is not a single value.** One percentile, everywhere. Two percentiles in one contract means two definitions of "slow".
- **A URL is in `surfaces` but the human said there is no browser.** One of the two is wrong; ask which.
- **`production_urls` is empty and `front_end_scan_notes` is not `no browser` with a reason.** The production scan is required. A test or QA URL does not satisfy it. Ask for the production URL. Do not proceed by reusing a different site. Previous scans of this site stay.
- **`session_replay_entitled` is true but `session_replay_accepted_in_writing` is false.** Replay stays out of the recommendation until the cost and Core Web Vitals risk are accepted in writing.
- **A business figure arrived as a benchmark.** "Retail typically loses $X a minute" is not this customer's number. Record `unknown` and name the ask.
- **`fit_to_entitlement: true` with no entitlement numbers.** Nothing to fit to; either get the numbers or set it back to false.
- **`public_evidence.allowed: true` with no brand terms.** A search for the parent company finds the investor-relations record and misses the market where customers are complaining.

### Step 6 — Write the file and report the gaps

Write `engagement-inputs.yaml`, then print a short report: what was filled, what stayed
`unknown`, and which sections of the eventual deliverable each `unknown` will weaken.
That report is the seed of the guide's "Open items and assumptions" appendix — the two
should not be written twice.

## Warning signs

- **The run asks the human a question the scan already answered.** The evidence wins; correct the file from the measurement and note the disagreement.
- **An `unknown` silently becomes a number later in the run.** If the budget was assumed, every sentence that depends on it says so.
- **The business commentary got summarised into a bullet.** The quote is the value; a paraphrase reads as our characterisation of their problem and the executive stops recognising themselves in it.
- **Entitlement asked for as a constraint.** It prices the recommendation. Asking as though it caps the design invites a customer to withhold it.
- **Intake grows a field for something one skill wanted once.** The file is read by every run; a field that serves one paragraph belongs in that paragraph.
- **The file accumulates a credential because someone pasted a whole config.** The validator exists for exactly this. Never commit the filled file to a customer repository without checking.

## Non-goals

- Does not scan, measure, or infer anything about the application. That is `instrumentation-analyze`.
- Does not decide dimensions or compute the prediction, only records the optional baselines and the entitlement they are compared with. The formulas live in `cardinality-budget`.
- Does not store a credential value. A submitted token, API key, or dummy test login is a reference, and it is rotated when the analysis completes.
