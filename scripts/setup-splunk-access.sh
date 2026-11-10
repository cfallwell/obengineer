#!/usr/bin/env bash
set -euo pipefail

# Configure read-only Splunk API access for an obengineer artifact repository.
# Run from the artifact repository. Values are written to local .env, never stdout.

ENV_FILE="${OBENGINEER_ENV_FILE:-.env}"
TEMPLATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../templates/memory-repo" 2>/dev/null && pwd || true)"

if [[ ! -t 0 ]]; then
  echo "This setup is interactive; run it in a terminal." >&2
  exit 2
fi

echo "obengineer Splunk access setup"
echo
echo "Create least-privilege read credentials before continuing:"
echo "  Observability Cloud: Profile -> Access Tokens; read APIs are preferred."
echo "  Splunk Platform: create an API token allowed to search only approved indexes."
echo "Leave a prompt blank to keep its current value or skip that integration."
echo

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -n "$TEMPLATE_DIR" && -f "$TEMPLATE_DIR/.env.template" ]]; then
    cp "$TEMPLATE_DIR/.env.template" "$ENV_FILE"
  else
    : > "$ENV_FILE"
  fi
fi
chmod 600 "$ENV_FILE"

upsert() {
  local key="$1" value="$2" tmp
  [[ -n "$value" ]] || return 0
  tmp="$(mktemp "${ENV_FILE}.XXXXXX")"
  awk -v key="$key" -v value="$value" '
    BEGIN { replaced = 0 }
    index($0, key "=") == 1 {
      if (!replaced) print key "=" value
      replaced = 1
      next
    }
    { print }
    END { if (!replaced) print key "=" value }
  ' "$ENV_FILE" > "$tmp"
  chmod 600 "$tmp"
  mv "$tmp" "$ENV_FILE"
}

read -r -p "Observability Cloud realm (for example us0): " realm
if [[ -n "$realm" && ! "$realm" =~ ^[a-z0-9-]+$ ]]; then
  echo "Realm may contain only lowercase letters, digits, and hyphens." >&2
  exit 2
fi
read -r -s -p "Observability Cloud read token: " o11y_token
echo
read -r -p "Splunk Platform API URL (for example https://splunk.example:8089): " splunk_host
read -r -s -p "Splunk Platform read token: " splunk_token
echo
read -r -p "Approved Splunk indexes, comma-separated: " indexes

upsert SPLUNK_REALM "$realm"
upsert SPLUNK_ACCESS_TOKEN "$o11y_token"
upsert SPLUNK_HOST "$splunk_host"
upsert SPLUNK_TOKEN "$splunk_token"
upsert SPLUNK_ENTERPRISE_INDEXES "$indexes"

unset o11y_token splunk_token

if [[ -f .gitignore ]]; then
  if ! awk '$0 == ".env" { found = 1 } END { exit !found }' .gitignore; then
    printf '\n.env\n' >> .gitignore
  fi
else
  printf '.env\n' > .gitignore
fi

echo
echo "Configured names in $ENV_FILE (values were not printed)."
echo "Restart or reload the agent host if it does not automatically reload .env."
