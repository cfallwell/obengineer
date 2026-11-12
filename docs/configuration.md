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

A valid run hashes every regular file under `artifacts.directory`, shows a condensed
redacted summary, and asks:

```text
Proceed with analysis using this configuration? (yes/no)
```

Exact `yes` creates one-shot authorization bound to schema version, config digest,
artifact-tree digest, originating command, and intended immutable version. Any input
change invalidates it before analysis.

## Access behavior

Configured Observability Cloud and Splunk Platform blocks mandate direct API attempts in
analysis and verification. Tokens are sent only in HTTPS request headers to validated
exact hosts; redirects do not forward them. Platform searches use only validated exact
indexes. MCP evidence is supplemental.

Analysis measures approved `sf.org` usage and `sf.org.limit.*` enforced system limits.
An enforced limit is not contractual entitlement. Contract terms remain unavailable
unless a separate measured API or approved export supports them.

## Legacy migration

When no actual config exists, `/ob-start` may migrate retained facts from local `.env`
and `docs/observability/engagement-inputs.yaml` after the explicit repair gate. Legacy
files are preserved. Conflicts, unresolved secret references, multiple deployment
environments, and artifact paths outside the selected directory require manual
resolution in `obconfig.yaml`.

New runs use schema v4 only. Historical accepted analyses and their provenance are never
rewritten.
