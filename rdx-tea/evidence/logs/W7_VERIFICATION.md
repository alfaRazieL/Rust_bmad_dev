# Wave 7 — Installer / bootstrap & project settings — verification

- **Repo / branch:** `rdx-workspace/Rust_bmad_dev` @ `rdx-tea-integration`
- **Basis:** D3_RULE_OPERATION_PROVEN (D3.4.1). Productionization only — the
  sequential wrapper-driven RDX→TEA lifecycle is already PROVEN; W7 adds the
  idempotent project installer that ships the proven surface. G7 (behavioural
  benefit vs baseline) is out of scope, not claimed.
- **W7 START_HEAD:** `e722d17df155e32d4f56e13edd35c89667366614` (== W6 FINAL_HEAD)
- **Pre-W7 owner checkpoint commit:** `28cbfc6` (record Wave 6 owner checkpoint)
- **Python:** 3.14.4 (`rdx-tea/.venv-baseline`)
- **cwd for all commands:** repo root `.../rdx-workspace/Rust_bmad_dev`
- **Live model calls:** NONE. The 12-run pilot / mass eval were NOT re-run;
  D3.4.1 evidence is cited. No `CLAUDE_CONFIG_DIR` override; no auth material
  read or written; inherited OAuth session unchanged.

## Pre-W7 regression (before any installer code) — all PASS

See `W7/PRE_W7_REGRESSION.txt`. Full suite 277 passed (matches W6 handoff).
W5/W6 generator invariants unchanged (canonical snapshot + W3 golden bundle
pins match).

## Change summary (packaging productionization; proven runtime untouched)

W7 adds `rdx-tea/installer/` — a repo/distribution-side project installer
(`project_installer.py` + package `__init__`, CLI `rdx-tea-setup`). It writes
the shipped surface from `poc/install-tree/` into a user project:

- `_bmad/rdx-tea/{canonical/**, scripts/** (all 10), bootstrap/sources.lock,
  VERSION}`
- `.claude/skills/rdx-tea-{test-design,atdd}/SKILL.md`
- `.claude/settings.json` — project-surface isolation ONLY
  (`disableBundledSkills`, `disableClaudeAiConnectors`,
  `autoMemoryEnabled:false`); no auth fields.
- `_bmad/custom/` overlay directory + an adapter-owned overlay writer that
  refuses `*.user.toml`.

No production runtime file (`canonical/`, `scripts/`, `SKILL.md`) was modified;
the installer only copies them. Determinism only: sorted inventory, no
wall-clock/random, byte-identical install + manifest across processes.

### Install / update / uninstall semantics

- **Install** — fails closed on an unsupported TEA version BEFORE any write;
  builds a deterministic, validated inventory (refuses if any of the 10
  required production scripts is absent from source); writes each file only if
  bytes differ (idempotent); writes an auth-free isolation `settings.json`
  (merge-preserving of any user keys); writes a deterministic install manifest.
- **Update** — idempotent re-install; refuses to overwrite `*.user.toml`
  (never part of the inventory; guarded).
- **Uninstall** — removes adapter-owned files (from the manifest) plus
  adapter-owned `bmad-testarch-*.toml` base overlays, reverses the settings
  isolation merge (preserving user keys / deleting the file only if empty),
  and KEEPS all `*.user.toml` and user artifacts.
- **Version-range refusal** — `_bmad/tea/config.yaml` declaring a TEA version
  outside `[1.19.0, 2.0.0)` (window derived from `sources.lock:tea_source_tag`)
  fails closed; unparseable version fails closed; absent version installs.

## Gates

| Gate | Command | Result |
|---|---|---|
| G-W7-INSTALL | `pytest rdx-tea/tests/lifecycle -k install` | PASS (22) |
| G-W7-NOAUTH | `pytest rdx-tea/tests/lifecycle -k noauth` | PASS (3) |
| G-W7-IDEMPOTENT | `pytest rdx-tea/tests/lifecycle -k idempot` | PASS (3) |
| G-AUTH | grep auth/config-dir over `install-tree` + `installer` | PASS (0 hits) |
| G-SPLIT-IMPORT | grep boundary over `install-tree` + `installer` | PASS (0 hits) |
| G-SCOPE | `git diff --name-only origin/main..HEAD` outside allowed prefixes | PASS (empty) |

See `W7/W7_GATES.txt` for command outputs and `auth-preflight/
W7_INSTALLER_NOAUTH.json` for the no-auth preflight.

## Installed-surface checks (prompt §"Required W7 installed-surface checks")

A temporary installed project CONTAINS (asserted): `canonical/**`,
`scripts/{admission,workspace_delta,binder,prepare,rdx_tea_wrapper,
rdx_tea_validator,router,diff,obligation_matrix,rdx_parser}.py`,
`bootstrap/sources.lock`, `VERSION`, both wrapper `SKILL.md`, and
`.claude/settings.json`. It does NOT contain: `live-harness/`, `evals/`,
`evidence/`, `research/`, `tests/`, `implementation/`, `implementation-plan/`.

Installed admission CLI smoke: running the INSTALLED
`_bmad/rdx-tea/scripts/admission.py admit` against a bundle that self-declares
`admissible:true` returns `admissible:false` (exit 2) — it recomputes from
primitives and never trusts self-reported admission (W6 invariant preserved).

## Full suite — GREEN

`pytest rdx-tea/tests -q` → **299 passed** (277 pre-W7 + 22 new W7 installer
tests). No regressions. See `W7/W7_full_suite_GREEN.log`.
