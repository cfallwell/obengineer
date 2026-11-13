from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location(
        "work_order_state", SCRIPTS / "work_order_state.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


state = _load()

APP = "shop"
VERSION = "V1"

ORDERS = {
    "WO-001": {"kind": "foundation", "depends_on": []},
    "WO-002": {"kind": "foundation", "depends_on": ["WO-001"]},
    "WO-010": {"kind": "use-case", "subordinates": ["WO-013", "WO-012", "WO-011"]},
    "WO-011": {"kind": "dashboard", "parents": ["WO-010"]},
    "WO-012": {"kind": "business-transaction", "parents": ["WO-010"]},
    "WO-013": {"kind": "workflow", "parents": ["WO-010"]},
}


def write_wiki(root: Path, deny: list[str] | None = None) -> Path:
    notes = root / "wiki" / "apps" / APP / "versions" / VERSION / "implementation" / "work-orders"
    notes.mkdir(parents=True)
    for order_id, fields in ORDERS.items():
        fm = {
            "work_order_id": order_id,
            "kind": fields["kind"],
            "parents": fields.get("parents", []),
            "subordinates": fields.get("subordinates", []),
            "depends_on": fields.get("depends_on", []),
            "status": "ready" if fields["kind"] == "foundation" else "blocked",
            "revision": 1,
        }
        (notes / f"{order_id}.md").write_text(
            "---\n" + yaml.safe_dump(fm) + "---\n\n# " + order_id + "\n"
        )
    schema = root / "docs" / "observability"
    schema.mkdir(parents=True)
    (schema / "attribute-schema.json").write_text(
        json.dumps({"deny": deny or ["user.email", "card.number"]})
    )
    return root


def run(root: Path, *args: str) -> int:
    return state.main([args[0], "--repo", str(root), "--app", APP, "--version", VERSION, *args[1:]])


def gate(root: Path, order_id: str, capsys, *extra: str) -> tuple[int, dict]:
    capsys.readouterr()
    code = run(root, "gate", "--work-order", order_id, *extra)
    return code, json.loads(capsys.readouterr().out)


def change_file(root: Path, name: str, payload: dict) -> str:
    path = root / name
    path.write_text(yaml.safe_dump(payload))
    return str(path)


def valid_change(**overrides) -> dict:
    payload = {
        "reason": "Align span naming with the platform convention.",
        "requested_by_role": "sre",
        "changes": {
            "attributes": {"add": ["checkout.step"], "rename": [{"from": "cart.size", "to": "cart.item_count"}]},
            "spans": {"add": ["checkout.validate"]},
            "notes": ["Keep the existing route classifier."],
        },
    }
    payload.update(overrides)
    return payload


def ledger(root: Path) -> dict:
    return yaml.safe_load(state.ledger_path(root, APP, VERSION).read_text())


def complete_foundation(root: Path) -> None:
    for order_id in ("WO-001", "WO-002"):
        assert run(root, "set-status", "--work-order", order_id, "--status", "implemented") == 0


def test_init_writes_ledger_and_refuses_overwrite(tmp_path):
    root = write_wiki(tmp_path)
    assert run(root, "init") == 0
    data = ledger(root)
    assert data["schema_version"] == 1
    assert data["analysis_version"] == VERSION
    entry = data["work_orders"]["WO-012"]
    assert entry["kind"] == "business-transaction"
    assert entry["revision"] == 1
    assert entry["implemented_revision"] is None
    assert entry["pull_requests"] == []
    assert run(root, "init") == 1
    assert run(root, "verify") == 0


def test_foundation_gate_blocks_then_releases(tmp_path, capsys):
    root = write_wiki(tmp_path)
    run(root, "init")
    code, result = gate(root, "WO-001", capsys)
    assert code == 0 and result["runnable"]
    code, result = gate(root, "WO-002", capsys)
    assert code == 1 and "WO-001" in result["reason"]
    code, result = gate(root, "WO-012", capsys)
    assert code == 1 and not result["runnable"]

    assert run(root, "set-status", "--work-order", "WO-001", "--status", "implemented",
               "--pr", "https://example.test/pr/1") == 0
    code, _ = gate(root, "WO-002", capsys)
    assert code == 0
    code, _ = gate(root, "WO-012", capsys)
    assert code == 1

    assert run(root, "set-status", "--work-order", "WO-002", "--status", "verified") == 1
    assert run(root, "set-status", "--work-order", "WO-002", "--status", "implemented") == 0
    code, result = gate(root, "WO-012", capsys)
    assert code == 0 and result["revision"] == 1
    assert result["revision_path"].endswith("work-orders/WO-012.md")
    assert ledger(root)["work_orders"]["WO-001"]["pull_requests"] == ["https://example.test/pr/1"]
    assert ledger(root)["work_orders"]["WO-001"]["implemented_revision"] == 1


def test_use_case_reports_next_subordinate_in_kind_order(tmp_path, capsys):
    root = write_wiki(tmp_path)
    run(root, "init")
    complete_foundation(root)
    code, result = gate(root, "WO-010", capsys)
    assert code == 0 and result["next_subordinate"] == "WO-013"
    run(root, "set-status", "--work-order", "WO-013", "--status", "implemented")
    _, result = gate(root, "WO-010", capsys)
    assert result["next_subordinate"] == "WO-012"


def test_reimplement_override_required(tmp_path, capsys):
    root = write_wiki(tmp_path)
    run(root, "init")
    complete_foundation(root)
    run(root, "set-status", "--work-order", "WO-012", "--status", "implemented")
    code, result = gate(root, "WO-012", capsys)
    assert code == 1 and "--reimplement" in result["reason"]
    code, result = gate(root, "WO-012", capsys, "--reimplement")
    assert code == 0 and result["runnable"]


def test_revise_chain_and_digest_verify(tmp_path, capsys):
    root = write_wiki(tmp_path)
    run(root, "init")
    complete_foundation(root)
    run(root, "set-status", "--work-order", "WO-012", "--status", "implemented")
    assert run(root, "revise", "--work-order", "WO-012", "--file",
               change_file(root, "c1.yaml", valid_change())) == 0
    assert run(root, "revise", "--work-order", "WO-012", "--file",
               change_file(root, "c2.yaml", valid_change(requested_by_role="engineering"))) == 0
    entry = ledger(root)["work_orders"]["WO-012"]
    assert entry["revision"] == 3
    assert entry["status"] == "changed"
    assert entry["implemented_revision"] == 1

    r2 = state.revision_path(root, APP, VERSION, "WO-012", 2)
    r3 = state.revision_path(root, APP, VERSION, "WO-012", 3)
    note = state.accepted_note(root, APP, VERSION, "WO-012")
    assert state.frontmatter(r2)["previous_digest"] == state.sha256(note)
    assert state.frontmatter(r3)["previous_digest"] == state.sha256(r2)
    assert run(root, "verify") == 0

    code, result = gate(root, "WO-012", capsys)
    assert code == 1
    code, result = gate(root, "WO-012", capsys, "--reimplement")
    assert code == 0 and result["revision"] == 3
    assert result["revision_path"].endswith("revisions/WO-012/R3.md")


def test_revise_rejected_for_foundation_and_use_case(tmp_path):
    root = write_wiki(tmp_path)
    run(root, "init")
    path = change_file(root, "c.yaml", valid_change())
    assert run(root, "revise", "--work-order", "WO-001", "--file", path) == 1
    assert run(root, "revise", "--work-order", "WO-010", "--file", path) == 1
    assert ledger(root)["work_orders"]["WO-001"]["revision"] == 1


def test_revise_rejects_deny_listed_and_invalid_input(tmp_path):
    root = write_wiki(tmp_path)
    run(root, "init")
    denied = valid_change(changes={"attributes": {"add": ["user.email"]}})
    renamed = valid_change(changes={"attributes": {"rename": [{"from": "a.b", "to": "card.number"}]}})
    bad_name = valid_change(changes={"spans": {"add": ["Checkout Validate"]}})
    person = valid_change(requested_by_role="Jane Doe")
    empty_reason = valid_change(reason="  ")
    for index, payload in enumerate((denied, renamed, bad_name, person, empty_reason)):
        path = change_file(root, f"bad{index}.yaml", payload)
        assert run(root, "revise", "--work-order", "WO-013", "--file", path) == 1
    assert ledger(root)["work_orders"]["WO-013"]["revision"] == 1
    assert not (state.state_dir(root, APP, VERSION) / "revisions").exists()


def test_verify_detects_tampering(tmp_path, capsys):
    root = write_wiki(tmp_path)
    run(root, "init")
    run(root, "revise", "--work-order", "WO-013", "--file", change_file(root, "c1.yaml", valid_change()))
    run(root, "revise", "--work-order", "WO-013", "--file", change_file(root, "c2.yaml", valid_change()))
    assert run(root, "verify") == 0

    r2 = state.revision_path(root, APP, VERSION, "WO-013", 2)
    original = r2.read_text()
    r2.write_text(original + "\nedited later\n")
    capsys.readouterr()
    assert run(root, "verify") == 1
    assert "R3 previous_digest" in capsys.readouterr().out
    r2.write_text(original)

    note = state.accepted_note(root, APP, VERSION, "WO-013")
    note.write_text(note.read_text() + "\nedited\n")
    assert run(root, "verify") == 1
    note.write_text(note.read_text().replace("\nedited\n", ""))
    assert run(root, "verify") == 0

    r2.unlink()
    capsys.readouterr()
    assert run(root, "verify") == 1
    assert "do not match ledger revision" in capsys.readouterr().out


LEGACY_ORDERS = {
    "WO-001": {"status": "implemented", "depends_on": []},
    "WO-002": {"status": "ready", "depends_on": ["WO-001"]},
    "WO-003": {"status": "ready", "depends_on": ["WO-002"]},
    "WO-004": {"status": "blocked", "depends_on": []},
}


def write_legacy_wiki(root: Path) -> Path:
    notes = root / "wiki" / "apps" / APP / "versions" / VERSION / "implementation" / "work-orders"
    notes.mkdir(parents=True)
    for order_id, fields in LEGACY_ORDERS.items():
        fm = {"work_order_id": order_id, "selectors": [], **fields}
        (notes / f"{order_id}.md").write_text(
            "---\n" + yaml.safe_dump(fm) + "---\n\n# " + order_id + "\n"
        )
    return root


def test_legacy_v3_init_gate_and_revise_refusal(tmp_path, capsys):
    root = write_legacy_wiki(tmp_path)
    notes = {p: p.read_bytes() for p in (
        root / "wiki" / "apps" / APP / "versions" / VERSION / "implementation" / "work-orders"
    ).glob("*.md")}
    assert run(root, "init") == 0
    data = ledger(root)
    assert data["mode"] == "legacy"
    assert all("kind" not in entry for entry in data["work_orders"].values())
    assert data["work_orders"]["WO-001"]["implemented_revision"] == 1
    assert run(root, "verify") == 0

    code, result = gate(root, "WO-002", capsys)
    assert code == 0 and result["mode"] == "legacy" and result["revision_paths"] == []
    code, result = gate(root, "WO-003", capsys)
    assert code == 1 and "WO-002" in result["reason"]
    code, result = gate(root, "WO-004", capsys)
    assert code == 1 and "blocked" in result["reason"]
    code, result = gate(root, "WO-001", capsys)
    assert code == 1 and "--reimplement" in result["reason"]
    code, _ = gate(root, "WO-001", capsys, "--reimplement")
    assert code == 0

    assert run(root, "set-status", "--work-order", "WO-002", "--status", "implemented") == 0
    code, _ = gate(root, "WO-003", capsys)
    assert code == 0

    capsys.readouterr()
    assert run(root, "revise", "--work-order", "WO-003", "--file",
               change_file(root, "c.yaml", valid_change())) == 1
    assert "v4 work-order hierarchy" in capsys.readouterr().out
    assert not (state.state_dir(root, APP, VERSION) / "revisions").exists()
    assert all(p.read_bytes() == content for p, content in notes.items())


def test_mixed_kind_notes_are_rejected(tmp_path):
    root = write_wiki(tmp_path)
    note = state.accepted_note(root, APP, VERSION, "WO-013")
    fm = state.frontmatter(note)
    del fm["kind"]
    note.write_text("---\n" + yaml.safe_dump(fm) + "---\n\n# WO-013\n")
    assert run(root, "init") == 1
    assert not state.ledger_path(root, APP, VERSION).exists()


def test_verified_requires_current_revision_implemented(tmp_path, capsys):
    root = write_wiki(tmp_path)
    run(root, "init")
    complete_foundation(root)
    run(root, "set-status", "--work-order", "WO-013", "--status", "implemented")
    run(root, "set-status", "--work-order", "WO-012", "--status", "implemented")
    _, result = gate(root, "WO-010", capsys)
    assert result["next_subordinate"] == "WO-011"
    assert run(root, "revise", "--work-order", "WO-013", "--file",
               change_file(root, "c.yaml", valid_change())) == 0
    _, result = gate(root, "WO-010", capsys)
    assert result["next_subordinate"] == "WO-013"

    assert run(root, "set-status", "--work-order", "WO-013", "--status", "verified") == 1
    assert ledger(root)["work_orders"]["WO-013"]["status"] == "changed"
    assert run(root, "set-status", "--work-order", "WO-013", "--status", "in-progress") == 0
    assert run(root, "set-status", "--work-order", "WO-013", "--status", "verified") == 1
    assert run(root, "set-status", "--work-order", "WO-013", "--status", "implemented") == 0
    assert run(root, "set-status", "--work-order", "WO-013", "--status", "verified") == 0
    assert ledger(root)["work_orders"]["WO-013"]["implemented_revision"] == 2


def test_verify_flags_verified_entry_behind_current_revision(tmp_path, capsys):
    root = write_wiki(tmp_path)
    run(root, "init")
    complete_foundation(root)
    run(root, "set-status", "--work-order", "WO-013", "--status", "implemented")
    run(root, "revise", "--work-order", "WO-013", "--file",
        change_file(root, "c.yaml", valid_change()))
    data = ledger(root)
    data["work_orders"]["WO-013"]["status"] = "verified"
    state.write_ledger(root, APP, VERSION, data)
    capsys.readouterr()
    assert run(root, "verify") == 1
    assert "WO-013: verified but implemented revision 1 is not current revision 2" in (
        capsys.readouterr().out
    )


def test_show_applies_revision_chain_cumulatively(tmp_path, capsys):
    root = write_wiki(tmp_path)
    run(root, "init")
    r2 = valid_change(changes={
        "attributes": {"add": ["checkout.step", "cart.coupon"],
                       "rename": [{"from": "cart.size", "to": "cart.item_count"}]},
        "spans": {"add": ["checkout.validate"]},
        "notes": ["Keep the existing route classifier."],
    })
    r3 = valid_change(requested_by_role="engineering", changes={
        "attributes": {"remove": ["cart.coupon", "order.legacy_id"],
                       "rename": [{"from": "cart.item_count", "to": "cart.items"},
                                  {"from": "checkout.step", "to": "checkout.stage"}]},
        "spans": {"rename": [{"from": "checkout.submit", "to": "checkout.place_order"}]},
        "names": {"rename": [{"from": "checkout", "to": "checkout.flow"}]},
        "notes": ["Use the platform span prefix."],
    })
    assert run(root, "revise", "--work-order", "WO-013", "--file", change_file(root, "r2.yaml", r2)) == 0
    assert run(root, "revise", "--work-order", "WO-013", "--file", change_file(root, "r3.yaml", r3)) == 0

    code, result = gate(root, "WO-013", capsys)
    assert result["revision_paths"] == [
        f"wiki/apps/{APP}/implementation/{VERSION}/revisions/WO-013/R2.md",
        f"wiki/apps/{APP}/implementation/{VERSION}/revisions/WO-013/R3.md",
    ]
    assert result["accepted_note"].endswith("work-orders/WO-013.md")

    capsys.readouterr()
    assert run(root, "show", "--work-order", "WO-013") == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["revision_paths"] == result["revision_paths"]
    changes = shown["effective_changes"]
    assert changes["attributes"] == {
        "add": ["checkout.stage"],
        "remove": ["order.legacy_id"],
        "rename": [{"from": "cart.size", "to": "cart.items"}],
    }
    assert changes["spans"] == {
        "add": ["checkout.validate"],
        "remove": [],
        "rename": [{"from": "checkout.submit", "to": "checkout.place_order"}],
    }
    assert changes["names"] == {"rename": [{"from": "checkout", "to": "checkout.flow"}]}
    assert [n["revision"] for n in changes["notes"]] == [2, 3]
    assert [r["requested_by_role"] for r in shown["revisions"]] == ["sre", "engineering"]

    r2_path = state.revision_path(root, APP, VERSION, "WO-013", 2)
    r2_path.write_text(r2_path.read_text() + "\nedited\n")
    assert run(root, "show", "--work-order", "WO-013") == 1
