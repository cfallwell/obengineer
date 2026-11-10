#!/usr/bin/env python3
"""Securely prefill engagement inputs from allowlisted environment names."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install PyYAML==6.0.3")

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLKIT_ROOT = SKILL_ROOT.parent.parent
SCHEMA_PATH = SKILL_ROOT / "schemas" / "env-prefill.schema.json"
DEFAULT_TEMPLATE = TOOLKIT_ROOT / "inputs" / "engagement-inputs.template.yaml"
PASSWORD_REFERENCE = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")


class PrefillError(ValueError):
    """A safe, value-free prefill validation error."""


def load_schema(path: Path = SCHEMA_PATH) -> dict:
    schema = json.loads(path.read_text())
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise PrefillError("prefill schema has no properties")
    return schema


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            raise PrefillError(f"{path}:{line_number}: expected NAME=value")
        name, value = stripped.split("=", 1)
        name = name.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        values[name] = value
    return values


def collect_values(
    project_root: Path,
    schema: dict,
    supplied: dict[str, object] | None = None,
) -> dict[str, str]:
    allowed = set(schema["properties"])
    values: dict[str, str] = {}
    for path in (project_root / ".env.template", project_root / ".env"):
        values.update(
            {
                name: value
                for name, value in parse_env_file(path).items()
                if name in allowed
            }
        )
    values.update(
        {
            name: os.environ[name]
            for name in allowed
            if name in os.environ
        }
    )
    if supplied is not None:
        unknown = sorted(set(supplied) - allowed)
        if unknown:
            raise PrefillError(
                "input contains names outside the prefill allowlist: "
                + ", ".join(unknown)
            )
        for name, value in supplied.items():
            if not isinstance(value, str):
                raise PrefillError(f"{name} must be a string")
            values[name] = value
    return values


def is_missing(value: object) -> bool:
    return value is None or value == "" or value == "unknown" or value == []


def get_path(data: dict, dotted: str) -> object:
    current: object = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def set_path(data: dict, dotted: str, value: object) -> None:
    parts = dotted.split(".")
    current = data
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def _uri_is_absolute(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def convert_value(name: str, raw: str, rule: dict) -> object:
    if "enum" in rule and raw not in rule["enum"]:
        raise PrefillError(f"{name} is not one of the allowed values")
    pattern = rule.get("pattern")
    if pattern and not re.fullmatch(pattern, raw):
        raise PrefillError(f"{name} has an invalid format")
    if rule.get("format") == "uri" and not _uri_is_absolute(raw):
        raise PrefillError(f"{name} must be an absolute http(s) URL")

    if reference := rule.get("x-reference-if-set"):
        return reference
    shape = rule.get("x-shape")
    if shape == "single-list":
        return [raw]
    if shape == "csv-list":
        return [item.strip() for item in raw.split(",") if item.strip()]
    if shape == "boolean":
        normalized = raw.lower()
        if normalized not in {"true", "false"}:
            raise PrefillError(f"{name} must be true or false")
        return normalized == "true"
    if shape == "number":
        try:
            number = float(raw)
        except ValueError as exc:
            raise PrefillError(f"{name} must be numeric") from exc
        return int(number) if number.is_integer() else number
    prefix = rule.get("x-prefix", "")
    if prefix and raw.lower().startswith(prefix):
        return raw
    return f"{prefix}{raw}"


def validate_access(data: dict) -> None:
    access = data.get("analysis_access")
    if not isinstance(access, dict):
        raise PrefillError("analysis_access must be an object")
    login = access.get("login_id")
    password = access.get("password_ref")
    login_set = not is_missing(login)
    password_set = not is_missing(password)
    if login_set != password_set:
        raise PrefillError(
            "TEST_LOGIN_ID and PASSWORD_REF must be supplied together"
        )
    if password_set and (
        not isinstance(password, str) or not PASSWORD_REFERENCE.fullmatch(password)
    ):
        raise PrefillError("PASSWORD_REF must be a ${VAR} reference")
    access_supplied = any(
        not is_missing(access.get(field))
        for field in ("token_ref", "api_key_ref", "login_id", "password_ref")
    )
    if access_supplied:
        access["rotate_on_completion"] = True


def apply_prefill(
    data: dict,
    values: dict[str, str],
    schema: dict,
    *,
    baseline: dict,
    force_names: set[str] | None = None,
) -> list[str]:
    production_url = values.get("PRODUCTION_URL", "").strip()
    no_browser = values.get("NO_BROWSER_REASON", "").strip()
    if production_url and no_browser:
        raise PrefillError(
            "set PRODUCTION_URL or NO_BROWSER_REASON, not both"
        )

    changed: list[str] = []
    force_names = force_names or set()
    for name, rule in schema["properties"].items():
        raw = values.get(name, "").strip()
        if not raw:
            continue
        target = rule["x-target"]
        current = get_path(data, target)
        default = get_path(baseline, target)
        if (
            name not in force_names
            and not is_missing(current)
            and current != default
        ):
            continue
        converted = convert_value(name, raw, rule)
        if current != converted:
            set_path(data, target, converted)
            changed.append(target)
    validate_access(data)
    return changed


def atomic_dump_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, encoding="utf-8"
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def prefill(
    project_root: Path,
    output: Path,
    template: Path = DEFAULT_TEMPLATE,
    supplied: dict[str, object] | None = None,
    *,
    overwrite_existing: bool = False,
) -> list[str]:
    schema = load_schema()
    values = collect_values(project_root, schema, supplied)
    source = output if output.is_file() else template
    try:
        data = yaml.safe_load(source.read_text())
        baseline = yaml.safe_load(template.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise PrefillError(f"cannot load engagement inputs: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(baseline, dict):
        raise PrefillError("engagement inputs and template top levels must be objects")
    changed = apply_prefill(
        data,
        values,
        schema,
        baseline=baseline,
        force_names=set(supplied or {}) if overwrite_existing else set(),
    )
    if changed or not output.exists():
        atomic_dump_yaml(output, data)
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/observability/engagement-inputs.yaml"),
    )
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="additional allowlisted values as a JSON object; use - for stdin",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="replace supplied human-editable values; use only for /ob-edit-inputs",
    )
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    output = (
        args.output
        if args.output.is_absolute()
        else project_root / args.output
    )
    supplied = None
    if args.json:
        try:
            text = sys.stdin.read() if args.json == "-" else Path(args.json).read_text()
            supplied = json.loads(text)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL — cannot read prefill JSON: {exc}")
            return 1
        if not isinstance(supplied, dict):
            print("FAIL — prefill JSON must be an object")
            return 1
    try:
        changed = prefill(
            project_root,
            output,
            args.template,
            supplied,
            overwrite_existing=args.overwrite_existing,
        )
    except PrefillError as exc:
        print(f"FAIL — {exc}")
        return 1
    if changed:
        print("Prefilled engagement input fields: " + ", ".join(sorted(changed)))
    else:
        print("No missing engagement input fields were prefilled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
