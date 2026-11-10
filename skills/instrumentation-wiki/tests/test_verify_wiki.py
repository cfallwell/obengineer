from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verify_wiki.py"
spec = importlib.util.spec_from_file_location("verify_wiki", SCRIPT)
verify = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verify
spec.loader.exec_module(verify)

POINTER = """# Agents

Before changing instrumentation, read `wiki/apps/app/index.md`, resolve the accepted
version, then load only the notes in scope. Do not load every version or the whole wiki.
Update the status and updated fields in the same commit.
"""


def note(
    title: str,
    kind: str,
    status: str,
    body: str = "Content line.\n",
    work_orders: str = "[]",
    extra_frontmatter: str = "",
) -> str:
    return (
        "---\n"
        f"title: {title}\n"
        f"type: {kind}\n"
        "app: app\n"
        "version: V1\n"
        f"status: {status}\n"
        "updated: 2026-01-01\n"
        "sources: []\n"
        f"work_orders: {work_orders}\n"
        f"{extra_frontmatter}"
        "---\n\n"
        f"[Analysis](../../../../../../../docs/observability/analysis/app/V1/index.md)"
        f" / **{title}**\n\n# {title}\n\n{body}"
    )


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    service = (
        tmp_path / "wiki" / "apps" / "app" / "versions" / "V1" /
        "services" / "payments"
    )
    for directory in (
        "contract", "findings", "business-transactions",
        "use-cases", "slos", "business", "workflows", "detectors",
    ):
        (service / directory).mkdir(parents=True, exist_ok=True)
    version = service.parents[1]
    (version / "meta").mkdir(parents=True)
    work_orders = version / "implementation" / "work-orders"
    work_orders.mkdir(parents=True)
    analysis = tmp_path / "docs" / "observability" / "analysis" / "app" / "V1"
    analysis.mkdir(parents=True)
    (analysis / "index.md").write_text("[V1]\n# Analysis\n")
    (tmp_path / "wiki" / "apps" / "app" / "index.md").write_text("[V1]\n")

    (service / "index.md").write_text(note(
        "app — index", "index", "designed",
        body="""One paragraph about the target.

| | Count |
|---|---|
| Open findings | 1 |
| Business transactions | 1 |
| Use cases | 1 |
| Work orders | 1 |
| Objectives | 1 |

- [[contract/cross-cutting]]
- [[findings/F-01-a-key]]
- [[business-transactions/checkout]]
- [[use-cases/checkout]]
- [[slos/checkout-success]]
""",
    ))
    (version / "index.md").write_text(note(
        "V1 index", "index", "designed",
        body="- [[services/payments/index]]\n- [[implementation/work-orders/index]]\n",
    ))
    (version / "meta" / "versions.md").write_text(note(
        "versions", "reference", "verified",
        body="| Component | Version | Checked | Provenance |\n|---|---|---|---|\n| semconv | 1.27 | 2026-01-01 | pin |\n",
    ))
    (version / "meta" / "run-log.md").write_text(
        note("run log", "run-log", "verified")
    )
    (version / "meta" / "decisions.md").write_text(
        note("decisions", "decision", "verified")
    )
    (service / "contract" / "cross-cutting.md").write_text(
        note("cross-cutting", "reference", "designed", "Contract. [[baggage]]\n")
    )
    (service / "contract" / "baggage.md").write_text(note("baggage", "reference", "designed"))
    (service / "contract" / "attribute-schema.json").write_text('{"version":"1"}\n')
    (service / "findings" / "F-01-a-key.md").write_text(
        note("F-01", "finding", "open", work_orders="[WO-001]")
    )
    (service / "business-transactions" / "checkout.md").write_text(
        note("checkout", "bt", "designed", work_orders="[WO-001]")
    )
    (service / "use-cases" / "checkout.md").write_text(
        note("Checkout", "use-case", "proposed", work_orders="[WO-001]")
    )
    (service / "workflows" / "checkout-submit.md").write_text(
        note(
            "checkout.submit", "workflow", "proposed",
            "The checkout submission workflow carries spans, metrics, and verification.\n"
            "Its code location is `src/checkout/submit.ts`.\n"
            "The work order installs the accepted signal contract.\n",
            work_orders="[WO-001]",
        )
    )
    (service / "slos" / "checkout-success.md").write_text(
        note("checkout success", "sli", "proposed")
    )
    (service / "business" / "value-model.md").write_text(
        note("value model", "reference", "proposed", "Incidents: unfilled (`stated`).\n")
    )
    (service / "business" / "public-evidence.md").write_text(
        note("public evidence", "reference", "proposed", "No public sources supplied.\n")
    )
    (work_orders / "index.md").write_text(note(
        "work orders", "index", "proposed", "- [[WO-001]]\n"
    ))
    (work_orders / "WO-001.md").write_text(note(
        "WO-001", "work-order", "proposed",
        body="""## Findings
- [[services/payments/findings/F-01-a-key]]
## Use cases
- [[services/payments/use-cases/checkout]]
## Workflows and business transactions
- [[services/payments/workflows/checkout-submit]]
- [[services/payments/business-transactions/checkout]]
## Target selectors
- Implement the mapped `workflow:checkout.submit` selector for this accepted scope.
## Repository legs
- Change the payments repository only under its authorized `src/` parent.
## Dependencies
- none
## Acceptance evidence
- Preserve passing deterministic contract checks and route classification evidence.
## Verification criteria
- Execute VC-001 and retain the bounded workflow query results.
## Coordination
- Record linked repository and coordination pull requests before completion.
## Manual issue text
Copy this work order into the configured issue tracker without changing scope.
""",
        extra_frontmatter="""work_order_id: WO-001
selectors: [workflow:checkout.submit]
depends_on: []
repository_legs:
  - repository: payments
    paths: [src/]
    changes: [Implement bounded checkout workflow instrumentation in the authorized source tree.]
    tests: [Run deterministic propagation and workflow contract tests for the repository leg.]
""",
    ))

    docs = tmp_path / "docs" / "observability"
    (docs / "implementation-map.json").write_text(json.dumps({
        "schema_version": 1,
        "repositories": [{
            "id": "payments", "remote": "owner/payments",
            "authorized_paths": ["src/"],
        }],
        "targets": [{
            "selector": "workflow:checkout.submit",
            "work_order": "WO-001",
            "repositories": ["payments"],
            "mapping_status": "complete",
            "evidence": [],
        }],
    }))

    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    (tmp_path / ".cursor" / "rules" / "obengineer-wiki.mdc").write_text(POINTER)
    (tmp_path / "CLAUDE.md").write_text(POINTER)
    (tmp_path / "AGENTS.md").write_text(POINTER)
    return service


def failures(service: Path) -> list[str]:
    return verify.check(service, service.parents[6], index_max_lines=200)


def test_a_conforming_wiki_passes(wiki):
    assert failures(wiki) == []


def test_proposed_wiki_does_not_require_acceptance(wiki):
    assert not any("acceptance" in failure for failure in failures(wiki))


def test_broken_wikilink_is_caught(wiki):
    (wiki / "index.md").write_text((wiki / "index.md").read_text() + "\n[[missing]]\n")
    assert any("broken wikilink" in failure for failure in failures(wiki))


def test_frontmatter_requires_version(wiki):
    path = wiki / "use-cases" / "checkout.md"
    path.write_text(path.read_text().replace("version: V1\n", ""))
    assert any("frontmatter has no version" in failure for failure in failures(wiki))


def test_frontmatter_requires_matching_app_and_list_links(wiki):
    path = wiki / "use-cases" / "checkout.md"
    path.write_text(
        path.read_text()
        .replace("app: app", "app: other")
        .replace("sources: []", "sources: F-01")
    )
    result = failures(wiki)
    assert any("does not match" in failure for failure in result)
    assert any("sources must be a list" in failure for failure in result)


def test_verifier_iterates_every_service(wiki):
    other = wiki.parent / "other"
    other.mkdir()
    assert any(
        "services/other" in failure and "missing required note" in failure
        for failure in failures(wiki)
    )


def test_note_requires_analysis_breadcrumb(wiki):
    path = wiki / "use-cases" / "checkout.md"
    path.write_text(path.read_text().replace("[Analysis](", "[Home]("))
    assert any("no Analysis breadcrumb" in failure for failure in failures(wiki))


def test_work_order_requires_reverse_link_sections(wiki):
    path = wiki.parents[1] / "implementation" / "work-orders" / "WO-001.md"
    path.write_text(path.read_text().replace("## Findings", "## Context"))
    assert any("## findings" in failure for failure in failures(wiki))


def test_work_order_status_sets_are_enforced(wiki):
    path = wiki.parents[1] / "implementation" / "work-orders" / "WO-001.md"
    path.write_text(path.read_text().replace("status: proposed", "status: accepted"))
    assert any("status 'accepted'" in failure for failure in failures(wiki))


def test_ready_work_order_requires_acceptance(wiki):
    path = wiki.parents[1] / "implementation" / "work-orders" / "WO-001.md"
    path.write_text(path.read_text().replace("status: proposed", "status: ready"))
    assert any("before acceptance" in failure for failure in failures(wiki))


def test_work_order_rejects_unknown_dependency_and_cycle(wiki):
    path = wiki.parents[1] / "implementation" / "work-orders" / "WO-001.md"
    path.write_text(path.read_text().replace("depends_on: []", "depends_on: [WO-999]"))
    result = failures(wiki)
    assert any("dependencies do not exist" in failure and "WO-999" in failure for failure in result)

    path.write_text(path.read_text().replace("depends_on: [WO-999]", "depends_on: [WO-001]"))
    assert any("dependency cycle" in failure for failure in failures(wiki))


def test_work_order_rejects_invalid_selector_and_meaningless_leg(wiki):
    path = wiki.parents[1] / "implementation" / "work-orders" / "WO-001.md"
    text = path.read_text()
    text = text.replace(
        "selectors: [workflow:checkout.submit]",
        "selectors: [unsupported:checkout]",
    )
    text = text.replace(
        "changes: [Implement bounded checkout workflow instrumentation in the authorized source tree.]",
        "changes: [xxxxx]",
    )
    path.write_text(text)
    result = failures(wiki)
    assert any("invalid target selector" in failure for failure in result)
    assert any("changes is not meaningful" in failure for failure in result)


def test_work_order_rejects_unauthorized_repository_path(wiki):
    path = wiki.parents[1] / "implementation" / "work-orders" / "WO-001.md"
    path.write_text(path.read_text().replace("paths: [src/]", "paths: [../secrets/]"))
    assert any("authorized relative paths" in failure for failure in failures(wiki))


def test_work_order_reverse_links_are_reciprocal(wiki):
    path = wiki / "use-cases" / "checkout.md"
    path.write_text(path.read_text().replace("work_orders: [WO-001]", "work_orders: []"))
    assert any(
        "does not declare the work order" in failure
        for failure in failures(wiki)
    )


def test_index_count_is_checked(wiki):
    path = wiki / "index.md"
    path.write_text(path.read_text().replace("| Work orders | 1 |", "| Work orders | 9 |"))
    assert any("claims 9" in failure for failure in failures(wiki))


def test_pointer_retrieval_rule_is_required(wiki):
    root = wiki.parents[6]
    (root / "CLAUDE.md").write_text("# Agents\n")
    assert any("retrieval rule" in failure for failure in failures(wiki))


def test_credential_is_caught(wiki):
    path = wiki / "findings" / "F-01-a-key.md"
    path.write_text(path.read_text() + "\n-----BEGIN " + "PRIVATE KEY-----\n")
    assert any("private key" in failure for failure in failures(wiki))
