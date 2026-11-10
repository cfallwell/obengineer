"""Regression guards for the versioned guided obengineer workflow."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

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


def test_guided_commands_replace_manual_intake_and_generation():
    stems = {path.stem for path in COMMANDS.glob("*.md")}
    assert {"ob-start", "ob-add-inputs", "ob-edit-inputs", "ob-analyze"} <= stems
    assert "ob-intake" not in stems
    assert "ob-generate" not in stems
    for name in ("ob-start", "ob-add-inputs", "ob-edit-inputs"):
        text = (COMMANDS / f"{name}.md").read_text()
        assert "yes 1 3 4" in text or name == "ob-edit-inputs"
        assert "ob-analyze.md" in text


def test_commands_are_short_dispatchers_and_plugin_complete():
    for command in COMMANDS.glob("*.md"):
        text = command.read_text()
        assert text.startswith("---\n")
        assert "description:" in text
        assert "{{OBENGINEER_ROOT}}" in text
        assert len(text.split()) < 400
        mirror = PLUGIN / "commands" / command.name
        assert mirror.is_file()
        assert mirror.read_text() == text.replace(
            "{{OBENGINEER_ROOT}}", "${CLAUDE_PLUGIN_ROOT}"
        )


def test_input_prompt_uses_number_selection_and_no_required_unknown():
    prompt = (PROMPTS / "00-manage-analysis-inputs.md").read_text()
    skill = (SKILLS / "engagement-intake" / "SKILL.md").read_text()
    for text in (prompt, skill):
        assert "Would you like to add more inputs to the analysis phase?" in text
        assert "yes 1 3 4" in text
        assert "one at a time" in text or "once for each selected" in text
        assert "never types `unknown`" in text or "never have to type `unknown`" in text
        assert "named owner" in text or "names of engineers" in text


def test_start_asks_required_question_before_any_discovery_and_gates_analysis():
    command = (COMMANDS / "ob-start.md").read_text()
    prompt = (PROMPTS / "00-manage-analysis-inputs.md").read_text()
    analyze = (COMMANDS / "ob-analyze.md").read_text()
    assert command.index("manage_run_context.py") < command.index(
        "prompts/00-manage-analysis-inputs.md"
    )
    assert command.index("Before reading source") < command.index(
        "discover measurable optional facts"
    )
    for text in (command, prompt):
        assert "explicit production URL" in text
        assert "no browser: <reason>" in text
        assert "what hurts" in text.lower()
        assert "yes 1 3" in text
        assert "never starts analysis" in text
        assert "exact `no`" in text
        for marker in ("[x]", "[ ]", "[-]"):
            assert marker in text
    assert "analysis_authorized: true" in analyze
    assert "last_event: review-no" in analyze


def test_intake_runtime_and_schemas_are_packaged():
    skill = SKILLS / "engagement-intake"
    for relative in (
        "scripts/prefill_engagement_inputs.py",
        "scripts/manage_run_context.py",
        "schemas/env-prefill.schema.json",
        "schemas/run-context.schema.json",
    ):
        path = skill / relative
        assert path.is_file()
        mirror = PLUGIN / "skills" / "engagement-intake" / relative
        assert mirror.is_file()
        assert mirror.read_bytes() == path.read_bytes()
    run_schema = json.loads((skill / "schemas/run-context.schema.json").read_text())
    assert run_schema["properties"]["state"]["enum"] == [
        "new", "required", "optional-review", "optional-answers"
    ]


def test_environment_template_starts_with_safe_onboarding_fields():
    template = (ROOT / "templates/memory-repo/.env.template").read_text()
    assert template.startswith(
        "PRODUCTION_URL=\nTEST_LOGIN_ID=\nPASSWORD_REF=\n"
    )
    assignments = [
        line.split("=", 1)[0]
        for line in template.splitlines()
        if line and not line.startswith("#") and "=" in line
    ]
    assert assignments[:3] == [
        "PRODUCTION_URL", "TEST_LOGIN_ID", "PASSWORD_REF"
    ]
    assert "RAW_PASSWORD" not in template
    assert "ARTIFACTS_DIR=artifacts" in template
    assert "${SPLUNK_ACCESS_TOKEN}" in template
    assert "${SPLUNK_TOKEN}" in template


def test_setup_script_is_secret_safe_and_guided():
    script = (ROOT / "scripts" / "setup-splunk-access.sh").read_text()
    assert "read -r -s" in script
    assert "chmod 600" in script
    assert "SPLUNK_ACCESS_TOKEN" in script and "SPLUNK_TOKEN" in script
    assert "values were not printed" in script
    assert "x-access-token" not in script


def test_direct_apis_and_mcp_are_complementary():
    analyze = (SKILLS / "instrumentation-analyze" / "SKILL.md").read_text()
    mcp = (SKILLS / "references" / "mcp-servers.md").read_text()
    telemetry = (SKILLS / "references" / "existing-telemetry.md").read_text()
    for text in (analyze, mcp, telemetry):
        assert "direct" in text.lower() and "API" in text
        assert "MCP" in text
    assert "MCP is not the only" in mcp
    for variable in (
        "SPLUNK_REALM", "SPLUNK_ACCESS_TOKEN", "SPLUNK_HOST",
        "SPLUNK_TOKEN", "SPLUNK_ENTERPRISE_INDEXES",
    ):
        assert variable in telemetry


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
    assert "manual SHA" in lifecycle
    assert "No accepter name" in lifecycle
    assert "accepted_by:" not in lifecycle
    verifier = (
        SKILLS / "instrumentation-wiki" / "scripts" /
        "verify_analysis_acceptance.py"
    ).read_text()
    assert "analysis_content_digest" in verifier
    assert "accepted_by" not in verifier


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
    for term in ("distinct values", "custom_mts_entitled", "custom_mts_in_use"):
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
    manifest["created"] = [
        str(retired) if entry == str(replacement) else entry
        for entry in manifest["created"]
    ]
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
    mirrored = sorted(path.parent.name for path in (PLUGIN / "skills").glob("*/SKILL.md"))
    assert mirrored == CANONICAL_SKILLS
    for skill in CANONICAL_SKILLS:
        assert (
            PLUGIN / "skills" / skill / "SKILL.md"
        ).read_text() == (SKILLS / skill / "SKILL.md").read_text()


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
