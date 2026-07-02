# RDX Validator Gate — Technical Architecture Report

All claims verified against live BMAD code (`/Users/m33tball/bmad_module_builder/.claude/skills/`), the `bmad-code-org` GitHub org (BMAD-METHOD v6.9.0, bmad-builder v2.1.0), and the full text of KB.md. No memory-only claims.

---

## 1. Executive Conclusion

**Direct answers to the user's questions:**

1. **Is something like this already in BMAD?** Partially. BMAD has the *vocabulary* (`on_complete`, `activation_steps_*`, `bmad-eval-runner`, `validate-module.py`) but **none of these are programmatic gates**. Every one is prose that an LLM is asked to follow. The only exit-code enforcement in the entire framework is `validate-module.py`, which checks module *structure*, not story behavior.

2. **Can the user's idea be implemented?** Yes — but BMAD will provide ~30% of the lift (the customization-override mechanism that lets RDX inject a wrapper skill without forking BMM). The remaining ~70% must be built by RDX: deterministic scripts, evidence schema, CI integration.

3. **Can all RDX rules be made deterministic?** No, and the user's source already knew this. Per the rule classification (§4), ~25% of CORE rules and ~15-20% of pack rules can be made fully deterministic (Cat 1). Another ~30% can be deterministically gated on *evidence presence* (Cat 2). The remaining ~45-55% require LLM-evaluator or specialist sign-off (Cat 3/4). Forcing binary verdicts on Cat 3 rules would produce false positives and noise that erode trust in the gate.

4. **What BMAD provides natively:** The `agent.menu` merge-by-`code` override (Agent 3's finding) is the single most valuable native primitive — it lets RDX replace the `DS` menu dispatch from `bmad-dev-story` to `rdx-dev-story` *without forking BMM*. Plus `validate-module.py` as the pattern for exit-code-blocking scripts.

5. **Where external enforcement is needed:** Anything that must survive an uncooperative LLM. The wrapper skill (`rdx-dev-story`) is enforceable only as long as Amelia obeys the menu. The only *truly* tamper-resistant gate is a CI required-status-check that runs the validator on the actual diff regardless of what the agent reported.

6. **Recommended architecture:** A **4-layer model**: (L1) `rdx-dev-story` wrapper skill that orchestrates router-replay + deterministic checks + evidence collection; (L2) `rdx-validator/` Python utility with exit-code semantics; (L3) optional evaluator skill for Cat 3 rules; (L4) GitHub Actions / pre-push hook for tamper-resistant enforcement. Distribute as four operating modes (Advisory → Local enforced → CI enforced → High assurance) so users opt in to the level of friction they need.

---

## 2. Current RDX Enforcement Model — Where It Breaks

| Mechanism RDX currently relies on | Type per ground-truth investigation | Failure mode |
|----------------------------------|-------------------------------------|--------------|
| `persistent_facts` with `file:` prefix loading KB sections | Convention only — `resolve_customization.py` returns the array as-is; LLM is told (in SKILL.md text) to load `file:` entries. **Not loaded by code.** | LLM may treat `file:` as literal text, partially load, or summarize on long contexts |
| `principles` array instructing "consult Risk Router" / "Contract before code" | Convention — appended to agent context as prose | LLM may skip, summarize, or apply selectively under cognitive load |
| Risk Router consultation before code | Pure prose obligation in `principles` | No verification that router was actually consulted on this story |
| Conditional pack loading on trigger match | Pure prose; agent is asked to detect triggers in story + diff | No re-verification on actual diff; LLM may activate wrong pack or skip activation |
| John (PM) "grading agent behavior" | Prose in `principles`; no eval artifact or schema | Self-graded with no independent evidence |
| Story completion / DoD | `bmad-dev-story` Steps 8-9 are `<action>` XML tags, LLM-interpreted | LLM can self-declare "ALL conditions met" with no external check |

**The structural weakness**: RDX is currently a 100% Layer-1 (prose) system layered on top of another 100% prose system (BMAD). Both layers are subject to the same failure modes the user's feedback describes: skipped reads, summarization, ignored rules under context pressure, self-attested PASS.

---

## 3. BMAD Capability Matrix

| Mechanism | Source-verified behavior | Deterministic? | Can block completion? | Checks runtime story? | Useful for RDX? |
|-----------|--------------------------|---------------|----------------------|----------------------|-----------------|
| `activation_steps_prepend`/`append` | Script merges array; SKILL.md tells LLM to "execute each entry"; resolver does not execute anything | No | No | No (runs on agent activation, not story end) | Limited — only as additional prose injection |
| `persistent_facts` (`file:`/`skill:`/literal) | Merged by `resolve_customization.py`; no expansion of `file:` in code | No | No | No | Currently used by RDX; convention-only |
| `on_complete` (workflow scalar) | Stored as string; one SKILL.md (`bmad-cis-innovation-strategy`) checks "if non-empty, follow it as terminal instruction"; LLM-interpreted; *not* a script runner | No | No (LLM-readable suggestion) | No | **Useful**: can point to `rdx-dev-story-validate` as the "terminal instruction" — but still relies on LLM cooperation |
| `agent.menu` merge by `code` | Verified in `resolve_customization.py` lines 96-136; replace by identifier | Yes (the merge itself) | N/A (it's a dispatch table, not a gate) | N/A | **Critical** — lets RDX replace `DS` from `bmad-dev-story` → `rdx-dev-story` without forking BMM |
| `validate-module.py` | Real exit-code enforcement (`sys.exit(1)` on critical findings) | Yes | Yes (when called in a script chain) | No — validates module structure only | Pattern to emulate; not directly applicable to story gates |
| `bmad-eval-runner` | LLM-as-judge over staged skill runs; produces `grading.json`; no exit-code blocking | No | No | No — runs at skill-authoring time, not story time | Useful for RDX *meta-evals* (§11), not runtime story gate |
| `bmad-code-review`, `bmad-review-*` | LLM-driven adversarial analysis; markdown findings; no gate | No | No | Story-time (when invoked) but advisory | Could be used as Cat 3 evaluator inside RDX gate |
| `bmad-testarch-trace` | Produces PASS/CONCERNS/FAIL/WAIVED — but the verdict is an LLM judgment | No | No | Story-time, advisory | Reference for verdict vocabulary |
| Step-XML `<action>`/`<check>` tags in SKILL.md | Read by LLM, no parser | No | No | Story-time | Already RDX's current substrate; insufficient |
| Resolver script exit codes (1/3) | Caught by SKILL.md prose: "If script fails, do this manually" | Yes for the script | No (SKILL.md instructs fallback) | No | Pattern: scripts that exit non-zero are *not* honored as gates by SKILL.md text |
| Scripts in `skills/*/scripts/` that call `subprocess.run` | 5 of 32 exist; all capture results into JSON and return 0; none gate continuation | Yes for the subprocess | No (results reported, not enforced) | Indirectly | Pattern proves scripts work; need RDX-specific gate semantics |

**Headline finding**: **`agent.menu` merge-by-`code`** is the only first-class composition primitive in BMAD that enables RDX's goal *without forking core*. Everything else is either prose (no enforcement) or out of scope (module structure only).

---

## 4. Rule Classification (CORE-001..018 + 12 packs)

(Full per-rule classification produced by the research; the 18-row table is the authoritative reference.)

**Distribution across 18 CORE rules:**

| Category | Count | Rules |
|----------|-------|-------|
| Cat 1 — Fully deterministic (script can verify compliance) | 5 partial + checks across many | CORE-007 (protected files), CORE-011 (compile run), CORE-014 (suppression regex), CORE-015 (router replay), partial: CORE-008, CORE-010, CORE-017, CORE-018 |
| Cat 2 — Deterministic evidence presence | All 18 (every CORE rule benefits) | Every rule can require a structured evidence field |
| Cat 3 — Judgment-based review | 13 of 18 (substantial component) | CORE-001 contract, CORE-003 ownership, CORE-004 root cause, CORE-005 invariants, CORE-006 abstractions, CORE-013 oracle quality, etc. |
| Cat 4 — Specialist/owner approval | 4 of 18 (escalation triggers) | CORE-007 boundary expansion, CORE-014 lint policy, CORE-008 panic discipline (in security context), CORE-016 escalation paths |

**Pack-level deterministic-trigger detection (router replay strength):**

| Pack | Trigger detection strength | Cat 1 ceiling |
|------|---------------------------|---------------|
| Unsafe & memory | Very strong (`rg '\bunsafe\b\|MaybeUninit\|transmute'`) | ~20% (SAFETY-comment proximity + Miri runnable) |
| Cargo/workspace | Very strong (manifest path filter) | ~30% (cargo metadata, cargo tree -d, MSRV) |
| Performance/no_std/WASM | Strong (`#![no_std]`, target_arch, benches/) | ~20% (benchmark presence + target matrix) |
| FFI | Strong (`extern "C"`, manifest crate-type) | ~10% |
| Async/concurrency | Strong (`async fn`/`.await`/spawn) | ~10% |
| Macros/build scripts | Strong (`macro_rules!`, build.rs) | ~15% |
| Public API/SemVer | Medium (needs `[lib]`/publish judgment) | ~15% (cargo public-api, cargo semver-checks) |
| Data/sec/IO | Medium (some triggers semantic) | ~15% (cargo audit, regex bounds) |
| DB/messaging | Medium (sqlx/diesel/migrations) | ~10% |
| Time/config/clients | Medium (Instant/SystemTime/reqwest) | ~10% |
| Ops/observability | Weak (needs story tag) | ~5% |
| Testing beyond core | Medium (needs story risk tag + tool detection) | ~25% |

**Top 5 low-hanging deterministic checks (validator MVP scope):**

1. **CORE-011 + `cargo check` exit-code capture** — invocation harness with structured `compile_check: {status, command, exit_code, output_digest}` evidence
2. **CORE-007 protected-files glob** — `git diff --name-only` ∩ story's `protected_files` registry
3. **CORE-014 suppression-regex** — `rg` over diff hunks for `#[ignore]`, new `#[allow(...)]`, removed `#[test]`, `assert!(true)`
4. **CORE-008 panic-discipline subset** — `rg '\.unwrap\(\)|\.expect\('` in added lines excluding `tests/`, `examples/`, `#[cfg(test)]`
5. **CORE-015 router-replay parity** — run the deterministic router script over the actual diff; compare to agent-reported `activated_packs`; flag divergence

**Top 5 resistant rules (always need LLM-review or specialist):**

1. CORE-003 (ownership/lifecycle) — semantic
2. CORE-005 (invariants in types) — design judgment
3. CORE-013 (oracle from spec) — requires understanding both spec + implementation
4. RP-UNSAFE-006 (atomic ordering) — happens-before reasoning
5. RP-API-009 (downstream compat) — migration-path quality

---

## 5. Architecture Options — Comparison

| Variant | Description | Guarantee strength | Complexity | BMAD-native | Portability (Codex/Cursor/etc.) | Public distribution | False-block risk | LLM cost | Maintainability |
|---------|-------------|--------------------|------------|-------------|-------------------------------|--------------------|--------------------|----------|-----------------|
| **A — Validator skill only** (`rdx-validator/` with scripts) | User invokes `/rdx-validator` manually after story | Low (depends on user cooperation) | Low | Yes (mirrors `validate-module.py` pattern) | High (scripts portable) | Easy | Low | None | Easy |
| **B — Standalone validation workflow** | `rdx-dev-story` workflow strings: contract → repo inspect → routing → impl → validator → judgment → escalate → verdict | Medium (LLM still chooses to enter the workflow) | Medium | Yes (custom workflow + scripts) | Medium (workflow assumes BMAD substrate) | Easy | Medium | Moderate (evaluator agent) | Medium |
| **C — Wrapper over `bmad-dev-story`** | RDX overrides `agent.menu[code=DS].skill = "rdx-dev-story"`; wrapper invokes original, then runs validator | Medium-high in BMAD ecosystem (replaces dispatch) | Medium | **Yes — uses native `agent.menu` merge-by-`code`** | Low (BMAD-specific) | Easy | Medium | Moderate | Medium |
| **D — External CI gate only** | RDX = KB + pre-push hook + GitHub Actions required-status-check | High (tamper-resistant) | Medium-high | No (orthogonal to BMAD) | Universal (CI/git is environment-agnostic) | Easy | High if rules over-broad | None at gate time | High initially, low ongoing |
| **E — Hybrid: B+C+D** | Wrapper skill (C) for in-loop UX; validator scripts (A) reusable; CI gate (D) as tamper-resistant outer layer; LLM evaluator + specialist approval for Cat 3/4 | High (CI is the source of truth) | Highest | Partially (BMAD provides L1, RDX provides L2-L4) | High at the script/CI level, low at the BMAD wrapper level | Medium (well-documented modes) | Configurable (per mode) | Configurable | Medium-high (more surface) |

**Recommendation**: **Variant E**, exposed to users as **four progressive modes** so the friction matches the team's risk profile. See §6 for the concrete layering.

---

## 6. Recommended Target Architecture

**Four-layer model, four operating modes.**

```
                       ┌─────────────────────────────────────┐
   Story start  ─────▶ │  L1: rdx-dev-story (wrapper skill)  │  ← BMAD-native; menu[DS] override
                       │  - Invokes bmad-dev-story           │
                       │  - Records contract + risk tags     │
                       │  - On completion: invokes L2        │
                       └────────────────┬────────────────────┘
                                        │
                                        ▼
                       ┌─────────────────────────────────────┐
                       │  L2: rdx-validator (Python utility) │  ← Deterministic, exit-code semantics
                       │  - Router replay over actual diff   │
                       │  - Cat 1 rule checks (Top 5 MVP)    │
                       │  - Cat 2 evidence-schema validation │
                       │  - Writes evidence.json             │
                       └────────────────┬────────────────────┘
                                        │
                              ┌─────────┴──────────┐
                              ▼                    ▼
                ┌──────────────────────┐  ┌────────────────────┐
                │ L3: rdx-judgment     │  │ L3: rdx-specialist │
                │     (LLM evaluator)  │  │  (Cat 4 routing)   │
                │ - Cat 3 rules        │  │ - unsafe/FFI/API/  │
                │ - Quality review     │  │   security owners  │
                └──────────────────────┘  └────────────────────┘
                                        │
                                        ▼
                       ┌─────────────────────────────────────┐
                       │  L4: CI required-status-check       │  ← Tamper-resistant
                       │  - Re-runs L2 on actual diff        │
                       │  - Validates evidence.json signature│
                       │  - Blocks merge on FAIL/missing     │
                       └─────────────────────────────────────┘
```

**Operating modes** (mode chosen at install time; stored in `config.toml`):

| Mode | L1 active | L2 active | L3 active | L4 active | Use case |
|------|-----------|-----------|-----------|-----------|----------|
| **Advisory** | ✓ | report-only | report-only | — | Solo dev / prototype; learn the rules without friction |
| **Local enforced** | ✓ | blocking | report-only | — | Solo dev who wants real gates; no CI |
| **CI enforced** | ✓ | blocking | optional | ✓ | Team / OSS project with PR review |
| **High assurance** | ✓ | blocking | required (LLM + specialist sign-off) | ✓ + protected validator + approval trail | Crypto / safety-critical / regulated |

This preserves RDX's pluripotency for distribution (anyone can adopt Advisory and skill up to High assurance over time) without forcing CI on a user without a repo, or letting a fragile gate falsely block a researcher.

---

## 7. Repository Change Map (`alfaRazieL/Rust_bmad_dev`)

```
.claude/skills/
├── rdx-setup/                         [existing — minor config additions]
│   └── assets/agent-overrides/
│       └── bmad-agent-dev.toml        [ADD: menu[code=DS].skill = "rdx-dev-story"]
├── rdx-dev-story/                     [NEW — wrapper skill]
│   ├── SKILL.md                       [orchestrates bmad-dev-story → L2]
│   └── assets/
│       ├── story-contract.schema.json [JSON Schema for L2 input]
│       └── workflow-steps.md          [phases: contract → impl → validate → verdict]
├── rdx-validator/                     [NEW — deterministic L2]
│   ├── SKILL.md                       [thin: explains output, defers to scripts]
│   ├── scripts/
│   │   ├── router_replay.py           [run §5 router over actual diff]
│   │   ├── check_protected_files.py   [CORE-007]
│   │   ├── check_compile_evidence.py  [CORE-011]
│   │   ├── check_suppressions.py      [CORE-014]
│   │   ├── check_panic_discipline.py  [CORE-008 subset]
│   │   ├── check_safety_comments.py   [RP-UNSAFE-001 subset]
│   │   ├── check_manifest.py          [RP-CARGO-001/002/004]
│   │   ├── validate_evidence.py       [JSON Schema validator for all Cat 2]
│   │   ├── run_rust_gates.py          [cargo check/test/audit/semver-checks orchestrator]
│   │   └── tests/                     [pytest unit tests per check]
│   ├── schemas/
│   │   └── rdx-evidence.v1.schema.json
│   └── resources/
│       └── rule-check-map.json        [rule_id → check_script mapping]
├── rdx-judgment/                      [NEW — optional L3 LLM evaluator]
│   ├── SKILL.md                       [Cat 3 quality review]
│   └── assets/
│       └── review-rubric.md
└── .claude-plugin/marketplace.json    [bump version; add new skills to plugins[].skills]

.github/workflows/                     [NEW — L4 CI scaffolding shipped as installable]
└── rdx-gate.yml.template              [user copies to their project]

scripts/                               [project-root utilities]
├── install-pre-push-hook.sh           [opt-in client-side enforcement]
└── ci-runner.py                       [Mode 3/4: re-runs L2 on CI]

docs/
├── modes.md                           [the 4 modes, how to pick]
├── evidence-schema.md                 [evidence.json explained]
├── extending-validators.md            [how to add new Cat 1 checks]
├── threat-model.md                    [§10 in this report, abridged]
└── governance.md                      [Cat 4 specialist routing]
```

**Files explicitly NOT changed**: anything in `/Users/m33tball/bmad_module_builder/.claude/skills/bmad-*` (BMAD core). All RDX integration is via `_bmad/custom/` overrides written at install time by the existing `rdx-setup` skill.

---

## 8. Runtime Protocol

End-to-end sequence for a single story under **CI enforced mode** (the design target; other modes drop the later phases):

```
1. User: "Amelia, implement story N"
2. Amelia (bmad-agent-dev) resolves agent.menu[DS] → "rdx-dev-story"        [BMAD-native dispatch]
3. rdx-dev-story phase A — Contract intake:
    - Loads story file; extracts acceptance criteria, protected_files,
      explicit risk_tags
    - If contract incomplete → HALT with template
4. rdx-dev-story phase B — Router pre-pass:
    - python3 scripts/router_replay.py --story story-N.md --diff HEAD
    - Output: { "activated_packs": [...], "evidence": [...] }
    - Stored as evidence.json/router_replay block
5. rdx-dev-story phase C — Delegate to bmad-dev-story:
    - Invokes bmad-dev-story directly (Skill tool)
    - bmad-dev-story executes its normal red/green/refactor loop
    - On return, rdx-dev-story regains control
6. rdx-dev-story phase D — Evidence collection:
    - LLM is asked to record: contract reference, repo model notes,
      activated_packs (its own claim), assumptions, compile_check,
      suppression_authorizations, behavioral_check
    - Written to .rdx/evidence-{story-id}.json
7. rdx-dev-story phase E — Validator gate:
    - python3 .claude/skills/rdx-validator/scripts/run-all.py \
        --evidence .rdx/evidence-{story-id}.json \
        --story story-N.md \
        --base-ref main \
        --head-sha $(git rev-parse HEAD)
    - Returns structured JSON + exit code:
        0 = all Cat 1+2 PASS (or NOT_APPLICABLE)
        1 = blocking FAIL or BASELINE_FAILURE
        2 = NOT_RUN with insufficient reason
        3 = REVIEW_REQUIRED (Cat 3 pending)
        4 = APPROVAL_REQUIRED (Cat 4 pending)
    - Exit code 1/2 → rdx-dev-story HALTs; refuses to mark story complete
8. rdx-dev-story phase F (if exit 3) — Invoke rdx-judgment:
    - Cat 3 evaluator skill runs; appends judgment block to evidence.json
    - Re-runs validator; verdict can now be PASS or downgrade to FAIL
9. rdx-dev-story phase G (if exit 4) — Specialist routing:
    - Cat 4 rules emit "needs owner X approval"; story marked
      blocked-on-approval; not completable until approval trail recorded
10. rdx-dev-story phase H — Final verdict:
    - If validator final_verdict == PASS: mark story review-ready
    - Records signed evidence.json digest in story metadata
11. Git push triggers L4:
    - GitHub Actions runs rdx-validator on actual HEAD diff
    - If evidence.json present + matches diff signature: PASS (idempotent)
    - If absent / signature mismatch / re-run FAIL: blocks merge
12. Merge allowed only if (Mode 3) CI green, (Mode 4) + specialist approval present
```

**Key property**: phases 7-9 happen *inside* the LLM session; phase 11 happens *outside*. Phase 11 is what makes the gate tamper-resistant.

---

## 9. Evidence Schema — `rdx-evidence.v1.schema.json`

The user's proposed schema is structurally sound. Here is the corrected and elaborated version:

```jsonc
{
  "schema_version": "1.0",
  "rdx_version": "1.0.0",
  "kb_digest": "sha256:...",          // SHA of KB sections used; mismatch = re-evaluate
  "repository": {
    "path": "...",
    "remote": "..."
  },
  "story": {
    "id": "story-N",
    "contract_ref": "stories/N.md#contract",
    "protected_files": ["src/auth/**"],
    "explicit_risk_tags": ["async", "security"]
  },
  "base_ref": "main",
  "base_sha": "abc123...",
  "head_sha": "def456...",
  "diff_digest": "sha256:...",         // Pins evidence to this diff; any later edit invalidates
  "router_replay": {
    "activated_packs": ["async", "security"],
    "trigger_evidence": [
      { "pack": "async", "signal": "tokio::spawn at src/worker.rs:42", "rule_ids": ["RP-ASYNC-006"] }
    ],
    "negative_triggers_matched": []
  },
  "rules": {
    "CORE-011": {
      "applicability": "APPLICABLE",
      "verdict": "PASS",
      "category": [1, 2],
      "evidence": [
        {
          "kind": "command",
          "command": "cargo check --message-format=json",
          "exit_code": 0,
          "stdout_digest": "sha256:...",
          "tool_version": "cargo 1.85.0",
          "ran_at": "2026-06-29T10:00:00Z"
        }
      ]
    },
    "CORE-006": {
      "applicability": "APPLICABLE",
      "verdict": "REVIEW_REQUIRED",
      "category": [3],
      "reasoning_record": "Added trait `Storage` to allow swap-in tests; justification: ...",
      "judgment_ref": "evidence-N.json#judgment.CORE-006"  // Filled by L3
    },
    "RP-UNSAFE-001": {
      "applicability": "APPLICABLE",
      "verdict": "APPROVAL_REQUIRED",
      "category": [1, 4],
      "evidence": [
        { "kind": "rg_match", "pattern": "unsafe \\{", "file": "src/ffi.rs:120" },
        { "kind": "safety_comment_check", "found": true, "near_line": 119 }
      ],
      "approval": {
        "owner": "@unsafe-reviewer-team",
        "approved": false,
        "approval_trail_ref": null
      }
    }
  },
  "blocking_findings": [],             // FAIL verdicts go here
  "review_required": ["CORE-006"],
  "approvals_required": ["RP-UNSAFE-001"],
  "skipped": [                         // NOT_RUN with required reason
    { "rule_id": "RP-PERF-001", "reason": "no benches/ in diff; not a perf story" }
  ],
  "final_verdict": "BLOCKED",          // PASS / FAIL / BLOCKED / REVIEW_REQUIRED
  "signature": {
    "scheme": "hmac-sha256",
    "value": "..."                     // Computed over (diff_digest + rules verdicts + kb_digest)
  }
}
```

**Status semantics (corrected from the user's proposal):**

| Status | Blocking? | Who sets it | Notes |
|--------|-----------|-------------|-------|
| `PASS` | No | Script (Cat 1/2) or L3/L4 (Cat 3/4 after review) | Source of truth |
| `FAIL` | **Yes** | Script (any tier) | Hard block |
| `NOT_APPLICABLE` | No | Script | Must have justification ref (e.g., trigger absent) |
| `NOT_RUN` | **Yes if no reason** | Script | Requires structured `reason`; otherwise upgraded to FAIL |
| `REVIEW_REQUIRED` | **Yes until reviewed** | Script (Cat 3) | Downgrades to PASS/FAIL after L3 evaluator |
| `APPROVAL_REQUIRED` | **Yes until approved** | Script (Cat 4) | Needs approval trail with owner identity + timestamp + diff_digest |
| `BLOCKED` | **Yes** | Validator orchestrator | Aggregate status when any blocking finding present |
| `BASELINE_FAILURE` | Special | Script | Pre-existing failures on base_ref; record + don't blame story |

**Trust rules:**
- Only Cat 1 scripts may set `PASS` for Cat 1 rules. LLM cannot self-attest Cat 1.
- L3 evaluator may set `REVIEW_REQUIRED → PASS/FAIL` for Cat 3 only, never Cat 1/4.
- Specialist approval must include diff_digest in approval trail. Re-using an approval for a different diff_digest is rejected.
- `signature` invalidates if anything in the document changes; prevents trivial editing of verdicts.
- `kb_digest` mismatch (KB updated since this evidence was recorded) downgrades all verdicts to REVIEW_REQUIRED.

---

## 10. Threat Model — Bypass Analysis

| Attack | Defense | Defense layer |
|--------|---------|---------------|
| Agent doesn't run validator | (a) Wrapper skill embeds validator call; (b) CI re-runs on push regardless | L1 (best effort) + L4 (authoritative) |
| Agent edits `rdx-validator/scripts/*` to weaken checks | (a) Scripts in `protected_files`; CORE-007 catches; (b) CI runs validator from a pinned ref (PR base or a vendored copy), not the PR's HEAD copy | L4 + governance |
| Agent edits `rdx-evidence.v1.schema.json` | Protected file; CI uses schema from base ref | L4 |
| Agent deletes a failing test | (a) `git diff` check for removed `#[test]` items requires authorization record (CORE-014); (b) CI compares test count to base | L2 + L4 |
| Agent runs check on a different commit | `diff_digest` and `head_sha` in evidence; CI verifies these match actual diff | L2 + L4 |
| Agent fabricates evidence (writes `PASS` manually) | (a) `signature` HMAC keyed in CI environment (LLM has no key); (b) Cat 1 PASS rejected unless command output digest matches a re-execution; (c) CI re-runs all Cat 1 scripts | L2 + L4 |
| Agent writes `PASS` directly to evidence.json | HMAC signature missing → CI rejects; CI is the only signer for Mode 3/4 | L4 |
| Agent excludes a pack that should be active | Router replay (Cat 1) compares activated_packs to recomputed list; mismatch = FAIL | L2 |
| Agent marks rule `NOT_APPLICABLE` without basis | Schema requires structured `not_applicable_reason` referencing trigger absence; router replay validates | L2 |
| Agent hides `NOT_RUN` | Schema requires structured `reason` for NOT_RUN; missing reason auto-upgraded to FAIL | L2 |
| Agent changes baseline silently | `base_sha` recorded; CI verifies base = PR target branch SHA | L4 |
| Agent weakens CI workflow | (a) Branch protection on `.github/workflows/`; (b) GitHub required-status-check setting (admin-only) | Repo + governance |
| Agent modifies protected files | CORE-007 detects in L2; CI blocks merge | L2 + L4 |
| Agent declares story complete before gate | `bmad-dev-story` already returned to wrapper; wrapper controls completion flag; if wrapper bypassed (LLM ignores menu override), CI catches at push | L1 + L4 |
| User has no GitHub / no CI | Pre-push git hook (Mode 2); validator still local-blocking. Mode 1 = advisory only — gracefully degraded but clearly labeled | L4 alternative + transparency |
| Environment has no Python / can't run scripts | RDX runs in Mode 0 (degraded advisory); user notified that enforcement is unavailable | Compatibility |
| LLM environment (web, no shell) | Same as above; Mode 0 only; documented limitation | Compatibility |
| Agent edits the KB to remove a rule | `kb_digest` in evidence; CI re-computes; mismatch invalidates all evidence | L4 + governance |

**Defense classifications:**
- **L2-level** (script): catches the careless / single-attempt evasion
- **L4-level** (CI + branch protection): catches the cooperative bypass; tamper-resistant
- **Governance**: KB updates, validator changes, schema changes require approval trail — same as protected files
- **Compatibility / transparency**: where no enforcement is possible, *say so loudly* in the gate output

**What we cannot defend against**: a user with admin privileges on the repo who turns off the required check. That is out of scope for any automated system and lives in organizational governance.

---

## 11. Evals — What to Test

Separated by category as the user requested:

### Artifact evals (does the agent produce the right artifact?)

- Given story X with `unsafe` in diff: does `evidence.json` contain `activated_packs: ["unsafe", ...]`?
- Given story without async: does evidence NOT include async pack?
- Given story with `cargo check` failure: does evidence record `compile_check: {status: "FAIL", ...}` and final_verdict include FAIL?
- Given story that touches a protected file: does evidence list the file under blocking_findings?

### Transcript evals (does the agent reason correctly?)

- Did the agent invoke `rdx-validator` (or did it skip)?
- Did the agent attempt to mark story complete before gate? (Should HALT.)
- On Cat 3 review: did the LLM evaluator's judgment cite specific rule text, not paraphrase?
- On baseline failure: did agent distinguish baseline from regression?

### Trigger evals (does the router fire correctly?)

These are the most important — they catch silent skip:
- Async lifecycle change (`async fn` added) → async pack activates
- Async mentioned only in doc comment → async pack does NOT activate
- New `unsafe` block → unsafe pack + Cat 4 escalation
- `Cargo.toml` dependency added → cargo pack activates
- Cargo.lock duplicate version added → NOT auto-FAIL without policy
- `cargo check` was run after change in semantic surface (not skipped)
- `NOT RUN` recorded with reason when tool unavailable (not silently absent)
- Failing test → not declared PASS
- Test weakened (assertion removed) → suppression authorization required
- Trivial story still consults router (does not skip "because trivial")
- Delegation preserves risk tags (sub-agent inherits active packs)

### Deterministic unit tests (validator scripts)

- `check_protected_files.py`: synthetic diffs touching/not touching protected globs → expected verdict
- `check_compile_evidence.py`: evidence with/without compile_check entry → expected verdict
- `check_suppressions.py`: diff hunks with `#[ignore]`, `#[allow]`, removed `#[test]` → expected matches
- `check_safety_comments.py`: `unsafe {` block with/without nearby `// SAFETY:` → expected
- `router_replay.py`: each pack's positive + negative triggers
- `validate_evidence.py`: schema-valid and schema-invalid evidence inputs

### Integration tests (end-to-end on fixtures)

- A green Rust crate: validator should return PASS
- A crate with failing `cargo check`: blocking FAIL
- A crate with unauthorized panic added: blocking FAIL with rule citation
- A crate with new `unsafe` and missing SAFETY: FAIL + Cat 4 routing

### Mutation/adversarial tests

- Fabricate an evidence.json with all PASS but `diff_digest` mismatched → CI rejects
- Edit a Cat 1 script in PR to weaken check → validator (running from base) catches
- Submit evidence with HMAC computed wrong → CI rejects
- Re-submit old approval for new diff_digest → rejected

**Critical distinction**: Trigger + artifact + transcript evals **measure RDX quality** (regression suite). Deterministic unit + integration + mutation tests **back the runtime gate**. The first set is run by us on the module; the second runs in user CI on every PR. Conflating them gives the wrong signals.

---

## 12. Security & Bypass — Summary

See §10 for the matrix. Three principles drive the security posture:

1. **CI is the source of truth.** The wrapper skill is best-effort UX. The HMAC-signed evidence + re-run on CI is the actual gate. Without CI, we are Mode 1/2 and we say so.

2. **No self-attestation for Cat 1.** A script must observe the command output. LLM-written `PASS` for Cat 1 is invalid by schema.

3. **Pin everything that defines the gate.** KB digest, validator script ref, schema ref, base-branch SHA — all pinned in the evidence. Any drift downgrades to REVIEW_REQUIRED. This stops "approve once, ride forever" attacks.

---

## 13. Compatibility — Graceful Degradation

| Environment | Mode supported | What works | What doesn't |
|-------------|---------------|-----------|--------------|
| macOS / Linux + Python 3.11+ + git + cargo + GitHub | 1-4 | Everything | — |
| macOS / Linux + Python + git, no GitHub (GitLab/local) | 1-3 (CI is generic; ship `.gitlab-ci.yml.template` too) | L1, L2, L3, local CI | GitHub-specific status check |
| Windows (with WSL or native Python) | 1-3 | All scripts (Python is portable) | pre-push hook syntax (bash → ship powershell variant) |
| Codex CLI / Cursor / Aider | 1-2 only | L2 scripts run from CLI; user must invoke manually | L1 wrapper (no `agent.menu` system); RDX ships an `AGENTS.md` snippet for Codex |
| Web-based Claude (no shell) | 0 (advisory) | KB-prose only, same as current RDX | No scripts — clearly labeled |
| No Python | 0 (advisory) | KB-prose only | Validator |
| Sandbox without network | 1-2 | All offline-able scripts; `cargo audit` skipped with NOT_RUN | Audit + semver-checks (network-dependent) |

**Critical rule from the user's brief**: do not call fallback "deterministic." Mode 0 evidence.json carries `enforcement_level: "advisory"` and CI cannot accept it — by design, an advisory run cannot mark a PR mergeable in Mode 3/4.

---

## 14. Implementation Roadmap

| Stage | Deliverables | Acceptance criteria | Effort |
|-------|--------------|--------------------|---------|
| **0. Prototype (1-2 days)** | `rdx-validator/scripts/check_protected_files.py` + `router_replay.py` only; ad-hoc invocation | Both scripts have ≥3 fixture-based unit tests; exit codes correct; rejects invalid input | Small |
| **1. Local validator (1 week)** | All 5 Top-5 Cat 1 checks + `validate_evidence.py` schema validator + evidence schema v1.0 + CLI orchestrator `run-all.py` | Validator runs on a sample Rust project; produces evidence.json; exit 1 blocks; 90%+ test coverage on scripts | Medium |
| **2. BMAD wrapper integration (3-5 days)** | `rdx-dev-story` skill; `agent.menu` override in `bmad-agent-dev.toml`; `rdx-setup` installs all | Wrapper invokes bmad-dev-story; on return invokes validator; HALTs on FAIL; documented in README | Medium |
| **3. L3 LLM evaluator (1 week)** | `rdx-judgment` skill; Cat 3 review rubric; integration with evidence schema (judgment block) | Evaluator produces structured judgment; can downgrade REVIEW_REQUIRED to PASS/FAIL; evals confirm consistency across runs | Medium |
| **4. Eval suite (1-2 weeks)** | Artifact + transcript + trigger evals (via `bmad-eval-runner`) for the 12 most-important behaviors from §11 | Eval suite has documented baseline; runs reproducibly; passes for current implementation | Medium |
| **5. CI enforcement (1 week)** | `.github/workflows/rdx-gate.yml.template`; `ci-runner.py`; HMAC signing; documentation for adoption | Sample repo demonstrates: PR with unauthorized panic gets blocked; PR with valid evidence passes; key rotation documented | Medium |
| **6. High-assurance hardening (2 weeks)** | Approval-trail enforcement; Cat 4 specialist routing; protected validator files; KB digest pinning; key management docs; threat-model walkthrough | Demonstrated tamper attempts (per §10) all caught; approval trails verifiable; reproducible from base ref | Large |
| **7. Modes documentation + UX (3-5 days)** | `docs/modes.md`; install-time mode selection in `rdx-setup`; clear advisory-mode labeling | User can pick a mode at install; mode affects which skills/CI assets are installed; advisory mode visibly self-labels | Small-medium |

Total minimum to deliver Variant E in Mode 3: ~4-5 weeks. Stages 0-2 alone (Mode 2: local-enforced wrapper + scripts) are a usable MVP at ~2 weeks.

---

## 15. Final Recommendation

**Implement Variant E in stages, starting with Stages 0-2 only (~2 weeks) and shipping as "RDX Mode 2 — Local Enforced."**

Reasoning:
1. **Mode 2 is the smallest configuration that *actually changes the user's experience* compared to the current RDX.** It introduces a real exit-code gate (the validator) and the wrapper skill that calls it. Without these, RDX is still 100% prose.
2. **Mode 2 ships only what is verifiable now.** The Top 5 Cat 1 checks are not speculative — they map directly to identifiable patterns in diffs. We avoid the trap of false-positive blocks that erode user trust.
3. **CI enforcement (Stages 5-6) requires user buy-in.** Most public adopters won't have a key-management process. Shipping CI as a *templated, opt-in upgrade* (Stage 5) lets the project mature without forcing infrastructure on solo Rust developers.
4. **Evals (Stage 4) are non-negotiable but can ship as v1.1.** They protect RDX from regression as we add more Cat 1 checks, but they are not user-visible enforcement.
5. **The user's source already accepted that not all rules can be deterministic.** This recommendation matches that acceptance: Cat 1+2 are gated, Cat 3 is structured for review, Cat 4 is documented as escalation. We do not promise binary judgment where none exists.

**Answer to the user's key question (§15 of brief):**

> *Как превратить RDX из системы, которая только инструктирует LLM, в гибридную систему, где проверяемые требования enforced детерминированно, непроверяемые — структурированно эвалюируемые, а задача не может быть объявлена проверенной без gate?*

By **separating four concerns that the current RDX (and most "rule" systems) conflate**:
- **(A) Knowledge** — KB stays exactly as is. KB is prose.
- **(B) Behavior** — the wrapper skill orchestrates the workflow. Behavior is prose-driven but exits through a deterministic gate.
- **(C) Verification** — `rdx-validator` scripts run with exit-code semantics. Verification is code, not prose. Cat 1+2 = scripts. Cat 3 = LLM-evaluator with structured rubric. Cat 4 = signed approval trail.
- **(D) Enforcement** — CI re-runs verification on the actual diff. Enforcement lives outside the LLM session, where the agent has no edit access at gate time.

BMAD provides the menu-override hook (A→B integration) and that is the only true native integration primitive available. Everything else (C and D) RDX must build itself. This is consistent with the official BMAD-METHOD documentation, which explicitly recommends *"belt-and-suspenders LLM-side reinforcement"* as the framework's answer to determinism — i.e., the framework itself does not provide it.

The proposed architecture turns the user's first reviewer's critique into the design constraint: **rules an LLM might skip should be enforced by code; rules code can't judge should be reviewed by an evaluator with structured evidence; rules no automation can settle should require a named owner's signature; nothing the agent self-attests counts as evidence.**

This is achievable, BMAD-compatible, distributable, and degradable across environments. Stage 0-2 implementation can begin immediately on confirmation.
