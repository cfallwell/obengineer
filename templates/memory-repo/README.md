# Memory repository template

Copy `.gitignore` and `.env.template` into the root of a new memory repository:

```bash
cp templates/memory-repo/.gitignore templates/memory-repo/.env.template /path/to/memory-repo/
```

In that repository, copy the template and fill it:

```bash
cp .env.template .env
```

`.env` is gitignored. Do not commit it. `.env.template` stays in git with empty values.

The analyze run reads these variables from `.env` or from the process environment. It uses the `splunk-observability` and `splunk-platform` MCP servers and the Splunk API endpoints (Observability and Enterprise) when it inventories existing telemetry. The procedure is `skills/references/existing-telemetry.md` in the toolkit.

Install does not copy this directory and does not write a filled `.env`.
