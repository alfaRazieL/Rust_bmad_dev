# INSTALL — RDX-TEA adapter

How to install, update, and uninstall the RDX-TEA shipped surface into a
project. The installer is idempotent, deterministic, and
authentication-preserving.

## Prerequisites

- A Python 3 interpreter with `PyYAML` available (the wrapper runtime
  reads `sources.lock` and `_bmad/tea/config.yaml`).
- A target **project** directory (the repository you want to run TEA
  workflows in). This is referred to below as `<project>`.

## The installer command

The installer identifies itself as **`rdx-tea-setup`**. Invoke it from the
adapter repository:

```bash
# install
python3 rdx-tea/installer/project_installer.py install --project <project>

# update (idempotent re-install; preserves user overlays)
python3 rdx-tea/installer/project_installer.py update --project <project>

# uninstall (removes adapter-owned files; keeps your content)
python3 rdx-tea/installer/project_installer.py uninstall --project <project>
```

Each subcommand prints a JSON result. A refusal prints
`{"status": "REFUSED", "reason": "..."}` and a non-zero exit code — the
installer **fails closed and writes nothing** on refusal.

Read `--help` for the exact surface:

```bash
python3 rdx-tea/installer/project_installer.py --help
python3 rdx-tea/installer/project_installer.py install --help
```

## What `install` places into `<project>`

The installer copies **only** the shipped adapter surface:

```
<project>/_bmad/rdx-tea/canonical/**              # the Rust rule KB + schema
<project>/_bmad/rdx-tea/scripts/**                # the 10 production scripts
<project>/_bmad/rdx-tea/bootstrap/sources.lock    # identity stamp
<project>/_bmad/rdx-tea/VERSION                    # adapter version
<project>/.claude/skills/rdx-tea-test-design/SKILL.md
<project>/.claude/skills/rdx-tea-atdd/SKILL.md
<project>/.claude/settings.json                   # project-surface isolation (merged)
<project>/_bmad/custom/                            # empty dir for per-run overlays
<project>/_bmad/rdx-tea/.rdx-tea-install-manifest.json  # tracks adapter-owned files
```

The install is deterministic: the same source tree always produces a
byte-identical install and manifest. A second `install` (or `update`)
with an unchanged source is a **no-op** — unchanged files are left
untouched and the JSON result lists them under `unchanged`.

## Project-surface isolation settings

The installer merges three **project-surface isolation** keys into
`<project>/.claude/settings.json`, preserving any keys you already have:

| Key | Value | Effect |
|---|---|---|
| `autoMemoryEnabled` | `false` | Keeps run-to-run state out of the project surface. |
| `disableBundledSkills` | `true` | Ensures the wrapper Skills are the ones that run. |
| `disableClaudeAiConnectors` | `true` | Isolates the project surface. |

These are the **only** keys the installer writes. It never adds an
authentication field of any kind. `uninstall` reverses the merge: it drops
only the isolation keys whose value still matches the template, preserves
your own keys, and deletes the file only if nothing else remains.

## Authentication is preserved by doing nothing

The installer **never writes or reads any authentication material**, and
**never sets or overrides the CLI configuration-directory environment
variable**. Authentication is preserved precisely because the installer
does nothing with it.

You do **not** need to configure any API key, OAuth token, credential
file, or key-helper for RDX-TEA. If you already run BMad TEA in the
project, RDX-TEA inherits your existing session unchanged. There are no
credential-configuration steps in this guide by design.

## TEA version-range refusal

Before writing anything, the installer checks the TEA version declared in
`<project>/_bmad/tea/config.yaml` (keys `tea_version`, `module_version`,
or `version`) against the supported window derived from `sources.lock`
(same major, at least the pinned minor/patch). If the declared version is
outside that window — or unparseable — the installer **refuses and
installs nothing**. See
[TROUBLESHOOTING.md](TROUBLESHOOTING.md#installer-version-refusal).

If the project declares no TEA version, there is nothing to be
incompatible with and the install proceeds.

## Update and user-owned overlays

`update` is an idempotent re-install. The installer never overwrites a
user-owned `*.user.toml` overlay — such files are never part of the
adapter inventory, so your customizations survive updates and uninstalls.

## Uninstall

`uninstall` removes exactly the adapter-owned files tracked in the install
manifest, plus adapter-owned base overlays
(`_bmad/custom/bmad-testarch-*.toml`, never `*.user.toml`), then reverses
the settings merge and prunes empty adapter directories. Your content and
every `*.user.toml` are reported under `kept` and left in place.

## Next step

Once installed, configure sequential mode and run a workflow — see
[RUN_WORKFLOWS.md](RUN_WORKFLOWS.md).
