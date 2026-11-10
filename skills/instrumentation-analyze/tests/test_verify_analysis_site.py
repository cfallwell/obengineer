from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "representative"
sys.path.insert(0, str(SCRIPTS))

import render_analysis_site as renderer  # noqa: E402
import verify_analysis_site as verify  # noqa: E402


@pytest.fixture
def site(tmp_path: Path) -> tuple[Path, Path]:
    version = tmp_path / "docs" / "observability" / "analysis" / "app" / "V1"
    contract = json.loads((FIXTURE / "analysis-contract.json").read_text())
    contract["application"]["id"] = "app"
    contract["application"]["name"] = "Representative App"
    renderer.Renderer(contract, version).render()
    return version, tmp_path


def test_conforming_site_passes(site):
    version, root = site
    assert verify.check(version, root, FIXTURE / "analysis-contract.json") == []


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


def test_landing_requires_visible_architecture_summary(site):
    version, root = site
    text = (version / "index.md").read_text()
    text = text.replace("## Architecture summary", "## Architecture details")
    (version / "index.md").write_text(text)
    assert any(
        "Architecture summary" in failure
        for failure in verify.check(version, root)
    )


def test_placeholder_page_fails(site):
    version, root = site
    path = version / "technology" / "index.md"
    path.write_text(path.read_text() + "\n\n## Pending\n\nTBD\n")
    assert any("placeholder" in failure for failure in verify.check(version, root))


def test_empty_heading_fails(site):
    version, root = site
    path = version / "technology" / "index.md"
    path.write_text(path.read_text() + "\n\n## Empty\n\n")
    assert any("empty heading" in failure for failure in verify.check(version, root))
