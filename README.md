# Rust Dev eXpert (RDX) — BMad Module

A [BMad](https://github.com/bmad-co) expansion module that injects production-grade Rust engineering expertise into your existing BMad agents — without replacing them.

**No new agents. No new personas.** RDX layers a structured Rust knowledge base directly on top of Developer (Amelia), Architect (Winston), and Product Manager (John) using BMad's team-override mechanism.

---

## What It Does

RDX distributes a curated Rust KB across three agents, each getting exactly the rules relevant to their role:

| Agent | What changes |
|-------|-------------|
| **Amelia** (Developer) | Always loads 18 Always-on Core rules (CORE-001..018) + the Risk Router table. Must consult the router before writing any story code and load the matching conditional pack (async, unsafe, FFI, macros, etc.) when triggered. |
| **Winston** (Architect) | Loads CORE-001/005/006 for strict contract design + the full Governance section for public API / SemVer / FFI / DB boundary rules. |
| **John** (PM) | Loads the Governance section and enforces "Contract before code" (CORE-001) in every PRD and story. Grades Developer behavior — not just the output artifact. |

### Knowledge Base Structure

The KB is organized into four loadable sections installed at `_bmad/rust-kb/`:

```
section-4-core.md        ← 18 Always-on Core rules (Amelia + Winston)
section-5-router.md      ← Risk Router: 12 conditional packs with triggers
section-6-packs.md       ← All 12 packs: async, unsafe, FFI, macros, API,
                            Cargo, testing, data/sec/IO, DB, time, ops, perf
section-8-governance.md  ← Builder/evaluator governance (Winston + John)
```

The Risk Router (§5) is the key mechanism: Amelia checks it before every story and loads only the relevant conditional pack from §6 — async rules only when there's `async fn`, unsafe rules only when there's `unsafe {}`, etc. No bloat, no over-loading.

---

## Requirements

- [BMad](https://github.com/bmad-co) installed in your project with the `bmm` module (provides Amelia, Winston, John)
- Claude Code CLI

---

## Installation

### 1. Copy the skill into your project

```bash
# Clone this repo
git clone https://github.com/alfaRazieL/Rust_bmad_dev.git

# Copy the skill into your project's Claude skills folder
cp -r Rust_bmad_dev/.claude/skills/rdx-setup YOUR_PROJECT/.claude/skills/
```

### 2. Run the setup skill

Open Claude Code in your project and run:

```
/rdx-setup
```

The skill will:
1. Register the `rdx` module in your `_bmad/config.yaml`
2. Copy KB section files to `_bmad/rust-kb/`
3. Create or merge agent overrides in `_bmad/custom/`
4. Register capabilities in `_bmad/module-help.csv`

### 3. Restart your agents

Close and reopen any active Amelia / Winston / John sessions. The new `persistent_facts` take effect on the next activation.

---

## Update

To update KB files to the latest version:

```bash
# Pull latest
git -C Rust_bmad_dev pull

# Re-copy the skill
cp -r Rust_bmad_dev/.claude/skills/rdx-setup YOUR_PROJECT/.claude/skills/

# Re-run setup (overwrites KB sections, skips already-merged overrides)
/rdx-setup
```

---

## How the Risk Router Works

Amelia loads §4 (core rules) and §5 (router table) on every activation. Before writing code for a story she runs through the router:

```
Story signal found?          → Load pack from section-6-packs.md
─────────────────────────────────────────────────────────────────
async fn / .await / spawn    → Async and concurrency pack
unsafe / raw pointers        → Unsafe and memory pack
extern / FFI / cdylib        → FFI and plugin ABI pack
macro_rules! / proc-macro    → Macros and build scripts pack
pub API / SemVer             → Public API pack
Cargo.toml changes           → Cargo / workspace pack
serde / untrusted input      → Data, security, I/O pack
database / migrations        → DB and distributed state pack
timeout / config reload      → Time and API clients pack
production service / tracing → Operations pack
hot path / no_std / WASM     → Performance and portability pack
No trigger matched           → Record "no conditional pack" and continue
```

Conditional packs are loaded on demand — Amelia never bloats her context with irrelevant rules.

---

## File Structure

```
.claude/skills/
├── rdx-setup/
│   ├── SKILL.md                        ← setup skill (self-registering)
│   ├── assets/
│   │   ├── module.yaml                 ← module identity (rdx v1.0.0)
│   │   ├── module-setup.md             ← config registration logic
│   │   ├── module-help.csv             ← capabilities for /bmad-help
│   │   ├── kb-sections/
│   │   │   ├── section-4-core.md       ← 18 CORE rules + KB meta-model
│   │   │   ├── section-5-router.md     ← Risk Router table
│   │   │   ├── section-6-packs.md      ← 12 conditional packs (~1400 lines)
│   │   │   └── section-8-governance.md ← governance rules
│   │   └── agent-overrides/
│   │       ├── bmad-agent-dev.toml     ← Amelia: core + router
│   │       ├── bmad-agent-architect.toml ← Winston: contracts + governance
│   │       └── bmad-agent-pm.toml      ← John: governance + grading
│   └── scripts/
│       ├── merge-config.py             ← writes to _bmad/config.yaml
│       └── merge-help-csv.py           ← writes to _bmad/module-help.csv
└── .claude-plugin/
    └── marketplace.json                ← BMad marketplace manifest
```

---

## License

MIT — see [LICENSE](LICENSE)
