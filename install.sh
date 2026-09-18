#!/usr/bin/env bash
# Install the obengineer skills and commands into Cursor, Claude Code, or Codex.
#
#   ./install.sh --cursor
#   ./install.sh --all
#   ./install.sh --all --project /path/to/repo
#   ./install.sh --list
#   ./install.sh --all --uninstall
#
# All options: ./install.sh --help
set -euo pipefail
cd "$(dirname "$0")"
exec "${PYTHON:-python3}" scripts/install.py "$@"
