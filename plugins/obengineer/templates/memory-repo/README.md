# Artifact repository scaffold

A project install creates only missing `.gitignore`, `obconfig.yaml.template`, and
`artifacts/README.md`. Existing files are never overwritten. Uninstall removes only
unchanged installer-owned files and preserves actual config, local state, and artifacts.

Copy and protect local configuration:

```bash
cp obconfig.yaml.template obconfig.yaml
chmod 600 obconfig.yaml
```

The actual config is ignored. It may contain least-privilege read tokens and one
disposable dummy password; never commit or print it. `/ob-start` validates it, hashes the
complete `artifacts/` tree, shows a redacted summary, and requires an exact proceed gate.

Configured direct Splunk API attempts are mandatory evidence sources. MCP integrations
may supplement them.
