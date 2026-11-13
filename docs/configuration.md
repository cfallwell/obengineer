# Configuration

Every obengineer engagement is driven by one local file, `obconfig.yaml`, in the root of
the artifact repository. This page explains how to create it, what each section
controls, and what the two confirmation gates mean. The committed
[`obconfig.yaml.template`](../obconfig.yaml.template) is the authority for every field's
type, default, and effect; this page explains how to use the sections, not every field.

## Create the file

Either let the first run create it:

```text
/ob-start
→ Created local obconfig.yaml. Edit it and rerun /ob-start.
```

or create it yourself:

```bash
cp obconfig.yaml.template obconfig.yaml
chmod 600 obconfig.yaml
```

Requirements that `/ob-start` enforces before reading anything:

- `obconfig.yaml` is a regular file (not a symlink) in the repository root;
- it is ignored by Git and not tracked (a project install adds `/obconfig.yaml` and
  `/.obengineer/` to `.gitignore`); and
- its mode is `0600` on macOS and Linux.

`obconfig.yaml` may hold three plaintext secrets: the dummy test password and the two
Splunk read tokens. `${VAR}` references are not interpreted, and obengineer never reads
`.env` files or process environment variables for configuration. Use a disposable test
account and least-privilege read tokens, and rotate them after the engagement.

## Minimum configuration

Three values are enough to run a first analysis:

```yaml
schema_version: 4
engagement:
  application: storefront          # used in every generated path
  deployment_environment: production
surfaces:
  production_urls:
    - https://www.example.com/
```

If the application has no browser surface, leave `production_urls` empty and set
`surfaces.no_browser_reason` instead. Everything else is optional: missing optional
values never block analysis, and useful gaps are listed on the analysis's Intake
recommendations page.

## Sections

### `engagement` — identity of the run

`application` is the stable id used in every path, for example
`docs/observability/analysis/storefront/V1/` and `terraform/apps/storefront/`. Choose it
once; changing it starts a new application history. `deployment_environment` names the
single environment this engagement targets. `customer`, `scope`, `date`, and
`document_version` appear in headings and the optional Word summary.

### `initial_scope` — what implementation may change

Controls which repositories and folders `/ob-implement` may edit. Analysis always runs;
implementation stops until this is set.

| `authorized` | Meaning |
|---|---|
| `unknown` (default) | No code changes. `/ob-implement` stops and asks engineering to authorize scope. |
| `full` | Every repository mapped by the accepted implementation map. |
| `repositories` | Only the `owner/name` entries in `repositories`. |
| `parent_folders` | Only the `{repository, path}` entries in `parent_folders`. |

```yaml
initial_scope:
  authorized: parent_folders
  parent_folders:
    - {repository: acme/web, path: src/}
  branches:
    - {repository: acme/web, branch: main}
```

`branches` is optional; empty means each repository's current checkout.

### `artifacts` — supplied evidence

`directory` (default `artifacts`) is a project-relative folder holding everything you
want analysis to read: architecture diagrams, prior guides, exports, runbooks. Every
regular file is hashed on each run; added and changed files are reread and deleted files
are dropped from context. Absolute paths, `..`, symlinks, and special files are
rejected.

### `surfaces` — what the live production scan visits

`production_urls` lists the exact pages the read-only browser scan loads. Test or QA URLs
are not a substitute. `host_and_remotes` describes bundle ownership (for example
micro-frontend remotes). `edge_cdn` names the CDN or edge/TLS boundary in front of the
site for analysis to verify; the CDN in front of the site also shapes the recommendation
for delivering the RUM agent. When the application has a web front-end, the analysis
links the matching CDN injection reference from its foundation section (see
[RUM load order and CDN delivery](how-it-works.md#rum-load-order-and-cdn-delivery)).

### `security_assessment` — security evidence collection

Explained in full under [Security assessment modes](#security-assessment-modes).

```yaml
security_assessment:
  mode: safe-active
  authorized_origins:
    - https://www.example.com
```

### `analysis_access` — dummy test login

`dummy_login.login_id` and `dummy_login.password` are set together or not at all. They
let the scan reach signed-in pages using a disposable test account. Never use a real
customer or production identity.

### Splunk tenant access

The `splunk` section grants read-only access to Splunk Observability Cloud and Splunk Platform. When a block is
configured, analysis and `/ob-verify` must attempt its direct API calls; connected MCP
tools add evidence but never replace those calls.

```yaml
splunk:
  observability:
    realm: us1
    read_token: "<least-privilege read token>"
  platform:
    host: https://splunk.example.com
    read_token: "<least-privilege read token>"
    index_allowlist: [web, app]
```

- `realm` and `read_token` are paired; the realm derives the exact API hosts.
- `host`, `read_token`, and `index_allowlist` are paired. Index names must be exact;
  wildcards and `_all` are rejected.
- Tokens are sent only in HTTPS request headers to the validated hosts and are never
  forwarded on redirects, written to logs, or included in generated files.

When a block is empty, the run records `not-configured` for those sources and tenant
facts are marked as unavailable rather than measured.

### `backends` — server-side shape

`languages`, `deploy_targets`, `buses`, `cloud_accounts`, and `gateway` select SDK
guidance, Collector placement, and message propagation. Measured source evidence
overrides them when they disagree.

### `tenancy` — tenant identifiers

`o11y_org_id`, `thousandeyes_account_group`, and `tokens_held_by` are identifiers and
roles only. Never put a token here.

### `standards` — naming and budget defaults

```yaml
standards:
  percentile: p90
  workflow_naming: "{surface}.{object}.{verb}"
  baggage_header_budget_bytes: 512
  baggage_value_ceiling_bytes: 64
  unknown_dimension_threshold_pct: 1
```

`percentile` is the single percentile used by every chart, detector, and objective.
`workflow_naming` is the naming pattern for new workflows. The two baggage values cap
the W3C Baggage header that carries cross-cutting attributes between services.

### `constraints` — vetoes on the design

`privacy_regimes`, `data_residency`, `consent_platform`, `pii_deny_list_additions`,
`competing_eum_agents`, `change_windows`, `who_deploys_front_end`, and
`who_deploys_collector`. These override otherwise-correct designs. An empty value is
treated as unconfirmed, not as permission: for example, an empty `data_residency` is
reported as a gap rather than assumed unrestricted.

### `outcomes` — what to prioritize

`first_journey` forces the first use case; leave it empty to let evidence rank them.
`audiences` (default `[sre, engineer, executive]`) selects the generated audience views
and Terraform persona modules.

### `traffic_baseline` and `business_context` — stated numbers

Optional numbers you know but obengineer may not be able to measure: RUM sessions, APM
request rates, log volume, incident timings (MTTD, MTTA, MTTR), tooling cost, revenue
per hour, and similar. `unknown` is accepted for every number. They are labelled
**stated** evidence; measured values from the tenant always win, and disagreements are
recorded. Nothing here is ever filled in from industry benchmarks.

### `public_evidence` — public research

`allowed` (default `true`) permits bounded public research within `window_months`.
`brand_terms`, `status_page_urls`, `exclude_domains`, and `competitors` narrow it.

### `developer_tools` — issue tracker integration

Jira is used only when it is named in `named` **and** matched to a connected integration:

```yaml
developer_tools:
  named: [jira]
  matched:
    - {tool: jira, via: mcp, key: "<connected server key>"}
```

Otherwise every work order still includes copy-and-paste issue text for your tracker.

### `extensions`

A namespaced mapping preserved verbatim and ignored by runtime logic. Never place
credentials here.

## The two gates before analysis

`/ob-start` asks two kinds of question on the first run and accepts only exact answers.
After the first analysis, `/ob-analyze` asks the same questions itself: rerun
`/ob-analyze`, not `/ob-start`, whenever you change `obconfig.yaml` or `artifacts/`.

**Repair gate.** If the YAML is invalid, it reports the position without printing values:

```text
obconfig.yaml is invalid at line 12, column 3: <redacted reason>. Repair it now? (yes/no)
```

`yes` applies a known safe repair after writing a mode-0600 backup, then revalidates.
`no` stops and leaves the file untouched. Anything else repeats the question. If there
is no safe repair (for example, ambiguous malformed YAML), the run stops and you edit
the file by hand.

**Proceed gate.** A valid file produces a redacted summary, then the proceed question:

```text
Configuration summary (redacted)
Application: storefront
Deployment environment: production
Production URLs: 1
Artifacts: artifacts — 4 files, tree 3f1c9a0b7d2e, delta +1 ~0 -0
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

`no` stops with no network or analysis activity. `yes` authorizes exactly one analysis
of exactly this configuration and artifact set. If you edit `obconfig.yaml` or the
artifacts while that analysis is still running, it is not published; rerun
`/ob-analyze` to summarize and analyze the edited inputs.

## Security assessment modes

`security_assessment.mode` controls how obengineer gathers security evidence. The
default, `passive`, reviews source, configuration, dependencies, supplied artifacts,
browser/runtime observations, and requests made by the application's normal flow. It
makes no additional security-specific requests. `none` opts out of this screening and
records the resulting evidence gap.

Optional `safe-active` performs the passive review plus two fixed checks against every
exact HTTPS origin listed in `security_assessment.authorized_origins`:

- `HEAD /robots.txt`
- `HEAD /.well-known/security.txt`

These checks use obengineer's built-in Python HTTPS executor, not ZAP, Burp, Nmap,
Nuclei, or another penetration-testing tool. The executor verifies TLS, rejects private
or mismatched DNS and peer addresses, does not follow redirects, sends no credentials,
and permits at most one request per second and 100 requests in total. It does not crawl,
log in, brute force, fuzz, submit forms, generate load, exploit findings, or make
state-changing requests.

The generated agent wiki applies the complete
[security assessment contract](../skills/references/security-assessment.md), including
OWASP coverage and evidence rules.

## Entitlements and limits

Analysis measures `sf.org` usage and the enforced `sf.org.limit.*` system limits when
Observability Cloud access is configured. An enforced limit is not a contractual
entitlement; contract terms are reported as unavailable unless a separate measured
source supports them.

## Migrating older inputs

If no `obconfig.yaml` exists but a legacy `.env`, `.env.template`, or
`docs/observability/engagement-inputs.yaml` does, `/ob-start` lists those files and the
destination keys, then asks the repair gate. After `yes` it copies the retained facts
into a new `obconfig.yaml` and leaves the legacy files in place. Conflicts, unresolved
secret references, multiple deployment environments, and artifact paths outside the
selected directory must be resolved by hand. New runs always write schema v4;
historical accepted analyses are never rewritten.

## Common problems

| Message or symptom | Fix |
|---|---|
| `Created local obconfig.yaml. Edit it and rerun /ob-start.` | Expected on the first run. Fill in at least the minimum configuration, then rerun. |
| The run refuses because the file is tracked, not ignored, a symlink, or not mode 0600. | `git rm --cached obconfig.yaml`, confirm `.gitignore` contains `/obconfig.yaml`, and run `chmod 600 obconfig.yaml`. |
| `obconfig.yaml is invalid at line …` with no safe repair. | Open the file at the reported line and column. Duplicate keys are a common cause. |
| A paired-field error for `splunk.observability` or `splunk.platform`. | Set both `realm` and `read_token`, or all of `host`, `read_token`, and `index_allowlist`, or leave the whole block empty. |
| `production_urls` error. | Add at least one production URL, or explain why there is none in `no_browser_reason`. |
| The analysis says a source is `not-configured`. | Expected when that `splunk` block is empty. Add read-only access and rerun `/ob-analyze` to produce a new version. |
| `/ob-implement` stops asking for authorization. | `initial_scope.authorized` is `unknown`. Set it to `full`, `repositories`, or `parent_folders`. |

## Internals

These details matter only when debugging the scripts under
`skills/engagement-intake/scripts/`.

- **One-shot authorization.** A `yes` at the proceed gate writes a local record under
  `.obengineer/` bound to the config digest, the full artifact file list and digests,
  the command, and the intended version `V<N>`. Analysis takes that record exactly once
  before doing any work ("claims" it); a second or concurrent attempt fails. Each
  network step re-checks that the inputs still match.
- **Configuration projection.** Analysis never reads `obconfig.yaml` directly. It reads
  a redacted JSON view from `manage_obconfig.py config-projection` that contains targets,
  constraints, scope, and availability flags but no secrets. All script output passes
  through one redactor that removes tokens, the password, the login id, full index
  names, and source lines.
- **Direct API and safe-active calls.** `manage_obconfig.py direct-api --phase analysis`
  (and `--phase verification` for `/ob-verify`) makes the tenant calls and returns
  redacted results for the provenance ledger. `manage_obconfig.py safe-active` makes the
  two fixed checks only in `safe-active` mode and zero requests otherwise.
- **Binding the published commit.** After the analysis is generated and staged,
  `finalize` records the exact Git tree being committed, `dispatch` records the commit,
  and `verify-dispatch` re-checks it immediately before push and PR creation, so the PR
  contains exactly what was validated. `consume` then marks the artifact snapshot as
  analyzed; `abort` releases the authorization after a decline or failure without
  changing that baseline. Edits made after `finalize` belong to the next run.
