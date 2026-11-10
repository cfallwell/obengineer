from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verify_analysis_site.py"
spec = importlib.util.spec_from_file_location("verify_analysis_site", SCRIPT)
verify = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verify
spec.loader.exec_module(verify)


@pytest.fixture
def site(tmp_path: Path) -> tuple[Path, Path]:
    version = tmp_path / "docs" / "observability" / "analysis" / "app" / "V1"
    version.parent.mkdir(parents=True)
    (version.parent / "index.md").write_text("[V1](V1/index.md)\n")
    detail_paths = {
        "Architecture": "overview",
        "Findings": "findings",
        "Instrumentation strategy": "strategy",
        "Implementation path": "implementation",
        "Use cases": "use-cases",
        "Workflows": "workflows",
        "Business transactions": "business-transactions",
        "Shared signal contracts": "contracts",
        "Operations and verification": "operations",
        "Reference": "reference",
    }
    for label, directory in detail_paths.items():
        target = version / directory
        target.mkdir(parents=True)
        (target / "index.md").write_text(
            f"[Analysis](../index.md) / **{label}**\n\n# {label}\n"
        )
    wiki = (
        tmp_path / "wiki" / "apps" / "app" / "versions" / "V1" /
        "implementation" / "work-orders"
    )
    wiki.mkdir(parents=True)
    (wiki / "index.md").write_text("# Work orders\n")
    rows = [
        f"| {label} | Detail | [Open]({directory}/index.md) |"
        for label, directory in detail_paths.items()
    ]
    rows.insert(
        4,
        "| Work orders | Queue | "
        "[Open](../../../../../wiki/apps/app/versions/V1/"
        "implementation/work-orders/index.md) |",
    )
    (version / "index.md").write_text(
        "[V1]\n\n[Analysis](../index.md)\n\n# Analysis\n\n"
        "> **Side-panel navigation**\n\n"
        "> **Next steps**\n\n"
        "## Changes in this version\n\nInitial run.\n\n"
        "## Contents\n\n"
        "| Section | What it contains | Open |\n"
        "|---|---|---|\n"
        + "\n".join(rows)
        + "\n\n## Analysis summary\n\nSummary.\n\n"
        "| Priority findings | Primary use cases |\n"
        "|---|---|\n"
        "| Finding | Use case |\n"
    )
    return version, tmp_path


def test_conforming_site_passes(site):
    version, root = site
    assert verify.check(version, root) == []


def test_broken_link_fails(site):
    version, root = site
    (version / "index.md").write_text(
        (version / "index.md").read_text() + "\n[Missing](missing.md)\n"
    )
    assert any("broken relative link" in failure for failure in verify.check(version, root))


def test_detail_requires_breadcrumb(site):
    version, root = site
    (version / "overview" / "index.md").write_text("# Architecture\n")
    assert any("no Analysis breadcrumb" in failure for failure in verify.check(version, root))


def test_localhost_preview_fails(site):
    version, root = site
    (version / "overview" / "index.md").write_text(
        "[Analysis](../index.md)\n\nhttp://localhost:4173\n"
    )
    assert any("localhost" in failure for failure in verify.check(version, root))


def test_landing_cannot_expand_detail_sections(site):
    version, root = site
    (version / "index.md").write_text(
        (version / "index.md").read_text() + "\n## Findings detail\n\nToo much.\n"
    )
    assert any(
        "approved compact index" in failure
        for failure in verify.check(version, root)
    )


def test_version_cannot_link_newer_wiki(site):
    version, root = site
    newer = (
        root / "wiki" / "apps" / "app" / "versions" / "V2" /
        "implementation" / "work-orders"
    )
    newer.mkdir(parents=True)
    (newer / "index.md").write_text("# Work orders\n")
    (version / "index.md").write_text(
        (version / "index.md").read_text()
        + "\n[Wrong wiki](../../../../../wiki/apps/app/versions/V2/"
        "implementation/work-orders/index.md)\n"
    )
    assert any("links wiki V2" in failure for failure in verify.check(version, root))
