"""Resolve engagement-intake package resources across supported installations."""

from __future__ import annotations

from pathlib import Path

TEMPLATE_NAME = "engagement-inputs.template.yaml"


def engagement_inputs_template(skill_root: Path) -> Path:
    """Prefer the namespaced host companion, then the toolkit/plugin template."""
    host_base = skill_root.parent.parent
    installed = host_base / "obengineer" / "inputs" / TEMPLATE_NAME
    if installed.is_file():
        return installed
    return host_base / "inputs" / TEMPLATE_NAME
