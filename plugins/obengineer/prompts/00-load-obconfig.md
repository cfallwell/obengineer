# Prompt 00 — Load local obconfig

**Skill:** `engagement-intake`
**Input:** ignored project-root `obconfig.yaml`
**Authority:** committed project-root `obconfig.yaml.template`

Run only `skills/engagement-intake/scripts/manage_obconfig.py` for intake state. Do not
read configuration directly, read process environment, or reconstruct retired fields.

## Preflight

Before parsing, require `obconfig.yaml` to be a root regular non-symlink file, ignored
by git, untracked, and mode `0600` on POSIX. Require the committed schema and template.
Missing config is copied atomically from the template at `0600`, then the command prints:

> Created local obconfig.yaml. Edit it and rerun /ob-start.

Stop after creation. Never analyze template defaults automatically.

## Repair gate

Validation rejects duplicate keys and reports exact 1-based line/column without a
source excerpt or value. On any error ask exactly:

> obconfig.yaml is invalid at line <n>, column <n>: <redacted reason>. Repair it now? (yes/no)

Only exact `yes` authorizes an enumerated safe repair. Exact `no` leaves bytes, inode,
and mode unchanged and stops. Any other answer repeats the gate. Repair writes a local
mode-0600 backup before mutation, preserves comments and unknown extensions for textual
repairs, atomically replaces, and revalidates. No safe repair means blocked, never a
guess.

## Proceed gate

Hash every regular file in `artifacts.directory` using `ob-artifact-tree-v1`, compare
the local manifest, then show only `obconfig.summary()` output. Ask exactly:

> Proceed with analysis using this configuration? (yes/no)

Only exact `yes` writes one-shot local authorization bound to schema version, config
digest, full artifact manifest/delta and tree digest, command, and intended version.
Exact `no` performs no network/API/analysis action. Analysis atomically claims the
authorization before dispatch; concurrent/repeated claims fail. Revalidate the claim
around every network consumer. After analysis, rendering, and validation, `finalize`
rehashes the claimed inputs and computes the generated-output digest from explicit
contained output paths immediately before commit/push/PR dispatch. Changed
config/artifacts before finalize prevents dispatch. Advance the artifact baseline only
when `consume` records the successfully published finalized snapshot. Input changes
after finalize belong to the next run and do not invalidate that consume.
Declined/failed analysis must invoke `abort` with the same command/version; abort changes
neither baseline nor history. Changed config/artifacts never prevent an explicit abort.

All output goes through the schema-derived redactor. Never show tokens, password, login
ID, full index names, config digest, unknown-extension values, or source lines.
