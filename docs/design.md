# Design notes

Why this agentry is shaped the way it is. For how to use it, start with the
[documentation index](README.md); for how to change it, see
[`CONTRIBUTING.md`](../CONTRIBUTING.md).

## The problem

An instrumentation engagement fails in one of three ways, and none of them are
technical:

1. **The design assumes an architecture the target does not have.** A guide written
   from a product playbook names journeys the application does not run and misses the
   ones it does. The fix is a discovery run whose output is measurements, not
   impressions — which is why `instrumentation-analyze` insists on timings, decoded
   beacon payloads, and a status-versus-content check rather than a list of installed
   products.
2. **The contract is written but not written down completely.** The section that gets
   dropped is always the same one: the cross-cutting attributes and how they
   propagate. It is dropped because it is the least visible and the most abstract, and
   its absence is not obvious until someone tries to build the first dashboard
   variable and finds the key is only on one span. This is why that section is
   mandatory in four places and guarded by a test.
3. **The deliverable and the implementation drift.** The customer reviews a Word
   document; the engineers work from something else. Six weeks later nobody can say
   which is authoritative. This is why the `.docx` is a build artifact rendered from
   the Markdown, verified programmatically, and never hand-edited.

## Structure

The layout is the conventional one for a multi-host agent bundle, chosen so this
directory can be lifted into its own repository, or folded into a larger agent
toolset, without rewriting paths:

- **`skills/` is canonical.** One source for each skill, with depth pushed into `references/` so `SKILL.md` stays readable and the host does not load a novel to answer a simple question.
- **`plugins/<name>/` is a self-contained bundle.** An installed plugin cannot reach back into this repository, so it carries copies of the skills plus the `agents/` and `prompts/` the skills link to. `scripts/sync_plugin_skills.py` is the only writer, and `--check` fails a build on drift.
- **Host wiring is symlinks, not copies,** for `.cursor/skills/` and `.agents/skills/`, so a local edit lands on the canonical file rather than a copy that will be overwritten.
- **Tests run over the agentry itself,** not just its scripts. A prescriptive document has contracts, and a contract without a test is a preference.

## One name: `obengineer`

The project refers to itself as `obengineer` in every identifier a host or a human can
see — the directory, the plugin name, the marketplace entry, the MCP server key, the
`metadata.author` on each skill. Not a display variant in the manifests and a different
spelling in the prose.

That matters because of what comes next. This bundle is expected to merge into a larger
agent toolset, and a merge is cheap only if the names it brings are already stable and
already unique. Two spellings of the same project become two entries in a marketplace,
and skills whose `$name` changes on merge break every prompt that referenced them.

So the merge path is a deliberate constraint, not an aspiration:

- **Skill names are the public API.** `$instrumentation-analyze`, `$baggage-propagation`, and the rest are referenced from prompts, from agent files, and from the customer documents this produces. Renaming one is a breaking change with no deprecation path, so treat it as one.
- **Nothing resolves paths above the bundle root.** Skills reach `../references/` and `../../agents/`, never an absolute path or a repository name. A bundle that only knows its own root can be moved by moving the directory.
- **Hosts are wired by generated links, not by hand.** `scripts/sync_plugin_skills.py` writes `.cursor/skills/` and `.agents/skills/`, so adopting a new host means teaching one script, and a move breaks nothing that a re-run will not fix.
- **MCP servers are declared, never assumed.** `.mcp.json` ships with an empty `mcpServers` object because the command is organisation-specific. Splunk Observability Cloud and Splunk Enterprise are mandatory to enable; the operator copies those entries and supplies the command. Other servers are recommended or used only when already present. The list has one home: `skills/references/mcp-servers.md`. A toolset that absorbs this one must not inherit a hardcoded endpoint or a token.

## Why the template is a file, not a habit

`skills/references/document-template.md` exists because the format was previously
carried in a single customer PDF. A future session with no access to that PDF would
produce a document with the same content in a different order, under different
headings, and the customer would experience it as a regression.

The template is deliberately self-contained: section order, every table's columns, the
front matter, the pre-delivery checklist. It is reproducible from nothing but itself,
and it names the three placements that are easy to get wrong — architecture near the
front, the attribute dictionary at the back, and the cross-cutting section between
them.

## Resolved design decisions

**Renderer migration uses a real Markdown parser.** The current line-based renderer is
the compatibility baseline, not the long-term parsing architecture. New parser work must
use a CommonMark syntax tree (`markdown-it-py` or an equivalent maintained parser) feeding
the existing `.docx` writer. The migration is complete only when the current structural,
cross-reference, credential, and round-trip verification suite passes and visual output
matches the approved format. Until then, the line-based implementation receives defect
fixes but no new Markdown syntax. Today, `python-docx` remains the only renderer runtime
dependency. The parser migration explicitly includes adding and pinning the maintained
parser dependency and updating the README, `make deps`, plugin bootstrap check, and
dependency documentation in the same change. The parser direction is settled; output
compatibility and an atomic dependency-contract update are the migration gates.

**MCP commands remain operator-supplied rather than hardcoded.** A server command or URL
cannot be verified by the repository because it is organisation-specific. Hardcoding a
placeholder makes plugin startup fail, while hardcoding a real endpoint creates customer
coupling and a credential risk. `.mcp.optional.json` therefore documents entries and
environment-variable references; the operator supplies the verified command. Splunk
Observability Cloud and Splunk Enterprise are mandatory to enable. ThousandEyes, local
OpenTelemetry tools, and cloud inventory are enabled when relevant. Jira is used only when
the human named it and the host already has its MCP. The classification lives in
`skills/references/mcp-servers.md`.

## What this agentry deliberately does not do

- **It does not apply Terraform automatically.** With tenant access, `/ob-terraform`
  inventories existing objects, generates import-aware Terraform for dashboards,
  detectors, SLOs, and other supported artifacts, and produces a reviewed plan. Without
  MCP or planning credentials, it generates the code with unresolved imports clearly
  marked and validates provider schemas; it reports that result as schema-checked, not
  planned. A human supplies the missing access, reviews the eventual plan, and runs
  `terraform apply` manually. The agent never applies its own plan.
- **It does not remediate the security findings the analysis surfaces.** The authorized
  OWASP/credential/API assessment records confidence-rated findings and P0 fixes with
  owners; runtime remediation is a separately accepted work order.
- **It does not implement the contract during analysis.** `instrumentation-implement`
  writes application code only against an exact-commit accepted guide and one unified
  bounded work order, coordinating linked PRs when repositories are separate.
