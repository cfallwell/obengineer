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


def note(title: str, kind: str, status: str, body: str = "Content line.\n") -> str:
    return (
        "---\n"
        f"title: {title}\n"
        f"type: {kind}\n"
        "app: app\n"
        "version: V1\n"
        f"status: {status}\n"
        "updated: 2026-01-01\n"
        "sources: []\n"
        "work_orders: []\n"
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
        note("F-01", "finding", "open")
    )
    (service / "business-transactions" / "checkout.md").write_text(
        note("checkout", "bt", "designed")
    )
    (service / "use-cases" / "checkout.md").write_text(
        note("Checkout", "use-case", "proposed")
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
- F-01
## Use cases
- Checkout
## Workflows and business transactions
- checkout
## Target selectors
- workflow:checkout.submit
## Repository legs
- payments: src/
## Dependencies
- none
## Acceptance evidence
- contract checks
## Verification criteria
- VC-001
## Coordination
- linked PRs
## Manual issue text
Copy this work order.
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
