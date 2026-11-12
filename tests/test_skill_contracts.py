"""Regression guards for the versioned guided obengineer workflow."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.codex_workflows import (
    WORKFLOW_ORDER,
    render_openai_yaml,
    render_skill,
)
from scripts.sync_plugin_skills import codex_root_problems

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
COMMANDS = ROOT / "commands"
PROMPTS = ROOT / "prompts"
AGENTS = ROOT / "agents"
PLUGIN = ROOT / "plugins" / "obengineer"
DESCRIPTION_LIMIT = 1536

CANONICAL_SKILLS = sorted(path.parent.name for path in SKILLS.glob("*/SKILL.md"))


def frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text()
    assert text.startswith("---\n")
    _, raw, body = text.split("---\n", 2)
    data: dict[str, str] = {}
    key = None
    for line in raw.splitlines():
        match = re.match(r"^([a-z_]+): *(.*)$", line)
        if match and not line.startswith(" "):
            key = match.group(1)
            data[key] = match.group(2).strip()
        elif key and line.startswith(" "):
            data[key] = (data[key] + " " + line.strip()).strip()
    return data, body


@pytest.mark.parametrize("skill", CANONICAL_SKILLS)
def test_skill_contract(skill):
    data, body = frontmatter(SKILLS / skill / "SKILL.md")
    assert data["name"] == skill
    description = data["description"].lstrip(">-").strip()
    assert f"${skill}" in description
    assert len(description) <= DESCRIPTION_LIMIT
    assert body.lstrip().startswith("# ")
    for target in re.findall(r"\]\((\.\.?/[^)#]+)\)", (SKILLS / skill / "SKILL.md").read_text()):
        assert ((SKILLS / skill / target).resolve()).exists(), f"{skill}: {target}"


@pytest.mark.parametrize("skill", CANONICAL_SKILLS)
def test_skill_python_compiles(skill):
    for script in (SKILLS / skill / "scripts").glob("*.py"):
        compile(script.read_text(), str(script), "exec")


def test_obconfig_commands_replace_prompt_driven_intake():
    stems = {path.stem for path in COMMANDS.glob("*.md")}
    assert {"ob-start", "ob-add-inputs", "ob-edit-inputs", "ob-analyze"} <= stems
    assert "ob-intake" not in stems
    assert "ob-generate" not in stems
    for name in ("ob-start", "ob-add-inputs", "ob-edit-inputs"):
        text = (COMMANDS / f"{name}.md").read_text()
        assert "obconfig.yaml" in text
        assert "Proceed with analysis using this configuration? (yes/no)" in text
        assert "yes 1 3" not in text


def test_commands_are_short_dispatchers_and_plugin_complete():
    for command in COMMANDS.glob("*.md"):
        text = command.read_text()
        assert text.startswith("---\n")
        assert "description:" in text
        assert "{{OBENGINEER_ROOT}}" in text
        assert len(text.split()) < 450
        mirror = PLUGIN / "commands" / command.name
        assert mirror.is_file()
        assert mirror.read_text() == text.replace(
            "{{OBENGINEER_ROOT}}", "${CLAUDE_PLUGIN_ROOT}"
        )


def test_input_prompt_uses_two_exact_gates():
    prompt = (PROMPTS / "00-load-obconfig.md").read_text()
    skill = (SKILLS / "engagement-intake" / "SKILL.md").read_text()
    for text in (prompt, skill):
        assert "Repair it now? (yes/no)" in text
        assert "Proceed with analysis using this configuration? (yes/no)" in text
        assert "artifact" in text.lower() and "digest" in text.lower()


def test_start_validates_before_discovery_and_gates_analysis():
    command = (COMMANDS / "ob-start.md").read_text()
    prompt = (PROMPTS / "00-load-obconfig.md").read_text()
    analyze = (COMMANDS / "ob-analyze.md").read_text()
    assert command.index("validate") < command.index("summary")
    for text in (command, prompt):
        assert "exact `yes`" in text or "Only exact `yes`" in text
        assert "exact `no`" in text or "Exact `no`" in text
    assert "one-shot authorization" in analyze
    assert "artifact-tree digest" in analyze


def test_intake_runtime_and_schemas_are_packaged():
    skill = SKILLS / "engagement-intake"
    for relative in (
        "scripts/obconfig.py",
        "scripts/manage_obconfig.py",
        "scripts/direct_api.py",
        "schemas/obconfig.schema.json",
    ):
        path = skill / relative
        assert path.is_file()
        mirror = PLUGIN / "skills" / "engagement-intake" / relative
        assert mirror.is_file()
        assert mirror.read_bytes() == path.read_bytes()
    schema = json.loads((skill / "schemas/obconfig.schema.json").read_text())
    assert schema["properties"]["schema_version"]["const"] == 4
    assert set(schema["x-obengineer-secret-paths"]) == {
        "splunk.observability.read_token",
        "splunk.platform.read_token",
        "analysis_access.dummy_login.password",
    }


def test_canonical_template_is_the_only_field_authority():
    template = (ROOT / "obconfig.yaml.template").read_text()
    assert "schema_version: 4" in template
    assert "deployment_environment: production" in template
    assert "read_token:" in template and "password:" in template
    assert not (ROOT / "inputs/engagement-inputs.template.yaml").exists()
    assert not (SKILLS / "references/engagement-inputs.md").exists()
    assert not (ROOT / "templates/memory-repo/.env.template").exists()
    assert not (ROOT / "scripts/setup-splunk-access.sh").exists()
    assert (
        PLUGIN / "obconfig.yaml.template"
    ).read_bytes() == (ROOT / "obconfig.yaml.template").read_bytes()
    uncommented_leaves = [
        line
        for line in template.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and ":" in line
        and not line.rstrip().endswith(":")
        and "#" not in line
    ]
    assert uncommented_leaves == []


def test_direct_apis_and_mcp_are_complementary():
    analyze = (SKILLS / "instrumentation-analyze" / "SKILL.md").read_text()
    mcp = (SKILLS / "references" / "mcp-servers.md").read_text()
    telemetry = (SKILLS / "references" / "existing-telemetry.md").read_text()
    for text in (analyze, mcp, telemetry):
        assert "direct" in text.lower() and "API" in text
        assert "MCP" in text
    assert "MCP is not the only" in mcp
    for term in (
        "sf.org.numActiveTimeSeries", "sf.org.limit.activeTimeSeries",
        "mandatory", "not-configured", "request headers",
    ):
        assert term in telemetry


def test_analysis_uses_bounded_host_parallelism_but_serial_names():
    skill = (SKILLS / "instrumentation-analyze" / "SKILL.md").read_text()
    lifecycle = (SKILLS / "references" / "analysis-run-lifecycle.md").read_text()
    assert "exactly six workstreams" in skill
    assert "one host concurrency slot for the coordinator" in skill
    assert "repository validates only" in skill
    assert "Naming and schema reconciliation remain serial" in lifecycle


def test_analysis_site_is_the_review_authority():
    site = (SKILLS / "references" / "analysis-site.md").read_text()
    analyze = (SKILLS / "instrumentation-analyze" / "SKILL.md").read_text()
    agent = (AGENTS / "instrumentation-architect.agent.md").read_text()
    for text in (site, analyze, agent):
        assert "side panel" in text
        assert "localhost" in text
        assert "[V1] [V2] [V3]" in text or "[V1] [V2]" in text or "[V1] [V2] ..." in text
    for required in (
        "Technology", "Current telemetry", "Findings", "Instrumentation strategy", "Work orders",
        "Use cases", "Workflows", "Business transactions",
        "Shared signal contracts", "Reference",
    ):
        assert required.lower() in site.lower()


def test_analysis_navigation_is_internal_and_breadcrumbed():
    site = (SKILLS / "references" / "analysis-site.md").read_text()
    assert "No run starts a web server" in site
    assert "opening a system browser" in site
    assert "[Analysis](../index.md)" in site
    assert "Every `Open` cell links the matching detail index" in site


def test_approved_long_linked_landing_layout_is_committed_and_ordered():
    template = (ROOT / "templates" / "analysis-site" / "index.md").read_text()
    required = (
        "[V1](../V1/index.md) [V2](../V2/index.md) **[V3]**",
        "[Analysis](../index.md)",
        "## Status",
        "Next steps",
        "## Changes in this version",
        "## Table of contents and section summaries",
        "## Architecture summary",
        "| Priority findings | Primary use cases |",
        "## Side-panel navigation",
    )
    positions = [template.index(item) for item in required]
    assert positions == sorted(positions)
    rows = (
        "Architecture", "Technology", "Current telemetry", "Findings", "Instrumentation strategy",
        "Implementation path", "Work orders", "Use cases", "Workflows",
        "Business transactions", "Shared signal contracts",
        "Operations and verification", "Reference",
    )
    row_positions = [template.index(f"| {row} |") for row in rows]
    assert row_positions == sorted(row_positions)
    assert template.count("\n## ") >= 7
    assert "storefront or client composition" in template


def test_analysis_creates_versioned_wiki_and_all_work_orders():
    command = (COMMANDS / "ob-analyze.md").read_text()
    wiki_prompt = (PROMPTS / "02-build-instrumentation-wiki.md").read_text()
    spec = (SKILLS / "references" / "agent-wiki.md").read_text()
    for text in (command, wiki_prompt, spec):
        assert "versions/V<N>" in text
        assert "work order" in text.lower()
    assert "There is no separate generation command" in wiki_prompt
    assert "Acceptance activates the queue" in spec or "Acceptance changes eligible" in spec


def test_work_orders_are_visible_and_reverse_linked():
    site = (SKILLS / "references" / "analysis-site.md").read_text()
    spec = (SKILLS / "references" / "agent-wiki.md").read_text()
    for column in ("ID", "Outcome", "Depends on", "Status", "Unlocks", "Detail"):
        assert column in site
    for relation in ("findings", "use cases", "workflows", "business transactions"):
        assert relation in spec.lower()
    assert "first work order installs deterministic" in spec.lower()


def test_acceptance_is_easy_content_bound_and_has_no_person_name():
    lifecycle = (SKILLS / "references" / "analysis-run-lifecycle.md").read_text()
    assert "reply `yes`" in lifecycle
    assert "analysis_content_digest" in lifecycle
    assert "schema_version: 2" in lifecycle
    assert "analysis-contract.json" in lifecycle
    assert "manual SHA" in lifecycle
    assert "No accepter name" in lifecycle
    assert "accepted_by:" not in lifecycle
    verifier = (
        SKILLS / "instrumentation-wiki" / "scripts" /
        "verify_analysis_acceptance.py"
    ).read_text()
    assert "analysis_content_digest" in verifier
    assert "accepted_by" not in verifier


def test_verification_and_wiki_generation_use_current_versioned_contracts():
    verification = (SKILLS / "references" / "verification-run.md").read_text()
    wiki = (SKILLS / "references" / "agent-wiki.md").read_text()
    analyze = (PROMPTS / "01-analyze-application.md").read_text()
    assert '"schema_version": 2' in verification
    assert '"source_ref"' in verification
    assert "source_section" in verification  # documented v1 read compatibility
    assert "versions/V<N>/meta/" in wiki
    assert "lists, including when empty" in wiki
    assert "analysis-contract.json" in analyze


def test_ready_for_review_comments_are_processed_before_merge():
    lifecycle = (SKILLS / "references" / "analysis-run-lifecycle.md").read_text()
    assert "ready for review" in lifecycle.lower()
    assert "unresolved review comments" in lifecycle
    assert "explicit `yes`" in lifecycle
    assert "without an explicit `yes`" in lifecycle


def test_chat_handoff_is_one_link_then_next_steps():
    site = (SKILLS / "references" / "analysis-site.md").read_text()
    command = (COMMANDS / "ob-analyze.md").read_text()
    for text in (site, command):
        assert "host-native" in text
        assert "Do not paste" in text or "do not paste" in text
        assert "/ob-implement work-order:<id>" in text


def test_word_is_optional_and_under_twenty_pages():
    analyze = (SKILLS / "instrumentation-analyze" / "SKILL.md").read_text()
    template = (SKILLS / "references" / "document-template.md").read_text()
    render = (SKILLS / "customer-doc-render" / "SKILL.md").read_text()
    assert "only when the human asks" in analyze
    assert "under 20 pages" in template
    assert "optional" in render.lower()
    assert "full attribute dictionary" in template.lower()


def test_cross_cutting_contract_still_has_all_patterns():
    reference = (SKILLS / "references" / "cross-cutting-attributes.md").read_text()
    for required in (
        "Provider bootstrap", "The SpanProcessor", "Writing baggage on login",
        "Reading baggage on the", "Messaging boundary",
    ):
        assert required in reference
    assert "onStart" in reference and "const KEYS" in reference
    for surface in (
        AGENTS / "instrumentation-architect.agent.md",
        PROMPTS / "01-analyze-application.md",
        SKILLS / "instrumentation-analyze" / "SKILL.md",
    ):
        assert "Cross-Cutting Attributes and Baggage Propagation" in surface.read_text()


def test_baggage_and_cardinality_budgets_remain_numeric():
    baggage = (SKILLS / "references" / "baggage-budget.md").read_text()
    assert "512" in baggage and "64 bytes" in baggage
    cardinality = (SKILLS / "cardinality-budget" / "SKILL.md").read_text()
    for term in ("distinct values", "enforced system limit", "current usage"):
        assert term in cardinality


def test_security_coverage_and_credential_handling_remain_contractual():
    security = (SKILLS / "references" / "security-assessment.md").read_text()
    critical = (SKILLS / "references" / "critical-findings.md").read_text()
    for term in ("OWASP Top 10:2025", "OWASP API Security Top 10:2023"):
        assert term in security
    assert "Never the value" in critical
    for required in (
        "Exposure", "Risk if unaddressed", "Remediation path", "Verification",
    ):
        assert required in critical


def test_linked_analysis_references_do_not_use_retired_section_numbers():
    for relative in (
        "critical-findings.md",
        "security-assessment.md",
        "service-levels.md",
        "existing-telemetry.md",
    ):
        text = (SKILLS / "references" / relative).read_text()
        assert not re.search(r"\bsection(?:s)?\s+(?:[0-9]+|[0-9]+ and [0-9]+)", text, re.I), (
            f"{relative} still routes generated analysis through retired monolith sections"
        )


def test_terraform_provider_names_and_no_apply_boundary():
    reference = (SKILLS / "references" / "splunk-terraform-providers.md").read_text()
    for pin in ("~> 9.34", "~> 3.0", "~> 1.5"):
        assert pin in reference
    for absent in ("APM MetricSets", "APM Business Transaction rules", "Log Observer Connect"):
        assert absent in reference
    command = (COMMANDS / "ob-terraform.md").read_text()
    assert "Never apply" in command


def test_implementation_requires_ready_order_in_accepted_version():
    command = (COMMANDS / "ob-implement.md").read_text()
    skill = (SKILLS / "instrumentation-implement" / "SKILL.md").read_text()
    for text in (command, skill):
        assert "Ready" in text
        assert "accepted version" in text
    assert "Proposed, Blocked, Superseded" in command


def test_verification_remains_read_only():
    for path in (
        COMMANDS / "ob-verify.md",
        PROMPTS / "05-verify-accepted-contract.md",
        SKILLS / "instrumentation-verify" / "SKILL.md",
        SKILLS / "references" / "verification-run.md",
    ):
        text = path.read_text().lower()
        assert "read-only" in text
        assert "unmet" in text


def test_agent_files_route_and_stay_bounded():
    for agent in AGENTS.glob("*.agent.md"):
        text = agent.read_text()
        assert "skills/" in text
        assert len(text.split()) < 2500


def test_installer_migrates_retired_commands():
    installer = (ROOT / "scripts" / "install.py").read_text()
    assert '"ob-start": ("ob-intake", "ob-generate", "ob-wiki")' in installer
    assert '"ob-terraform": ("ob-build-terraform",)' in installer
    for host in ("cursor", "claude", "codex"):
        assert f'"{host}"' in installer


def test_reinstall_removes_only_manifest_owned_retired_commands(tmp_path):
    subprocess.run(
        [str(ROOT / "install.sh"), "--cursor", "--project", str(tmp_path)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    commands = tmp_path / ".cursor" / "commands"
    manifest_path = tmp_path / ".cursor" / ".obengineer-install.json"
    manifest = json.loads(manifest_path.read_text())
    replacement = commands / "ob-start.md"
    retired = commands / "ob-intake.md"
    replacement.rename(retired)
    manifest["owned"]["commands/ob-intake.md"] = manifest["owned"].pop(
        "commands/ob-start.md"
    )
    manifest_path.write_text(json.dumps(manifest))
    subprocess.run(
        [str(ROOT / "install.sh"), "--cursor", "--project", str(tmp_path)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    assert not retired.exists()
    assert replacement.exists()


def test_plugin_manifests_and_mirrors_agree():
    claude = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    codex = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
    assert claude["version"] == codex["version"]
    assert codex["version"] == "0.2.1"
    assert claude["skills"] == ["./skills/"]
    assert codex["skills"] == "./codex-skills/"
    assert codex["requires_local_executor"] is True
    mirrored = sorted(path.parent.name for path in (PLUGIN / "skills").glob("*/SKILL.md"))
    assert mirrored == CANONICAL_SKILLS
    for skill in CANONICAL_SKILLS:
        assert (
            PLUGIN / "skills" / skill / "SKILL.md"
        ).read_text() == (SKILLS / skill / "SKILL.md").read_text()
        assert (
            PLUGIN / "codex-skills" / skill / "SKILL.md"
        ).read_text() == (SKILLS / skill / "SKILL.md").read_text()


def test_codex_workflow_wrappers_match_every_command_and_are_explicit_only():
    commands = sorted(path.stem for path in COMMANDS.glob("ob-*.md"))
    assert commands == sorted(WORKFLOW_ORDER)
    codex_skills = PLUGIN / "codex-skills"
    generated = ROOT / ".agents/skills"

    for name in WORKFLOW_ORDER:
        command = COMMANDS / f"{name}.md"
        plugin_wrapper = codex_skills / name
        local_wrapper = generated / name
        plugin_text = (plugin_wrapper / "SKILL.md").read_text()
        local_text = (local_wrapper / "SKILL.md").read_text()
        assert plugin_text == render_skill(command, "${PLUGIN_ROOT}")
        assert "${CLAUDE_PLUGIN_ROOT}" not in plugin_text
        assert local_text == render_skill(command)
        data, body = frontmatter(plugin_wrapper / "SKILL.md")
        assert data["name"] == name
        assert f"${name}" in data["description"]
        assert body.lstrip().startswith(f"# {name}")
        assert f"${name}" in plugin_text
        assert f"@{name}" in plugin_text
        assert "$ARGUMENTS" in plugin_text
        assert "Preserve all user-supplied text" in plugin_text
        expected_openai = render_openai_yaml(name)
        assert (
            plugin_wrapper / "agents/openai.yaml"
        ).read_text() == expected_openai
        assert (
            local_wrapper / "agents/openai.yaml"
        ).read_text() == expected_openai
        metadata = yaml.safe_load(expected_openai)
        assert metadata["policy"]["allow_implicit_invocation"] is False
        assert f"${name}" in metadata["interface"]["default_prompt"]


def test_codex_plugin_drift_rejects_unexpected_root_files_and_symlinks(tmp_path):
    expected = tmp_path / "expected-skill"
    expected.mkdir()
    unexpected_file = tmp_path / "README.tmp"
    unexpected_file.write_text("unexpected\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "linked-skill").symlink_to(outside, target_is_directory=True)

    problems = codex_root_problems(tmp_path, {"expected-skill"})

    assert any("unexpected root file" in problem for problem in problems)
    assert any("unexpected root symlink" in problem for problem in problems)


CREDENTIAL_PATTERNS = [
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+"),
    re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[A-Z0-9]{12,}\b"),
    re.compile(r"\bgh[posur]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
]
UNSCANNED = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv"}


def source_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or UNSCANNED & set(path.relative_to(root).parts):
            continue
        if path.suffix in {".md", ".json", ".py", ".yaml", ".yml", ".sh", ""}:
            yield path


def test_no_credentials_or_personal_paths_committed():
    failures = []
    for path in source_files(ROOT):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(errors="replace")
        if any(pattern.search(text) for pattern in CREDENTIAL_PATTERNS):
            failures.append(str(path.relative_to(ROOT)))
        if re.search(r"/(?:Users|home)/(?!you\b)[A-Za-z0-9._-]+", text):
            failures.append(str(path.relative_to(ROOT)))
    assert failures == []
