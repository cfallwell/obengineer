"""Deterministic contract tests for the agentry.

These are regression guards, not style checks. The one that matters most is
`test_cross_cutting_section_is_mandatory_everywhere`: the Cross-Cutting Attributes
and Baggage Propagation section was once absent from the architect agent and the
generated guide, which produced a contract that could not drive a single dashboard
variable or detector grouping. Nothing may silently drop it again.

    python3 -m pytest "obengineer/tests" -q
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
AGENTS = ROOT / "agents"
PROMPTS = ROOT / "prompts"
PLUGIN = ROOT / "plugins" / "obengineer"

CANONICAL_SKILLS = sorted(
    p.parent.name for p in SKILLS.glob("*/SKILL.md")
)
# Claude Code truncates long skill descriptions; keep discovery text within budget.
DESCRIPTION_LIMIT = 1536

SECTION = "Cross-Cutting Attributes and Baggage Propagation"


def frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    assert text.startswith("---\n"), f"{path} must open with YAML frontmatter"
    _, raw, body = text.split("---\n", 2)
    data: dict[str, str] = {}
    key = None
    for line in raw.split("\n"):
        if not line.strip():
            continue
        m = re.match(r"^([a-z_]+): *(.*)$", line)
        if m and not line.startswith(" "):
            key = m.group(1)
            data[key] = m.group(2).strip()
        elif key and line.startswith(" "):
            data[key] = (data[key] + " " + line.strip()).strip()
    return data, body


# --------------------------------------------------------------------------- #
# skills
# --------------------------------------------------------------------------- #
def test_skills_exist():
    assert CANONICAL_SKILLS, "no canonical skills found under skills/"
    for expected in ("baggage-propagation", "customer-doc-render",
                     "instrumentation-analyze", "instrumentation-guide",
                     "instrumentation-implement"):
        assert expected in CANONICAL_SKILLS, f"missing skill: {expected}"


@pytest.mark.parametrize("skill", CANONICAL_SKILLS)
def test_skill_frontmatter(skill):
    data, body = frontmatter(SKILLS / skill / "SKILL.md")
    assert data.get("name") == skill, (
        f"{skill}: frontmatter name '{data.get('name')}' must match the directory"
    )
    description = data.get("description", "").lstrip(">-").strip()
    assert description, f"{skill}: description is required for discovery"
    assert len(description) <= DESCRIPTION_LIMIT, (
        f"{skill}: description is {len(description)} chars, limit {DESCRIPTION_LIMIT}"
    )
    assert f"${skill}" in description, (
        f"{skill}: description must name its ${skill} invocation so hosts can route to it"
    )
    assert body.lstrip().startswith("# "), f"{skill}: body needs an H1 title"


@pytest.mark.parametrize("skill", CANONICAL_SKILLS)
def test_skill_links_resolve(skill):
    """A skill that points at a reference which does not exist is a dead end."""
    skill_md = SKILLS / skill / "SKILL.md"
    for target in re.findall(r"\]\((\.\.?/[^)#]+)\)", skill_md.read_text()):
        assert (skill_md.parent / target).resolve().exists(), (
            f"{skill}: broken link to {target}"
        )


@pytest.mark.parametrize("skill", CANONICAL_SKILLS)
def test_skill_scripts_are_executable_python(skill):
    for script in (SKILLS / skill / "scripts").glob("*.py"):
        compile(script.read_text(), str(script), "exec")


# --------------------------------------------------------------------------- #
# the regression this repo exists to prevent
# --------------------------------------------------------------------------- #
def test_cross_cutting_section_is_mandatory_everywhere():
    surfaces = {
        "architect agent": AGENTS / "instrumentation-architect.agent.md",
        "prompt 02": PROMPTS / "02-develop-instrumentation-guide.md",
        "document template": SKILLS / "references" / "document-template.md",
        "guide skill": SKILLS / "instrumentation-guide" / "SKILL.md",
    }
    for label, path in surfaces.items():
        assert SECTION in path.read_text(), (
            f"{label} no longer requires the '{SECTION}' section"
        )


def test_cross_cutting_reference_carries_all_five_code_subsections():
    text = (SKILLS / "references" / "cross-cutting-attributes.md").read_text()
    for required in (
        "Provider bootstrap",
        "The SpanProcessor",
        "Writing baggage on login",
        "Reading baggage on the",
        "Messaging boundary",
    ):
        assert required in text, f"cross-cutting reference is missing: {required}"
    # The stamp must be an onStart hook over an explicit allowlist, not a
    # loop over whatever a future caller put into baggage.
    assert "onStart" in text
    assert "const KEYS" in text
    assert "Attribute | Type | Set at | Dimension? | Notes" in text


def test_architect_agent_requires_both_artifacts():
    text = (AGENTS / "instrumentation-architect.agent.md").read_text()
    assert "customer-doc-render" in text, (
        "architect agent must route the .docx through the customer-doc-render skill"
    )
    assert ".docx" in text
    assert "attribute-schema.json" in text


def test_template_puts_architecture_in_front_and_dictionary_at_back():
    text = (SKILLS / "references" / "document-template.md").read_text()
    arch = text.index("Backend Architecture (Observed)")
    baggage = text.index(SECTION)
    dictionary = text.index("Appendix A: Master Attribute Dictionary")
    assert arch < baggage < dictionary, (
        "order must be architecture, then cross-cutting attributes, then the "
        "dictionary appendix at the back"
    )


# --------------------------------------------------------------------------- #
# one authority per fact
# --------------------------------------------------------------------------- #
SECTION_LIST_AUTHORITY = SKILLS / "references" / "document-template.md"

# Sections the architect agent required while the canonical template's numbered
# spine omitted them. The agent papered over the gap with a paragraph saying they
# "go where they belong", which is not a specification, so a run could ship without
# them and still believe it had followed the template.
ONCE_MISSING_SECTIONS = (
    "Course of action",
    "Missing portfolio components",
    "RUM SPA / client route changes",
    "Custom meters (business vs developer/execution)",
    "Splunk portfolio mapping",
    "Phased plan and exit criteria",
    "Bootstrap vs non-goals",
)


def test_section_list_has_exactly_one_authority():
    """Two copies of the section list drift, and then both claim to be the spec."""
    pattern = re.compile(r"^\| *#? *\| *Heading *\|", re.MULTILINE)
    carriers = [
        path
        for path in sorted(ROOT.rglob("*.md"))
        if PLUGIN not in path.parents and pattern.search(path.read_text())
    ]
    assert carriers == [SECTION_LIST_AUTHORITY], (
        "the numbered section list belongs only in document-template.md; found it in "
        + ", ".join(str(p.relative_to(ROOT)) for p in carriers)
    )


@pytest.mark.parametrize("heading", ONCE_MISSING_SECTIONS)
def test_template_carries_every_required_section(heading):
    text = SECTION_LIST_AUTHORITY.read_text()
    assert heading in text, (
        f"'{heading}' is required of every deliverable but is absent from the only "
        "file that lists the sections, so a run can omit it and still pass review"
    )


def test_agent_files_route_rather_than_duplicate():
    """An agent file is loaded whole, every run. Depth belongs in references.

    The architect agent reached 7,200 words by carrying the decision engine, the
    platform expertise, and the output template inline -- all three of which already
    existed as references it also linked to. The cap is what keeps that from
    regrowing quietly.
    """
    for agent in sorted(AGENTS.glob("*.agent.md")):
        words = len(agent.read_text().split())
        assert words < 2500, (
            f"{agent.name} is {words} words; move depth into skills/references/ and "
            "leave a pointer"
        )
        assert "skills/" in agent.read_text(), (
            f"{agent.name} must route to the skills that carry the detail"
        )


def test_budgets_are_numbers_not_adjectives():
    """'Keep cardinality low' loses every argument; a budget wins them."""
    baggage = (SKILLS / "references" / "baggage-budget.md").read_text()
    assert "512" in baggage and "64 bytes" in baggage, (
        "the baggage budget must state byte limits, not just advise restraint"
    )
    assert "SQS" in baggage and "message attributes" in baggage, (
        "the bus attribute cap is the constraint people meet first in production"
    )

    cardinality = (SKILLS / "cardinality-budget" / "SKILL.md").read_text()
    for term in ("distinct values", "custom_mts_included", "custom_mts_in_use"):
        assert term in cardinality, (
            f"the cardinality budget must compute against entitlement; missing {term}"
        )


# --------------------------------------------------------------------------- #
# inputs are collected once, by reference
# --------------------------------------------------------------------------- #
def test_inputs_template_captures_what_no_scan_can_measure():
    template = (ROOT / "inputs" / "engagement-inputs.template.yaml").read_text()
    for field in ("custom_mts_included", "custom_mts_in_use", "mms_slots_remaining",
                  "tms_cardinality_ceiling", "session_replay_accepted_in_writing",
                  "baggage_header_budget_bytes", "percentile"):
        assert field in template, f"engagement inputs must capture {field}"
    assert "unknown" in template, (
        "unknown must be a legitimate answer, or the run stalls on procurement"
    )


def test_prompts_reference_the_inputs_file_instead_of_carrying_placeholders():
    for prompt in sorted(PROMPTS.glob("0*.md")):
        text = prompt.read_text()
        assert "engagement-inputs.yaml" in text, (
            f"{prompt.name} must read the inputs file rather than ask inline"
        )
        assert "Copy below the line" not in text and "Copy everything below" not in text, (
            f"{prompt.name} still tells the human to paste it; the copy that runs "
            "would not be the copy under review"
        )


def test_commands_invoke_the_run_contracts_rather_than_copying_them():
    commands = sorted((ROOT / "commands").glob("*.md"))
    assert commands, "no installable commands found"
    for command in commands:
        text = command.read_text()
        assert text.startswith("---\n") and "description:" in text, (
            f"{command.name} needs frontmatter with a description for host discovery"
        )
        assert "{{OBENGINEER_ROOT}}" in text, (
            f"{command.name} must resolve bundle paths at install time"
        )
        assert len(text.split()) < 400, (
            f"{command.name} is long enough to be a second copy of a run contract; "
            "point at prompts/ instead"
        )

    stems = {c.stem for c in commands}
    for prompt in sorted(PROMPTS.glob("0*.md")):
        referenced = any(prompt.name in c.read_text() for c in commands)
        assert referenced, f"{prompt.name} has no command that invokes it"
    assert "obengineer-intake" in stems


def test_installer_offers_every_host_and_installs_every_skill():
    text = (ROOT / "scripts" / "install.py").read_text()
    for host in ("cursor", "claude", "codex"):
        assert f'"{host}"' in text, f"installer must support {host}"
    for flag in ("--all", "--project", "--uninstall", "--dry-run", "--list"):
        assert flag in text, f"installer must document {flag}"
    assert (ROOT / "install.sh").is_file()
    readme = (ROOT / "README.md").read_text()
    assert "./install.sh" in readme, "the README must show how to install"
    assert "/obengineer-" in readme, "the README must show how to invoke"


# --------------------------------------------------------------------------- #
# the approved layout: simple title page, contents, one section per page
# --------------------------------------------------------------------------- #
def test_house_style_is_committed_not_remembered():
    """The layout must survive a session with no approved sample to copy."""
    render = SKILLS / "customer-doc-render"
    spec_path = render / "references" / "document-format.json"
    assert spec_path.is_file(), "document-format.json must be committed"
    assert (render / "references" / "document-format.md").is_file()
    assert (render / "assets" / "header-banner.png").is_file()
    assert (render / "scripts" / "extract_docx_format.py").is_file(), (
        "the spec must be re-derivable from a newly approved document"
    )

    spec = json.loads(spec_path.read_text())
    assert spec["page"]["page_width_in"] == 8.5
    assert spec["styles"]["Heading 1"]["size_pt"] == 16.0
    assert spec["sections"]["section_style"] == "Heading 1"
    assert "pageBreakBefore" in spec["sections"]["renderer_uses"]
    # Formatting only: tenant labels and author names have no place in a template.
    blob = spec_path.read_text()
    for leak in ("MSIP_Label", "siteId", "lastModifiedBy"):
        assert leak not in blob, f"{leak} leaked into the committed format spec"


def test_title_page_contract_is_stated_everywhere_it_is_enforced():
    template = (SKILLS / "references" / "document-template.md").read_text()
    architect = (AGENTS / "instrumentation-architect.agent.md").read_text()
    skill = (SKILLS / "customer-doc-render" / "SKILL.md").read_text()
    prompt = (ROOT / "prompts" / "02-develop-instrumentation-guide.md").read_text()

    for name, text in (("template", template), ("architect agent", architect),
                       ("render skill", skill), ("prompt 02", prompt)):
        assert "title-page" in text, f"{name} must declare the title-page block"
        assert "Document control and evidence basis" in text, (
            f"{name} must send metadata to a body section, not the title page"
        )

    # Markdown ## -> Word Heading 1 is the visible difference between a document
    # that looks like the approved sample and one that does not.
    assert "Heading 1" in template
    assert "pageBreakBefore" in template
    assert "pageBreakBefore" in skill


# --------------------------------------------------------------------------- #
# plugin packaging
# --------------------------------------------------------------------------- #
def test_plugin_manifests_agree():
    claude = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    codex = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
    assert claude["name"] == codex["name"] == PLUGIN.name
    assert claude["version"] == codex["version"], (
        "Claude and Codex plugin manifest versions must match"
    )


def test_plugin_mcp_config_has_no_inline_credentials():
    config = json.loads((PLUGIN / ".mcp.json").read_text())
    blob = json.dumps(config)
    assert "mcpServers" in config
    for pattern in (r"eyJ[A-Za-z0-9_-]{8,}\.", r"\b[0-9a-f]{32,}\b",
                    r"\bAKIA[A-Z0-9]{12,}\b"):
        assert not re.search(pattern, blob), (
            f"credential-shaped value in .mcp.json matching {pattern}; "
            "use ${ENV_VAR} references only"
        )


def test_plugin_skills_mirror_canonical_skills():
    mirrored = sorted(p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md"))
    assert mirrored == CANONICAL_SKILLS, (
        "plugin skills drifted from canonical skills; run "
        "`make sync-plugin-skills`"
    )
    for skill in CANONICAL_SKILLS:
        canonical = (SKILLS / skill / "SKILL.md").read_text()
        assert (PLUGIN / "skills" / skill / "SKILL.md").read_text() == canonical, (
            f"{skill}: plugin copy differs from canonical; run "
            "`make sync-plugin-skills`"
        )


def test_cursor_skill_links_resolve():
    links = sorted((ROOT / ".cursor" / "skills").iterdir())
    assert links, ".cursor/skills must expose the skills to Cursor"
    for link in links:
        assert (link / "SKILL.md").exists(), f"{link.name}: dangling skill link"


# --------------------------------------------------------------------------- #
# no credentials anywhere in the agentry
# --------------------------------------------------------------------------- #
CREDENTIAL_PATTERNS = [
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+")),
    ("aws access key", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[A-Z0-9]{12,}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("github token", re.compile(r"\bgh[posur]_[A-Za-z0-9]{20,}\b")),
    ("stripe key", re.compile(r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("basic-auth url", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
]


def test_no_credentials_committed():
    findings = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".json", ".py", ".yaml",
                                                     ".yml", ".cjs", ".mk", ""}:
            continue
        if path.name == Path(__file__).name:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in CREDENTIAL_PATTERNS:
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
    assert not findings, "credential-shaped values committed: " + "; ".join(findings)
