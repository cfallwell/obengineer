# Engagement inputs — what each answer decides

Authoring reference for [`engagement-intake`](../engagement-intake/SKILL.md). The
template is [`../../inputs/engagement-inputs.template.yaml`](../../inputs/engagement-inputs.template.yaml).

This file exists so that a run can be told the inputs **by reference** rather than by
having them re-typed into a prompt. Prompts name the inputs file; they do not carry a
copy of the questions. When a question needs to change, it changes here and in the
template, and every run picks it up.

## Why an inputs file rather than prompt placeholders

Bracketed placeholders inside a prompt have three failure modes, all of which happened:

1. **They get pasted unfilled.** `Realm: [ ]` reaches the agent verbatim, and the agent either asks again or proceeds without it.
2. **They drift between prompts.** The same question appears in the analyze prompt and the guide prompt with different wording, so the two runs get different answers to what should be one fact.
3. **They are lost when the session ends.** The second run cannot see what the first was told, so the human answers twice and the deliverables disagree.

A file fixes all three: it is filled once, visible, diffable, and reviewable. It also
gives the engagement an artifact that outlives the chat.

## Sections, and what goes wrong when they are blank

| Section | Decides | Blank means |
|---|---|---|
| `engagement` | Filenames, document title, version on the deliverable | The run invents a name, and the next run invents a different one |
| `artifacts` | Whether the backend map is diagram-driven or guessed; whether an existing taxonomy is extended | Journeys get named from a product playbook instead of this application |
| `surfaces` | Whether there is a front-end scan at all, and whether authenticated pages can be reached | The scan covers only anonymous surfaces, and the checkout journey is missing |
| `backends` | Which SDK sections and which bus inject/extract subsections the guide must contain | The messaging boundary section is written as `Not in evidence` for a bus that exists |
| `tenancy` | Whether exit criteria can be phrased as queries a TAM can run | Exit criteria become assertions instead of checks |
| `entitlement` | Every dimension-versus-attribute-only decision, sampling, and what may be recommended at all | Cardinality guidance is generic advice; the customer discovers the cost after implementing |
| `constraints` | What is vetoed regardless of technical merit | The guide recommends something legal or platform ownership will reject |
| `outcomes` | Journey ranking when several candidates are equally instrumentable | The run picks a defensible journey that nobody asked for |

## Entitlement, in detail

Entitlement is the only section that cannot be measured from the application, and the
only one that turns cardinality from a preference into arithmetic.

### The numbers and where the human finds them

| Field | Where it comes from |
|---|---|
| `custom_mts_included` | The order form or subscription terms |
| `custom_mts_in_use` | Observability Cloud → Settings → **Subscription Usage** / Org Metrics |
| `hosts_licensed`, `containers_licensed` | Order form; usage on the same page |
| `traces_per_minute` | APM entitlement on the order form |
| `mms_slots_remaining` | Settings → **APM MetricSets**: count the Monitoring MetricSets already defined |
| `tms_cardinality_ceiling` | Not on any page. It is a number the customer agrees to; propose one and get it accepted. |
| `sessions_per_month` (RUM) | Order form; usage in Subscription Usage |
| Synthetics run quota | Order form; Synthetics usage page |
| Platform `ingest_gb_per_day`, `retention_days` | The platform license and index definitions |
| ThousandEyes units and slots | Account Settings → usage |

### How the numbers become decisions

```
proposed MTS for one promotion
  = distinct values of the tag
  × number of metrics the tag is added to
  × number of services reporting them
```

Compare the sum of proposed promotions against
`custom_mts_included - custom_mts_in_use` and keep headroom for growth. The full
method, including the defaults to use when the numbers are `unknown`, is
[`../cardinality-budget/SKILL.md`](../cardinality-budget/SKILL.md).

Two entitlement answers are hard vetoes rather than budget inputs:

- **`session_replay_accepted_in_writing: false`** — always-on session replay stays out of the recommendation. Cost and the Core Web Vitals cost are both real, and "the customer seemed keen" is not acceptance.
- **`log_observer_connect_entitled: false`** — the guide must not specify Log Observer Connect panels. Reroute those questions to platform dashboards and say why in the portfolio mapping.

## Credentials

The file records **who holds** a credential, never its value. That applies to ingest
tokens, API tokens, and test-account passwords alike.

A test account is worth asking about, because an unauthenticated scan cannot see
checkout, subscription, or account journeys — which are usually the ones the engagement
is about. Record `held_by` and `rotates_after_run`, and have the human supply the
credential in the session rather than in the file. A credential in a file gets committed.

## Precedence when sources disagree

1. **Measured evidence** from a scan or the tenant. A router observed in the bundle beats a router named in the file.
2. **The inputs file**, for anything not measurable.
3. **Documented platform behaviour**, for how Splunk products work.
4. **Nothing else.** No industry assumption, no prior customer's journey names, no other document in the workspace unless it was attached as an input.

Record the disagreement when 1 overrides 2. A file that says Angular and a bundle that
says React is a finding about the customer's own documentation, and it belongs in the
deliverable.
