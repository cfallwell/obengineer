# Installation

This page explains how to install obengineer's commands and skills into Cursor, Claude
Code, Codex CLI, or ChatGPT Desktop, how to confirm the install worked, and how to
upgrade or remove it. After installation, continue with [Configuration](configuration.md)
and the [end-to-end walkthrough](usage.md).

The installer copies or links Markdown command files and skill directories into a host's
configuration directory. It does not install Python, create a Git repository, write a
credential, or contact any network service.

## Prerequisites

| Requirement | Needed for | Notes |
|---|---|---|
| Git | Everything | The artifact repository must be a Git repository with at least one commit, because every analysis is delivered as a pull request. |
| Python 3 and `PyYAML==6.0.3` | Everything | The intake, validation, wiki, and state-ledger scripts are Python. |
| Push access and a forge CLI or integration the host can use | Analysis, implementation, and revision PRs | The agent opens pull requests against the artifact repository and the mapped application repositories. |
| Terraform CLI | `/ob-terraform` only | Analysis, review, implementation, and verification do not use Terraform. |
| `python-docx` and `markdown-it-py==4.2.0` | `/ob-render` only | Needed only for the optional Word summary. |
| Read-only Splunk tokens | Measured tenant evidence (optional) | Configured later in `obconfig.yaml`; see [Configuration](configuration.md#splunk-tenant-access). |

## 1. Choose the artifact repository

Keep the toolkit checkout separate from the repository that receives generated
artifacts:

```text
/path/to/obengineer/       toolkit: commands, prompts, agents, skills, scripts
/path/to/memory-repo/      artifacts: obconfig.yaml, analysis, wiki, Terraform
```

The artifact repository can be:

- the application repository itself, which keeps code and contract checks in one place;
- a separate memory repository shared by several application repositories; or
- a Git submodule mounted into each relevant application repository.

See [CI integration](../skills/references/ci-integration.md) for the trade-offs. If the
repository does not exist yet, create it with an initial commit:

```bash
mkdir -p /path/to/memory-repo
git -C /path/to/memory-repo init
git -C /path/to/memory-repo commit --allow-empty -m "Initial commit"
```

## 2. Clone the toolkit and install Python dependencies

```bash
git clone https://github.com/cfallwell/obengineer.git
cd obengineer
python3 -m pip install PyYAML==6.0.3
```

Install the optional Word renderer dependencies only if you plan to use `/ob-render`:

```bash
python3 -m pip install python-docx markdown-it-py==4.2.0
```

`make deps` installs the renderer and test dependencies together, which is useful for
toolkit maintainers.

## 3. Install into a host

Project-scoped installation is recommended. The commands then appear only when the host
has the artifact repository open:

```bash
./install.sh --cursor --project /path/to/memory-repo          # Cursor
./install.sh --claude --project /path/to/memory-repo          # Claude Code
./install.sh --codex  --project /path/to/memory-repo          # Codex CLI and ChatGPT Desktop
./install.sh --all    --project /path/to/memory-repo          # every supported host
```

Host flags can be combined, for example `--claude --codex`. Omit `--project` to install
for the current user in every repository:

```bash
./install.sh --cursor
./install.sh --all
```

Restart the host or open a new session afterwards so it discovers the new commands.

### How each host invokes the commands

| Host | Invocation | Example |
|---|---|---|
| Cursor | Slash command | `/ob-start` |
| Claude Code | Slash command | `/ob-start` |
| Codex CLI | Explicit workflow skill | `$ob-start` |
| ChatGPT Desktop | Explicit workflow skill, with its local executor available | `@ob-start` |

ChatGPT web, ChatGPT cloud, and other surfaces without local command execution are not
supported, because every workflow runs Python scripts in the artifact repository.

Codex workflow skills are explicit-only: they never activate implicitly from a prompt.
Type `/skills` in Codex CLI to list them, then invoke one by name.

## What the installer creates

### Host files

| Host | User-scoped location | Project-scoped location |
|---|---|---|
| Cursor | `~/.cursor/skills/`, `~/.cursor/commands/` | `<project>/.cursor/skills/`, `<project>/.cursor/commands/` |
| Claude Code | `~/.claude/skills/`, `~/.claude/commands/` | `<project>/.claude/skills/`, `<project>/.claude/commands/` |
| Codex CLI and ChatGPT Desktop | `~/.agents/skills/` | `<project>/.agents/skills/` |

- **Cursor and Claude Code** receive one command file per workflow (`ob-start.md`,
  `ob-analyze.md`, `ob-implement.md`, `ob-revise.md`, `ob-terraform.md`, `ob-verify.md`,
  `ob-review.md`, `ob-render.md`, and the rest) plus the canonical skill directories.
  Skills are relative symlinks into the toolkit by default; command files are written
  as copies because each one contains the toolkit's resolved absolute path.
- **Codex** receives copied canonical skill directories plus one `ob-*` workflow skill per
  command. Each workflow skill delegates to the matching command contract and passes
  your arguments through. Codex skills are always copies because Codex ignores skill
  symlinks that resolve outside the opened repository. The config template is copied to
  `<Codex base>/obengineer/obconfig.yaml.template`.
- Every host directory receives `.obengineer-install.json`, an ownership manifest that
  records the toolkit path, the scope, and a digest or symlink target for every file the
  installer created. Reinstall and uninstall use it to touch only installer-owned files.

### Project scaffold (project-scoped installs only)

The installer creates these root files only if they are missing, and never overwrites
an existing file:

```text
.gitignore                ignores /obconfig.yaml and /.obengineer/, keeps the template tracked
obconfig.yaml.template    the configuration template; copy it to obconfig.yaml
artifacts/README.md       explains the supplied-evidence directory
```

If `.gitignore` already exists, the installer appends only the missing ignore lines.
`.obengineer/scaffold-manifest.json` (itself ignored) records which scaffold files and
`.gitignore` lines the installer added.

The installer never creates `obconfig.yaml`. The first `/ob-start` run does that.

## Verify the install

1. List what is installed:

   ```bash
   ./install.sh --list --project /path/to/memory-repo
   ```

   A healthy Cursor and Codex install reports:

   ```text
   scope: project /path/to/memory-repo

     Project scaffold 2 installer-owned file(s)
     Cursor       installed
       skills   /path/to/memory-repo/.cursor/skills
       commands /path/to/memory-repo/.cursor/commands
     Claude Code  host not found
     ...
     Codex        installed
       skills   /path/to/memory-repo/.agents/skills
       workflows /path/to/memory-repo/.agents/skills/ob-*
       companion /path/to/memory-repo/.agents/obengineer/obconfig.yaml.template
   ```

2. Open the artifact repository in the host and type `/ob-` (Cursor or Claude Code),
   `/skills` (Codex CLI), or `@ob-` (ChatGPT Desktop). The `ob-start` command should be
   listed.
3. Before running `/ob-start` Copy the `obconfig.yaml.template` to `obconfig.yaml` and configure for your application. If you miss this step, `/ob-start` will create the file for you, reporting back `Created local obconfig.yaml. Edit it and rerun /ob-start.` That confirms the scripts run from the host.

## Installer options

Output of `./install.sh --help`, summarized:

| Option | Behavior |
|---|---|
| `--cursor` | Install for Cursor. |
| `--claude` | Install for Claude Code. |
| `--codex` | Install for Codex CLI and ChatGPT Desktop. |
| `--all` | Install for every supported host. Combining it with individual host flags changes nothing. |
| `--project PATH` | Install into host directories beneath `PATH` instead of the user's home directory. |
| `--copy` | Copy Cursor and Claude Code skills (instead of symlinking) and install their config-template companion. Codex skills are always copied. |
| `--uninstall` | Remove what a previous install created for the selected hosts and scope. |
| `--list` | Show what is installed and where, then exit without changes. |
| `--dry-run` | Print every planned link, copy, write, or removal without changing anything. |
| `-h`, `--help` | Print the command-line reference. |

At least one host flag is required, except with `--list`.

## Upgrade

Pull the toolkit, then rerun the install with the same host flags and scope you used
originally:

```bash
cd /path/to/obengineer
git pull --ff-only
./install.sh --cursor --project /path/to/memory-repo
```

Rerun the install after any of these:

- a `git pull`, because command files are copies;
- moving the toolkit checkout, because installed commands contain its absolute path; or
- a skill change, if you installed with `--copy` or use Codex.

Symlinked Cursor and Claude Code skills pick up toolkit edits immediately; the host may
need a new session.

Reinstall replaces only files whose ownership record still matches. It refuses (prints
`REFUSE` and changes nothing) when a destination exists that the installer did not create
or that you have modified. Move or back up the reported file, then rerun.

Reinstalling also migrates older installations: retired commands (`/ob-intake`,
`/ob-generate`, `/ob-wiki`, `/ob-build-terraform`) are removed when the previous manifest
proves the installer created them, and older Codex installs under `.agents/prompts` or
`~/.codex` are moved to `.agents/skills`. Files you created or modified are preserved.

## Uninstall

Preview, then remove, using the same host flags and scope as the install:

```bash
./install.sh --cursor --project /path/to/memory-repo --uninstall --dry-run
./install.sh --cursor --project /path/to/memory-repo --uninstall
```

Uninstall removes only installer-owned files whose content is unchanged. When the last
installed host is removed, it also removes unchanged scaffold files and the `.gitignore`
lines it added. It never removes `obconfig.yaml`, the ignore line protecting it while it
exists, the `artifacts/` directory, generated analysis or wiki content, or any file you
edited or added.

## Claude Code plugin (alternative)

Claude Code can install the self-contained plugin bundle instead of loose project files:

```bash
claude plugin marketplace add /path/to/obengineer
```

Then install the `obengineer` plugin from the added marketplace. The plugin contains the
commands, agents, prompts, hooks, skills, and an intentionally empty `.mcp.json`; add any
tenant-specific MCP servers yourself.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No `/ob-*` commands or `$ob-*` skills appear. | The host has not reloaded, or it opened the toolkit checkout instead of the artifact repository. | Restart the host, open the artifact repository, and run `./install.sh --list --project <repo>` to confirm the paths. Rerun the install if you moved the toolkit. |
| Codex does not run a workflow from a plain-language request. | Workflow skills are explicit-only by design. | Invoke it by name: `$ob-start` in Codex CLI, `@ob-start` in ChatGPT Desktop. |
| The install prints `REFUSE` and exits. | A file with the same name exists that the installer does not own, or an owned file was modified. | Move or back up the named file, then rerun. Nothing was changed. |
| The install reports an incomplete rollback. | A file was replaced concurrently during the install. | The backup staging directory is kept; restore from it manually, then rerun. |
| A command fails with `ModuleNotFoundError: yaml` or `docx`. | Dependencies are installed into a different Python. | Install into the `python3` on the host's `PATH`: `python3 -m pip install PyYAML==6.0.3 python-docx markdown-it-py==4.2.0`, then check with `python3 -c "import yaml, docx, markdown_it"`. |
| Skill edits in the toolkit are not visible. | The skills are copies (`--copy` or Codex). | Rerun the install, or for Cursor and Claude Code reinstall without `--copy` to use symlinks. |
| Analysis labels tenant facts "Not in evidence". | Installation does not grant tenant access. | Add read-only tokens in `obconfig.yaml` (see [Configuration](configuration.md#splunk-tenant-access)) or connect the relevant MCP servers. |

## Internals

The installer is transactional. Before writing, it stages backups in a private
(mode 0700) hidden directory on the same filesystem as each target, creates every new
target exclusively, and records the inode, type, mode, and digest of what it wrote. If
any step fails it rolls back only paths that still match what it wrote; anything
replaced concurrently is preserved and the staging directory is kept for manual
recovery. Scaffold files are stricter still: an existing file is never replaced, even
one an earlier install created, and an owned file you edited is treated as yours.
