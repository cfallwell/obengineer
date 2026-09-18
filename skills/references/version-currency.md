# Version currency — designing against what exists now, not what existed then

Every recommendation this project makes depends on a moving part with a version number. A
guide written against one collector release and applied two years later is not merely dated:
it recommends a processor that has been renamed, an SDK method that has moved, a Terraform
resource that no longer exists. The failure looks like an agent bug and costs a day to trace.

So versions are **recorded, checked, and diffed** — recorded when a run produces a design,
checked when a later run touches it, diffed into an upgrade path the agents act on.

## What moves

| Component | Where its version matters | Recorded as |
|---|---|---|
| **OpenTelemetry semantic conventions** | Attribute names. `http.method` became `http.request.method`; a contract naming the old one produces spans that no built-in chart matches | `semconv` |
| **OTel SDK, per in-scope language** | The `SpanProcessor` interface, the baggage API, propagator construction | `sdk.<language>` |
| **Splunk RUM browser agent** | `init` options, `setGlobalAttributes`, which instrumentations exist and their defaults | `rum_agent` |
| **Splunk distribution of the OTel Collector** | Which processors exist, OTTL syntax, config schema. OTTL grammar has changed shape across releases | `collector` |
| **Splunk language agents / distros** | Auto-instrumentation coverage and the environment variables that configure it | `distro.<language>` |
| **Terraform providers** | Resource names and arguments. See [`splunk-terraform-providers.md`](splunk-terraform-providers.md) | `tf.signalfx`, `tf.synthetics`, `tf.splunk` |
| **Terraform itself** | A provider major can raise the floor — signalfx 10 requires Terraform 1.11 | `terraform` |
| **This bundle** | Which version of the rules the design was produced under, so a rule change is attributable | `obengineer` |

## Where it is recorded

`wiki/<Customer>/<app>/meta/versions.md`, as a table with a **provenance** column, because
"how do you know" is the question that matters when a number turns out to be wrong:

```markdown
| Component | Version | Checked | Provenance |
|---|---|---|---|
| semconv | 1.27.0 | 2026-09-18 | pinned in the contract; upstream latest at time of run |
| sdk.node | 1.26.0 | 2026-09-18 | `package.json` in the target repo |
| rum_agent | 0.20.3 | 2026-09-18 | observed in the served bundle |
| collector | 0.108.0 | 2026-09-18 | customer-reported; not verified against the running pod |
| tf.signalfx | 9.34.0 | 2026-09-18 | registry, cross-checked against the provider resource map |
| obengineer | 0.1.0 | 2026-09-18 | bundle manifest |
```

`unknown` is a legitimate value and is better than a guess: a recorded `unknown` gets
resolved on the next run, while a wrong number gets built on. What is **not** acceptable is
an absent row — an unlisted component is one nobody will check.

The document repeats these in `### Document control and evidence basis`, so a reader holding
only the `.docx` can tell what it was written against.

## Checking on a later run

Three questions, in order, and each has a defined answer when the check cannot be performed:

1. **What is recorded?** Read `meta/versions.md`. No file means this is a first run: record and move on.
2. **What is current?** Determine the current version from the authoritative source for each component — the registry for providers, the release feed for the collector and SDKs, the served bundle for the RUM agent, the target repository's manifests for SDK pins. Where the environment has no network access, say so per component and mark it `unverified this run` rather than reusing the recorded number as though it were confirmed. A stale check silently presented as current is worse than a skipped one.
3. **What changed, and does it break anything we recommended?** Only this third question is expensive, and it is scoped: compare against the design, not against the changelog. A release that renamed a processor the contract does not use is not a finding.

A version bump is reportable when it touches something the design names. Three classes:

| Class | Example | Consequence |
|---|---|---|
| **Breaking** | A resource type removed; a semconv attribute renamed; a config key relocated | Named in the document, scheduled, and blocking for the affected slice |
| **Behavioural** | A default changed — an instrumentation now on by default, a sampling default altered | Named, because it changes data volume or cardinality without any code change |
| **Additive** | New processor, new resource, new instrumentation | Mentioned only where it would simplify something the design does the hard way |

## The upgrade path

A detected breaking change produces a **note the agents consume**, not a paragraph the human
is left to act on. It goes in `meta/versions.md` under `## Upgrade path`, one entry per
change, and it must be specific enough to execute:

```markdown
### semconv 1.24 → 1.27 — HTTP attribute rename

- **Breaks:** `contract/cross-cutting.md` and every detector grouped on `http.method`
- **Affected notes:** [[cross-cutting]], [[checkout.order.submit]], [[detector-checkout-error-rate]]
- **Action for the implementer agent:** rename `http.method` → `http.request.method` in the
  shared library and the OTTL derive; keep both for one release with the old key marked
  deprecated, because dashboards and detectors cut over on a different schedule from code
- **Action for the as-code agent:** update `group_by` in the affected detectors after the
  dual-write release is deployed, not before
- **Verification:** Tag Spotlight shows both keys during the overlap, then only the new one
- **Status:** open
```

Two things make this work. It names the **notes** affected, so scope is a lookup rather than
a judgement. And it splits the code action from the configuration action with an ordering
between them, because the failure mode of a rename is not the rename — it is a dashboard
cutting over before the data does, which reads as an outage.

Each subsequent analysis document **calls out open upgrade-path entries in
`Changes since v<N-1>`**, with their age. An upgrade path that has been open for three runs is
itself a finding.

## Rules

- **Record the version, not "latest".** "Latest" is not a version; it is a timestamp nobody wrote down.
- **Pin what you recommend.** A Terraform provider, a collector image, an SDK — unpinned, the design is untestable and the next `init` is an unplanned upgrade.
- **Never present an unverified version as verified.** Say which source answered and which did not.
- **Do not chase a bump for its own sake.** An upgrade with no consequence for this design is noise, and noise trains people to skip the section.
- **A version claim in the document is a claim about the target too.** "Splunk RUM agent 0.20.3" observed in the served bundle is evidence; the same string taken from a customer's slide is hearsay, and the provenance column exists to keep them apart.

## Warning signs

- **A design with no recorded versions.** Every later run has to re-derive them and cannot tell what changed.
- **All rows checked the same day, every run, including the ones with no network access.** Someone is copying the date forward.
- **An upgrade path with no verification step.** It will be marked done without anyone knowing whether it worked.
- **A breaking change recorded as a document paragraph and nowhere else.** The agents do not read the document; they read the wiki.
- **Provider pins in the generated Terraform that disagree with `meta/versions.md`.** One of the two is lying, and the plan will tell you which.
