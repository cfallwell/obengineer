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
                     "instrumentation-analyze", "instrumentation-wiki",
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
        "prompt 01": PROMPTS / "01-analyze-application.md",
        "document template": SKILLS / "references" / "document-template.md",
        "analyze skill": SKILLS / "instrumentation-analyze" / "SKILL.md",
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
    "Custom Metrics",
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
# generated Terraform names a real resource or refuses
# --------------------------------------------------------------------------- #
def test_terraform_reference_pins_versions_and_records_the_hard_negatives():
    """A resource type that does not exist fails as what looks like a provider bug.

    The expensive half of this reference is the negative half: the names that read
    as though they must exist, and do not. Losing those lines costs a plan cycle
    each time, so they are asserted rather than trusted.
    """
    ref = (SKILLS / "references" / "splunk-terraform-providers.md").read_text()

    for pin in ("~> 9.34", "~> 3.0", "~> 1.5"):
        assert pin in ref, (
            f"every provider needs a major pin; missing {pin}. An unpinned provider "
            "turns an unrelated init into an unplanned upgrade"
        )

    for absent in ("APM MetricSets", "APM Business Workflows", "Log Observer Connect"):
        assert absent in ref, (
            f"{absent} has no Terraform resource; the reference must say so and name "
            "the manual path, or a generator will invent a resource for it"
        )

    assert "no `splunk_acl` resource" in ref, (
        "splunk_acl has a documentation page and no resource behind it — the single "
        "most inviting wrong name in the platform provider"
    )
    assert "synthetics_create_http_check_v2" in ref and "`_v2`" in ref, (
        "synthetics 3.0.0 removed the non-_v2 resources; generating a legacy name "
        "fails at init"
    )
    assert "200" in ref, (
        "the registry answers 200 for pages that do not exist, so a link check is "
        "not verification; the reference must say what is"
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
# the customer document: findings up front, catalogue at the back, one artifact
# --------------------------------------------------------------------------- #
TEMPLATE = SKILLS / "references" / "document-template.md"

# Order matters and is the request: architecture, then the findings it produced,
# then what to do, then the catalogue the build reads, then appendices.
CATALOGUE_SECTIONS = (
    "Business Transactions",
    "Workflows",
    "Custom Metrics",
    "BT-Aligned Workflows",
    "Detectors and Thresholds",
    "Service Level Indicators and Objectives",
    "Composite Use Cases",
)


def test_findings_come_immediately_after_the_architecture():
    """A reachable credential was once on page 180 of a document nobody finished.

    Section 4 exists so a reader who stops after six pages still leaves with the
    list. Anything placed between the architecture and the findings pushes them
    down, so the ordering is asserted rather than described.
    """
    text = TEMPLATE.read_text()
    arch = text.index("| 3 | **\\<Frontend\\> and Backend Architecture (Observed)**")
    findings = text.index("| 4 | **Critical Findings** |")
    course = text.index("| 5 | Course of action |")
    assert arch < findings < course, (
        "critical findings must sit between the architecture section and the "
        "course of action"
    )

    spec = (SKILLS / "references" / "critical-findings.md").read_text()
    for required in ("Exposure", "Risk if unaddressed", "Remediation path",
                     "Verification", "Files and surfaces involved"):
        assert required in spec, f"findings spec is missing: {required}"
    assert "Never the value" in spec, (
        "the findings spec must forbid reproducing a discovered credential"
    )


def test_catalogue_sections_are_contiguous_and_ordered():
    text = TEMPLATE.read_text()
    positions = []
    for name in CATALOGUE_SECTIONS:
        marker = f"**{name}** | H1 |"
        assert marker in text, (
            f"'{name}' must be a top-level section of the customer document; the "
            "catalogue is what the implementer and the Terraform run read"
        )
        positions.append(text.index(marker))
    assert positions == sorted(positions), (
        "catalogue sections are out of order; each is defined in terms of the one "
        f"before it. Required order: {' -> '.join(CATALOGUE_SECTIONS)}"
    )
    # And they close the body: nothing but appendices after the last one.
    assert text.index("| Appendix A: Master Attribute Dictionary") > positions[-1]


def test_appendices_are_topic_scoped_not_a_container_for_the_document():
    """The whole analysis was once nested under 'Appendix A — Target breakdown'.

    That put the substance of the document behind a heading that reads as
    optional. Appendices now have named topics, and the rule is stated where a
    run will read it.
    """
    text = TEMPLATE.read_text()
    for appendix in ("Appendix A: Master Attribute Dictionary",
                     "Appendix B: Supplementary Code and Configuration",
                     "Appendix C: Instrumentation Agent Work Order",
                     "Appendix D: Supplementary Evidence",
                     "Appendix E: Open Items and Assumptions"):
        assert appendix in text, f"missing topic-scoped appendix: {appendix}"
    assert "Body content under an appendix heading" in text, (
        "the completeness bar must fail a document that hides body content in an "
        "appendix"
    )


def test_every_detector_needs_a_threshold_and_every_objective_a_budget():
    text = TEMPLATE.read_text()
    assert "A detector with no threshold" in text
    assert "error budget" in text
    levels = (SKILLS / "references" / "service-levels.md").read_text()
    for required in ("Good events", "Total events", "error budget",
                     "burn-rate", "user-facing statement"):
        assert required.lower() in levels.lower(), (
            f"the service-levels spec must define {required}"
        )
    assert "voice" in levels.lower(), (
        "objectives are written in the customer's voice first, the query second"
    )


def test_use_cases_open_with_a_narrative():
    text = TEMPLATE.read_text()
    narrative = text.index("**`Narrative`**")
    identity = text.index("**`Workflow identity`**")
    assert narrative < identity, (
        "the narrative comes first; a use case whose narrative cannot be written "
        "does not exist"
    )


# --------------------------------------------------------------------------- #
# one customer document, and a wiki underneath it
# --------------------------------------------------------------------------- #
def test_there_is_exactly_one_customer_facing_document():
    """The second document duplicated the first and was read by nobody.

    Customers did not read it and agents could not load it without spending
    their whole context on irrelevant material. Nothing may reintroduce it.
    """
    template = TEMPLATE.read_text()
    assert "One customer document, two renderings" in template
    assert "A second customer-facing document" in template, (
        "the completeness bar must fail a run that produces two documents"
    )

    wiki_prompt = (PROMPTS / "02-build-instrumentation-wiki.md").read_text()
    assert "Do not produce a second document" in wiki_prompt
    assert ".docx" in wiki_prompt, "the wiki prompt must say it emits no .docx"

    # Naming the retired artifact to say it is retired is fine; producing or
    # reading it is not, so the check is for a live path reference.
    stale = [
        path
        for path in sorted(ROOT.rglob("*.md"))
        if PLUGIN not in path.parents
        and "docs/observability/INSTRUMENTATION-GUIDE.md" in path.read_text()
    ]
    assert not stale, (
        "the retired guide artifact is still read or written by "
        + ", ".join(str(p.relative_to(ROOT)) for p in stale)
    )


def test_wiki_is_addressable_and_host_readable():
    spec = (SKILLS / "references" / "agent-wiki.md").read_text()
    # Customer above application, because tenancy and entitlement are
    # customer-level facts that must not be duplicated per application.
    assert spec.index("<Customer>/") < spec.index("<app>/")
    for required in ("business-transactions/", "workflows/", "use-cases/",
                     "findings/", "detectors/", "slos/", "work-orders/",
                     "meta/", "index.md"):
        assert required in spec, f"wiki layout is missing {required}"
    # Frontmatter is what makes it machine-usable rather than a folder of prose.
    for field in ("type:", "status:", "updated:", "tags:"):
        assert field in spec, f"note frontmatter must carry {field}"
    assert "[[wikilinks]]" in spec
    for host in (".cursor/rules", "CLAUDE.md", "AGENTS.md"):
        assert host in spec, f"the wiki must be reachable from {host}"
    assert "Do not load the whole wiki" in spec, (
        "the retrieval rule is the point of having a wiki rather than a document"
    )


def test_a_note_earns_its_file():
    """One note per subject is not one note per name. An application with four
    hundred workflows would otherwise open with four hundred frontmatter stubs,
    which dilutes every search and hides the twenty that have a design."""
    spec = (SKILLS / "references" / "agent-wiki.md").read_text()
    rule = spec[spec.index("## A note earns its file"):]
    rule = rule[:rule.index("\n## ", 10)]
    # The promotion trigger has to be concrete, or it is a matter of taste.
    for trigger in ("spans", "threshold", "objective", "work order"):
        assert trigger in rule, f"promotion trigger {trigger} is not named"
    assert "BT note" in rule, "an unpromoted workflow needs a stated home"
    assert "index.md" in rule, (
        "counts belong in the index, so the gap is visible rather than looking "
        "like an omission"
    )
    # And the rule must come before the note shape, since it decides whether a
    # note exists at all.
    assert spec.index("## A note earns its file") < spec.index("## Note shape")


# --------------------------------------------------------------------------- #
# the run repeats: versions tracked, deltas not rewrites, CI possible
# --------------------------------------------------------------------------- #
def test_versions_are_tracked_with_provenance_and_an_upgrade_path():
    spec = (SKILLS / "references" / "version-currency.md").read_text()
    for component in ("semconv", "collector", "tf.signalfx", "rum_agent"):
        assert component in spec, f"version tracking must cover {component}"
    assert "Provenance" in spec or "provenance" in spec, (
        '"how do you know" is the question that matters when a number is wrong'
    )
    assert "Upgrade path" in spec
    assert "unverified" in spec, (
        "a version that could not be checked must be marked, not reused as though "
        "it were confirmed"
    )
    # A breaking change has to reach the agents, and code cuts over before config.
    assert "Action for the implementer agent" in spec
    assert "Action for the as-code agent" in spec


def test_repeat_runs_are_deltas_and_carry_findings_forward():
    spec = (SKILLS / "references" / "incremental-runs.md").read_text()
    assert "Changes since v" in spec
    for required in ("New surfaces and services", "Drift", "re-baseline"):
        assert required.lower() in spec.lower(), f"delta spec is missing {required}"
    assert "never renumbered" in spec, (
        "finding ids outlive the document; renumbering invalidates every ticket"
    )
    template = TEMPLATE.read_text()
    assert "Changes since v<N-1>" in template, (
        "the template must carry the delta subsection, or a repeat run has nowhere "
        "to put what changed"
    )


def test_ci_layers_are_ordered_and_have_runnable_examples():
    spec = (SKILLS / "references" / "ci-integration.md").read_text()
    one = spec.index("Contract checks")
    two = spec.index("Agent instrumentation")
    three = spec.index("Configuration delivery")
    assert one < two < three, (
        "adopt deterministic checks before agent pull requests; without them "
        "nothing measures whether the pull requests helped"
    )
    assert "never pushes to the default branch" in spec
    assert "Detectors arrive disabled" in spec
    assert "own repository" in spec, (
        "observability configuration belongs beside neither the application's "
        "reviewers nor its revert history"
    )

    examples = ROOT / "examples" / "ci"
    for name in ("contract-checks.yml", "agent-instrument.yml",
                 "terraform-plan-apply.yml", "README.md"):
        assert (examples / name).is_file(), f"missing CI example: {name}"
    # An example that leaks a token teaches the wrong thing more effectively
    # than the prose teaches the right one.
    for workflow in examples.glob("*.yml"):
        text = workflow.read_text()
        # Full-length shapes only: these workflows legitimately contain the
        # prefixes as part of a detection pattern.
        assert not re.search(
            r"(AKIA[A-Z0-9]{16}|ghp_[A-Za-z0-9]{20,}|sk_live_[A-Za-z0-9]{20,}"
            r"|eyJ[A-Za-z0-9]{20,}\.)", text), (
            f"{workflow.name} contains a credential-shaped literal"
        )
        if "secrets." in text:
            assert "${{ secrets." in text, (
                f"{workflow.name} must read tokens from the secret store"
            )


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
    prompt = (ROOT / "prompts" / "01-analyze-application.md").read_text()

    for name, text in (("template", template), ("architect agent", architect),
                       ("render skill", skill), ("prompt 01", prompt)):
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
