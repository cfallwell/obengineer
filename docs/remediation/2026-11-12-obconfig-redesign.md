# obconfig redesign remediation plan

Status: implementation-ready plan only
Baseline: `redesign-obconfig` at `28d113e`, after PR #28
Scope: local YAML intake, its consumers, packaging, migration, security, and tests

## Outcome and boundaries

Replace `.env.template`, `.env`-driven prefill, committed
`docs/observability/engagement-inputs.yaml`, and the guided optional-input conversation
with one project-root configuration:

- `obconfig.yaml.template` is committed and is the canonical field-definition authority.
- `obconfig.yaml` is local, ignored, mode `0600` where POSIX permissions are supported,
  and may contain plaintext read-only tokens and a dummy test password.
- `/ob-start` validates, optionally repairs only after an explicit `yes`, loads, shows a
  condensed redacted summary, and asks whether to proceed.
- `/ob-add-inputs` and `/ob-edit-inputs` become compatibility entry points for a
  file-driven rerun; neither asks field-by-field questions.
- Every analysis hashes the complete artifact directory, rereads changed context, and
  uses direct Splunk APIs whenever the matching access is configured.

No application instrumentation, analysis-site redesign, browser/localhost workflow, or
tenant mutation belongs in this change. The implementation PR must never contain an
actual `obconfig.yaml`.

## Evidence and root-cause-to-change matrix

| Confirmed cause | Current evidence | Required change | Acceptance |
|---|---|---|---|
| Input meaning has two authorities that can drift. | `inputs/engagement-inputs.template.yaml` defines fields while `skills/references/engagement-inputs.md` separately defines consequences. | Move every retained field definition, example, default, consequence, and secret annotation into root `obconfig.yaml.template`; delete the old template and field reference. Operational references may link to the template but may not redefine fields. | A repository test fails on old authority paths or field-definition tables outside the canonical template. |
| Intake is prompt-driven even though persistence is file-driven. | `prompts/00-manage-analysis-inputs.md`, `manage_run_context.py`, and the commands implement required/optional review states and numbered answers. | Replace the prompt/state machine with a deterministic config loader and a two-gate interaction: repair if invalid, then proceed after a redacted summary. | No numbered-input or “what hurts” prompt remains; command tests assert the new states and exact prompts. |
| `.env` and engagement YAML create duplicate configuration and secret-reference semantics. | `.env.template`, `env-prefill.schema.json`, `prefill_engagement_inputs.py`, and `analysis_access.*_ref` map one fact through multiple files. | Read only root `obconfig.yaml`; accept plaintext local secrets; remove `${VAR}` requirements and environment prefill. | A plaintext fixture loads, while stdout, errors, provenance, and generated artifacts contain no fixture secret. |
| “What hurts” is mandatory but did not deterministically shape output in issue discovery. | Start requires `business_context.commentary`; the validator rejects its absence. | Remove the question, required field, `WHAT_HURTS`, and free-form pain aliases used only by intake ranking. Ranking comes from evidence or explicit `first_journey`. | Analysis of otherwise identical configs cannot differ because a pain-text field exists; the schema rejects the retired field with a migration message. |
| Artifact inputs are individually named and can become stale. | `artifacts.diagrams`, `narrative`, `prior_*`, and related path checks are independent. | Accept one contained directory, hash its complete regular-file tree every run, compare with the prior local manifest, and reread new/changed files. | Identical bytes yield an identical tree hash regardless of creation order or mtime; one-byte changes force reread. |
| Authorization can outlive the inputs it authorized. | `.obengineer/run-context.json` records `analysis_authorized` without binding it to config and artifact bytes. | Replace it with ignored local state bound to config digest, artifact-tree digest, schema version, and command. Revalidate immediately before dispatch. | Editing config or artifacts after `yes` invalidates approval and returns to summary. |
| Safe-active scope is described but not strictly normalized. | `authorized_origins` is required only by prose; mutable exclusions and request limits are user inputs. | Keep `mode` and `authorized_origins`; explain passive versus safe-active in the template; make non-mutating methods and request/rate ceilings fixed code policy. Strictly validate exact origins. | Safe-active without valid origins fails on the field line; passive performs no active probes. |
| Deployment environment is represented as a list although one run targets one environment. | `tenancy.environments` and `DEPLOYMENT_ENVIRONMENTS` are plural. | Replace them with scalar `deployment_environment`. | Lists and the retired plural key fail with a migration instruction; one scalar is rendered consistently. |
| Tenant access is indirect and split between `.env` and references. | Realm, host, tokens, and index allowlist are split; MCP may supplement direct APIs. | Add Observability realm/read token and Platform host/read token/index allowlist directly to ignored YAML. Mandate direct API attempts in analysis and verification when configured; MCP remains supplemental. | Request-capture tests prove direct calls and prove MCP-only data is not labeled direct/measured. |
| Entitlement input invites stale order-form data and duplicates measurable limits. | The input schema has a large `entitlement` section and optional human entitlement questions. | Remove entitlement input fields and `fit_to_entitlement`; measure the approved `sf.org` usage and `sf.org.limit.*` metrics. Keep contractual entitlement explicitly unavailable unless a separate measured API/export supports it. | No entitlement key is accepted from config; reports distinguish measured usage/system limits from contractual entitlement. |
| Current comments under-explain vetoes and journey choice. | Privacy, residency, consent, change windows, and `first_journey` have terse comments. | Put expanded examples, consequences, and “leave empty” behavior in the canonical template. | Template contract tests assert each explanation and docs link only to the template. |
| Installer ownership can accidentally expose a local config during uninstall. | Installer currently owns `.env.template` and can remove installer-added ignore lines. | Own only the committed template and exact ignore edits; never own or remove actual `obconfig.yaml`; retain its ignore line while the actual file exists. | Uninstall preserves actual config and its ignore protection, including after template modification or symlink substitution. |

## Canonical schema shape

Use schema version 4. The template is both a valid default document and the only
field-definition authority. Comments must state type, requirement, default, operational
effect, and secret handling. A machine schema enforces the same shape but does not
compete as user documentation.

```yaml
schema_version: 4

engagement:
  application: ""
  customer: ""
  scope: ""
  date: ""
  document_version: 1
  deployment_environment: production

initial_scope:
  authorized: unknown
  repositories: []
  parent_folders: []
  branches: []

artifacts:
  directory: artifacts

cloud_diagrams:
  generate: true
  notes: ""

surfaces:
  production_urls: []
  no_browser_reason: ""
  host_and_remotes: ""
  edge_cdn: ""

security_assessment:
  mode: passive
  authorized_origins: []

analysis_access:
  dummy_login:
    login_id: ""
    password: ""                  # secret; dummy test account only

splunk:
  observability:
    realm: ""
    read_token: ""                # secret; read-only token
  platform:
    host: ""
    read_token: ""                # secret; read-only token
    index_allowlist: []

backends:
  languages: []
  deploy_targets: []
  buses: []
  cloud_accounts: []
  gateway: ""

tenancy:
  o11y_org_id: ""
  thousandeyes_account_group: ""
  tokens_held_by: ""

standards:
  percentile: p90
  workflow_naming: "{surface}.{object}.{verb}"
  baggage_header_budget_bytes: 512
  baggage_value_ceiling_bytes: 64
  unknown_dimension_threshold_pct: 1

constraints:
  privacy_regimes: []
  data_residency: ""
  consent_platform: ""
  pii_deny_list_additions: []
  competing_eum_agents: []
  change_windows: ""
  who_deploys_front_end: ""
  who_deploys_collector: ""

outcomes:
  first_journey: ""
  audiences: [sre, engineer, executive]

traffic_baseline:
  rum: {}
  apm: {}
  logs: {}
  infra_integrations: []

business_context:
  incident_experience: {}
  operating_cost: {}
  revenue_context: {}
  business_information: {}

public_evidence:
  allowed: true
  window_months: 12
  brand_terms: []
  status_page_urls: []
  exclude_domains: []
  competitors: []

developer_tools:
  named: []
  matched: []
```

The abbreviated `{}` blocks above expand to the current detailed traffic and business
leaves, with their comments moved into this template. The field disposition is explicit:

| Current section | v4 disposition |
|---|---|
| `engagement` | Retain; add singular `deployment_environment`. |
| `initial_scope` | Retain unchanged so this redesign cannot widen implementation authorization. |
| `artifacts` | Replace every individual artifact path with directory-only `artifacts.directory`. |
| `cloud_diagrams` | Retain `generate` and `notes`; the singular deployment environment supplies its environment scope. |
| `surfaces` | Retain production URLs, host/remotes, and edge/CDN; remove non-production URLs and move the no-browser reason to this section. |
| `security_assessment` | Retain only `mode` and `authorized_origins`; fixed code policy replaces configurable exclusions and request limits. |
| `analysis_access` | Replace references/rotation flag with one paired dummy login ID/password; rotation is a generated instruction. |
| `backends` | Retain. |
| `tenancy` | Move realm, host, and environments to their v4 locations; retain org ID, ThousandEyes account group, and future ingest-token holder. |
| `entitlement` | Retire in full. |
| `traffic_baseline` | Retain all current detailed leaves as optional stated fallback data; measured API facts outrank them. |
| `standards` | Retain. |
| `constraints` | Retain all current leaves and expand privacy/residency/consent/change comments. |
| `outcomes` | Retain audiences and `first_journey`; retire `known_pain` as a second free-form “what hurts” path. |
| `developer_tools` | Retain. |
| `business_context` | Retain numeric/structured incident, cost, revenue, and business leaves; retire free-form pain commentary. |
| `public_evidence` | Retain. |
| `input_provenance` | Retire; sanitized generated provenance and ignored local state replace it. |

Unknown keys are round-tripped unchanged. Unknown keys inside known sections produce a
warning and are ignored by runtime consumers. Unknown top-level content from legacy
input is retained under `extensions.legacy` only when keeping it in place would collide
with a known v4 key. Values are never printed while reporting an unknown key.

### Strict field rules

- `engagement.application` and `engagement.deployment_environment` are nonempty scalars.
- Exactly one of nonempty `surfaces.production_urls` and
  `surfaces.no_browser_reason` is required.
- `artifacts.directory` is one project-relative directory. Absolute paths, `..`, NUL,
  symlinks in any path component, and a path resolving outside the project fail closed.
- `security_assessment.mode` is `passive`, `safe-active`, or `none`.
- `authorized_origins` must be empty outside safe-active and nonempty for safe-active.
  Each entry is a normalized exact HTTPS origin: scheme, IDNA host, and optional port;
  no credentials, wildcard, path, query, fragment, loopback, link-local, or unspecified
  address. A request is active only when its normalized origin exactly matches.
- Observability realm and token are supplied together. Platform host, token, and a
  nonempty index allowlist are supplied together. Platform host is HTTPS with no
  userinfo, query, or fragment. Duplicate or wildcard indexes are invalid.
- Dummy login ID and password are supplied together. The template explains that this is
  never a production account and must be rotated after use.
- Token and password values are ordinary YAML strings. `${VAR}` has no special meaning
  and is never required.
- The retired `entitlement`, `tenancy.environments`, and pain-commentary keys receive
  line-specific migration errors, not silent acceptance.

## Deterministic loader, repair, and artifact hashing

Create one library and one CLI under `skills/engagement-intake`:

- `scripts/obconfig.py`: path containment, permission and git-safety checks, marked YAML
  parsing, schema validation, redaction, migration, atomic repair, summary generation,
  authorization binding, and artifact hashing.
- `scripts/manage_obconfig.py`: stable CLI with `init`, `validate`, `repair`, `summary`,
  `authorize`, `show`, and `migrate-legacy` subcommands.
- `schemas/obconfig.schema.json`: machine validation, secret-path annotations, defaults,
  retired-key messages, and extension policy.

Use a round-trip YAML parser so repair preserves comments, ordering, scalar quoting, and
unknown extensions. Reject duplicate keys. Convert parser exceptions into
`line <n>, column <n>: <reason>` without echoing the source line.

Repair is deliberately bounded. After `yes`, it may:

1. migrate known legacy names and shapes;
2. insert missing sections/defaults from the template;
3. normalize scalar/list shapes where conversion is lossless;
4. fix POSIX mode to `0600`; and
5. apply syntax repairs only from an enumerated, independently revalidated catalog.

Arbitrary invalid YAML cannot be safely guessed. If no catalogued repair produces one
unambiguous valid document, preserve the file, report that no safe repair exists, and
stop. Before any mutation, atomically write an ignored mode-`0600` backup beneath
`.obengineer/backups/`; after mutation, parse and validate again before replacing the
original. A failed post-repair check restores the original.

The artifact tree algorithm is versioned as `ob-artifact-tree-v1`:

1. Open the configured directory under the project boundary without following symlinks.
2. Enumerate regular files recursively and sort by UTF-8 POSIX relative path bytes.
3. For each file, hash bytes with SHA-256, then feed the tree hash a framed record
   containing path-byte length, path bytes, file-byte length, and file digest.
4. Do not include mtime, owner, mode, directory entries, or traversal order.
5. Reject symlinks, sockets, devices, FIFOs, unreadable files, and a file replaced
   between stat/open/read checks.
6. Store the full local manifest under ignored `.obengineer/`; provenance receives only
   the algorithm, tree hash, file count, total bytes, and changed/added/deleted relative
   paths after secret-name redaction.
7. Reread every added or changed file, remove deleted-file context, and permit cached
   context only for files whose path, byte length, and digest are unchanged.

## User-visible states

| State | Visible behavior | Transition |
|---|---|---|
| `preflight` | Check root regular files, ignore status, tracked status, mode, and schema availability. Print no config value. | Missing config → `initialized`; unsafe path/tracked config → `blocked`; otherwise `validate`. |
| `initialized` | Copy the committed template to `obconfig.yaml` atomically, set `0600`, and say: `Created local obconfig.yaml. Edit it and rerun /ob-start.` | Stop; never analyze defaults automatically. |
| `validate` | Parse with duplicate-key detection and validate marked nodes. | Valid → `hash-artifacts`; invalid → `repair-offer`. |
| `repair-offer` | Say exactly `obconfig.yaml is invalid at line <n>, column <n>: <redacted reason>. Repair it now? (yes/no)` | `no` → `stopped`; exact `yes` → `repair`; anything else repeats this gate. |
| `repair` | Back up, run only catalogued repair, restore on failure, enforce mode, and revalidate. Report changed key paths, never values. | Success → `hash-artifacts`; unsafe/ambiguous → `blocked`. |
| `hash-artifacts` | Hash every artifact file and calculate the delta from the last run. Long scans emit count/byte progress, never content. | Success → `summary`; containment/race/read failure → `blocked`. |
| `summary` | Show the condensed redacted summary below and ask exactly `Proceed with analysis using this configuration? (yes/no)` | `no` → `stopped`; exact `yes` → `authorize`; anything else repeats this gate. |
| `authorize` | Persist ignored authorization bound to schema version, config digest, artifact-tree digest, and intended next version. Recheck all bindings immediately. | Unchanged → `analysis`; changed → `validate` and a new summary. |
| `analysis` | Run the next immutable version and one analysis PR. | Complete → clear one-shot authorization. Failure → clear authorization and retain diagnostics without secrets. |
| `blocked` | Give the exact safe corrective action and exit nonzero. | User corrects local files and reruns. |

The condensed summary contains application, deployment environment, production URL
count or no-browser status, artifact directory/file count/tree-hash prefix and delta
counts, security mode and authorized-origin count, Observability realm plus token
`configured`/`not configured`, Platform host plus token status and index count, dummy
login `configured`/`not configured`, constraint counts, percentile, first journey or
`evidence-ranked`, and direct-API availability. It never shows tokens, password, login
ID, full index names, config digest, or unknown-extension values.

`/ob-add-inputs` and `/ob-edit-inputs` both:

1. state that inputs are managed in local `obconfig.yaml`;
2. validate and compare it with the last authorized local digest;
3. stop with `Edit obconfig.yaml, then rerun this command.` when unchanged; and
4. when changed, use the same redacted summary/proceed gate and dispatch the next
   immutable version.

They do not edit YAML on the user's behalf, list numbered fields, or maintain separate
add/edit state. `/ob-analyze` accepts only an unconsumed, digest-bound authorization.

## Direct API and access strategy

### Observability Cloud

- Derive only documented resource and SignalFlow hosts from the validated realm.
- Send the read token only in the required header to those exact hosts; never put it in
  a URL, query, exception, command argument, worker result, or MCP request.
- Disable cross-host credential forwarding on redirects. Use certificate verification,
  bounded connect/read timeouts, bounded retries for idempotent reads, and response-size
  limits.
- Analysis and verification directly query the documented `sf.org` metrics already
  listed in `skills/references/existing-telemetry.md`, including active/custom MTS,
  enforced limits, APM traces/bytes, and MMS/TMS cardinality.
- `sf.org.limit.*` is an enforced system limit, never contractual entitlement. Reports
  label current usage, limit, and derived system headroom separately.

### Splunk Platform

- Send the read token only to the exact validated HTTPS host.
- Permit only read/introspection endpoints and search export/jobs required by the
  existing procedure. No saved-object writes, configuration changes, or mutation.
- Build searches from a validated index allowlist; reject `*`, `_all`, empty names, and
  any requested index outside the set. Escape every index and application constraint.
- Record event/byte counts and index-level scope without putting raw events or index
  names from config into generated examples.

### Analysis and verification contract

- When a product block is configured, a direct API attempt is mandatory in both analysis
  and verification. Success, access denial, timeout, and unsupported endpoint are
  explicit source-specific dispositions.
- MCP may add evidence but cannot replace, suppress, or relabel the direct API attempt.
- When access is absent, the run records `not configured`; it must not call tenant data
  “measured” from MCP alone.
- Verification uses the same loader, redaction map, host restrictions, and index
  allowlist. It remains read-only.

## Security controls

1. Add exact `/obconfig.yaml` and `/.obengineer/` root rules to the project scaffold
   `.gitignore`; keep `!/obconfig.yaml.template` committed.
2. Refuse to load a symlink, non-regular file, path outside the project root, or a config
   tracked by git. Refuse analysis if `git check-ignore` does not prove the actual file
   is ignored.
3. Create actual config, backups, local state, and temporary rewrites with `0600` on
   POSIX. Use same-directory atomic replace, fsync file and directory, and restore mode.
   On platforms without POSIX modes, report that the check is unsupported without
   claiming it passed.
4. Define secret paths in one schema-derived registry:
   `splunk.observability.read_token`, `splunk.platform.read_token`, and
   `analysis_access.dummy_login.password`. Add defense-in-depth key-name and
   credential-shape redaction for unknown extensions.
5. Route every stdout, stderr, exception, summary, migration report, provenance write,
   worker result, generated Markdown/JSON, and test snapshot through the same redactor.
   Error messages may contain a key path and line number, never a source excerpt/value.
6. Never copy actual config into plugin packages, installer manifests, scaffold
   ownership, analysis branches, commits, PRs, or generated artifacts.
7. Keep only local binding digests under `.obengineer/`. Generated provenance records
   secret fields as `configured`/`not configured`, not values or secret-derived config
   digests.
8. Do not read process environment as a fallback. This prevents stale `.env` values
   from silently overriding YAML.
9. Use fixed safe-active policy: non-mutating methods, fixed request/rate ceilings, no
   credential brute force, no state-changing forms, and exact authorized-origin checks.

## File-level ownership plan

“Owner” below names the subsystem that controls the file, not a person.

| Owner | Canonical files | Change |
|---|---|---|
| Config contract | `obconfig.yaml.template` | Add the sole field-definition authority with complete comments. |
| Config contract | `inputs/engagement-inputs.template.yaml`, `skills/references/engagement-inputs.md` | Delete after migration tests no longer need them. Do not leave redirect copies containing definitions. |
| Intake runtime | `skills/engagement-intake/SKILL.md` | Replace guided intake with local config lifecycle and redaction rules. |
| Intake runtime | `skills/engagement-intake/scripts/obconfig.py`, `manage_obconfig.py` | Add deterministic loader/CLI. |
| Intake runtime | `skills/engagement-intake/schemas/obconfig.schema.json` | Add v4 validation, source marks, secret annotations, and retired-key guidance. |
| Intake runtime | `start_turn.py`, `manage_run_context.py`, `prefill_engagement_inputs.py`, `verify_engagement_inputs.py`, `skill_paths.py`, `env-prefill.schema.json`, `run-context.schema.json` | Remove once their behavior is covered by the new CLI. |
| Intake tests | `skills/engagement-intake/tests/` | Replace state/prefill tests with syntax, schema, repair, migration, redaction, mode, authorization, and tree-hash tests. |
| Workflow routing | `commands/ob-start.md`, `ob-add-inputs.md`, `ob-edit-inputs.md`, `ob-analyze.md`, `prompts/00-manage-analysis-inputs.md` | Route all four commands through the loader; rename the prompt to `prompts/00-load-obconfig.md` or delete it if the skill and CLI fully own the behavior. |
| Analysis | `skills/instrumentation-analyze/SKILL.md`, `prompts/01-analyze-application.md` | Require digest-bound config, full artifact delta, and direct API dispositions. |
| Analysis contract | `skills/instrumentation-analyze/schemas/analysis-contract.schema.json`, `scripts/analysis_contract.py`, renderer, fixtures, tests | Remove supplied-entitlement assumptions; represent measured usage, enforced limits, and unavailable contractual entitlement. |
| Verification | `skills/instrumentation-verify/SKILL.md`, `prompts/05-verify-accepted-contract.md`, verification scripts/tests | Load obconfig securely and mandate direct read API attempts when configured. |
| Telemetry/cardinality | `skills/references/existing-telemetry.md`, `entitlement-exposure.md`, `skills/cardinality-budget/SKILL.md` | Replace entitlement-input guidance with measured `sf.org` usage/limit arithmetic and explicit labeling. |
| Security | `skills/references/security-assessment.md` | Explain passive/safe-active and bind safe-active solely to validated origins plus fixed code limits. |
| Provenance | `skills/references/provenance-ledger.md` and verifier/tests | Define sanitized config provenance and artifact-tree/delta records. |
| Installer | `scripts/install.py`, `templates/memory-repo/.gitignore` | Scaffold template/ignore, migrate ownership, preserve actual config, and make uninstall secret-safe. |
| Installer | `templates/memory-repo/.env.template`, `scripts/setup-splunk-access.sh` | Remove; no `.env` or setup script remains an active configuration path. |
| Packaging | `scripts/sync_plugin_skills.py`, `scripts/codex_workflows.py` if path rendering changes | Package the canonical template and generated commands for Cursor, Claude, and Codex. |
| Generated mirrors | `plugins/obengineer/**`, `.cursor/skills/**`, `.agents/skills/**` | Regenerate only with `make sync-plugin-skills`; never hand-edit. Plugin template copies must be byte-identical to root authority. |
| Installer tests | `tests/test_installer_scaffold.py`, `tests/test_installed_walkthrough.py` | Cover clean install, copied/user installs, migration, ownership, uninstall, first output, and no secret copy. |
| Contract tests | `tests/test_skill_contracts.py` | Ban old paths/phrases, assert one authority, all mirrors, API requirements, and command routing. |
| User docs | `README.md`, `docs/installation.md`, `docs/configuration.md`, `docs/usage.md`, `docs/how-it-works.md`, `docs/design.md`, `plugins/obengineer/README.md`, `AGENTS.md` | Document copy/edit/start flow, permissions, migration, direct APIs, and new authority map without repeating field definitions. |

## Migration and compatibility design

### Detection and precedence

On install or first `/ob-start`, inspect only names/existence first:

1. Valid existing `obconfig.yaml` wins; do not merge legacy values into it.
2. If it is absent, detect local `.env`, project `.env.template`, and
   `docs/observability/engagement-inputs.yaml`.
3. Show only source paths and a redacted list of destination key paths, then ask whether
   to migrate as the repair gate.
4. Values from legacy engagement YAML outrank `.env` for the same non-secret fact.
   Actual secret values from `.env` populate the matching secret fields. A disagreement
   between two supplied nonempty values is a redacted conflict and blocks automatic
   migration.
5. Write one atomic mode-`0600` `obconfig.yaml`; validate it before making it active.
   Preserve legacy files and write local migration completion state. Never delete them
   automatically.

### Deterministic mapping

- `engagement`, retained architecture/standards/constraint/outcome/business/public/tool
  fields map by path.
- `artifacts.location` becomes `artifacts.directory`. Other artifact path fields are
  not copied as separate config; ensure their contained files are present under the
  directory and report any outside path as a blocking, redacted migration item.
- `tenancy.environments` maps only when it has exactly one value; otherwise require the
  user to choose one in the file.
- `tenancy.o11y_realm`/`SPLUNK_REALM` maps to
  `splunk.observability.realm`.
- actual `SPLUNK_ACCESS_TOKEN` maps to `splunk.observability.read_token`;
  `${SPLUNK_ACCESS_TOKEN}` is treated as an unresolved legacy reference, not a token.
- `tenancy.splunk_platform_host`/`SPLUNK_HOST`, actual `SPLUNK_TOKEN`, and
  `SPLUNK_ENTERPRISE_INDEXES` map to the Platform block and list.
- Dummy login ID and actual referenced password map together. An unresolved
  `password_ref` blocks credential migration but not non-secret migration.
- `entitlement`, `input_provenance`, run-context authorization, and pain commentary are
  intentionally retired and listed by key path only.
- Unknown legacy extensions are preserved as specified by the extension policy.

### Installer ownership and uninstall

Upgrade the scaffold manifest schema. A reinstall:

- creates `obconfig.yaml.template` only when missing;
- removes an unchanged installer-owned `.env.template` only when its recorded digest
  matches;
- preserves modified/unowned legacy templates and reports them;
- adds the exact root ignore for `obconfig.yaml`;
- never records actual config as owned; and
- rolls back template, ignore, and manifest edits together on failure.

Uninstall removes only an unchanged installer-owned template and ownership metadata.
It preserves `obconfig.yaml`, backups, user artifacts, modified templates, legacy files,
and the `obconfig.yaml` ignore whenever the actual file still exists. Host uninstall
continues to remove only digest-matched generated commands/skills.

Compatibility wrappers keep `/ob-add-inputs` and `/ob-edit-inputs` discoverable for one
release line. Existing accepted analysis versions remain immutable and readable. A new
analysis version uses only v4 config; it does not rewrite historical inputs or
provenance.

## Dependency-ordered workstreams

1. **W0 — contract freeze and redaction registry.** Land the v4 template, machine
   schema, retired-key map, exact secret paths, artifact-tree algorithm, and golden
   fixtures. This blocks every consumer.
2. **W1 — loader and local state.** Implement marked parse/schema errors, safe repair,
   permissions, git checks, unknown-key round trip, redacted summary, artifact hash,
   and digest-bound one-shot authorization.
3. **W2 — scaffold and legacy migration.** After W0, update installer ownership,
   ignore rules, host companion lookup, migration, rollback, and uninstall. W2 can run
   in parallel with W1 but cannot integrate until loader fixtures are stable.
4. **W3 — command UX.** After W1, replace start/add/edit/analyze routing and remove the
   old conversation/run-context path. Add exact state-transition tests.
5. **W4 — analysis and verification consumers.** After W0 and the W1 read API stabilize,
   update artifact delta use, direct API requirements, usage/limit semantics,
   provenance, analysis schema/renderer, and verification. Observability and Platform
   adapters can be developed in parallel.
6. **W5 — package and docs.** After W2–W4, regenerate all plugin/host mirrors and update
   authority, install, configuration, and usage docs. Do not manually patch mirrors.
7. **W6 — integrated and live QA.** Run clean install, all three host modes, legacy
   migration, repair/no-repair, analysis/verification request capture, uninstall, and
   secret-diff scans. Then run the complete deterministic suite.

W1 and W2 are the first parallel lane. Within W4, analysis-contract work, direct API
adapters, and verification can proceed in parallel against W0 fixtures. W3 must not
remove the old path until W1 and the W2 migration are green.

## Performance budgets

These are hard upper bounds recorded in tests and `analysis-run-timing.json`, not effort
estimates:

| Stage | Budget |
|---|---|
| Command startup to first visible local status | p95 ≤ 1 second; hard ≤ 5 seconds |
| Syntax/schema failure to repair question | ≤ 1 second for config ≤ 1 MiB |
| Valid config to redacted proceed question | ≤ 5 seconds for the QA tree of 1,000 files/100 MiB |
| Any answer turn to next visible state | ≤ 2 seconds excluding a newly required full artifact hash; hash progress begins by 2 seconds |
| Full artifact hash | ≥ 100 MiB/s on the CI fixture or explicit progress every 30 seconds; no content buffering proportional to tree size |
| Parallel collection | ≤ 600 seconds; exactly six bounded jobs, one coordinator slot reserved, and at least two runnable intervals overlap when host capacity permits |
| Reconciliation | ≤ 240 seconds, serial |
| Deterministic render | ≤ 180 seconds |
| Validation | ≤ 120 seconds |
| Total analysis after proceed | ≤ 1,200 seconds, with progress at least every 60 seconds |

The loader records its local timings without values. Existing output file/byte budgets
remain unchanged. A budget miss is a failing QA result with the phase and measured
duration.

## Exact acceptance tests

### Authority and schema

1. `obconfig.yaml.template` parses as schema v4 and contains every retained field,
   default, type/example, consequence, and secret annotation.
2. Repository search finds no active reference to `.env.template`,
   `docs/observability/engagement-inputs.yaml`, `WHAT_HURTS`,
   `DEPLOYMENT_ENVIRONMENTS`, numbered optional input, or `${VAR}` as a credential
   requirement.
3. `inputs/engagement-inputs.template.yaml` and
   `skills/references/engagement-inputs.md` are absent; docs link to the root template
   instead of restating field tables.
4. A fixture with `deployment_environment: production` passes. A list and the retired
   plural key fail at their exact lines.
5. A fixture containing `entitlement` or retired pain commentary fails with the exact
   key line and migration reason.
6. Unknown extension mappings and comments survive validate/repair byte-equivalently
   except for the specifically repaired nodes.

### Validation, repair, and UX

7. Malformed YAML reports exact 1-based line and column plus a sanitized reason; the
   output does not contain the malformed source line or adjacent token value.
8. A semantic type error reports the field path and source line.
9. Replying `no` to repair leaves inode content and mode unchanged and does not load or
   authorize analysis.
10. Replying `yes` to a catalogued repair creates a mode-`0600` ignored backup,
    preserves comments/extensions, atomically writes, revalidates, and then shows the
    summary.
11. Replying `yes` to ambiguous invalid YAML reports no safe repair, restores the exact
    original bytes, and stops.
12. Missing actual config creates it from the committed template with `0600`, prints the
    exact edit/rerun instruction, and does not proceed.
13. Valid config shows the specified condensed summary and exact proceed question.
    Tokens, password, login ID, full index names, and unknown values are absent.
14. `no` at proceed performs no API/network/analysis action. `yes` writes a one-shot
    local binding and dispatches.
15. Mutating either config or one artifact after `yes` invalidates the binding before
    dispatch and returns to a newly calculated summary.
16. `/ob-add-inputs` and `/ob-edit-inputs` ask no field questions. Unchanged config
    prints the exact edit/rerun instruction; changed config reaches the common summary
    gate and creates only the next immutable version after `yes`.

### Filesystem and secrets

17. `obconfig.yaml` is ignored and `obconfig.yaml.template` is tracked on clean install.
    A tracked or non-ignored actual config blocks before parsing.
18. POSIX files created for config, backups, state, and temporary replacement are
    `0600`; a permissive existing file is not loaded until explicit repair tightens it.
19. Config, artifact directory, backup, and state symlink substitutions are rejected
    without reading or changing the external target.
20. Plaintext read-only token and dummy-password fixtures load successfully with no
    `${VAR}` syntax.
21. Secret canaries do not occur in captured stdout, stderr, exceptions, local
    non-secret state, provenance, worker results, rendered Markdown/JSON, git diff, or
    packaged plugin files.
22. High-entropy/credential-shaped values under unknown extension keys are also
    redacted from diagnostics and summaries.

### Artifacts

23. A file supplied instead of `artifacts.directory`, traversal, absolute path,
    unreadable entry, special file, or any symlink fails before analysis.
24. Two trees with identical relative paths/bytes but different creation order, mtimes,
    modes, and directory order produce the same `ob-artifact-tree-v1` hash.
25. Rename, add, delete, and one-byte modification produce the expected delta and a new
    hash. New/changed files are reread, deleted context is removed, and unchanged files
    alone may reuse cached context.
26. A stat/open/read replacement race fails closed and writes no partial manifest.

### Authorization and direct APIs

27. Passive mode makes zero safe-active requests. Safe-active without origins fails;
    malformed/wildcard/path-bearing/loopback origins fail on their lines; a normalized
    exact HTTPS origin passes.
28. Safe-active request capture contains only fixed non-mutating methods, exact
    authorized origins, and fixed request/rate ceilings.
29. Configured Observability access causes analysis and verification to make direct
    requests to the derived realm hosts and query the approved `sf.org` usage/limit
    metrics. The token appears only in the request header captured by the mock.
30. Configured Platform access causes analysis and verification to use only the exact
    host and allowlisted indexes. Wildcard or out-of-allowlist searches are rejected.
31. Redirect tests prove neither token is forwarded to a different host. TLS, timeout,
    retry, and response-size failures become redacted source-specific limitations.
32. MCP-only evidence cannot satisfy the direct-attempt record and is not labeled as
    direct tenant measurement.
33. Generated output labels `sf.org.limit.*` as enforced system limit, calculates
    system headroom, and leaves contractual entitlement unavailable.

### Migration, installer, and mirrors

34. Legacy YAML plus `.env` migrates according to documented precedence; actual token
    values move only into ignored YAML, unresolved references are reported by key path,
    and conflicts block without exposing either value.
35. A plural legacy environment migrates only when it has one item. Multiple values
    block for file-based selection.
36. Legacy artifact paths outside the selected directory block migration; unknown
    extensions survive under the extension policy; retired entitlement/pain fields do
    not migrate.
37. Reinstall removes only digest-matched installer-owned `.env.template`, preserves
    modified/unowned legacy files, and rolls back all scaffold changes on injected
    failure.
38. Uninstall preserves actual config, backup/state, user artifacts, modified template,
    and the config ignore while actual config exists. It removes only unchanged owned
    template/host files.
39. Cursor and Claude link installs, Cursor/Claude copy installs, Codex project/user
    materializations, and the plugin all resolve the same schema/template. Every
    packaged template is byte-identical to root canonical.
40. `make sync-plugin-skills`, `make check`, `make test`, `make qa-analysis`, secret
    scanning, and repeated deterministic rendering all pass.

### Live QA without browser or localhost

41. In isolated clean and legacy repositories, run install/start/repair/summary,
    fixture-backed analysis, direct-API request capture, verification, reinstall, and
    uninstall without opening a browser, starting a server, or emitting localhost.
42. Capture timings proving all budgets, the redacted transcript proving exact state
    transitions, the artifact hash/delta, and `git status` proving actual config never
    entered the PR.

## Migration and compatibility risks

| Risk | Mitigation |
|---|---|
| Arbitrary YAML repair corrupts intent. | Enumerated repairs only, explicit yes, local backup, post-repair validation, atomic restore. |
| Round-trip parser changes comments or unknown fields. | Golden byte/AST fixtures and extension round-trip tests before deleting old scripts. |
| Plaintext local tokens are accidentally committed or logged. | Root ignore/tracked checks, `0600`, centralized schema-driven redaction, secret canaries, and no actual-config ownership. |
| User-scope installs cannot locate the canonical template. | Package a byte-identical namespaced companion and test every host/scope/copy mode. |
| Removing entitlement changes report semantics. | Preserve measured usage/system-limit reporting and explicitly mark contractual values unavailable; do not silently compare unlike facts. |
| One deployment environment cannot represent a multi-environment engagement. | One run/version targets one environment; users run another immutable version/config selection for another environment. Do not reintroduce a list. |
| Full tree hashing is expensive for very large artifact sets. | Stream bytes, bound memory, show progress, retain only digest metadata, and fail transparently on budget breach rather than skipping files. |
| Legacy files continue to influence runs. | Loader has no environment fallback and records local migration completion; repository tests ban active legacy references. |
| Removing the old state machine opens a bypass. | `/ob-analyze` requires one-shot authorization bound to current config/artifact digests and intended version. |
| Installer uninstall removes ignore protection. | Preserve the ignore whenever actual config exists, regardless of prior ownership. |

## Rollback points

1. **R0 — baseline:** `28d113e`. No behavior change.
2. **R1 — schema/loader additive:** v4 template and loader exist while old commands still
   route to the old path. Revert W0/W1 without touching customer repositories.
3. **R2 — dual migration:** installer can create/migrate obconfig, but consumers still
   have a feature-switched legacy read path for test rollback. Never dual-read values in
   one run.
4. **R3 — command cutover:** commands use only obconfig; legacy files remain preserved.
   Rollback restores command routing and leaves ignored obconfig untouched.
5. **R4 — authority cleanup:** old scripts/templates/references are deleted only after
   clean, migrated, copied, user-scope, and plugin tests pass. Rollback restores those
   files from the prior commit, not from customer data.
6. **R5 — final package:** mirrors and docs are regenerated. If live QA fails, revert to
   R3/R4 as a unit; do not publish a mixed plugin where commands and packaged schema
   disagree.

Each implementation commit should correspond to one rollback point or one independently
revertible direct-API adapter. No rollback may delete or rewrite a user's actual config,
backup, or legacy files.
