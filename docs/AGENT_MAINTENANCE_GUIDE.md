# RDX Agent Maintenance Guide

**Audience:** AI agents (Claude Code, Codex CLI, others) and human maintainers extending RDX after the 1.1 release.

**What this is:** the *living* reference for how RDX is organised and how to safely change it. Everything you need to add a check, expand the router, ship a new mode, or maintain the test suite is here.

**What this is not:** a rebuild of the historical planning documents. Those are frozen at [`../archive-docs-dev/`](../archive-docs-dev/) — read them only for "why was this decided that way in 1.1".

---

## 1. Ten non-negotiable principles

Any patch that violates one of these must be reverted before merge.

1. **Test-first.** Write a failing test, then make it pass. Never commit production code without a matching test.
2. **No "hard enforcement" claim for the wrapper.** Wrapper (`rdx-dev-story`, `rdx-code-review`) is a *soft* gate — an LLM-cooperative UX layer. Hard enforcement lives only in git hooks and CI.
3. **Status taxonomy is locked.** 14 verdicts + 3 severities. `WARNING` is a severity, not a verdict. See `tests/contracts/status-definitions.json`.
4. **LLM never sets a Cat-1 PASS.** The evidence schema rejects a Cat-1 PASS without a matching command+exit-code+output-digest. See `tests/contracts/schemas/rdx-evidence.v1.schema.json`.
5. **R2 is the primary Code-Review integration.** R1 (on_complete) ships as a documented fallback with an explicit timing-limitation comment.
6. **CI loads validator from BASE branch, not PR head.** This is the tamper-resistance contract from `RDX_TEST_STRATEGY.md` §7 (Option B). See `.github/workflows/rdx-gate.yml` and `.github/scripts/rdx-ci-runner.py`.
7. **Do not fork BMAD core.** All BMAD integration happens through `_bmad/custom/` overrides and `agent.menu` merge-by-`code` replacement.
8. **No HMAC in v6.** See `docs/threat-model.md` §7. Add signed attestations only when a real bypass proves CI re-run is circumventable.
9. **Weak-signal packs (Ops, Perf claims, etc.) do not block without an explicit story tag.** See `tests/contracts/router-rules.json` activation classes.
10. **Never touch `rdx-setup` production code without a plan.** This is the module's public installer and any regression breaks every existing user's project.

---

## 2. Repository map

```
Rust_bmad_dev/                             ← repo root
├── README.md                              ← user-facing: what RDX is, how to install, modes, CI cost
├── LICENSE
├── CHANGELOG.md                           ← every user-visible change per release
├── .gitignore
│
├── .claude/                               ← Claude Code skill installation surface
│   ├── skills/
│   │   ├── rdx-setup/                     ← installer + mode selection + sync-codeowners
│   │   ├── rdx-dev-story/                 ← Mode 1 wrapper around bmad-dev-story
│   │   ├── rdx-code-review/               ← Mode 4 R2 wrapper around bmad-code-review
│   │   ├── rdx-judgment/                  ← Cat-3 LLM evaluator (invoked by rdx-code-review)
│   │   └── rdx-hooks/                     ← pre-push hook installer for Mode 2
│   └── .claude-plugin/marketplace.json    ← BMAD marketplace manifest (bump version here on release)
│
├── rdx-validator/                         ← standalone Python package (BMAD-independent)
│   ├── README.md
│   └── rdx_validator/
│       ├── cli.py                         ← argparse entry point (`python -m rdx_validator ...`)
│       ├── checks/                        ← Cat-1 check implementations (one file per rule ID)
│       ├── evals/                         ← Cat-3 eval harness (statistical rubrics)
│       ├── approvers.py                   ← Cat-4 approver lookup (A3 hybrid)
│       ├── status.py                      ← status taxonomy + exit code mapping
│       └── judgment.py                    ← helpers consumed by bmad-eval-runner
│
├── _bmad/                                 ← runtime configuration surface (per-user project data)
│   └── rdx/
│       ├── approval.v1.schema.json        ← Cat-4 approval envelope schema (B1)
│       ├── approvers.schema.json          ← A3 approvers.yaml schema
│       └── approvers.yaml.example         ← template shipped for user projects
│
├── docs/                                  ← living user + agent documentation
│   ├── AGENT_MAINTENANCE_GUIDE.md         ← THIS FILE
│   ├── branch-protection.md               ← Mode 3+4 required-check setup
│   ├── threat-model.md                    ← Phase 9 formal threat model + §8 triggers-to-revisit
│   └── doc-review-checklist.md            ← run before each release
│
├── .github/
│   ├── scripts/
│   │   └── rdx-ci-runner.py               ← Option B loader — pulls validator from BASE branch
│   └── workflows/
│       ├── rdx-gate.yml                   ← ONLY workflow users copy to their own projects
│       └── rdx-l0..rdx-l8/rdx-full-regression/rdx-compat-matrix/rdx-docs.yml
│                                          ← internal CI for this repo (see §5.4 below)
│
├── tests/                                 ← 307 tests, 12 subdirectories, see §5
│
└── archive-docs-dev/                      ← frozen at 1.1 release. Read-only history.
    ├── README.md                          ← inventory of the archive
    ├── planning/                          ← pre-1.1 research + verification
    ├── test-design/                       ← test strategy + traceability + full YAML catalog
    ├── implementation-plans/              ← frozen original + completed working plan
    ├── phase-runner/                      ← template for future release cycles
    └── spikes/                            ← Phase 0 empirical proofs
```

---

## 3. The Cat-1 / Cat-2 / Cat-3 / Cat-4 framework

This is *the* load-bearing taxonomy. Every rule you add or change lives at exactly one category.

| Cat | Name | Verdict reached by | PASS authority | Enforcement layer |
|-----|------|--------------------|----------------|-------------------|
| Cat-1 | Deterministic | An executed command with exit code + output digest (e.g. `cargo check`, `clippy`, regex over diff) | Validator only — schema rejects LLM-set Cat-1 PASS | Validator + CI recomputation |
| Cat-2 | Evidence verification | Validator checks that supplied evidence matches the diff | Validator | Validator + CI recomputation |
| Cat-3 | Judgment review | `rdx-judgment` reviews scoped findings | LLM (only for its own Cat-3 verdicts — never Cat-1 or Cat-4) | Wrapper + human review of the LLM output |
| Cat-4 | Specialist approval | Named role member signs an approval JSON pinned to the diff | Approver (via `_bmad/rdx/approvers.yaml`), recorded in `_bmad/rdx/approvals/<diff_digest>.json` | CI recomputes approver identity + diff_digest match |

**Rule of thumb for deciding category:**

- Can a Python function inspect the diff/evidence and return PASS/FAIL with zero LLM interpretation? → **Cat-1**.
- Is the LLM providing evidence and we only check that it's structurally there? → **Cat-2**.
- Does correctness require reading code and reasoning about intent? → **Cat-3**.
- Does correctness require a *named human* (or role) to say "yes I looked at this and approve"? → **Cat-4**.

Add a rule to `tests/contracts/rule-check-map.json` at the correct category. The drift-check in CI will fail if a rule is in the KB but not the map, or vice versa.

---

## 4. How to add …

### 4.1 A new Cat-1 check

1. **Pick a rule ID.** Use the KB convention: `CORE-NNN` for core rules, `RP-<PACK>-NNN` for pack rules. Confirm it doesn't exist yet with the drift-check.
2. **Add a YAML entry** in `archive-docs-dev/test-design/RDX_TEST_CASES.yaml` (yes, we still catalogue test IDs there — the two mutation tests that read this file use it as the bypass-class catalogue). Follow the existing schema.
3. **Author fixtures** under `tests/fixtures/diffs/<pack>/` with sibling `.expected.json` files.
4. **Write the test** under `tests/unit/validator/` or `tests/integration/` depending on scope. Run pytest — should fail (red).
5. **Implement the check** in `rdx-validator/rdx_validator/checks/`. One file per rule where practical. Return `CheckResult` with `verdict`, `severity`, optional `evidence`.
6. **Wire the check** into `rdx-validator/rdx_validator/cli.py`'s check registry so `python -m rdx_validator validate` runs it.
7. **Verify.** Run pytest — should pass (green). Run L0 drift-check — should still pass.
8. Commit with `feat(check): CORE-NNN <description>` — see §7 for full commit style.

### 4.2 A new pack in the Risk Router

1. **Add a KB section.** Update `_bmad/rust-kb/section-5-router.md` (activation triggers) and `_bmad/rust-kb/section-6-packs.md` (rule bodies). Follow the existing table format.
2. **Add the pack** to `tests/contracts/router-rules.json` with:
   - `positive_signals` (regexes over added lines)
   - `path_signals` (regexes over changed paths)
   - `negative_signals` (comment-only exclusions)
   - `activation_policy`: one of `AUTO_ACTIVATE`, `AUTO_SUGGEST`, `STORY_TAG_REQUIRED`, `REVIEW_REQUIRED`
3. **Add positive + negative fixtures** under `tests/fixtures/diffs/<pack>/`.
4. **Run the drift check** — it must confirm KB and JSON are in sync.

**Do not** default new weak-signal packs to `AUTO_ACTIVATE`. Use `STORY_TAG_REQUIRED` unless the signal is unambiguous (like `unsafe {` or a new `Cargo.toml`).

### 4.3 A new operating mode

If you're adding Mode 5 or a variant, remember every mode must answer:

1. What runs? (validator? wrapper? hook? CI?)
2. Where does enforcement live? (nowhere, dev machine, CI, human)
3. What is the documented bypass?
4. Does the validator stamp the mode label in every evidence envelope? (Yes — see `rdx-validator/rdx_validator/status.py`.)

Update `.claude/skills/rdx-setup/assets/modes.md` (the single source of truth for mode names — checked by the L4 `test_mode_naming` test).

Do NOT introduce a mode that claims enforcement it can't provide. That trips `test_doc_honesty.py` (T-V5-ACC-06).

### 4.4 A new Cat-3 rule

1. Add the rule to the KB.
2. Add the rule ID to `rdx-validator/rdx_validator/evals/` scope tables — this is what `filter_active_scope` reads to decide which rules go to the evaluator for a given active-pack set.
3. Add an eval fixture under `tests/fixtures/cat3-cases/`.
4. Reference it in `rdx-judgment` SKILL.md's rubric section only if the rule needs a special instruction beyond the shared rubric.

### 4.5 A new Cat-4 category

1. Add a pattern → role → identities entry to `_bmad/rdx/approvers.yaml.example`.
2. Update `.claude/skills/rdx-setup/scripts/sync_codeowners.py` if the new category needs a special CODEOWNERS render path.
3. Add a fixture under `tests/fixtures/approvers/` covering both authorised and unauthorised cases.
4. Add coverage in `tests/integration/cat4/`.

---

## 5. Test suite anatomy

### 5.1 Layers (per `RDX_TEST_STRATEGY.md` in archive)

- **L0** — static contracts (schemas, mappings, drift)
- **L1** — deterministic unit
- **L2** — fixture-based per pack / per CORE rule
- **L3** — real Cargo project integration
- **L4** — BMAD workflow integration (menu override, wrapper, code review)
- **L5** — behavioral evals (statistical, via `bmad-eval-runner`)
- **L6** — hook + CI end-to-end
- **L7** — security / mutation / adversarial
- **L8** — V6 Cat-3 + Cat-4 governance

### 5.2 Directory layout

```
tests/
├── contracts/          ← L0. Schemas, mappings, drift-check.
├── unit/validator/     ← L1.
├── integration/        ← L3 (cargo/) + L8 (cat4/).
├── bmad/               ← L4. menu-override/, wrapper-resume/, setup-uninstall/, modes/, code-review/.
├── ci/                 ← L6. sample-repo-hook/, sample-github-repo/, trusted-source-tests/, baseline-regression/.
├── mutation/           ← L7. One folder per bypass class + a full-suite driver.
├── acceptance/         ← V5/V6 release-gate black-box tests.
├── evals/              ← L5.
├── compatibility/      ← cross-OS × Python × BMAD matrix.
├── docs/               ← Phase 10: README + docs structural tests.
└── fixtures/           ← inputs for all layers.
```

### 5.3 Running tests locally

```bash
python -m pytest -q                                    # full suite (~15 s)
python -m pytest tests/contracts -q                    # just L0
python -m pytest tests/unit -q                         # just L1
python -m pytest -k "cat4" -q                          # by keyword
python -m pytest -q --lf                               # only last-failed
python -m pytest -q --tb=short tests/mutation          # L7 detail on failure
```

Coverage:
```bash
python -m pytest --cov=rdx_validator --cov-report=term-missing
```

### 5.4 The CI workflows

There are two categories in `.github/workflows/`. **Do not delete internal ones — they gate every PR against this repo.**

| Workflow | Category | What it does |
|----------|----------|--------------|
| `rdx-gate.yml` | **user-facing template** | The workflow users copy into their own Rust project. Loads validator from PR base branch (Option B). |
| `rdx-l0-contracts.yml` | internal | L0 schema + drift on every PR. |
| `rdx-l1-l3-validator.yml` | internal | L1 + L2 + L3 on the validator. |
| `rdx-l4-bmad-integration.yml` | internal | L4 wrapper / menu-override tests. |
| `rdx-l4-modes.yml` | internal | L4 mode selector + mode naming. |
| `rdx-l4-l8-judgment.yml` | internal | L4 code-review + L8 judgment. |
| `rdx-l6-l7.yml` | internal | L6 CI/hook + L7 mutation. |
| `rdx-l8-cat4.yml` | internal | L8 Cat-4 approval integration. |
| `rdx-full-regression.yml` | internal | Full 307-test suite, scheduled nightly. |
| `rdx-compat-matrix.yml` | internal | Python 3.11/3.12/3.13 × OS matrix. |
| `rdx-docs.yml` | internal | Phase 10 doc structural tests. |

---

## 6. Release checklist for 1.2+

When you're ready to ship 1.2:

1. **Create a new working plan** — take `archive-docs-dev/implementation-plans/RDX_IMPLEMENTATION_PLAN_TESTED.md` as the template. Save the new plan somewhere living (e.g., `docs/plans/RDX_1_2_PLAN.md`).
2. **Cut a feature branch** off `main` (`git checkout -b rdx-1.2-improvements`).
3. **Reuse the phase runner** — copy `archive-docs-dev/phase-runner/PHASE_RUNNER_PROMPT.md` into your session context, replace `{PHASE}` per phase, update the "readings" section if any new documents were added.
4. **Run every phase in a fresh context window.** The prompt already documents the discipline (test-first, no principle violations, clear commit prefixes, categorised final report).
5. **Before merge to main:**
   - All 307 (or more) tests green
   - `docs/threat-model.md` §8 triggers reviewed for hits
   - `docs/doc-review-checklist.md` walked
   - README updated with new mode/features
   - CHANGELOG bumped
   - `marketplace.json` version bumped
6. **Squash merge to main** with commit message `RDX 1.2 release: <headline features>`.

---

## 7. Commit style used through 1.1

Use these prefixes on commits and the test-first convention becomes visible in `git log`:

- `test: Phase N <topic> (red)` — new tests, expected to fail against unimplemented code
- `feat: Phase N — <topic> complete (green)` — implementation making the red tests pass
- `feat(check): CORE-NNN <description>` — single new Cat-1 check outside a phase
- `docs(<area>): <what changed>` — documentation-only
- `chore(<area>): <what>` — housekeeping (moves, renames, dependency bumps)
- `fix(<area>): <what>` — bug fix

Every implementation commit must reference the test IDs it closes in the body.

---

## 8. Where to look when stuck

| Question | Look here |
|----------|-----------|
| Why is Cat-1 PASS schema-enforced? | `docs/threat-model.md` §7 + `RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md` (archive) |
| What does status X mean and does it block? | `tests/contracts/status-definitions.json` |
| Which rule is Cat-1/2/3/4? | `tests/contracts/rule-check-map.json` |
| What does the router activate for signal X? | `tests/contracts/router-rules.json` |
| How does mode X enforce? | `.claude/skills/rdx-setup/assets/modes.md` + `docs/threat-model.md` §5 |
| Why does CI load from base, not PR head? | `docs/threat-model.md` §6 + trust model section of README |
| Why was R2 chosen over R1 for Code Review? | `RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md` §8 (archive) + `docs/threat-model.md` |
| How do I add a test / fixture / check? | §4 above |
| I need the full 1.1 test catalogue | `archive-docs-dev/test-design/RDX_TEST_CASES.yaml` |
| I need the reasoning for a Phase-N design decision | `archive-docs-dev/implementation-plans/RDX_IMPLEMENTATION_PLAN_TESTED.md` (search by phase) |

---

## 9. What to never do

- Never edit `archive-docs-dev/` files — that folder is a frozen historical record. Add new docs to `docs/` instead.
- Never bypass the drift check when adding a rule to the KB. If the check fails, add the mapping entry — do not disable the check.
- Never let a `--no-verify` bypass become the norm in your workflow. It is a documented emergency escape hatch, not a habit.
- Never call the wrapper "enforcement" in user-facing docs. `test_doc_honesty.py` will fail on you.
- Never add HMAC without a documented threat-model trigger firing (see `docs/threat-model.md` §8).
- Never fork BMAD core to hack in an integration. Use `_bmad/custom/` overrides. If overrides can't express what you need, escalate — do not silently fork.
