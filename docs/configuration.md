# Configuration

Project-root [`obconfig.yaml.template`](../obconfig.yaml.template) is the only authority
for field definitions, defaults, examples, consequences, and secret annotations. Do not
duplicate its field table in documentation.

## Set up

```bash
cp obconfig.yaml.template obconfig.yaml
chmod 600 obconfig.yaml
# edit obconfig.yaml, then run /ob-start
```

Project install adds exact root ignores for `/obconfig.yaml` and `/.obengineer/`.
`/ob-start` can create the local copy atomically and will stop so it can be edited.
Actual config, backups, artifact manifests, and authorization state remain local.

Plaintext values are accepted for the dummy test password and Splunk Observability
Cloud/Platform read tokens. `${VAR}` is not required and has no special meaning.
Use only a disposable dummy account and least-privilege read tokens. Rotate temporary
dummy access after use.

## Gates

Validation detects duplicate YAML keys and reports exact redacted line/column errors.
Only exact `yes` permits a catalogued safe repair, with a mode-0600 backup and
post-repair validation. Arbitrary malformed YAML is never guessed.
Identity-bound local-state updates/removals use atomic exchange and quarantine; a
concurrent pathname replacement is restored and preserved. Platforms without the
required exchange syscall fail closed.

A valid run hashes every regular file under `artifacts.directory`, shows a condensed
redacted summary, and asks:

```text
Proceed with analysis using this configuration? (yes/no)
```

Exact `yes` creates one-shot authorization bound to schema version, config digest,
full artifact manifest/delta and tree digest, originating command, and intended immutable
version. Analysis atomically claims that authorization. Any input change invalidates the
claim before API work or finalization; concurrent or repeated claims fail. After all
analysis output is rendered and validated, `finalize` revalidates those inputs and binds
the complete staged Git index tree and runtime-computed manifest of explicit contained
generated-output blobs. The commit must have exactly that tree. `dispatch` records the
matching HEAD commit/tree and `verify-dispatch` rechecks immutable Git objects before
push/PR work.

## Access behavior

Configured Observability Cloud and Splunk Platform blocks mandate direct API attempts in
analysis and verification. Tokens are sent only in HTTPS request headers to validated
exact hosts; redirects do not forward them. Platform searches use only validated exact
indexes. MCP evidence is supplemental.

The supported production commands are:

```bash
python3 skills/engagement-intake/scripts/manage_obconfig.py --project-root . config-projection --command <origin> --intended-version V<N>
python3 skills/engagement-intake/scripts/manage_obconfig.py --project-root . direct-api --phase analysis --command <origin> --intended-version V<N>
python3 skills/engagement-intake/scripts/manage_obconfig.py --project-root . safe-active --command <origin> --intended-version V<N>
python3 skills/engagement-intake/scripts/manage_obconfig.py --project-root . finalize --command <origin> --intended-version V<N> --output docs/observability --output wiki/apps/<app>/versions/V<N>
python3 skills/engagement-intake/scripts/manage_obconfig.py --project-root . dispatch --command <origin> --intended-version V<N>
python3 skills/engagement-intake/scripts/manage_obconfig.py --project-root . verify-dispatch --command <origin> --intended-version V<N>
python3 skills/engagement-intake/scripts/manage_obconfig.py --project-root . direct-api --phase verification
```

The claim-bound projection is the sole supported downstream analysis configuration
source; it exposes required non-secret targets, constraints, context, artifact metadata,
and availability without credentials. Analysis must not read raw `obconfig.yaml`.
The commands securely load ignored mode-0600 config and emit only centralized-redacted JSON.
Safe-active uses fixed HEAD paths/rates/ceilings with DNS and peer-address defenses;
passive/none makes no request. Dispatch begins only after staged-tree finalization, exact
commit, and commit verification succeed. Successful final consume re-verifies the commit
tree/output blobs and advances the artifact baseline to the finalized input snapshot;
declined/failed analysis uses `abort`, which releases only the exact claim. Post-finalize
input edits belong to the next run and do not invalidate consumption of the already
published finalized snapshot.
Analysis and verification append its dispositions and parsed aggregate measurements to
provenance. Missing config emits explicit `not-configured` dispositions; it does not
read `.env` or process environment.

Analysis measures approved `sf.org` usage and `sf.org.limit.*` enforced system limits.
An enforced limit is not contractual entitlement. Contract terms remain unavailable
unless a separate measured API or approved export supports them.

## Legacy migration

When no actual config exists, `/ob-start` may migrate retained facts from local `.env`
and `docs/observability/engagement-inputs.yaml` after the explicit repair gate. Legacy
files are preserved. Conflicts, unresolved secret references, multiple deployment
environments, and artifact paths outside the selected directory require manual
resolution in `obconfig.yaml`.
Migration revalidates source and destination identities through final commit. If another
cooperating same-user process replaces a destination during migration, rollback removes
only files still proven to be migration-owned; replacement bytes are preserved.

New runs use schema v4 only. Historical accepted analyses and their provenance are never
rewritten.
