from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location(
        "verify_implementation_map",
        SCRIPTS / "verify_implementation_map.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = _load()


def valid_map() -> dict:
    return {
        "schema_version": 1,
        "repositories": [
            {
                "id": "web",
                "remote": "owner/web",
                "authorized_paths": ["src/"],
                "jira_project": "WEB",
            }
        ],
        "targets": [
            {
                "selector": "workflow:account.update",
                "work_order": "WO-001",
                "repositories": ["web"],
                "mapping_status": "complete",
                "evidence": ["SRC-account-route"],
            }
        ],
    }


def write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "implementation-map.json"
    path.write_text(json.dumps(data))
    return path


def test_valid_map_passes(tmp_path):
    assert verifier.verify(write(tmp_path, valid_map())) == []


def test_empty_map_fails(tmp_path):
    failures = verifier.verify(write(tmp_path, {}))
    assert "repositories must be a list" in failures
    assert "targets must be a non-empty list" in failures


def test_non_object_top_level_fails_cleanly(tmp_path):
    for value in ([], None):
        assert verifier.verify(write(tmp_path, value)) == [
            "implementation map top level must be an object"
        ]


def test_dangling_repository_fails(tmp_path):
    data = valid_map()
    data["targets"][0]["repositories"] = ["missing"]
    assert any(
        "unknown repositories" in failure
        for failure in verifier.verify(write(tmp_path, data))
    )


def test_authorized_paths_reject_traversal_absolute_backslash_and_dot(tmp_path):
    for unsafe in (
        "../../outside",
        "/absolute/path",
        r"..\outside",
        "./relative",
        "src/../outside",
    ):
        data = valid_map()
        data["repositories"][0]["authorized_paths"] = [unsafe]
        assert any(
            "safe relative paths" in failure
            for failure in verifier.verify(write(tmp_path, data))
        )


def test_authorized_path_rejects_symlink_escape_when_repository_is_mounted(
    tmp_path,
):
    repository = tmp_path / "web"
    repository.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (repository / "src").symlink_to(outside, target_is_directory=True)
    path = write(tmp_path, valid_map())

    failures = verifier.verify(path, {"web": repository})

    assert any("escapes the repository through a symlink" in failure for failure in failures)


def test_duplicate_and_unsupported_selectors_fail(tmp_path):
    data = valid_map()
    duplicate = dict(data["targets"][0])
    data["targets"].append(duplicate)
    assert any(
        "duplicate target selector" in failure
        for failure in verifier.verify(write(tmp_path, data))
    )
    data["targets"][1]["selector"] = "unsupported:item"
    assert any(
        "selector is invalid" in failure
        for failure in verifier.verify(write(tmp_path, data))
    )


def test_hierarchy_selector_kinds_are_accepted(tmp_path):
    data = valid_map()
    for index, selector in enumerate(
        ("alert-condition:checkout-errors", "dashboard:checkout", "custom-code:cart-size-attribute"),
        start=2,
    ):
        target = dict(data["targets"][0])
        target["selector"] = selector
        target["work_order"] = f"WO-00{index}"
        data["targets"].append(target)
    assert verifier.verify(write(tmp_path, data)) == []
