# How obengineer operates

obengineer is not a conventional application with one long-running process. It is a
versioned set of agent commands, operating contracts, skills, references, validators,
and renderers. The host model performs the investigation and authoring; repository
files constrain what it reads, what it may change, what it must produce, and how the
result is verified.

## Runtime model

An invocation follows this path:

```text
host command
  → command entry point under commands/
  → agent definition and run contract
  → task-specific skills
  → canonical references and engagement inputs
  → workspace artifacts
  → deterministic validators
```

For example, `/ob-analyze` does not contain the analysis procedure itself. It:

1. loads the instrumentation architect agent definition;
2. requires `docs/observability/engagement-inputs.yaml`;
3. determines whether this is a first or delta run;
4. delegates to `prompts/01-analyze-application.md`;
5. invokes analysis, baggage, cardinality, rendering, and review skills; and
6. requires named output files and a successful render verification.

This indirection keeps a short command stable while deeper behavior remains reviewable
in dedicated source files.

## Repository components

| Path | Role |
|---|---|
| `commands/` | User-facing slash-command entry points. |
| `agents/` | Always-on operating doctrine and boundaries for architect, implementer, and Terraform roles. |
| `prompts/` | Ordered run contracts for analysis, wiki creation, implementation, and Terraform generation. |
| `skills/` | Canonical task procedures and supporting scripts. |
| `skills/references/` | Shared specifications used by several skills. |
| `inputs/` | Complete engagement input schema. |
| `scripts/install.py` | Host installer and manifest-based removal. |
| `plugins/obengineer/` | Self-contained distribution bundle for plugin hosts. |
| `.cursor/skills/`, `.agents/skills/` | Generated links to canonical skills for repository-local host discovery. |
| `tests/` and skill `tests/` | Contract, packaging, renderer, and wiki verification tests. |

`skills/` is the source for skill behavior. The plugin copies exist because an installed
bundle cannot assume the original repository remains reachable. Maintainers update
canonical skills and run `make sync-plugin-skills`; hand-editing plugin copies creates
drift and is rejected by `make check`.

## How installation wires a host

The installer selects one or more host layouts. For each host it:

1. enumerates every `skills/*/SKILL.md` directory and shared reference directory;
2. symlinks those directories into the selected host by default, or copies them with
   `--copy`;
3. copies every `commands/*.md` file into the host command directory;
4. replaces `{{OBENGINEER_ROOT}}` in each command with the absolute toolkit path; and
5. writes `.obengineer-install.json` with every created path.

Commands are copied, even in symlink mode, because they contain the resolved root. Skills
are linked by default so canonical edits are immediately visible. Uninstall reads only
the manifest and removes only paths it recorded.

The Claude Code plugin is different: it carries agents, prompts, skills, hooks, and MCP
metadata as a self-contained bundle. Its generated copies are kept synchronized with
the same canonical sources.

## Authorities and conflict resolution

obengineer follows “one authority per fact.” Important examples:

| Fact | Authority |
|---|---|
| Engagement input fields | `inputs/engagement-inputs.template.yaml` |
| Analysis section order and completeness | `skills/references/document-template.md` |
| Wiki tree, frontmatter, and host pointers | `skills/references/agent-wiki.md` |
| Cross-cutting attribute patterns | `skills/references/cross-cutting-attributes.md` |
| Baggage key and byte budgets | `skills/references/baggage-budget.md` |
| Platform selection behavior | `skills/references/portfolio-decision-engine.md` |
| Terraform resource names | `skills/references/splunk-terraform-providers.md` |
| Word layout | `skills/customer-doc-render/references/document-format.json` |

Agent files route to these references instead of restating them. Tests guard important
requirements such as the mandatory cross-cutting section and exact document-section
authority.

Explanatory pages in `docs/` describe the workflow but do not supersede these contracts.

## Evidence model

obengineer separates facts into four classes:

- **measured** — observed from source, a production scan, or a tenant query;
- **stated** — supplied by a human or engagement input;
- **public** — cited public evidence from the configured research window; and
- **derived** — arithmetic shown from measured, stated, or public inputs.

Measured evidence wins when it conflicts with a stated description. The conflict is
recorded because stale customer documentation is itself useful evidence. Unknown facts
remain unknown; the system does not fill them with industry benchmarks or examples from
another engagement.

Examples in canonical references describe shape with placeholders such as `<app>` and
`<service>`. They are not proposed taxonomy.

## State and memory

obengineer stores state in the artifact repository rather than in a chat session:

- `engagement-inputs.yaml` stores human-supplied facts once;
- the analysis is the accepted customer contract;
- `attribute-schema.json` is the machine-readable attribute and dimension contract;
- the wiki stores one subject per note for targeted retrieval;
- work orders define implementation slices;
- `meta/versions.md` records component versions and provenance;
- `meta/run-log.md` records each analysis run;
- `meta/decisions.md` records accepted and rejected decisions; and
- host pointer files tell future agents to load the index and only relevant notes.

This design makes completed runs inspectable and diffable. Acceptance itself is not stored
before the wiki run: the human must explicitly reassert acceptance when `/ob-wiki` starts.
The wiki then records the accepted and rejected decisions durably.

## Analysis operation

### 1. Establish inputs and run type

Analysis first validates engagement inputs. It then checks for an existing service wiki:

- no wiki means a first full analysis;
- a wiki with run-log entries means a delta;
- a rewritten application requires an explicitly declared re-baseline and archival of
  the old wiki.

On a delta, accepted names, finding IDs, prior decisions, and version history are loaded
before scanning. Reading them afterward would let the new scan invent names that already
have code and dashboards attached.

### 2. Collect evidence

The run combines:

- static application source and configuration;
- the current production front end;
- supplied architecture diagrams and narratives;
- backend, gateway, cloud, and message-bus boundaries;
- existing Observability Cloud and Enterprise data;
- optional ThousandEyes and cloud inventory;
- customer-stated constraints and business context; and
- permitted public evidence.

Production front-end analysis considers load order, provider initialization, competing
RUM/EUM agents, routing, CSP, consent, browser-to-backend continuity, and whether HTTP
success pages contain valid content. Tenant inventory is bounded by configured MCP
servers and approved Enterprise indexes.

An unavailable source becomes “Not in evidence” with the information needed to resolve
it. It is not silently converted into a claim.

### 3. Build the contract

The analysis turns evidence into:

- observed architecture and critical findings;
- business transactions and bounded workflow names;
- cross-cutting attributes and their propagation paths;
- span trees, events, metrics, and Collector transformations;
- dimension eligibility with cardinality arithmetic;
- dashboard variables, data links, detectors, SLIs, SLOs, and error budgets;
- composite use cases and labeled joins;
- phased implementation work; and
- a business value section tied to mechanisms specified in the contract.

Critical findings appear early because buried security or operability findings are not
actionable. Catalogue sections remain contiguous so the wiki can lift them without
reinterpreting the design.

### 4. Price without silently constraining

Entitlement and traffic baselines feed a separate exposure calculation. By default this
prices the design for the account team but does not reduce the recommendation.
`fit_to_entitlement: true` changes that behavior only when explicitly requested, and
every cut must name the observability question it makes unanswerable.

Licensing and overage figures stay out of the customer analysis. Keeping audiences
separate prevents a technical design review from becoming a licensing negotiation and
prevents the same number from acquiring multiple authorities.

### 5. Render and grade

Markdown is the analysis source. The renderer converts it into Word using the recorded
format specification, creates bookmarks and internal links, and starts each top-level
section on a new page.

The verifier compares source and output structure and scans for credential-shaped data.
The independent reviewer then checks semantic completeness against the canonical rubric.
Successful rendering proves format consistency, not human acceptance.

## Acceptance and wiki operation

Human acceptance is a hard boundary. Before it, obengineer may analyze and revise
documentation. After it, accepted names and schema decisions become dependencies.
Because the inputs schema has no acceptance field, the wiki gate relies on an explicit
human statement rather than inferring acceptance from the presence of generated files.

The wiki run lifts rather than redesigns the accepted contract. It creates:

- a short index used as the retrieval entry point;
- subject notes for transactions, workflows, findings, detectors, objectives, and use
  cases;
- contract notes for propagation, Collector behavior, and dimension budgeting;
- business workings and source provenance;
- ordered implementation work orders; and
- run metadata and host pointers.

The wiki is not a second customer document. Agents load only notes relevant to the current
slice, reducing context use and the chance of unrelated changes.

`verify_wiki.py` checks a minimal required-path set and selected frontmatter fields, plus
links, recognized counts, pointer rules, limited provenance, and credential-shaped
values. The canonical wiki reference defines the fuller structure and metadata. Human
review still checks those unenforced requirements, semantic duplication, stale statuses,
and whether notes accurately reflect code.

## Implementation operation

Implementation consumes one accepted work order and changes one authorized slice. It
reads:

- the analysis for intent;
- `attribute-schema.json` for allowed keys and dimensions;
- the relevant workflow and contract notes;
- the work order for boundaries and acceptance evidence; and
- `initial_scope` for repository and path authorization.

It stops when required design is missing. This is intentional: inventing an attribute in
code would make the accepted document, schema, wiki, dashboards, and code disagree.

Changes are ordered by dependency and trust. Shared helpers and single initialization
precede journeys; identity and propagation precede meters; signal production precedes
alerting. One slice per pull request keeps review and rollback bounded.

Deterministic checks eventually enforce the contract on every application change. Model
assistance may propose instrumentation, but schema agreement, initialization count,
workflow validity, baggage allowlists, and deny-list checks do not require a model.

## Terraform operation

Terraform generation reads the same accepted contract and schema but writes tenant
configuration rather than application telemetry.

Before writing HCL, it maps each contract item to a persona, provider resource, required
dimensions, and initial arm state. Missing dimension eligibility becomes a refusal rather
than an empty chart. Identified tenant resources become imports; when inventory is
unavailable, import IDs remain `TODO` and the handoff warns about duplication risk.

Three providers cover different product surfaces. Generated code is organized by
application, persona, and environment so a plan has a bounded blast radius. The run
formats, validates, and plans where possible, then hands off explicit imports, gaps,
placeholders, unsupported items, and costs.

It never applies. Configuration follows verified telemetry, and detectors start disabled
until their signals have been observed for the agreed window.

## Repeat-run behavior

Delta mode preserves external dependencies:

- workflow values and attribute keys are not renamed for style;
- finding IDs retain history;
- removed services are retired rather than deleted without explanation;
- drift between contract, code, and tenant is explicit;
- additions create new catalogue entries and work orders; and
- only reconsidered notes receive updated metadata.

A change to an accepted identifier is treated as a migration. The run must state old and
new values, affected code and configuration, cutover order, and verification.

## Safety boundaries

obengineer is constrained to:

- read-only analysis of production surfaces and tenant inventory;
- no storage or output of credential values;
- no application changes before acceptance and explicit scope authorization;
- one implementation slice per reviewable change;
- no widening of the accepted attribute schema during implementation;
- no automatic remediation of unrelated security findings;
- no duplicate customer document;
- no tenant mutation during analysis;
- no `terraform apply`; and
- no enabled detectors before signal validation.

Temporary authenticated scan access uses references to a dummy account or secret.
obengineer records `rotate_on_completion`, but the credential owner must perform the
rotation after analysis; this repository has no credential-provider integration that can
rotate it. Generated artifacts and validators scan for credential shapes, but operators
must also remove sensitive values from source captures before a run.

## Deterministic and model-driven parts

The distinction matters:

| Model-driven | Tool-executed checks |
|---|---|
| Evidence interpretation, architecture mapping, workflow discovery, recommendation writing | Installer path planning and manifests |
| Source and production-surface analysis | Plugin synchronization and manifest checks |
| Mapping findings to remediation | Contract tests |
| Choosing bounded attributes from evidence | Wiki structural verification |
| Producing application changes within a work order | Markdown-to-Word rendering and structural verification |
| Mapping accepted requirements into Terraform | Terraform format, static validation, and provider-schema checks. `plan` is an external-state-dependent verification result, not a deterministic check |

The model-driven parts can vary with available evidence. Canonical contracts, stable
state, acceptance gates, and deterministic verification provide the control surface that
keeps those variations reviewable.
