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
    work_orders = (
        tmp_path / "wiki" / "apps" / "app" / "versions" / "V1" /
        "implementation" / "work-orders"
    )
    work_orders.mkdir(parents=True)
    for order in contract["workOrders"]:
        (work_orders / f"{order['id']}.md").write_text(
            f"# {order['id']}\n\n{order['outcome']}\n"
        )
    return version, tmp_path


def test_conforming_site_passes(site):
    version, root = site
    assert verify.check(version, root, FIXTURE / "analysis-contract.json") == []


def test_exact_parent_schema_v2_fixture_renders_and_verifies_without_mutation(
    tmp_path,
):
    fixture = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "representative-v2"
        / "analysis-contract.json"
    )
    before = fixture.read_bytes()
    contract = json.loads(before)
    app = contract["application"]["id"]
    version = (
        tmp_path / "docs" / "observability" / "analysis" / app / "V1"
    )
    renderer.Renderer(contract, version).render()
    work_orders = (
        tmp_path / "wiki" / "apps" / app / "versions" / "V1"
        / "implementation" / "work-orders"
    )
    work_orders.mkdir(parents=True)
    for order in contract["workOrders"]:
        (work_orders / f"{order['id']}.md").write_text(
            f"# {order['id']}\n\n{order['outcome']}\n"
        )

    assert verify.check(version, tmp_path, fixture) == []
    assert fixture.read_bytes() == before
    cardinality = (version / "contracts" / "cardinality.md").read_text()
    assert "maps legacy `entitlement`, `inUse`, and `headroomAfter` losslessly" in cardinality
    assert "Enforced system limit" in cardinality
    assert "50000" in cardinality
    assert "30000" in cardinality
    assert "12600" in cardinality


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


def test_repeated_character_page_is_not_substantive(site):
    version, root = site
    path = version / "technology" / "index.md"
    path.write_text("[Analysis](../index.md)\n\n# Technology\n\n" + "x" * 500)
    assert any(
        "insufficient substantive content" in failure
        for failure in verify.check(version, root)
    )
