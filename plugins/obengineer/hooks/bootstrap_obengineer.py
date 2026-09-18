#!/usr/bin/env python3
"""SessionStart hook: report whether this plugin's prerequisites are available.

Read-only and non-fatal by design. It installs nothing, contacts nothing outside
localhost, and always exits 0 — a session must never fail to start because a
document renderer is missing. It prints one short status block so the agent knows
up front whether it can render a customer .docx or must ask the user to install
python-docx.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

PLUGIN_ROOT = Path(
    os.environ.get("CLAUDE_PLUGIN_ROOT")
    or os.environ.get("PLUGIN_ROOT")
    or Path(__file__).resolve().parent.parent
)


def check_renderer() -> tuple[bool, str]:
    try:
        import docx  # noqa: F401
    except ImportError:
        return False, "python-docx missing — run: pip install python-docx"
    return True, "python-docx available"


def check_skills() -> tuple[bool, str]:
    skills = sorted(p.parent.name for p in (PLUGIN_ROOT / "skills").glob("*/SKILL.md"))
    if not skills:
        return False, "no skills found under the plugin root"
    return True, f"{len(skills)} skills: " + ", ".join(skills)


def check_local_mcp() -> tuple[bool, str]:
    """Local MCP servers are optional; note reachability rather than requiring it."""
    config = PLUGIN_ROOT / ".mcp.json"
    if not config.is_file():
        return True, "no MCP servers declared"
    try:
        servers = json.loads(config.read_text()).get("mcpServers", {})
    except json.JSONDecodeError as exc:
        return False, f".mcp.json is not valid JSON: {exc}"
    host_port = []
    for name, spec in servers.items():
        url = spec.get("url", "")
        if "127.0.0.1" not in url and "localhost" not in url:
            continue
        try:
            authority = url.split("//", 1)[1].split("/", 1)[0]
            host, _, port = authority.partition(":")
            with socket.create_connection((host, int(port or 80)), timeout=0.4):
                host_port.append(f"{name} up")
        except (OSError, ValueError, IndexError):
            host_port.append(f"{name} not running (optional)")
    return True, "; ".join(host_port) if host_port else "no local MCP servers"


def main() -> int:
    host = os.environ.get("OBSERVABILITY_ENGINEER_HOST", "claude")
    print(f"obengineer ({host})")
    ok = True
    for label, (passed, detail) in {
        "skills": check_skills(),
        "renderer": check_renderer(),
        "mcp": check_local_mcp(),
    }.items():
        print(f"  {'ok  ' if passed else 'warn'} {label}: {detail}")
        ok = ok and passed
    if not ok:
        print("  Skills still load; the warnings above limit what can be produced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
