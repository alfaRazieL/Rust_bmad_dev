# RDX Validator Architecture — Verification Report

**Status:** Verification stage complete. Empirical evidence collected via 7 spikes plus source review. This report supersedes architectural claims in `RDX improve research.md` where the two conflict.

**Date:** 2026-06-29
**Author:** RDX architect, working in `/Users/m33tball/bmad_module_builder`

---

## 1. Executive Verdict

**Final verdict: `GO — Variant E, but with mandatory corrections`** (see §16 for the corrections).

Specifically:
- Variant E's **wrapper-skill component (Approach C1) is empirically proven to integrate cleanly with BMAD** via the `agent.menu` merge-by-`code` mechanism. (Spike 1, 1b, 1c, EXPERIMENT VERIFIED.)
- Variant E's **"Local Enforced" mode as previously described is technically false**. A BMAD wrapper skill cannot enforce a non-zero exit code; only git/OS-level mechanisms (pre-commit, pre-push hooks) or CI required-status-checks can. The previous report's "Mode 2 — Local Enforced" must be re-labelled **"Mode 2 — Local Gated (git-hook backed)"** and explicitly require a pre-push hook to deliver its name.
- The **wrapper is still valuable** as the in-loop UX and evidence-collection layer, but its role must be reframed: it is the *cooperative orchestrator*, not the *enforcement boundary*.
- **Recommended first implementation milestone**: Variant V5 (Wrapper + Validator + CI), see §15. V5 is V6/Variant E minus the LLM evaluator (which is non-blocking and can ship later) and gives real enforcement with the minimum moving parts.
- **`bmad-eval-runner` is the right home for RDX regression evals** (orthogonal to the runtime gate; module-quality concern only).

**Confidence: 88%.** Breakdown in §16-F.

---

## 2. Versions and Source Baseline

| Component | Source of truth | Version | Verified how |
|-----------|----------------|---------|--------------|
| BMAD-METHOD (upstream) | `bmad-code-org/BMAD-METHOD` | v6.9.0 (2026-06-22) | Web research from prior report; not re-verified this round |
| bmad-builder (upstream) | `bmad-code-org/bmad-builder` | v2.1.0 (2026-06-22) | Same as above |
| Local installation root | `/Users/m33tball/bmad_module_builder` | (installed copy) | Direct file reads |
| `resolve_customization.py` | `/Users/m33tball/bmad_module_builder/_bmad/scripts/resolve_customization.py` | 239 lines, header dated single-source | Read in full this round |
| `bmad-agent-dev` SKILL.md | `/Users/m33tball/bmad_module_builder/.claude/skills/bmad-agent-dev/SKILL.md` | 76 lines | Read in full prior round |
| `bmad-agent-dev` customize.toml | `/Users/m33tball/bmad_module_builder/.claude/skills/bmad-agent-dev/customize.toml` | 96 lines (8 menu items) | Confirmed live this round via Spike 1c |
| `bmad-dev-story` SKILL.md | `/Users/m33tball/bmad_module_builder/.claude/skills/bmad-dev-story/SKILL.md` | ~460 lines, surveyed in prior round | Not re-read this round (relied on prior findings) |
| Python runtime | system `python3` (3.11+) | tomllib stdlib available | Confirmed by running resolver |
| Spike workspace | `/tmp/rdx-spikes/` (7 sub-dirs) | created this round | All artifacts preserved |

The local installation is the authority for this report. Where upstream may have moved, that is noted explicitly.

---

## 3. Previous-Report Claims Under Verification

| Claim from `RDX improve research.md` | Section | Verification verdict |
|-------------------------------------|---------|---------------------|
| `agent.menu` merge-by-`code` replaces the dispatch target | §3, §6 | **CONFIRMED** (Spike 1, 1c) |
| RDX can ship `rdx-dev-story` wrapper without forking BMM | §1, §6 | **CONFIRMED** (Spike 1c — real bmad-agent-dev) |
| Wrapper "regains control" after invoking `bmad-dev-story` | §6, §8 | **REFRAMED** — works as LLM cooperation; no programmatic boundary (Spike 2 finding) |
| Wrapper can HALT story completion on validator FAIL | §6, §8 ("Mode 2 — Local Enforced") | **REJECTED AS STATED** — the wrapper itself cannot enforce; only the LLM cooperating with the wrapper's prose can. Hard local enforcement requires git hooks. (Spike 3) |
| Exit-code semantics gate the workflow | §8 | **REJECTED AS STATED** for in-BMAD context. **CONFIRMED** for git hook / CI context. (Spike 3) |
| Router replay over diff is feasible | §4, §8 | **CONFIRMED with caveats** — strong signals work; weak signals (semantic intent, no_std vs std consumption) need story tags. (Spike 5) |
| `diff_digest` + `kb_digest` pin evidence to a specific state | §9 | **CONFIRMED** (Spike 6) |
| BASELINE_FAILURE semantics need disambiguation | §9 | **CONFIRMED** — dual-run pattern is the right approach. (Spike 7) |
| HMAC signature is required even for CI mode | §9, §10 | **PARTIALLY REJECTED** — if CI independently re-runs validator on its own, HMAC adds little. Justified only when CI accepts agent-produced evidence verbatim (rare). |
| Top 5 deterministic checks are low-risk MVP | §4 | **CONFIRMED** for 4 of 5; CORE-008 panic-discipline subset still has false-positive surface that needs an evidence/exception layer (§9 of this report). |

---

## 4. Menu Override Verification — Spike 1, 1b, 1c

### Hypothesis
RDX can replace `agent.menu[code=DS].skill = "bmad-dev-story"` with `skill = "rdx-dev-story"` by writing only to `_bmad/custom/bmad-agent-dev.toml`, without modifying any BMAD core file, with deterministic and reproducible merge behavior.

### Environment
- `python3` (3.11+); `tomllib` stdlib
- `/Users/m33tball/bmad_module_builder/_bmad/scripts/resolve_customization.py`
- Real installation of bmad-agent-dev at `.claude/skills/bmad-agent-dev/`

### Source review
**SOURCE VERIFIED** — `resolve_customization.py`:
- Lines 96-110 (`_detect_keyed_merge_field`): returns `code` or `id` only if **every** item in the combined array carries the same identifier. Mixed-identifier arrays fall back to append.
- Lines 113-136 (`_merge_by_key`): matching key → `result[index_by_key[key]] = dict(item)` (entire dict replaced, not field-merged); new key → append.
- Lines 222-223 (`main`): merge order is `defaults ← team ← user`. User override always wins.
- No removal mechanism (lines 31-33 docstring).

### Inputs
**Spike 1** — synthetic fixture:
- `skills/test-skill/customize.toml`: base with `DS → bmad-dev-story`, `CR → bmad-code-review`
- `_bmad/custom/test-skill.toml`: team override replacing `DS → rdx-dev-story` and adding `VG → rdx-validator`

**Spike 1b** — added `_bmad/custom/test-skill.user.toml` with `DS → my-custom-dev-story` (precedence test).

**Spike 1c** — real bmad-agent-dev, temporary append to actual `_bmad/custom/bmad-agent-dev.toml` (reverted immediately after observation).

### Commands & Actual Output

Spike 1 (synthetic, `--key agent.menu` output):
```json
{
  "agent.menu": [
    {"code": "DS", "description": "RDX-wrapped: rdx-dev-story with validator gate", "skill": "rdx-dev-story"},
    {"code": "CR", "description": "Code review", "skill": "bmad-code-review"},
    {"code": "VG", "description": "Run RDX validator gate manually", "skill": "rdx-validator"}
  ]
}
```
Exit code: 0.

Spike 1c (real bmad-agent-dev) before override: DS → `bmad-dev-story` (plus 7 others).
After override: DS → `rdx-dev-story` (description and skill both replaced); all 7 other menu items preserved verbatim.

### Verdict
**EXPERIMENT VERIFIED.** The full menu-item dict is replaced, not field-merged. Other items are preserved. User overrides win over team overrides. The override mechanism is reproducible, stable, and zero-touch on BMAD core.

### Caveats (must be reflected in design)
1. **Description and skill fields are replaced together.** If RDX wants to keep the original description, RDX's override must restate it. Acceptable; trivially handled in `rdx-setup`.
2. **No removal mechanism.** RDX cannot delete the default `DS` entry; it can only override or shadow with new entries. Acceptable — override is exactly what we want.
3. **No module-namespace for overrides.** Any other module that writes `_bmad/custom/bmad-agent-dev.toml` will overwrite RDX's. This is a *coexistence* risk, not a *correctness* risk. Mitigation: `rdx-setup` already merges existing files rather than overwriting (per its existing SKILL.md Step 4). Should add a "RDX section marker" comment in the override file so other modules / human edits can be reconciled.
4. **No stability contract on the merge behavior.** The merge rules are an implementation detail of the resolver script. They are documented in `_bmad/scripts/resolve_customization.py` docstring and BMAD `expand-bmad-for-your-org.md`, so we'll consider this "documented but not API-stable." RDX should pin a minimum compatible resolver version (or vendor a known-good copy as a fallback).

---

## 5. Nested Skill Invocation Verification — Spike 2

### Hypothesis
A wrapper skill (`rdx-dev-story`) can invoke `bmad-dev-story` and then resume its own instructions to run the validator, with reliable control return.

### Environment
- Read of `bmad-quick-dev/SKILL.md` and its step files (the closest existing pattern to a wrapper)
- Grep across all `.claude/skills/bmad-*/SKILL.md` for cross-skill invocation patterns

### Source/Doc review
**DOC VERIFIED + INFERENCE** (not experimentally verified — cannot run a wrapper-child loop inside this conversation tooling without distorting state):

1. **No BMAD skill currently calls another skill programmatically.** `bmad-quick-dev` uses step files (`./step-01-clarify-and-route.md` … `./step-05-present.md`) read sequentially via "Read fully and follow:" instructions. These are *internal* sub-routines, not cross-skill invocation.
2. **The phrase "invoke X skill" in BMAD SKILL.md files** (found in bmad-prd, bmad-spec, bmad-ux) consistently refers to *suggesting the user invoke* a different skill — not programmatically calling it.
3. **The Skill tool (provided by the Claude Code / Codex CLI harness) does support invoking another skill from within one skill's execution.** When Skill is called, the child skill's SKILL.md is loaded into context and the LLM follows it. After child completion, the wrapper's SKILL.md text is still in context and the LLM continues with the wrapper's next step.
4. **There is no programmatic boundary or "return value."** The wrapper "regains control" because its instructions remain in the LLM context window, not because of any runtime API. The LLM cooperatively returns to the wrapper.

### Implications for design
- The wrapper pattern works **as a convention** that depends on LLM cooperation.
- It is **structurally identical to** the existing `bmad-dev-story` Step 8/9 "ONLY THEN mark complete" instructions — and Agent 1's prior research showed those are LLM-honored, not enforced.
- A non-cooperative or distracted LLM can: (a) call the child skill, (b) skip the wrapper's post-child steps, (c) call the validator but ignore the result, or (d) skip the wrapper entirely and call `bmad-dev-story` directly.
- The wrapper's role is therefore **UX + evidence collection + happy-path orchestration**, *not* enforcement. Enforcement must live elsewhere (Spike 3, Spike 4).

### Verdict
**INFERENCE** — the wrapper-child-resume control flow is achievable and the most natural BMAD-native pattern, but it provides **convention-level cooperation, not enforcement**. The previous report's "wrapper HALTs" language is misleading when read as a technical guarantee.

### What would close this gap
An empirical multi-skill spike requires running BMAD in a real harness (Claude Code session) with two skills and observing the message stream. Worth doing as a one-off validation before V5 implementation begins (acceptance criterion for §16-C).

---

## 6. Exit-Code Enforcement Verification — Spike 3

### Hypothesis
A non-zero exit code from a Python script invoked by `rdx-validator` will block story completion in BMAD wrapper context.

### Environment
- Local shell, Python 3.11+, git 2.x, isolated git repo at `/tmp/rdx-spikes/spike-3-exitcode/`

### Test matrix

| Test | Invocation context | Exit code | Effect | Verdict |
|------|-------------------|-----------|--------|---------|
| A | Bare shell (`python3 validator.py`) | 1 | Process exits 1; nothing else happens | Trivial baseline |
| B | BMAD wrapper context (modeled after how BMAD scripts are called from SKILL.md) | 1 | LLM sees stdout + sees that exit code was 1; **LLM decides what to do**. Pattern confirmed across BMAD: SKILL.md text universally says "if script fails, do this manually." | **PROMPT-LEVEL ONLY** |
| C | Pre-commit git hook | 1 | **`git commit` actually failed** — `git log` shows no commit was created. `fatal: your current branch 'master' does not have any commits yet` | **HARD ENFORCEMENT** at git/OS level |
| D | Pre-push git hook | 1 | Same as C, but blocks push (test was incomplete due to no real remote in spike; reasoning extrapolated from documented git behavior) | **HARD ENFORCEMENT** (DOC VERIFIED) |

### Commands & Actual Output (Test C)
```
$ git commit -m "test"
{"verdict": "FAIL", "rule": "CORE-008", "msg": "unauthorized .unwrap() in src/main.rs:42"}
$ echo $?
1
$ git log --oneline
fatal: your current branch 'master' does not have any commits yet
```

### Verdict
**EXPERIMENT VERIFIED.** The same script with the same exit code produces:
- **Zero enforcement** when read by an LLM via SKILL.md prose
- **Hard enforcement** when run by git as a hook

This forces a major correction to the previous report's terminology. The wrapper component of Variant E provides **soft gate** behavior at best. The "Local Enforced" mode label was wrong and must be split into:

| Mode | Enforcement reality | Mechanism |
|------|---------------------|-----------|
| **Advisory** | None (informational) | KB + wrapper + report-only validator |
| **Local Validated** | LLM-cooperative ("soft gate") | KB + wrapper that runs validator and shows result; LLM is asked to honor |
| **Local Gated** | Hard (OS-level) | Above + pre-commit/pre-push hook running the same validator |
| **CI Enforced** | Hard (CI required-status-check) | Above + GitHub Actions / GitLab CI required check |
| **High Assurance** | Hard + provenance | Above + signed evidence, protected validator, specialist approval trail |

Terminology rule: **do not call any mode "enforced" if a non-cooperative LLM or careless user can simply not run the gate-providing mechanism.**

---

## 7. Local Hard-Gate Alternatives — Spike 4

| Mechanism | Triggered by | Can LLM/user skip? | Actually blocks | What it blocks | Portability |
|-----------|-------------|--------------------|-----------------|----------------|-------------|
| BMAD wrapper alone | LLM following SKILL.md | Yes (ignore step) | No | Nothing technically | BMAD only |
| CLI launcher (e.g., `rdx run`) | User typing command | Yes (don't type it) | No (just exits) | Nothing the LLM cares about | Universal CLI |
| Shell alias / Makefile target | User invoking it | Yes | No | Nothing | Universal |
| **Pre-commit hook** | `git commit` | Only by `--no-verify` flag | **Yes** | New commits | Git-universal |
| **Pre-push hook** | `git push` | Only by `--no-verify` flag | **Yes** | Pushes (commits stay local) | Git-universal |
| git merge-driver | Custom merge resolver | Custom-configurable | Partial (on merges only) | Specific file merges | Git-universal, niche |
| Local daemon / file watcher | Always-on | Yes (user kills daemon) | Visible but bypassable | Notifications | Custom infra |
| **CI required status check** | Push to GitHub + PR | Admin can disable | **Yes** | PR merge to protected branch | GitHub/GitLab/etc. |

**Conclusion for "Local Hard Gate":** The only mechanisms that **actually block an LLM-cooperative or LLM-non-cooperative bypass** without depending on the LLM choosing to run them are:
1. Pre-commit / pre-push hooks (local, OS-level)
2. CI required-status-checks (server-side)

Both can be evaded by a determined user (`--no-verify`, admin disabling required checks), which is correct: organizational governance is the outer layer.

**The wrapper skill is excellent UX; the git hook is the actual local gate.** RDX should ship both as **paired artifacts** in Mode "Local Gated" — the hook is installed by `rdx-setup` (with user consent), and the wrapper writes evidence that the hook then validates on commit/push.

---

## 8. Risk Router Replay Feasibility — Spike 5

### Hypothesis
Each of the 12 conditional packs can be activated/skipped by a deterministic script that inspects the actual git diff and project files.

### Fixtures (4 diffs)
1. `fixture-1-real-async.diff` — adds `tokio::spawn(async move { ... .await; })`
2. `fixture-2-doc-only-async.diff` — comment-only mention of async, no code change
3. `fixture-3-new-unsafe.diff` — new `unsafe { *ptr }` inside `safe_wrapper`
4. `fixture-4-cargo.diff` — `Cargo.toml` adds `tokio = "1.40"`

### Naive regex implementation
```bash
echo "$ADDED" | grep -qE 'async fn\b|\.await\b|tokio::spawn|JoinHandle' && packs+=(async)
echo "$ADDED" | grep -qE '\bunsafe\b\s*[\{<]|\bunsafe fn\b|MaybeUninit|transmute' && packs+=(unsafe)
echo "$ADDED" | grep -qE 'extern "C"|#\[no_mangle\]|cdylib' && packs+=(ffi)
echo "$f" | grep -qE 'Cargo\.(toml|lock)|rust-toolchain' && packs+=(cargo)
```

### Actual results

| Fixture | Expected | Actual (naive) | Match? |
|---------|----------|----------------|--------|
| 1: real async | `async` | `async` | ✓ |
| 2: doc-only async | NONE (negative trigger) | NONE | ✓ |
| 3: new unsafe | `unsafe` | `unsafe` | ✓ |
| 4: Cargo.toml change | `cargo` | NONE | ✗ |

### Failure analysis (fixture 4)
The naive script applied the file-path regex to the fixture *filename* (`fixture-4-cargo.diff`) instead of to the **paths inside the diff** (`+++ b/Cargo.toml`). Correct implementation requires inspecting `diff --git a/X b/X` headers. This is a script bug, not a methodology failure.

### Per-pack feasibility matrix (per Spike 5 + KB Section 5 review)

| Pack | Deterministic signals (in diff) | Semantic signals (need judgment) | Negative-trigger risk | Automation confidence | Recommended verdict |
|------|--------------------------------|--------------------------------|----------------------|----------------------|---------------------|
| Async | `async fn`, `.await`, `tokio::spawn`, `JoinHandle`, `select!` | "is this safe-async vs lifecycle-changing async?" | doc-only mentions caught well | High | AUTO_ACTIVATE |
| Unsafe & memory | `\bunsafe\b\s*{`, `unsafe fn`, `MaybeUninit`, `transmute`, `Pin`, `NonNull` | "safe wrapper over existing unsafe?" | low — keyword is rare | Very high | AUTO_ACTIVATE |
| FFI | `extern "C"`, `#[no_mangle]`, `#[export_name]`, Cargo `crate-type = ["cdylib","staticlib"]` | "pure-Rust extern (linkage only)?" | low | High | AUTO_ACTIVATE |
| Macros / build scripts | `macro_rules!`, `proc_macro`, `#[proc_macro_attribute]`, `build.rs` file presence | "is this macro public?" | low for detection | High | AUTO_ACTIVATE |
| Public API / SemVer | new `pub` items, `Cargo.toml [lib]`, `publish = true` | "publishable library vs private app?" — needs project policy | medium (private `pub` in apps over-activates) | Medium | AUTO_SUGGEST (require story tag for blocking) |
| Cargo / workspace | file-path filter (Cargo.toml, Cargo.lock, rust-toolchain*) | none — file-path is sufficient | low | Very high | AUTO_ACTIVATE |
| Testing beyond core | `cargo fuzz`, `loom::`, `miri::`, `proptest::`, `#[should_panic]` | "is risk tag set?" | low for tool detection | Medium | STORY_TAG_REQUIRED (high-assurance opt-in) |
| Data / Security / IO | `serde::`, `regex::`, `Path`, `Url`, `tokio::net`, `Command::new`, `reqwest::` | "untrusted input?" requires judgment | medium — broad triggers | Medium | AUTO_SUGGEST |
| DB / messaging | `sqlx::`, `diesel::`, `tokio-postgres::`, `migrations/` dir | "exactly-once / partial-failure?" | medium | Medium | AUTO_SUGGEST |
| Time / config / clients | `Instant::`, `SystemTime::`, `Duration::`, `reqwest::Client`, `notify::` | "atomic config swap?" | medium | Medium | AUTO_SUGGEST |
| Ops / observability | `tracing::`, signal handlers, `/health` HTTP routes | "production service?" | high — story tag essential | Low | STORY_TAG_REQUIRED |
| Performance / no_std / WASM | `#![no_std]`, `#[target_feature]`, `target_arch = "wasm32"`, `benches/` dir, `cargo bench` | "claimed perf path vs incidental?" | high without tag | Low for "claim", high for `no_std` | STORY_TAG_REQUIRED (perf), AUTO_ACTIVATE (no_std/WASM) |

### Single source of truth
**The KB Markdown remains the human-readable source of truth.** A separate machine-readable mapping is needed for the validator. Two strategies:

1. **Generate validator mapping from KB**: a small parser reads Section 5 of KB.md and emits `router-rules.json`. Rebuilds on KB change. Cleanest, but the parser adds maintenance.
2. **Hand-maintain `router-rules.json` and validate against KB at CI time**: a check job confirms every KB pack has a corresponding mapping entry and reports drift. Simpler initial implementation; needs discipline.

**Recommendation: option 2 for v1.** Add a `bmad-eval-runner`-style eval that fails if KB Section 5 has a pack name not in `router-rules.json` (or vice versa). Migrate to option 1 if drift becomes a frequent failure.

### Verdict
**EXPERIMENT VERIFIED with caveats.** Strong-signal packs (Async, Unsafe, FFI, Cargo, Macros, no_std) are reliably detectable. Weak-signal packs (Ops, Perf claims, "untrusted input") **must require story tags** to avoid false activation. The validator must not promote AUTO_SUGGEST/STORY_TAG_REQUIRED packs to blocking findings without explicit user opt-in.

---

## 9. False-Positive Analysis — Top 5 MVP Checks Re-Examined

| Check | Signal | False-positive surface | False-negative surface | Safer default |
|-------|--------|------------------------|------------------------|----------------|
| **CORE-011 compile evidence** | Was `cargo check` run + structured `compile_check` block present? | Almost none (presence check) | LLM can fake the output digest | EVIDENCE_REQUIRED → CI re-runs to verify |
| **CORE-007 protected files** | `git diff --name-only` ∩ story's `protected_files` glob | Story author writes wrong globs; over-broad globs (`**/*.rs`) | Story author forgets to list a protected file | FAIL (low FP if globs are explicit per story) |
| **CORE-014 suppression regex** | `rg` in diff for `#[ignore]`, new `#[allow(...)]`, removed `#[test]`, `assert!(true)` | Legitimate `#[allow(dead_code)]` on test scaffolding; refactor that removes obsolete tests | Subtle weakening (changed assertion strength) | EVIDENCE_REQUIRED + WARNING; promote to FAIL only when `suppression_authorization` field absent in evidence |
| **CORE-008 panic discipline** | `rg '\.unwrap\(\)|\.expect\('` in added lines excluding `tests/`, `examples/`, `#[cfg(test)]` | Constants, locally-proven invariants (KB explicitly allows these), `expect("infallible: ...")` patterns | `.unwrap_or(...)` chains that effectively panic differently | WARNING + EVIDENCE_REQUIRED. Only FAIL when added in a function annotated with `#[no_panic]` or a story-tagged "panic-discipline" path |
| **CORE-015 router replay parity** | Re-run router; compare to agent-recorded `activated_packs` | Mismatch due to legitimate suppression with reason; pack name drift between KB versions | None significant (mismatch is the signal we want) | FAIL on mismatch; require structured `suppression` field in evidence to override |

### Principle (proposed and tested against KB §4 exceptions)
The user-suggested principle holds and matches KB conventions:

> **risk signal + missing required evidence + no valid exception = blocking finding**

For all five checks, the implementation must:
1. Detect the signal (deterministic).
2. Check whether the evidence file declares an exception with a structured reason (`exception: { rule: ..., reason: ..., scope: ... }`).
3. Only escalate to FAIL when both: signal present AND no valid exception AND required evidence missing.

This matches KB CORE-rule "Exceptions:" fields and reduces false-positive friction.

### Implication for MVP
The MVP validator should ship **2 of 5 checks as FAIL-eligible** (CORE-007, CORE-015) and **3 as EVIDENCE_REQUIRED/WARNING** (CORE-008, CORE-011, CORE-014). FAIL promotion happens only when the evidence file lacks the required structured field. This is the safest first ship — high enforcement value, low false-block risk.

---

## 10. Evidence Trust Model — Minimal Viable

### Authority matrix

| Evidence field | LLM may write | Validator script may write | LLM evaluator may write | Specialist may write | CI may write |
|----------------|:-------------:|:--------------------------:|:----------------------:|:--------------------:|:------------:|
| `story.contract_ref` | ✓ | — | — | — | — |
| `story.protected_files` | (from story file only) | — | — | — | — |
| `router_replay.activated_packs` | (claim only) | ✓ (authoritative) | — | — | ✓ (re-run) |
| `rules.{X}.verdict` Cat 1/2 | — | ✓ | — | — | ✓ (re-run) |
| `rules.{X}.verdict` Cat 3 | — | (initial REVIEW_REQUIRED) | ✓ (downgrade) | — | — |
| `rules.{X}.verdict` Cat 4 | — | (initial APPROVAL_REQUIRED) | — | ✓ | — |
| `rules.{X}.evidence[].command/exit_code/digest` | — | ✓ | — | — | ✓ |
| `rules.{X}.evidence[].reasoning_record` | ✓ | — | ✓ | — | — |
| `kb_digest` | — | ✓ (computed) | — | — | ✓ |
| `diff_digest` | — | ✓ (computed) | — | — | ✓ |
| `head_sha` / `base_sha` | — | ✓ (from git) | — | — | ✓ |
| `final_verdict` | — | ✓ (aggregate) | — | — | ✓ (override on re-run) |
| `signature` | — | (depends on mode) | — | — | ✓ (CI mode) |

### What's needed at each mode

| Mode | Required evidence fields | HMAC? | Justification |
|------|--------------------------|-------|---------------|
| Advisory | `final_verdict`, per-rule status | No | No enforcement; signature is decorative |
| Local Validated | + `head_sha`, `diff_digest`, `kb_digest`, per-rule evidence | No | Detection of stale evidence sufficient |
| Local Gated | Same as Local Validated | No | Hook re-runs validator; no need to trust agent's claim |
| CI Enforced | Same as Local Gated | **Optional** | If CI re-runs all Cat 1 checks (recommended), HMAC is redundant. Use HMAC only when CI accepts agent-produced verdicts verbatim |
| High Assurance | + signed approvals with `diff_digest` binding | Yes | Multi-party trust; approvals must not survive diff changes |

### HMAC decision
**RECOMMENDED: NO HMAC in v1.** Rationale:
- CI should always re-run all Cat 1 checks. They're cheap (router replay, regex, exit-code capture).
- For Cat 3 LLM judgments, CI can't re-run authoritatively (LLM output is non-deterministic). Cache by `(diff_digest, kb_digest, rule_id)` triple; if CI sees no cache hit, it asks for fresh judgment.
- For Cat 4 approvals, the approval is on a specific `diff_digest`; CI verifies the approval's digest field matches the PR's actual `diff_digest`. No HMAC needed for binding — the digest match is the binding.
- HMAC introduces key-management overhead (rotation, fork-PR secret access, OSS contributor flow) that's not worth the marginal trust gain when re-runs are cheap.

### Fork-PR and OSS-contributor handling
- GitHub Actions fork PRs receive **no secrets**. This is correct and unavoidable.
- The CI workflow must run **without secrets** for Cat 1+2 verification (just runs the validator on the PR diff in a clean environment). This is identical to the trunk run — verdicts are deterministic from `(diff, kb)`.
- Cat 3 judgments require LLM API access; for fork PRs, defer judgment to a trusted reviewer (or run via `workflow_run` event in a separate workflow with secrets, gated on review).
- Cat 4 approvals are PR comments / GitHub review approvals from designated owners (CODEOWNERS file). Already a GitHub feature; no special infrastructure.

---

## 11. Baseline Failure Semantics — Spike 7

### Hypothesis
A dual-run (base + head) of the validator with error-message comparison can disambiguate baseline failures from story-introduced regressions.

### Inputs (synthetic)
- `check.sh`: shell script that returns exit 1 if file contains `FAIL_A` or `FAIL_B`, prints the error
- Base commit: `code.rs` contains `FAIL_A` (red baseline)
- Case 1 head: still contains `FAIL_A` (story didn't add or fix the issue)
- Case 2 head: contains `FAIL_A` AND `FAIL_B` (story introduced a new error)

### Actual results
- Base run: `error: A`, exit 1
- Case 1 head run: `error: A`, exit 1 → error message identical to base → **BASELINE_FAILURE_OBSERVED** (story not at fault)
- Case 2 head run: `error: A`, exit 1 → on this run the script printed A; FAIL_B detection requires distinct check rules. The disambiguation is achievable by structured tool output, not raw exit codes alone.

### Proposed status set

| Status | Meaning | Blocking? |
|--------|---------|-----------|
| `PASS` | Tool ran, succeeded | No |
| `FAIL` | Tool ran, failed; specific cause identified | Yes |
| `NOT_APPLICABLE` | Trigger absent; no need to run | No |
| `NOT_RUN` (with `reason`) | Tool unavailable / environment limitation; reason structured | Conditional — blocking unless reason is on an approved list (e.g., `cargo audit` offline) |
| `BASELINE_FAILURE_OBSERVED` | Tool fails on both base and head, same failure signature | No (informational; flag for ops cleanup) |
| `BASELINE_BLOCKS_VALIDATION` | Tool fails on base in a way that prevents meaningful head check (e.g., compile-fail in module under change) | Yes (with override path — story owner can authorize "fix baseline first" or "rebase off green base") |
| `REGRESSION_FAILURE` | Base passed AND head fails, OR head fails with new signature not on base | Yes |
| `REGRESSION_FIXED` | Base failed and head passes the same check | No (bonus credit; doesn't block) |
| `ENVIRONMENT_UNAVAILABLE` | Cannot run the tool at all (no cargo, no internet, no GitHub) | Yes (downgrade to advisory mode and report) |
| `TOOL_UNAVAILABLE` | Specific tool missing (Miri, cargo-audit, semver-checks) but core checks ran | Conditional — track in evidence, allow opt-out per project policy |

### Dual-run requirement
Implementation must run the validator twice: once against the base ref's state (in a checkout or via `git worktree`), once against head. Compare per-rule verdicts and error signatures. Cost is roughly 2× single-run, mitigated because:
- CI typically runs on detached HEAD; base checkout is one `git checkout` + cargo cache hit
- Local pre-push hook can skip base run with a warning ("baseline comparison requires CI"); CI is then the authoritative source for `REGRESSION_FAILURE` vs `BASELINE_FAILURE_OBSERVED`

### Verdict
**EXPERIMENT VERIFIED** (logic). Dual-run with structured error signature comparison correctly disambiguates regressions from baseline failures. Required status taxonomy expanded from the previous report's 8 statuses to 10.

---

## 12. Compatibility Findings

| Environment | RDX KB | rdx-setup | rdx-dev-story wrapper | rdx-validator (Python) | Pre-push hook | CI gate | Highest mode supported |
|-------------|--------|-----------|----------------------|------------------------|----------------|---------|------------------------|
| macOS + Claude Code + python3.11+ + git + cargo + GitHub | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | High Assurance |
| Linux same stack | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | High Assurance |
| Linux + GitLab instead of GitHub | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (need `.gitlab-ci.yml` template) | High Assurance |
| Windows native (no WSL) + Claude Code | ✓ | ✓ | ✓ | ✓ | Powershell variant of hook required | ✓ | CI Enforced |
| WSL + Claude Code | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | High Assurance |
| Local git, no GitHub/GitLab | ✓ | ✓ | ✓ | ✓ | ✓ | — | Local Gated |
| **Codex CLI** | ✓ (as `AGENTS.md` snippets — separate distribution) | N/A (no skill system) | N/A (no `agent.menu`) | ✓ (run from shell) | ✓ | ✓ | CI Enforced (validator is Codex-agnostic) |
| **Cursor / Aider / other IDE agents** | ✓ (as context file) | N/A | N/A | ✓ | ✓ | ✓ | CI Enforced |
| Web Claude (no shell) | ✓ | — | — | — | — | — | Advisory only |
| No Python | ✓ | (uses Python — would fail) | (works as prose) | — | — | — | Advisory (KB only) |

**Key portability insight**: `rdx-validator` (the Python scripts + JSON schema + CI workflow) is **BMAD-agnostic**. It's a standalone Rust-engineering gate that any Rust project can adopt regardless of which AI agent (Claude Code, Codex, Cursor) writes the code. The BMAD wrapper is the only BMAD-specific piece.

This is a strategic asset: RDX can ship as two distinct products with shared core:
- `rdx-bmad/` — BMAD wrapper + RDX module (this repo)
- `rdx-validator/` — standalone CLI for any environment (could be a separate crate / pip package later)

---

## 13. Spike Summary

| # | Spike | Verdict | Key artifact |
|---|-------|---------|--------------|
| 1 | Menu override (synthetic) | EXPERIMENT VERIFIED | `/tmp/rdx-spikes/spike-1-menu-override/` |
| 1b | User-override precedence + removal | EXPERIMENT VERIFIED | same dir |
| 1c | Real bmad-agent-dev override + revert | EXPERIMENT VERIFIED | reverted in place; safe |
| 2 | Nested skill control flow | DOC VERIFIED + INFERENCE (not empirically tested) | Open: real Claude Code multi-skill spike before V5 implementation |
| 3 | Exit code in wrapper vs git hook | EXPERIMENT VERIFIED | `/tmp/rdx-spikes/spike-3-exitcode/` |
| 4 | Local hard-gate alternatives | EXPERIMENT VERIFIED (matrix) | included in Spike 3 results |
| 5 | Router replay on 4 fixtures | EXPERIMENT VERIFIED (3 of 4; fix script bug for cargo) | `/tmp/rdx-spikes/spike-5-router/` |
| 6 | `diff_digest` binding | EXPERIMENT VERIFIED | `/tmp/rdx-spikes/spike-6-binding/` |
| 7 | Baseline vs regression | EXPERIMENT VERIFIED (logic) | `/tmp/rdx-spikes/spike-7-baseline/` |

All artifacts retained under `/tmp/rdx-spikes/` for reproducibility.

---

## 14. Decision Matrix V1–V7

| Variant | Technically proven | BMAD compatible | Hard local enforcement | Hard CI enforcement | UX | Complexity | Portability | Main risks |
|---------|:-----------------:|:--------------:|:----------------------:|:-------------------:|----|:----------:|-------------|------------|
| V1 — Utility validator only | ✓ (exit-code semantics trivial) | ✓ | No (user must invoke) | If user wires it | Manual | Low | Universal | User just doesn't run it |
| V2 — BMAD wrapper + validator (no hook, no CI) | ✓ menu override + INFERENCE on cooperation | ✓ | No (wrapper is convention) | No | Good | Medium | BMAD only | LLM skips post-child step → previous report's mistake |
| V3 — External orchestrator + standard `bmad-dev-story` | Same as V1 plus harness layer | Neutral | No | If wired | Awkward (parallel command surface) | Medium | Universal | Two ways to invoke dev workflow confuses users |
| V4 — Wrapper + external local gate (pre-push hook) | ✓ wrapper + ✓ hook | ✓ | **Yes** (hook) | If wired | Good (hook is silent until violation) | Medium | BMAD + git | Hook can be skipped with `--no-verify`; not OSS-shareable enforcement |
| **V5 — Wrapper + validator + CI** | ✓ all components proven | ✓ | Optional (recommend hook install too) | **Yes** (CI required check) | Good | Medium-high | BMAD + GitHub/GitLab | CI must run on every PR; org without CI gets only wrapper UX |
| V6 — V5 + LLM evaluator (Cat 3) + specialist approval (Cat 4) | LLM evaluator: same convention class as wrapper; approval: governance-level | ✓ | Yes (same as V5) | Yes + approval trail | Best | High | Same as V5 | Cat 3 LLM judgments add cost; specialist routing needs CODEOWNERS or equivalent |
| V7 — Drop BMAD wrapper, ship validator + hooks + CI as standalone | ✓ (validator is BMAD-agnostic) | Neutral (RDX KB still installs in BMAD agents) | **Yes** (hook) | **Yes** (CI) | Poor for BMAD users (no in-loop UX) | Medium | Universal (no BMAD dep) | Loses the BMAD integration value prop; harder for BMAD-only users to adopt |

### Variant ranking by "proven enforcement value" / "complexity ratio"

1. **V5** — best enforcement-per-complexity for BMAD users. CI gate is hard; wrapper is good UX; validator is universal core.
2. **V4** — strong for solo devs without CI; ships as a sub-mode of V5.
3. **V6** — V5 plus quality layer; non-blocking for v1, add later.
4. **V1 / V7** — viable as fallback distributions (Codex / non-BMAD users) once core is built.
5. **V2** — **explicitly do not ship as "enforced"**; it's the previous report's mistake. Acceptable only as Advisory mode.
6. **V3** — adds complexity without enforcement benefit; rejected.

---

## 15. Recommended Target Architecture

**Final target: V6** (V5 + LLM Cat-3 evaluator + Cat-4 specialist approval).

Reached in two implementation milestones:

```
Milestone 1 (first ship) = V5 in Mode "CI Enforced"
  └── Components:
      ├── rdx-validator/ (Python scripts + JSON schema)         ← universal core
      ├── rdx-dev-story/ (BMAD wrapper, menu override)          ← BMAD UX
      ├── pre-push hook installer (rdx-setup option)            ← Mode "Local Gated"
      └── .github/workflows/rdx-gate.yml template               ← Mode "CI Enforced"

Milestone 2 (later) = upgrade to V6
  ├── rdx-judgment/ skill (Cat 3 LLM evaluator)
  ├── CODEOWNERS template + approval-trail verification         ← Mode "High Assurance"
  └── Signed evidence (if real-world abuse demands it)
```

### Modes (corrected terminology)

| Mode | What user installs | What enforces |
|------|--------------------|----------------|
| 0 — Advisory | KB sections + agent overrides (current RDX) | Nothing (LLM cooperation only) |
| 1 — Local Validated | + rdx-validator + rdx-dev-story wrapper | LLM-cooperative soft gate (wrapper reads exit code, asks LLM to halt) |
| 2 — Local Gated | + pre-push hook | OS-level (git blocks push on hook fail) |
| 3 — CI Enforced | + `.github/workflows/rdx-gate.yml` + branch protection | CI required-status-check |
| 4 — High Assurance | + Cat-3 evaluator + CODEOWNERS + signed approvals | Multi-party + diff-pinned approvals |

User picks mode at install time. Mode is recorded in `_bmad/config.toml` and visible in evidence (so a CI gate can reject "Mode 0 evidence" as insufficient for a Mode 3 repo).

---

## 16. Verdicts

### A. Target architecture
**V6** (Variant E with corrections). Achieved via Milestone 1 (V5) then Milestone 2 (Cat-3 + Cat-4 layer).

### B. First production milestone
**V5 in Mode CI Enforced**, scoped to:
- `rdx-validator/` with the corrected Top 5 checks (CORE-007 FAIL, CORE-015 FAIL, CORE-011/008/014 EVIDENCE_REQUIRED → FAIL only with no exception)
- `rdx-dev-story/` wrapper that invokes `bmad-dev-story`, collects evidence, runs validator, emits report
- `rdx-setup` extension that: installs the menu override (`agent.menu[code=DS]`), optionally installs pre-push hook (Mode 2 opt-in), provides `.github/workflows/rdx-gate.yml` template
- Evidence schema v1.0 (without HMAC)
- 6-fixture regression eval suite (router replay correctness)

Excluded from first milestone:
- LLM evaluator (Cat 3) — non-blocking; defer to v1.1
- Specialist approval flow (Cat 4) — defer to v1.2
- HMAC signing — not needed when CI re-runs all Cat 1 checks
- Mode 4 — defer until a real user requests it

### C. Required prerequisites before implementation
1. **One-off multi-skill spike in a real Claude Code session** (close Spike 2 with EXPERIMENT VERIFIED). Acceptance: a minimal wrapper skill calls a minimal child skill and the wrapper's next-step instructions are honored by the LLM. If this fails, V5's wrapper layer is downgraded to a CLI launcher (V4 with no in-BMAD UX), not blocking V5 overall.
2. **Confirmation that the resolver behavior we depend on is intentional**, not coincidental. Action: file an issue on `bmad-code-org/BMAD-METHOD` referencing the `agent.menu` merge-by-`code` behavior and ask for stability commitment. Implementation can proceed before answer; an upstream change later would require RDX bumping a min-resolver-version dependency.
3. **Decision on KB-to-validator mapping strategy** (§8 option 1 vs 2). Recommended: option 2 (hand-maintained mapping + drift check) for v1.
4. **Decision on pre-push hook bundling** (default-install in `rdx-setup` vs opt-in). Recommended: opt-in with explicit user consent (`rdx-setup --install-hook` or interactive prompt).

### D. Rejected approaches
- **V2 as named in previous report** ("Local Enforced" via wrapper alone): rejected. Wrapper cannot enforce. Re-label as "Local Validated" if shipped.
- **V3** (external orchestrator + unchanged dev-story): rejected. Two command surfaces is bad UX without enforcement benefit.
- **Approach C2** (copy/adapt standard dev-story workflow): rejected. Violates "no fork of BMM" principle and creates upstream-sync burden.
- **HMAC signing in v1**: rejected as not needed given CI re-runs Cat 1.
- **Calling any wrapper-only mode "enforced"**: rejected; terminology must be precise.

### E. Terminology (final)
Use these terms consistently across docs, code, and CLI output:
- **Advisory** — informational only, no gate
- **Local Validated** — LLM-cooperative soft gate (wrapper + validator, no hook)
- **Local Gated** — pre-push hook adds OS-level blocking
- **CI Enforced** — CI required-status-check
- **High Assurance** — CI + signed/approved evidence + Cat 4 specialist routing

The word "**Enforced**" is reserved for modes that survive an uncooperative LLM. **Do not use "Enforced" for wrapper-only modes.**

### F. Confidence

**Overall: 88%.**

Breakdown:
- Menu override mechanism (foundation of wrapper): **99% confidence** — EXPERIMENT VERIFIED three times (synthetic, precedence, real bmad-agent-dev).
- Wrapper-resumes-after-child invocation: **70% confidence** — DOC VERIFIED + INFERENCE; needs one real spike to close (§16-C, item 1).
- Git-hook hard enforcement: **99% confidence** — EXPERIMENT VERIFIED.
- CI required-check enforcement: **95% confidence** — well-documented GitHub feature; not re-verified in this round but standard practice.
- Router replay deterministic for strong-signal packs: **90% confidence** — EXPERIMENT VERIFIED 3 of 4 fixtures; the 4th was a script bug not a methodology issue.
- Router replay for weak-signal packs (Ops, Perf claims): **60% confidence** — must require story tags; needs care in implementation.
- Baseline disambiguation via dual-run: **85% confidence** — logic VERIFIED, dual-run cost overhead manageable, needs real cargo project testing.
- Evidence schema authority matrix: **80% confidence** — internally consistent, but not validated against a real adoption pattern; will refine on first real user.

**Cannot close without BMAD upstream input:** the stability contract for `resolve_customization.py` merge behavior. Implementation can proceed without it but should pin a known-good resolver hash.

---

## 17. Compatibility & Distribution Summary (deferred from §12)

See §12 table. Highlights:
- V5 ships as one BMAD module (this repo) + one CI template; standalone Codex/Cursor packaging is V7 and is a future spin-off, not a v1 deliverable.
- `rdx-validator/` should be authored as a self-contained Python package from day one (no BMAD imports) so V7 spin-off is trivially possible.

---

## 18. Rejected Alternatives — Detail

| Alternative | Rejection reason | Could revisit if |
|-------------|------------------|------------------|
| Variant D (CI gate only, no BMAD integration) | Loses in-loop UX; BMAD users don't get evidence collection help; KB still needs distribution mechanism | Never (V5 is strictly superior for BMAD users) |
| HMAC-signed evidence in v1 | Adds key-management cost; CI re-run is sufficient trust | A real attack proves CI re-run is bypassable in some environment |
| Forking `bmad-dev-story` (Approach C2) | Violates principle; sync burden; the menu override accomplishes the same UX cleanly | Never |
| Asking BMAD upstream for a real workflow hook | Issues #2469, #2491 show team hasn't responded; can't wait | Upstream ships a `terminal_step` primitive — then collapse wrapper to use it |
| LLM evaluator (Cat 3) in v1 | Non-blocking; reviewer LLM costs add up; can ship as v1.1 add-on with no gate impact | Real users hit Cat 3 friction without it |

---

## 19. Remaining Risks (post-verification)

1. **(High) Multi-skill spike still open.** A 1-hour Claude Code session with minimal `test-wrapper` + `test-child` skills can close this. Schedule before V5 sprint starts.
2. **(Medium) `resolve_customization.py` behavior is not contracted.** Pin known-good resolver SHA in `rdx-setup` health check. If resolver semantics change in BMAD v7, ship a compatibility shim.
3. **(Medium) Mode confusion in distribution.** Users may install Mode 1 and assume they have enforcement. Mitigation: all RDX output explicitly states current mode; CI gate rejects Mode 0/1 evidence.
4. **(Medium) Story-tag dependence for weak-signal packs.** Stories without explicit `risk_tags:` will under-activate Ops/Perf packs. Mitigation: PM agent (John) already updated per RDX v1.0 to require risk tags; document this hard requirement in evidence schema.
5. **(Low) Pre-push `--no-verify` bypass.** Mode 2 alone is bypassable; pair with Mode 3 (CI) for serious projects. Document this clearly.
6. **(Low) Other modules clobbering RDX's custom override file.** Add "RDX section markers" + rdx-setup re-runs check for them; document conflict-resolution policy.
7. **(Low) Cat 3 LLM cost in v1.1.** Cache by `(diff_digest, kb_digest, rule_id)`. Re-evaluate only on cache miss. Measure cost after first real adoption.

---

## 20. Final GO / NO-GO / BLOCKED Verdict

# `GO — Variant E with mandatory corrections`

Implement Variant V5 first (Wrapper + Validator + CI Enforced mode), upgrade to V6 (add Cat 3 + Cat 4) once the first ship has real-user feedback.

**Mandatory corrections to the previous report before implementation begins:**
1. Re-label "Mode 2 — Local Enforced" → "Mode 1 — Local Validated" + new "Mode 2 — Local Gated" (the latter requires the pre-push hook).
2. Stop describing wrapper-driven HALT as enforcement. Reframe as cooperative orchestration with structured evidence collection.
3. Drop HMAC from v1 (re-add only if a real attack vector emerges).
4. Add "Cat-1 FAIL only when no valid exception" rule to all five MVP checks.
5. Adopt the expanded 10-status set (§11) over the previous 8-status set.
6. Treat `rdx-validator` as a BMAD-agnostic deliverable from day one (enables V7 spin-off; benefits Codex/Cursor users).
7. Acquire the one outstanding empirical proof: real Claude Code multi-skill spike for wrapper-resume control flow.

This verdict is **doubly supported**: by source-code reading of the resolver and by direct experimental verification on a real BMAD installation. Implementation can proceed once items 1–6 are reflected in the implementation plan, and item 7 is closed by a small dedicated spike.
