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


def v4_contract() -> dict:
    contract = json.loads((FIXTURE / "analysis-contract.json").read_text())
    contract["application"]["id"] = "app"
    contract["schemaVersion"] = 4
    base = contract["workOrders"]
    finding = contract["findings"][0]["id"]
    use_case = contract["useCases"][0]["id"]

    def order(source: dict, identifier: str, title: str, kind: str, **fields) -> dict:
        item = json.loads(json.dumps(source))
        item.update(id=identifier, title=title, kind=kind, revision=1)
        item.setdefault("parentIds", [])
        item.setdefault("subordinateIds", [])
        item.setdefault("subjectIds", [])
        item.setdefault("findingIds", [])
        item.update(fields)
        return item

    contract["workOrders"] = [
        order(base[0], "WO-001", "Install guardrails", "foundation", findingIds=[finding]),
        order(
            base[1], "WO-002", "Order submission use case", "use-case",
            subjectIds=[use_case],
            subordinateIds=["WO-005", "WO-003", "WO-004"],
        ),
        order(
            base[2], "WO-003", "Checkout transaction", "business-transaction",
            parentIds=["WO-002"], subjectIds=["checkout"],
        ),
        order(
            base[2], "WO-004", "Submit workflow", "workflow",
            parentIds=["WO-002"], subjectIds=["checkout-order-submit"],
        ),
        order(
            base[2], "WO-005", "Checkout dashboard", "dashboard",
            parentIds=["WO-002"],
        ),
    ]
    return contract


def test_v4_work_orders_render_foundation_then_use_case_groups(site):
    version, root = site
    contract = v4_contract()
    site_renderer = renderer.Renderer(
        json.loads((FIXTURE / "analysis-contract.json").read_text()), version
    )
    site_renderer.c = json.loads(json.dumps(contract))
    site_renderer.render_work_orders()
    text = (version / "work-orders" / "index.md").read_text()

    title = contract["useCases"][0]["title"]
    positions = [
        text.index(heading)
        for heading in (
            "## Foundation work orders",
            f"## Use case: {title}",
            "### Use-case work order",
            "### Workflows",
            "### Business transactions",
            "### Dashboards",
        )
    ]
    assert positions == sorted(positions)
    assert "released once all foundation work orders are complete" in text
    assert "| ID | Title | Outcome | Findings | Status | Detail |" in text
    assert contract["findings"][0]["id"] in text
    for absent in ("### Detectors", "### Alert conditions", "### Custom code"):
        assert absent not in text
    assert "Mapping evidence" not in text

    site_renderer.render_work_orders()
    assert (version / "work-orders" / "index.md").read_text() == text

    notes = root / "wiki" / "apps" / "app" / "versions" / "V1" / "implementation" / "work-orders"
    for item in contract["workOrders"]:
        (notes / f"{item['id']}.md").write_text(f"# {item['id']}\n\n{item['outcome']}\n")
    assert verify.check(version, root) == []


def test_v3_work_orders_keep_flat_table(site):
    version, _ = site
    text = (version / "work-orders" / "index.md").read_text()
    assert "| ID | Outcome | Depends on | Status | Repository mapping |" in text
    assert "## Foundation work orders" not in text
