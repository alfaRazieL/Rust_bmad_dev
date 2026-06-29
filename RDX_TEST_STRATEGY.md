# RDX Test Strategy — V5 → V6

**Status:** Authoritative test architecture for the `rdx-improvements` branch. Drives test-first development of Phase 1-10.
**Companion documents:** `RDX_TEST_TRACEABILITY_MATRIX.md`, `RDX_TEST_CASES.yaml`, `RDX_IMPLEMENTATION_PLAN_TESTED.md`, `RDX_TEST_DESIGN_REPORT.md`.

This document is the **why and how** of testing. The matrix and YAML are **what** specifically.

---

## 1. Principles

1. **Test before code.** Every Phase-1+ deliverable starts with the test that proves its acceptance criteria. Tests written after-the-fact are accepted only when they would have caught a real defect during development.
2. **Deterministic ≠ LLM judgment.** Layers L0–L4, L6–L7 must be reproducible (same inputs → same outputs). Layer L5 (behavioral evals) is non-deterministic by nature and is measured statistically with explicit thresholds.
3. **Authority over status.** The same status string from different sources is not equal. CI-rerun PASS overrides local PASS; specialist approval overrides Cat-3 verdict; Cat-1 verdict is immutable for evaluators.
4. **No self-attested PASS.** A Cat-1 PASS must have a command + exit code + output digest. LLM-written PASS without command evidence is invalid by schema.
5. **False positives erode trust.** Weak-signal packs (Ops, Perf claims) must require explicit story tags before they FAIL. A wrong block is a worse failure than a missed defect at this stage of the gate.
6. **Convention is documented as convention.** Wrapper-resume, on_complete hooks, and other LLM-cooperative mechanisms are tested as "best-effort soft gates" — not as hard enforcement.

---

## 2. Test Layers

| Layer | Name | What it proves | Determinism | Where it runs | Failure consequence |
|-------|------|----------------|-------------|---------------|---------------------|
| **L0** | Static contracts | JSON Schema, router mapping, rule-check mapping, status definitions, KB ↔ mapping drift | Full | Local + CI | Blocks merge of any change to schemas/mappings |
| **L1** | Deterministic unit | Individual functions: diff parser, digest, exception parser, status aggregator, baseline comparator | Full | Local + CI | Blocks merge |
| **L2** | Fixture tests | Per-pack positive + negative diff fixtures + ambiguous cases | Full | Local + CI | Blocks merge |
| **L3** | Real Rust project integration | Validator runs against actual Cargo crates (green, broken, workspace, async, unsafe, FFI, etc.) | Full (toolchain-pinned) | Local + CI | Blocks merge |
| **L4** | BMAD workflow integration | Menu override, wrapper→child→wrapper, setup/uninstall, customization preservation | Full (where script-based); LLM-cooperative where wrapper-resume | Local + CI for scripted parts; one-shot manual session for resume | Blocks Phase 3 completion |
| **L5** | BMAD behavioral evals | Via `bmad-eval-runner` — does Amelia actually consult Router? Does she hide NOT_RUN? Does she falsely PASS? | **Statistical** (multi-run with thresholds) | Local + scheduled | Blocks release if pass rate < threshold |
| **L6** | Hook + CI end-to-end | Pre-push really blocks, required check really blocks, fork PR safety, secrets handling | Full | Real GitHub repo (sample) | Blocks Phase 5 completion |
| **L7** | Security / mutation / adversarial | Bypass attempts: fake PASS, stale diff, modified validator, deleted test, approval reuse | Full | Local + CI | Blocks release |
| **L8** | V6 judgment + governance | Cat-3 evaluator scoping, false-positive rate, Cat-4 approval binding, governance artifact protection | Mixed (some statistical, some deterministic) | Local + CI | Blocks V6 release |

### Determinism precision

- **Full**: same inputs → identical outputs across runs (modulo timestamps written to evidence).
- **Statistical**: variance expected; assess with N≥10 runs and acceptance thresholds.
- **Toolchain-pinned**: deterministic given a pinned cargo/rustc version. CI must pin or accept flake budget.

---

## 3. Phase Gates (entry / exit)

Each implementation phase has an entry gate (tests that must exist before code) and an exit gate (tests that must pass to mark phase done).

| Phase | Entry gate (tests written first) | Exit gate (tests must pass) | Release impact |
|-------|----------------------------------|------------------------------|----------------|
| **Phase 1 — Contracts** | L0 contract specs exist; YAML test cases for evidence schema authored | All L0 contract tests pass; KB↔mapping drift check runs in CI | Blocks Phase 2 |
| **Phase 2 — Validator** | L1 unit specs + L2 fixture set authored; failing-by-design tests committed | All L1/L2 pass; L3 green-crate baseline passes | Blocks Phase 3 |
| **Phase 3 — Wrapper** | L4 menu override + wrapper-resume scenarios authored as test cases | L4 scripted parts green; L5 happy-path eval pass rate ≥ 85% | Blocks Phase 4 |
| **Phase 4 — Modes** | Per-mode acceptance test specs written | All mode acceptance tests pass | Blocks Phase 5 |
| **Phase 5 — Hook + CI** | L6 end-to-end fixture repo prepared; bypass tests authored | L6 pre-push blocks; L6 CI required check blocks; L7 trust-model tests pass | Blocks V5 release |
| **Phase 6 — Evals & regression** | L5 eval suite assembled; L7 mutation suite assembled | L5 ≥ stated thresholds; L7 catches all listed bypasses | V5 release gate |
| **Phase 7 — RDX Rule Auditor** | L8 Cat-3 scoping tests written | L8 evaluator only sees active packs; false-positive ≤ threshold | Blocks Phase 8 |
| **Phase 8 — Cat-4 approvals** | L8 approval binding tests authored | Diff-mismatched approvals rejected; CODEOWNERS routes match | V6 release gate |
| **Phase 9 — High Assurance** | L7 hardening suite authored | All hardening adversarial tests pass | Release for HA-claiming projects |
| **Phase 10 — Docs** | Doc-review checklist | Doc spot-check tests pass | Publication |

---

## 4. Test Environments

| Environment | Purpose | When |
|-------------|---------|------|
| **Local developer (Python 3.11+, git, cargo)** | L0, L1, L2, L3 quick loop; L4 scripted parts | Every change |
| **Synthetic Cargo fixtures** | L3 integration | Reused across CI |
| **One-shot Claude Code session (manual)** | L4 wrapper-resume; L5 small evals; L8 evaluator consistency | Phase 3 entry gate; Phase 7 |
| **`bmad-eval-runner` orchestrated** | L5 batch behavioral evals | Phase 6, scheduled regression |
| **GitHub-hosted sample repo with PRs** | L6 + L7 | Phase 5, V5 release gate |
| **Tampered-validator harness** | L7 mutation tests | Phase 5 + release |
| **CI matrix runners (macOS/Linux/Windows)** | Compatibility | Phase 4 + release |

---

## 5. Status Taxonomy (final, normative)

The previous plan ambiguously listed "15 statuses" with 14 entries plus an undefined `WARNING`. This is now the canonical set:

### 5.1 Verdict statuses (per rule)

| Status | Meaning | Set by | Blocking in modes |
|--------|---------|--------|-------------------|
| `PASS` | Tool/check confirmed compliant | Validator (Cat 1/2), Evaluator (Cat 3 only), Specialist (Cat 4 only) | No |
| `FAIL` | Tool/check confirmed violation, no valid exception | Same as PASS | Always |
| `NOT_APPLICABLE` | Trigger absent (router didn't activate) — no check needed | Validator | No |
| `NOT_RUN` | Tool unavailable; structured reason recorded | Validator | Blocking in Mode 2+ unless reason is on approved list (e.g., `cargo audit` offline) |
| `EVIDENCE_REQUIRED` | Signal detected; evidence absent or insufficient | Validator | Blocking in Mode 2+ |
| `REVIEW_REQUIRED` | Cat-3 rule needs evaluator pass | Validator | Blocking in Mode 4 (CI may proceed in Mode 3 with informational note) |
| `APPROVAL_REQUIRED` | Cat-4 rule needs specialist sign-off | Validator | Always blocking; pinned to `diff_digest` |
| `BASELINE_FAILURE_OBSERVED` | Same error signature on base and head; story not at fault | Validator (dual-run) | No (informational) |
| `BASELINE_BLOCKS_VALIDATION` | Base failure prevents meaningful head check | Validator (dual-run) | Conditional — override path: rebase, or story-owner authorization |
| `REGRESSION_FAILURE` | Base passed; head fails OR head fails with new signature | Validator (dual-run) | Always |
| `REGRESSION_FIXED` | Base failed; head passes | Validator (dual-run) | No (bonus credit) |
| `ENVIRONMENT_UNAVAILABLE` | Cannot run validator at all (no Python, no git) | Validator self-detected | Blocking in Mode 2+; downgrade to Mode 0 + report |
| `TOOL_UNAVAILABLE` | Specific tool missing (Miri, cargo-audit) but core ran | Validator | Conditional per project policy |
| `BLOCKED` | Aggregate flag — at least one blocking finding present | Validator orchestrator | Always |

### 5.2 Severities (finding-level, orthogonal to verdict)

| Severity | When used |
|----------|-----------|
| `INFO` | Informational; never blocks |
| `WARNING` | Non-blocking advice (e.g., CORE-008 `.unwrap()` without `panic-discipline` story tag) |
| `BLOCKING` | Drives FAIL verdict |

**WARNING is a severity, not a verdict.** A check can have `verdict: PASS, severity: WARNING` (informational hit) or `verdict: FAIL, severity: BLOCKING`. This resolves the prior ambiguity.

### 5.3 Exit code mapping (stable contract)

| Exit code | Meaning |
|-----------|---------|
| 0 | All verdicts: PASS / NOT_APPLICABLE / REGRESSION_FIXED |
| 1 | At least one FAIL or REGRESSION_FAILURE |
| 2 | ENVIRONMENT_UNAVAILABLE — validator could not run |
| 3 | At least one BLOCKED or BASELINE_BLOCKS_VALIDATION or APPROVAL_REQUIRED or EVIDENCE_REQUIRED (and no exit-1 reason) |
| 4 | At least one REVIEW_REQUIRED (and no exit-1/2/3 reason) — informational in Mode 3, blocking in Mode 4 |

Callers (hook / CI) map exit codes to enforcement actions per mode policy.

### 5.4 State transitions (per rule, during processing)

```
[initial detection]
       │
       ▼
NOT_APPLICABLE ──── (trigger absent)
       │
       ▼
EVIDENCE_REQUIRED ─── (signal present, no evidence) ──────────► FAIL (in Mode 2+, after grace)
       │
       ▼
APPLICABLE ──── (signal + evidence present)
       │
       ▼
   [Cat 1/2 deterministic check]
       │
       ├──► PASS              (verdict authoritative)
       ├──► FAIL              (BLOCKING)
       ├──► NOT_RUN           (with reason)
       └──► BASELINE_*        (dual-run path)

   [Cat 3 path]
       │
       ▼
REVIEW_REQUIRED ──── (evaluator runs)
       │
       ├──► PASS  (set by evaluator only)
       ├──► FAIL  (set by evaluator only)
       └──► INSUFFICIENT_EVIDENCE — kicks back to LLM/author

   [Cat 4 path]
       │
       ▼
APPROVAL_REQUIRED ──── (specialist signs)
       │
       ├──► PASS  (set by specialist; pinned to diff_digest)
       └──► [diff change] ──► back to APPROVAL_REQUIRED (approval invalidated)
```

---

## 6. Metrics & Acceptance Thresholds

| Metric | Target for V5 release | Measurement |
|--------|----------------------|-------------|
| L0/L1/L2 unit branch coverage | ≥ 85% of validator code | `coverage.py` |
| L2 fixture coverage per pack | ≥ 1 strong-positive, ≥ 1 strong-negative, ≥ 1 doc-only-negative per pack with auto-activation | Manual review of fixture set |
| L2 false-positive rate | ≤ 5% across fixture set | Inverse of `correctly-negative / total-negatives` |
| L2 false-negative rate | ≤ 2% across fixture set | Inverse of `correctly-positive / total-positives` |
| L3 integration green-crate PASS | 100% (3 consecutive runs) | CI cargo cache pinned |
| L4 menu override correctness | 100% (deterministic, no flake) | Script-based |
| L4 wrapper-resume reliability | ≥ 90% over N=20 sessions | Manual + telemetry-style log of test sessions |
| L5 router-not-skipped eval | ≥ 90% pass rate over N=20 runs | bmad-eval-runner |
| L5 self-attested-PASS-rejected eval | 100% (must never accept) | bmad-eval-runner |
| L6 pre-push blocks invalid evidence | 100% | Sample repo |
| L6 CI required check blocks invalid PR | 100% | Sample repo |
| L7 bypass tests all caught | 100% | Each listed bypass has a test |
| L7 flake rate | ≤ 1% per gate | Tracked over rolling 30-day window |
| Execution time L0+L1+L2 locally | ≤ 30s | `pytest --duration=30` |
| Execution time L3 locally | ≤ 5 min cold; ≤ 60s cargo-cached | Manual |
| Execution time full L0–L7 in CI | ≤ 15 min | GitHub Actions timing |
| Supported Python | 3.11, 3.12, 3.13 | matrix |
| Supported Rust | stable + N–1 MSRV | matrix |
| Supported BMAD resolver | known SHA pinned in `rdx-setup` | health check |

---

## 7. Trusted CI Model

PR submitters can modify any file in the PR — including the validator itself. Naive CI that runs the PR's `rdx-validator/scripts/run-all.py` lets attackers weaken the gate.

**The CI workflow must source the validator from outside the PR.** Options compared:

| Option | Source of validator code | Tamper resistance | Complexity |
|--------|--------------------------|--------------------|------------|
| A — PR head | Use the PR's own files | None | Trivial |
| B — Target/base branch | Validator from `main`/PR base | Strong (PR can't change main) | Low (just `git checkout base -- scripts/`) |
| **C — Pinned RDX release** | Validator from a tagged release pulled fresh | **Strongest** (immutable tag) | Medium (release management) |
| D — Reusable workflow from trusted repo | `uses: alfaRazieL/Rust_bmad_dev/.github/workflows/validate.yml@v1` | Strong (workflow ref is pinned) | Medium (depends on cross-repo permissions for fork PRs) |

**Recommended for V5: Option B** initially (validator from `main`, recomputed on every PR), **migrate to Option C** when a stable RDX release exists. Option D is best long-term but adds friction for first release.

L7 adversarial test cases include:
- PR modifies `rdx-validator/scripts/check_protected_files.py` to always PASS → CI loads validator from `main` → still detects boundary violation → block
- PR modifies `router-rules.json` to drop the `unsafe` pack → CI loads mapping from `main` → still activates pack → block
- PR modifies `.github/workflows/rdx-gate.yml` itself → CI uses workflow from PR base, not head → block

---

## 8. R1 vs R2 — Code Review Integration Decision

The Phase 0.2 spike found two viable integration patterns for adding `rdx-judgment` (Cat-3 layer) into `bmad-code-review`:

### Variant R1 — `on_complete` post-pass
Customize `_bmad/custom/bmad-code-review.toml` with an `on_complete` hook that invokes `rdx-judgment` after the standard review completes.

- ✓ Zero modification of step files
- ✓ Pure customization, BMAD-native
- ✗ Timing: fires **after** triage finalization and story status update. RDX findings cannot influence the standard review's verdict.
- ✗ Reverting story state from "review" back to "in-progress" is structurally awkward.
- ✗ on_complete is convention (LLM-cooperative); same enforcement class as wrapper.

### Variant R2 — `rdx-code-review` wrapper
RDX overrides `agent.menu[code=CR].skill = "rdx-code-review"`. Wrapper calls `bmad-code-review` as a child skill, captures findings, runs RDX Rule Auditor, applies unified finalization.

- ✓ Same proven pattern as `rdx-dev-story` wrapper (Phase 0.1 verified)
- ✓ RDX Rule Auditor runs **before** triage finalization → can influence final verdict
- ✓ Unified status decision (no race between standard review and RDX)
- ✓ Same menu-override mechanism (zero BMAD core change)
- ✗ Adds one more wrapper skill (and an integration test surface)
- ✗ Wrapper is still LLM-cooperative — but matches the enforcement class users already accept for DS

### **Decision: R2 (wrapper), DOC VERIFIED + INFERENCE**

Rationale: R2's timing properties matter more than R1's setup simplicity. A Cat-3 finding that arrives *after* story status update is a finding too late. The proven Phase 0.1 pattern carries over directly.

R2 will be empirically validated in Phase 7 entry-gate (test ID `T-L4-CR-001` per the YAML catalog). Until then, status is **DOC VERIFIED + INFERENCE**, matching the Spike 0.1 wrapper-resume status before its empirical close.

Fallback if R2 fails in Phase 7: revert to R1, accept the timing limitation, document that Cat-3 findings are advisory unless CI re-runs the auditor on the PR.

---

## 9. Phase 0 Corrections (carried into tested plan)

Three Phase 0 items were marked complete without sufficient evidence:

| Item | Original status | Corrected status | Reason |
|------|-----------------|-------------------|--------|
| 0.1 — "Поведение при context pressure" | `[x]` | `[ ]` (pending) | No test was actually run for long-context behavior. Marked pending until L5 eval `T-L5-CTX-001` runs. |
| 0.1 — "child с неполным результатом → wrapper detects" | `[x]` | `[~]` (partial) | Spike covered "child errored" only via validator-stub FAIL; did not cover "child completed but didn't produce expected artifact". Test ID `T-L4-WR-005` reopens this. |
| 0.2 — overall | `EXPERIMENT VERIFIED`-adjacent | `DOC VERIFIED` only | No experiment was run; recipe was inferred from `bmad-code-review` source. Empirical close requires `T-L4-CR-001` (R2 wrapper test) or `T-L4-CR-002` (R1 on_complete test) in Phase 7. |

Tracking: see `RDX_TEST_CASES.yaml` entries `T-L4-WR-005`, `T-L5-CTX-001`, `T-L4-CR-001`, `T-L4-CR-002`. The corrected plan (`RDX_IMPLEMENTATION_PLAN_TESTED.md`) reflects these.

---

## 10. Flaky-Test Policy

L5 (behavioral evals) is statistical by nature. Flake budget:

- **Hard flake** (test fails sometimes, passes others, same inputs): not allowed in L0–L3. Investigate immediately.
- **Statistical flake** (L5): acceptable up to thresholds in §6. Track over 30-day window.
- **Environment flake** (L3 `cargo` cache miss, network blip): acceptable; mark `NOT_RUN` with reason. Don't retry indefinitely.
- **L4 wrapper-resume flake**: budget 2 of 20 sessions. >2 means architectural problem, not test problem.

Any L0–L4/L6–L7 test that flakes is blocked from being release-gating until stabilized. The release process cannot consume known flaky tests.

---

## 11. Ownership

| Test layer | Owner | Reviewer |
|------------|-------|----------|
| L0 contracts | Schema/mapping author | Architect |
| L1/L2 unit/fixture | Validator developer | Cat-1/2 rule author |
| L3 integration | Validator developer | Architect |
| L4 BMAD integration | Wrapper developer | BMAD integration reviewer |
| L5 evals | Eval owner | Architect |
| L6 CI/hook | DevOps/release engineer | Architect |
| L7 security | Security reviewer | Architect |
| L8 V6 judgment | Cat-3 evaluator author | Cat-3 rule author |

For a solo project, the role columns collapse but the conceptual separation drives the review checklist: did the test author and the rule author confirm the test reflects the rule?

---

## 12. Test Artifact Structure

```
tests/
├── contracts/                # L0
│   ├── schemas/              #   JSON Schema files (canonical)
│   └── golden/               #   golden snapshots of router-rules.json
├── unit/                     # L1
│   └── validator/            #   pytest module per source file
├── fixtures/                 # L2 inputs
│   ├── diffs/                #   one .diff per case (named per pack and signal)
│   ├── cargo-projects/       # L3 inputs — minimal Cargo crates
│   ├── stories/              # L4 inputs — synthetic story files
│   ├── evidence/             # L1/L2/L7 inputs — synthetic evidence.json
│   └── approvals/            # L8 inputs — synthetic approval trails
├── integration/              # L3
│   └── cargo/                #   driver scripts that run validator on each fixture
├── bmad/                     # L4
│   ├── menu-override/        #   scripted test of resolver merge
│   ├── wrapper-resume/       #   one-shot session protocols (manual)
│   └── setup-uninstall/      #   driver scripts
├── evals/                    # L5
│   └── (managed by bmad-eval-runner)
├── ci/                       # L6
│   ├── sample-repo-spec.md   #   how the sample repo is constructed
│   └── trusted-source-tests/ #   adversarial: validator from PR vs from main
├── mutation/                 # L7
│   ├── fake-pass/
│   ├── stale-diff/
│   ├── deleted-test/
│   └── approval-reuse/
├── compatibility/            # cross-cutting
│   └── matrix.md             #   OS × Python × Rust × BMAD versions
└── acceptance/               # release gates
    ├── v5-acceptance.md
    └── v6-acceptance.md
```

Files in `tests/fixtures/` carry their expected verdict in the filename or a sibling `.expected.json`. Tests must not invent expected outputs — they live alongside the fixture.

---

## 13. Execution Order

For a developer starting Phase 1:

```
1. Open RDX_TEST_CASES.yaml; filter to phase=1
2. Write the L0 contract specs (schemas, mappings) FIRST
3. Commit the contracts + their failing tests (red phase)
4. Implement the schema/mapping definitions to make the tests pass (green phase)
5. Refactor if needed (green stays green)
6. Move to Phase 2 only after exit gate tests in §3 pass
```

For CI:

```
On every PR:
  L0 contract checks                # < 5 s
  L1 unit tests                     # < 20 s
  L2 fixture tests                  # < 30 s
  L3 integration (cached)           # < 90 s
  L4 scripted bits                  # < 30 s
  L7 mutation suite (subset)        # < 60 s
  Total target: ≤ 5 min on cached CI

Scheduled (nightly or weekly):
  L5 behavioral evals               # heavyweight, multi-run
  L7 full mutation suite
  L3 cold (no cache) timing budget verification

On release tag:
  Full L0–L8 plus acceptance suites
```

---

## 14. What This Strategy Does Not Cover

- **Production hardening of `rdx-validator`** — that's Phase 2 implementation, not test strategy.
- **Specific eval prompts** — owned by `RDX_TEST_CASES.yaml` entries with `layer: L5`.
- **CI pipeline implementation** — Phase 5 deliverable; test cases for it are in the YAML.
- **Documentation review checklists** — Phase 10 deliverable.
- **Performance optimization targets** — defer until V5 ships and real workloads exist.

---

## 15. Open Questions (track separately)

- BMAD resolver stability: file upstream issue on `bmad-code-org/BMAD-METHOD` after V5 release.
- HMAC necessity: revisit when first real abuse vector emerges.
- GitLab/Bitbucket templates: defer until at least one user requests.
- Codex/Cursor `AGENTS.md` packaging: V7 spin-off, post-V6.

---

## Appendix A — Layer-to-Phase Quick Reference

| Phase | Primary layers exercised | Secondary |
|-------|--------------------------|-----------|
| 1 — Contracts | L0 | — |
| 2 — Validator | L1, L2 | L3 (smoke) |
| 3 — Wrapper | L4 | L5 (small) |
| 4 — Modes | L4 acceptance | L7 (mode bypass) |
| 5 — Hook + CI | L6, L7 | L4 |
| 6 — Evals/regression | L5, L7 full | All others as smoke |
| 7 — Rule Auditor | L8 | L5 |
| 8 — Cat-4 approvals | L8 | L7 |
| 9 — High Assurance | L7 hardening | L8 |
| 10 — Docs | doc tests | — |
