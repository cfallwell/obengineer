"""Tests for the agent-wiki verifier.

Builds a minimal wiki that satisfies agent-wiki.md, asserts the verifier passes
on it, then damages one rule at a time and asserts each damage is caught. A
verifier that cannot fail is decoration.

    python3 -m pytest "obengineer/skills/instrumentation-wiki/tests" -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


verify = _load("verify_wiki")

POINTER = """# Agents

Before changing instrumentation, read `wiki/Customer/app/index.md`, then only the notes
for the BTs and workflows in scope. Do not load the whole wiki. After a change lands, update
the `status` and `updated` fields of the notes you touched in the same commit.
"""


def note(title: str, kind: str, status: str, body: str = "Content line.\n") -> str:
    return (
        "---\n"
        f"title: {title}\n"
        f"type: {kind}\n"
        "customer: Customer\n"
        "app: app\n"
        f"status: {status}\n"
        "updated: 2026-01-01\n"
        "run: v1\n"
        "---\n"
        f"\n# {title}\n\n{body}"
    )


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    app = tmp_path / "wiki" / "Customer" / "app"
    for directory in ("meta", "contract", "findings", "business-transactions",
                      "use-cases", "slos", "business", "implementation/work-orders"):
        (app / directory).mkdir(parents=True, exist_ok=True)

    (app / "index.md").write_text(
        note("app — index", "index", "designed", body="""One paragraph about the target.

| | Count |
|---|---|
| Open findings | 1 |
| Business transactions | 1 |
| Use cases | 1 |
| Work orders | 1 |
| Objectives | 1 |

- [[contract/cross-cutting]]
- [[findings/F-01-a-key-in-a-public-payload]]
- [[business-transactions/checkout]]
- [[use-cases/checkout-flow-f1]]
- [[slos/checkout-success]]
- [[implementation/work-orders/01-the-shared-library]]
"""))
    (app / "meta" / "versions.md").write_text(note("versions", "reference", "verified", body="""| Component | Version | Checked | Provenance |
|---|---|---|---|
| semconv | 1.27.0 | 2026-01-01 | pinned in the contract |
"""))
    (app / "meta" / "run-log.md").write_text(note("run log", "reference", "verified"))
    (app / "meta" / "decisions.md").write_text(note("decisions", "reference", "verified"))
    (app / "contract" / "cross-cutting.md").write_text(
        note("cross-cutting", "reference", "designed", body="The attribute set. [[baggage]]\n"))
    (app / "contract" / "baggage.md").write_text(note("baggage", "reference", "designed"))
    (app / "contract" / "attribute-schema.json").write_text('{"version": "1.0.0"}\n')
    (app / "findings" / "F-01-a-key-in-a-public-payload.md").write_text(
        note("F-01 — a key in a public payload", "finding", "open"))
    (app / "business-transactions" / "checkout.md").write_text(
        note("checkout", "bt", "designed"))
    (app / "use-cases" / "checkout-flow-f1.md").write_text(
        note("Checkout", "use-case", "proposed"))
    (app / "slos" / "checkout-success.md").write_text(
        note("checkout-success", "sli", "proposed"))
    (app / "implementation" / "work-orders" / "01-the-shared-library.md").write_text(
        note("The shared library", "work-order", "proposed"))
    (app / "business" / "value-model.md").write_text(note(
        "value model", "reference", "proposed",
        body="Incidents per month: not supplied (`stated` when the customer gives it).\n"))
    (app / "business" / "public-evidence.md").write_text(note(
        "public evidence", "reference", "proposed",
        body="- Status page, https://status.example.com, 2026-01-01, read 2026-01-02.\n"))

    root = tmp_path
    (root / ".cursor" / "rules").mkdir(parents=True)
    (root / ".cursor" / "rules" / "obengineer-wiki.mdc").write_text(
        "---\nalwaysApply: true\n---\n\n" + POINTER)
    (root / "CLAUDE.md").write_text(POINTER)
    (root / "AGENTS.md").write_text(POINTER)
    return app


def failures(app: Path) -> list[str]:
    return verify.check(app, app.parent.parent.parent, index_max_lines=200)


def test_a_conforming_wiki_passes(wiki: Path):
    assert failures(wiki) == []


def test_a_broken_wikilink_is_caught(wiki: Path):
    (wiki / "business-transactions" / "checkout.md").write_text(
        note("checkout", "bt", "designed", body="Hosts [[workflows/checkout.order.submit]].\n"))
    assert any("broken wikilink" in f for f in failures(wiki))


def test_an_ambiguous_bare_wikilink_is_caught(wiki: Path):
    # Two notes share a stem, so [[checkout]] resolves differently per tool.
    (wiki / "use-cases" / "checkout.md").write_text(note("Checkout", "use-case", "proposed"))
    (wiki / "contract" / "cross-cutting.md").write_text(
        note("cross-cutting", "reference", "designed", body="See [[checkout]].\n"))
    assert any("ambiguous wikilink" in f for f in failures(wiki))


def test_missing_frontmatter_fields_are_caught(wiki: Path):
    (wiki / "slos" / "checkout-success.md").write_text(
        "---\ntitle: checkout-success\ntype: sli\ncustomer: Customer\napp: app\n---\n\n# x\n")
    found = failures(wiki)
    assert any("has no status" in f for f in found)
    assert any("has no updated" in f for f in found)


def test_a_status_from_the_wrong_set_is_caught(wiki: Path):
    # `open` belongs to findings; a BT at `open` means the enum was guessed.
    (wiki / "business-transactions" / "checkout.md").write_text(note("checkout", "bt", "open"))
    assert any("status 'open' is not one of" in f for f in failures(wiki))


def test_an_index_count_that_disagrees_with_the_tree_is_caught(wiki: Path):
    text = (wiki / "index.md").read_text().replace("| Open findings | 1 |",
                                                   "| Open findings | 4 |")
    (wiki / "index.md").write_text(text)
    assert any("claims 4 for 'open findings'" in f for f in failures(wiki))


def test_an_index_that_grew_into_a_summary_is_caught(wiki: Path):
    text = (wiki / "index.md").read_text() + "\n".join(
        f"Workflow {i} does something worth a paragraph." for i in range(220))
    (wiki / "index.md").write_text(text)
    assert any("index.md is" in f and "lines" in f for f in failures(wiki))


def test_a_stub_promoted_to_its_own_note_is_caught(wiki: Path):
    (wiki / "workflows").mkdir()
    (wiki / "workflows" / "checkout.order.submit.md").write_text(
        note("checkout.order.submit", "workflow", "designed", body=""))
    assert any("earns its file" in f for f in failures(wiki))


def test_versions_without_a_provenance_column_is_caught(wiki: Path):
    (wiki / "meta" / "versions.md").write_text(note("versions", "reference", "verified",
                                                    body="""| Component | Version |
|---|---|
| semconv | 1.27.0 |
"""))
    assert any("provenance" in f for f in failures(wiki))


def test_a_missing_host_pointer_is_caught(wiki: Path):
    (wiki.parent.parent.parent / "CLAUDE.md").unlink()
    assert any("no host pointer at CLAUDE.md" in f for f in failures(wiki))


def test_a_pointer_without_the_retrieval_rule_is_caught(wiki: Path):
    (wiki.parent.parent.parent / "AGENTS.md").write_text(
        "Read `wiki/Customer/app/index.md` and update notes in the same commit.\n")
    assert any("AGENTS.md does not carry the retrieval rule" in f for f in failures(wiki))


def test_a_credential_in_a_note_is_caught(wiki: Path):
    # Assembled at runtime so this test file is not itself a committed token.
    token = ".".join(["ey" + "JhbGciOiJIUzI1NiJ9", "ey" + "JzdWIiOiIxMjM0NSJ9", "c2lnbmF0dXJl"])
    (wiki / "contract" / "baggage.md").write_text(note(
        "baggage", "reference", "designed", body=f"Token: {token}\n"))
    assert any("possible jwt" in f for f in failures(wiki))


def test_a_required_note_missing_is_caught(wiki: Path):
    (wiki / "meta" / "run-log.md").unlink()
    assert any("missing required note: meta/run-log.md" in f for f in failures(wiki))


def test_a_value_model_with_no_labelled_figure_is_caught(wiki: Path):
    # An unlabelled business number is indistinguishable from an invented one.
    (wiki / "business" / "value-model.md").write_text(note(
        "value model", "reference", "proposed",
        body="Incidents per month: 40. Cost per hour: $50,000.\n"))
    assert any("labels no figure" in f for f in failures(wiki))


def test_cited_evidence_with_no_read_date_is_caught(wiki: Path):
    (wiki / "business" / "public-evidence.md").write_text(note(
        "public evidence", "reference", "proposed",
        body="- Outage coverage, https://news.example.com/outage, 2026-01-01.\n"))
    assert any("no read date" in f for f in failures(wiki))
