---
name: engagement-intake
description: >-
  Load and protect schema-v4 obconfig for /ob-start, /ob-add-inputs, and
  /ob-edit-inputs. Validate, safely repair only after explicit consent, hash all
  supplied artifacts, show a redacted summary, and bind one-shot analysis
  authorization to exact input bytes. Use for $engagement-intake or local input changes.
metadata:
  author: obengineer
  version: 0.3.0
  category: observability
---

# Local obconfig lifecycle

The committed project-root `obconfig.yaml.template` is the sole field-definition
authority. The actual project-root `obconfig.yaml` is local, ignored, mode `0600`, and
may hold plaintext read-only tenant tokens and one dummy test password. It is never
committed, copied to generated output, or printed.

The deterministic implementation is:

- `scripts/obconfig.py` — secure loading, marked validation, centralized redaction,
  bounded repair, artifact tree hashing, summary, and authorization binding;
- `scripts/manage_obconfig.py` — `init`, `validate`, `repair`, `summary`, `changed`,
  `authorize`, atomic `claim`, `consume`, claim-bound `direct-api`, fixed-policy
  `safe-active`, and `migrate-legacy` commands;
- `scripts/direct_api.py` — fixed read-only Observability Cloud and Platform request
  adapters; and
- `schemas/obconfig.schema.json` — machine shape and schema-derived secret registry.

## Required flow

Follow [`../../prompts/00-load-obconfig.md`](../../prompts/00-load-obconfig.md).

1. Preflight refuses a symlink/non-regular/tracked/non-ignored config before parsing.
   Missing config is copied from the template at `0600`, then the run stops for editing.
2. Duplicate keys and syntax/semantic failures carry exact redacted line/column errors.
   Ask `Repair it now? (yes/no)`; only exact `yes` permits catalogued, backed-up repair.
3. Hash the complete configured artifact directory every run. Added/changed files are
   reread, deleted context is removed, and unchanged path/length/digest context alone is
   reusable.
4. Show the condensed redacted summary and ask exactly
   `Proceed with analysis using this configuration? (yes/no)`.
5. Exact `yes` writes one-shot authorization bound to config, full artifact
   manifest/delta and tree digest, schema, command, and intended version. Analysis must
   atomically claim it; each network/dispatch consumer revalidates it. Advance the
   artifact baseline only on successful final consume.

`/ob-add-inputs` and `/ob-edit-inputs` are compatibility entry points. They never edit
YAML or ask field questions. Unchanged config prints
`Edit obconfig.yaml, then rerun this command.`; changed config uses the same proceed gate.

## Security invariants

- Secret paths come only from the schema registry. Defense-in-depth key-name and
  credential-shape filtering covers unknown extensions.
- Every terminal message, error, state/provenance projection, and adapter result passes
  through `Redactor`. No source excerpt or config value appears in parser errors.
- Local state, backups, temporary rewrites, and actual config are regular non-symlink
  files at `0600`; writes are same-directory atomic and fsynced.
- Artifact paths are project-relative and directory-only. Traversal, symlinks, special
  files, unreadable files, and stat/open/read races fail closed.
- `passive` performs no safe-active probes. `safe-active` requires normalized exact
  public HTTPS origins and the supported executor's fixed non-mutating paths/method,
  DNS/peer checks, request/rate ceilings, and no redirects. `none` records a coverage gap.
- Observability realm/token and Platform HTTPS host/token/index allowlist are paired.
  Wildcard indexes and cross-origin redirect credential forwarding are forbidden.
- Direct API attempts are mandatory in analysis and verification when configured.
  The supported production entry point is `manage_obconfig.py --project-root .
  direct-api --phase <analysis|verification>` (with claim command/version in analysis);
  it emits centralized-redacted JSON for
  provenance. Tokens exist only in request headers. MCP evidence supplements but never
  replaces or relabels the direct attempt.
- `.env`, process environment, and legacy engagement input are never runtime fallback
  sources. `${VAR}` has no special semantics in schema v4.

## Migration

When `obconfig.yaml` is absent, detect legacy names without reading values. After exact
repair consent, `migrate-legacy` maps deterministic retained fields, uses legacy YAML
over `.env` for non-secret facts, accepts actual local token values from `.env`, and
blocks redacted conflicts/unresolved references. It preserves every legacy file.
Multiple legacy environments and artifact paths outside the chosen directory require
the human to select or move them in `obconfig.yaml`.

Historical accepted analysis versions and their old inputs/provenance remain immutable
and readable. Every new analysis uses schema v4 only.
