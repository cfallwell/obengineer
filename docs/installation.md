# Installation and lifecycle

obengineer installs Markdown command entry points and skill directories into an agent
host. The installer does not install Python, create a Git repository, or write a
credential. The guided setup script creates local `.env` without displaying values.

## 1. Choose where generated artifacts will live

The toolkit checkout and generated artifacts should remain separate:

```text
/path/to/obengineer/       toolkit, prompts, agents, and canonical skills
/path/to/memory-repo/      engagement inputs, analysis, wiki, and Terraform
```

The artifact repository can be:

- the application repository, which keeps code and contract checks together;
- a separate memory repository shared by several application repositories; or
- a submodule mounted into the relevant repositories.

Record the choice in the generated wiki's `meta/decisions.md` and keep only one copy.
See the canonical [CI integration reference](../skills/references/ci-integration.md)
for the trade-offs.

Create or clone the repository before project-scoped installation:

```bash
mkdir -p /path/to/memory-repo
git -C /path/to/memory-repo init
git -C /path/to/memory-repo commit --allow-empty -m "Initial commit"
```

## 2. Clone the toolkit and install dependencies

```bash
git clone https://github.com/cfallwell/obengineer.git
cd obengineer
python3 -m pip install PyYAML==6.0.3
```

`PyYAML==6.0.3` validates/migrates engagement inputs. Install `python-docx` and
`markdown-it-py==4.2.0` only when rendering the optional Word summary. `make deps`
installs development and renderer dependencies.

Install the Terraform CLI when using `/ob-terraform`; analysis, review, and application
implementation do not require it.

## 3. Install into one or more hosts

Project-scoped installation is recommended because the commands are available only
when working in the repository that owns the artifacts:

```bash
./install.sh --cursor --project /path/to/memory-repo
./install.sh --claude --codex --project /path/to/memory-repo
./install.sh --all --project /path/to/memory-repo
```

User-scoped installation omits `--project`:

```bash
./install.sh --cursor
./install.sh --all
```

Restart the host after installation so it discovers the new commands and skills.

### Install locations

| Host | User-scoped | Project-scoped |
|---|---|---|
| Cursor | `~/.cursor/{skills,commands}` | `<project>/.cursor/{skills,commands}` |
| Claude Code | `~/.claude/{skills,commands}` | `<project>/.claude/{skills,commands}` |
| Codex | `~/.codex/skills` and `~/.codex/prompts` | `<project>/.agents/skills` and `<project>/.agents/prompts` |

Each host directory receives `.obengineer-install.json`. The manifest records the
source checkout, scope, and paths created by the installer so removal is bounded to
those paths.

### Installer options

| Option | Behavior |
|---|---|
| `--cursor` | Select Cursor. |
| `--claude` | Select Claude Code. |
| `--codex` | Select Codex. |
| `--all` | Select all supported hosts. It can be combined with individual host flags without changing the result. |
| `--project PATH` | Resolve `PATH` to an absolute path and install into host-specific directories beneath it. Without this option, installation is under the current user's home directory. |
| `--copy` | Copy skill trees instead of creating relative directory symlinks. Commands are always copied because the installer substitutes the toolkit's absolute path into them. |
| `--list` | Display all host paths and whether each host has an obengineer manifest, then exit without changing files. |
| `--dry-run` | Print every planned link, copy, write, or removal without changing files or writing a manifest. |
| `--uninstall` | Remove paths listed in the selected host's manifest. Combine it with a host selector and the same `--project` scope used for installation. |
| `-h`, `--help` | Print the current command-line reference. |

At least one host selector is required except with `--list`.

### Symlink and copy behavior

Symlinks are the default. A canonical skill edit in the toolkit is then visible to the
host immediately, although the host may need a restart or new session. `--copy` is for
hosts, filesystems, or distributable workspaces that cannot follow symlinks.

Re-run installation after:

- using `git pull` to receive command changes, because command files are copied;
- moving the toolkit checkout, because installed commands contain its resolved
  absolute path; or
- receiving skill changes when the original install used `--copy`.

Reinstalling this release migrates `/ob-intake`, `/ob-generate`, and `/ob-wiki` to
`/ob-start`, and
`/ob-build-terraform` to `/ob-terraform`. The installer removes retired command files
only when the prior obengineer manifest proves it created them; same-named user files that
were not installed by obengineer are left alone.

The installer replaces an existing destination with the same skill or command name.
Uninstall removes the replacement; it cannot restore content that existed before the
install. Review a `--dry-run` before installing into a host with custom files of the
same names.

## 4. Configure optional read-only Splunk access

No manual file editing or template copying is required. From the memory repository run:

```bash
/path/to/obengineer/scripts/setup-splunk-access.sh
```

The script explains where to create least-privilege credentials, prompts in the terminal,
writes `.env` with restrictive permissions, and ensures `.env` is ignored. It never prints
tokens. Existing relevant MCP integrations are discovered by `/ob-start`; direct APIs
remain available when an MCP server is absent or incomplete.

## Claude Code plugin installation

Claude Code can install the self-contained plugin bundle instead of loose
project-scoped skills:

```bash
claude plugin marketplace add /path/to/obengineer
# Install the obengineer plugin from the added marketplace.
```

The plugin includes commands (with `${CLAUDE_PLUGIN_ROOT}` paths), agents, prompts, hooks,
skills, and MCP declarations. Its committed
`.mcp.json` is empty by design; tenant-specific server commands still require operator
configuration.

## Inspect, upgrade, and remove

Inspect project-scoped status:

```bash
./install.sh --list --project /path/to/memory-repo
```

Upgrade a symlink-based installation by reusing the original host selectors. For
example, upgrade a Cursor-only installation with:

```bash
git pull --ff-only
./install.sh --cursor --project /path/to/memory-repo
```

Use `--all` only when all three hosts were installed originally or should be installed
now.

Preview and then remove selected hosts:

```bash
./install.sh --cursor --project /path/to/memory-repo --uninstall --dry-run
./install.sh --cursor --project /path/to/memory-repo --uninstall
```

Use the same toolkit checkout when possible. The manifest contains absolute paths, so
uninstall can remove installed entries even when the source checkout has moved, but
running from the original checkout makes the intended source and scope clear.

## Installation troubleshooting

### No commands appear

1. Restart the host or open a new session.
2. Run `./install.sh --list --project <repo>`.
3. Confirm that the host opened `<repo>`, not the toolkit checkout.
4. Confirm the command directory in the status output matches the host's current
   convention.
5. Re-run installation after moving the toolkit.

### Rendering fails with an import error

Install into the same Python interpreter used by the command:

```bash
python3 -m pip install python-docx markdown-it-py==4.2.0 PyYAML==6.0.3
python3 -c "import docx, markdown_it, yaml; print(docx.__version__, markdown_it.__version__, yaml.__version__)"
```

### A copied skill did not update

Re-run the install with `--copy`, or uninstall and return to the default symlink mode.

### Tenant data is reported as “Not in evidence”

Installation alone does not enable tenant access. Configure the required MCP servers
and environment variables described in [Configuration](configuration.md). The analysis
continues without them, but tenant facts remain stated or unavailable rather than
measured.
