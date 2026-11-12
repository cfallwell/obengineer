from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location(
        "verify_provenance_ledger",
        SCRIPTS / "verify_provenance_ledger.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = _load()


def valid_ledger() -> dict:
    fact = {
        "id": "FACT-001",
        "provenance": "measured",
        "value": 1,
        "collected_at": "2026-11-09T00:00:00Z",
        "tool": "splunk-observability",
        "method": "SignalFlow query",
        "scope": "org",
        "observation_window": "PT1H",
        "limitations": [],
    }
    digest = hashlib.sha256(
        json.dumps([fact], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": 1,
        "engagement": {"application": "app"},
        "contract": {"sealed_ids": ["FACT-001"]},
        "context_profile": {
            "predicates": {"browser": False, "language:python": True},
            "loaded_references": [{
                "path": "platform/languages/python.md",
                "predicate": "language:python",
            }],
        },
        "sources": [],
        "facts": [fact],
        "runs": [],
        "checks": [],
        "artifacts": [],
        "decisions": [],
        "unresolved": [],
        "seals": {"analysis": {"ids": ["FACT-001"], "digest": digest}},
    }


def write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "provenance-ledger.json"
    path.write_text(json.dumps(data))
    return path


def test_valid_ledger_passes(tmp_path):
    assert verifier.verify(write(tmp_path, valid_ledger())) == []


def test_duplicate_and_dangling_ids_fail(tmp_path):
    data = valid_ledger()
    data["facts"].append(dict(data["facts"][0]))
    data["facts"][0]["source_ids"] = ["missing"]
    failures = verifier.verify(write(tmp_path, data))
    assert any("duplicate ledger id" in failure for failure in failures)
    assert any("references unknown id" in failure for failure in failures)


def test_measured_and_derived_provenance_is_enforced(tmp_path):
    data = valid_ledger()
    data["facts"][0].pop("method")
    data["facts"].append({
        "id": "FACT-002",
        "provenance": "derived",
        "source_fact_ids": [],
        "formula": "",
    })
    failures = verifier.verify(write(tmp_path, data))
    assert any("measured fact missing method" in failure for failure in failures)
    assert any("derived fact needs" in failure for failure in failures)


def test_false_context_predicate_rejects_loaded_reference(tmp_path):
    data = valid_ledger()
    data["context_profile"]["loaded_references"].append({
        "path": "platform/browser.md",
        "predicate": "browser",
    })
    assert any(
        "violates false predicate: browser" in failure
        for failure in verifier.verify(write(tmp_path, data))
    )
    data = valid_ledger()
    data["context_profile"]["loaded_references"].append({
        "path": "platform/browser.md",
        "predicate": "language:python",
    })
    assert any(
        "requires one of ['browser']" in failure
        for failure in verifier.verify(write(tmp_path, data))
    )
    data = valid_ledger()
    data["context_profile"]["predicates"]["language:typescript"] = True
    data["context_profile"]["loaded_references"].append({
        "path": "platform/languages/node.md",
        "predicate": "language:typescript",
    })
    assert verifier.verify(write(tmp_path, data)) == []


def test_seal_mutation_and_secret_shapes_fail(tmp_path):
    data = valid_ledger()
    data["facts"][0]["value"] = "changed"
    data["decisions"].append({
        "id": "DEC-001",
        "note": "ghp_" + ("a" * 30),
    })
    failures = verifier.verify(write(tmp_path, data))
    assert "analysis seal digest does not match sealed entries" in failures
    assert "credential-shaped value in provenance ledger" in failures
