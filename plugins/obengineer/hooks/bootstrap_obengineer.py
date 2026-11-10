#!/usr/bin/env python3
"""SessionStart hook: report whether this plugin's prerequisites are available.

Read-only and non-fatal by design. It installs nothing, contacts nothing outside
localhost, and always exits 0. PyYAML supports guided inputs; Word rendering is
optional and its missing packages are reported as an optional capability.
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


def check_runtime() -> tuple[bool, str]:
    try:
        import yaml
    except ImportError:
        return False, "PyYAML missing — run: pip install PyYAML==6.0.3"
    if yaml.__version__ != "6.0.3":
        return False, (
            f"PyYAML {yaml.__version__} found; run: pip install PyYAML==6.0.3"
        )
    return True, "PyYAML 6.0.3 available"


def check_optional_word() -> tuple[bool, str]:
    try:
        import docx  # noqa: F401
        import markdown_it
    except ImportError:
        return True, (
            "optional Word rendering unavailable — run when needed: "
            "pip install python-docx markdown-it-py==4.2.0 PyYAML==6.0.3"
        )
    if markdown_it.__version__ != "4.2.0":
        return True, (
            f"optional Word rendering has markdown-it-py {markdown_it.__version__}; "
            "run: pip install markdown-it-py==4.2.0"
        )
    return True, "optional Word rendering available"


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
        "runtime": check_runtime(),
        "word": check_optional_word(),
        "mcp": check_local_mcp(),
    }.items():
        print(f"  {'ok  ' if passed else 'warn'} {label}: {detail}")
        ok = ok and passed
    if not ok:
        print("  Skills still load; the warnings above limit what can be produced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
