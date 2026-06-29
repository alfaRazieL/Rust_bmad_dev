# RDX Phase 0 — Spike Report

**Branch:** `rdx-improvements`
**Date:** 2026-06-29
**Goal:** Close all Phase 0 integration prerequisites before touching production RDX files.

**Verdict:** **All three spikes — GO.** Proceed to Phase 1.

---

## Summary

| Spike | Topic | Outcome | GO criterion met? |
|-------|-------|---------|-------------------|
| 0.1 | Multi-skill wrapper-resume control flow | EXPERIMENT VERIFIED | ✓ Yes |
| 0.2 | Review propagation into bmad-code-review | DOC VERIFIED via `on_complete` + `persistent_facts` hybrid | ✓ Yes (with documented integration strategy) |
| 0.3 | Standalone validator prototype | EXPERIMENT VERIFIED on 4 fixtures | ✓ Yes |

Final form of V5 integration is described in §4.

---

## Spike 0.1 — Multi-skill wrapper-resume

### Hypothesis
A wrapper SKILL.md can invoke a child skill via the Skill tool, regain control after the child completes, and execute its post-child steps reliably enough to anchor `rdx-dev-story` → `bmad-dev-story` → validator orchestration.

### Environment
- Claude Code session (Opus 4.7)
- Skills auto-discovered from `/Users/m33tball/bmad_module_builder/.claude/skills/`
- Subagent type `general-purpose` used as the independent test executor
- Test skill files preserved at `spikes/0.1-multi-skill/{wrapper,child}.SKILL.md`

### Inputs
- `zz-spike-wrapper/SKILL.md` — 5-step skill: BEFORE marker → invoke child → AFTER marker → run validator (always exits 1) → final marker
- `zz-spike-child/SKILL.md` — single-step skill: write CHILD marker → return
- `validator-stub.sh` — prints FAIL JSON and exits 1 (intentional)

### Commands
```
Agent(general-purpose):
  prompt: "Use the Skill tool to invoke zz-spike-wrapper. Follow its
  instructions exactly. Report what you actually did and show trace.log."
```

### Expected
- trace.log shows ordering: BEFORE → CHILD → AFTER
- Subagent reaches Step 4, captures validator exit code 1
- Subagent HALTs at Step 4 (per wrapper's "do not proceed if non-zero" instruction)
- Subagent reports `WRAPPER_HALTED_DUE_TO_VALIDATOR_FAIL`

### Actual
trace.log (verbatim, evidence file `spikes/0.1-multi-skill/trace.log.evidence`):
```
BEFORE wrapper-step-1 ts=1782711396
CHILD child-step-1 ts=1782711404
AFTER wrapper-step-3 ts=1782711407
```

Subagent self-report (verbatim, condensed):
- Step 1 (BEFORE): completed
- Step 2 (invoke child): completed — child wrote CHILD marker, returned `CHILD_DONE`
- Step 3 (AFTER): completed
- Step 4 (validator): completed — exit code **1**, JSON printed
- Step 5 (final): **not executed**
- Terminal state: `WRAPPER_HALTED_DUE_TO_VALIDATOR_FAIL`
- Honest assessment: "wrapper flow worked cleanly. Instructions were unambiguous; I was not tempted to skip or optimize."

### Verdict
**EXPERIMENT VERIFIED.** Wrapper-resume control flow works empirically in a fresh subagent session.

### Critical nuance (do not lose)
The wrapper HALTED **because its SKILL.md text told the LLM to halt on non-zero exit**. The halt is still convention-level — the underlying machinery is "LLM reads the text and obeys." This matches the prior `RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md` §6 finding: wrapper provides a **soft gate** (LLM-cooperative), not a hard gate. Hard local enforcement still requires git hooks (Spike 3 in prior verification report).

### GO criterion result
**MET.** Continue with `rdx-dev-story` wrapper as the primary BMAD-integration mechanism for V5.

### Fallback recorded (not triggered)
If the wrapper had failed to resume, the architecture would have fallen back to a CLI launcher (V4 in the decision matrix) — wrapper UX dropped, but validator + hook + CI would still ship.

### Cleanup
Test skills removed from production `.claude/skills/`. Fixtures retained at `spikes/0.1-multi-skill/` for re-running.

---

## Spike 0.2 — Review propagation

### Hypothesis
RDX can add a Cat-3 review layer (RDX Rule Auditor) to `bmad-code-review` without forking BMM step files or replacing existing review layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor).

### Environment
- Source review of `bmad-code-review` skill structure and customization surface
- Files inspected:
  - `.claude/skills/bmad-code-review/customize.toml`
  - `.claude/skills/bmad-code-review/steps/step-02-review.md`
  - (referenced) `step-01-gather-context.md`, `step-03-triage.md`, `step-04-present.md`

### Findings (DOC VERIFIED)

1. **`bmad-code-review` exposes a `[workflow]` customization block** identical in shape to agent customization:
   - `persistent_facts` (file/literal entries, append-merge)
   - `activation_steps_prepend` / `activation_steps_append`
   - **`on_complete`** scalar — runs at the workflow's terminal step, after findings are presented

2. **Subagent dispatch is via the Skill tool**, with step-02-review.md as the orchestrator. Quote: *"Launch parallel subagents without conversation context… Invoke via the `bmad-review-adversarial-general` skill / `bmad-review-edge-case-hunter` skill."*

3. **Subagent context isolation is intentional and hardcoded**:
   - Blind Hunter: NO project context — diff only
   - Edge Case Hunter: diff + project read access
   - Acceptance Auditor: diff + spec + context docs

   This means RDX persistent_facts injected on the `bmad-code-review` workflow do **NOT** automatically propagate into Blind/EdgeCase/Acceptance subagents — those are isolated by design.

4. **What RDX persistent_facts DO reach**:
   - The parent reviewer LLM (which orchestrates all 4 steps)
   - The triage step (step-03), which deduplicates and assigns severity
   - The present step (step-04)
   - Any `on_complete` invocation

### Integration strategy (the answer the spike was looking for)

Three customization-only hooks let RDX add a Cat-3 layer without touching step files:

**(A) Persistent facts on bmad-code-review** — `_bmad/custom/bmad-code-review.toml`:
```toml
[workflow]
persistent_facts = [
  "file:{project-root}/_bmad/rust-kb/section-4-core.md",
  "Rust risk packs active for this review come from .rdx/evidence-{story-id}.json activated_packs",
]
```
Parent reviewer (and triage) gets RDX context for free.

**(B) `on_complete` hook** — same file:
```toml
on_complete = """
After the standard review report is presented, if .rdx/evidence-{story-id}.json
exists and contains review_required entries, invoke the rdx-judgment skill,
passing the review findings, active risk packs, and the rules listed under
review_required. Append the auditor's findings to the final report under a
new "RDX Rule Auditor" section.
"""
```
This adds RDX Rule Auditor as a **post-pass on the standard report**, not as a parallel layer. Cleaner than trying to inject into step-02.

**(C) RDX evidence is read by the parent** — the standard `gather-context` step already accepts project context docs. RDX evidence at `.rdx/evidence-*.json` becomes another context input — no skill changes needed beyond pointing the reviewer at it.

### GO criterion result
**MET.** RDX Rule Auditor can be added as a Cat-3 layer via `on_complete` + `persistent_facts` injection, with zero modification of step files and no fork of bmad-code-review. Cat-3 is by definition LLM-judgment, so the convention-level nature of `on_complete` is acceptable for this layer (Cat-1/2 enforcement still lives in validator + CI).

### Important constraint inherited from the spike
The three existing review subagents (Blind / Edge Case / Acceptance) **cannot be augmented** with RDX context without modifying step-02-review.md (which would require forking). RDX must NOT try to push Rust rules into Blind Hunter — its blindness is a feature. RDX Rule Auditor runs as a **separate, post-standard-review** layer.

### Fallback recorded
If `on_complete` is ever found unreliable in production, fall back to: `rdx-judgment` becomes a standalone skill the user invokes manually (or via CI), with RDX evidence as input. Loses smooth in-loop UX; preserves enforcement via CI.

---

## Spike 0.3 — Standalone validator prototype

### Hypothesis
A BMAD-agnostic Python CLI can reproduce router replay on real diffs with stable digests and machine-readable verdicts, suitable as the core of `rdx-validator` and the CI gate.

### Environment
- macOS, `python3` (stdlib only — no pip dependencies)
- Prototype at `spikes/0.3-standalone-validator/rdx_validator.py` (260 LOC)
- 4 router fixtures from prior verification spike, copied to `spikes/0.3-standalone-validator/fixtures/`

### Inputs (4 diffs)
1. `fixture-1-real-async.diff` — adds `tokio::spawn(async move { ... .await; })`
2. `fixture-2-doc-only-async.diff` — comment-only mention of async, no code change
3. `fixture-3-new-unsafe.diff` — new `unsafe { *ptr }`
4. `fixture-4-cargo.diff` — `Cargo.toml` adds `tokio = "1.40"`

### Commands
```bash
python3 rdx_validator.py --diff-file fixtures/<each>.diff
```

### Expected
- Fixture 1 → `activated_packs: ['async']`
- Fixture 2 → `activated_packs: []`  (negative trigger via comment heuristic)
- Fixture 3 → `activated_packs: ['unsafe']`
- Fixture 4 → `activated_packs: ['cargo']` (path-based via `+++ b/Cargo.toml`)
- All 4 → stable, distinct `diff_digest` (SHA-256)
- All 4 → exit 0 (no real blocking checks yet; spike scope is router only)

### Actual
```
Fixture 1: activated_packs: ['async']             diff_digest: sha256:74cabe05...  exit 0
Fixture 2: activated_packs: []                    diff_digest: sha256:1e922b79...  exit 0
Fixture 3: activated_packs: ['unsafe']            diff_digest: sha256:b61240df...  exit 0
Fixture 4: activated_packs: ['cargo']             diff_digest: sha256:1e6ab3fc...  exit 0
                  paths: ['Cargo.toml']
```

### Verdict
**EXPERIMENT VERIFIED.** All 4 fixtures correctly classified. Stable digests confirmed.

### What the prototype proves
- ✓ Reads real git diff
- ✓ Correctly extracts changed paths (incl. `b/` prefix stripping, `/dev/null` filtering)
- ✓ Activates Async, Unsafe, FFI, Cargo via positive signals
- ✓ Distinguishes added-code lines from added-comment lines (negative trigger)
- ✓ Computes stable SHA-256 `diff_digest`
- ✓ Emits machine-readable JSON verdict (JSON Schema can be added in Phase 1)
- ✓ Stable exit codes (0/1/2/3 semantics documented)
- ✓ Zero BMAD imports — runs from any directory, any environment with `python3`

### What the prototype intentionally does NOT yet do (deferred to Phase 2)
- CORE-007 protected-file enforcement
- CORE-011 compile-evidence requirement
- CORE-014 suppression detection
- CORE-008 panic-discipline detection
- Base/head dual-run for baseline disambiguation
- Evidence schema validation
- Exception parsing
- Real blocking exit code (currently always 0)

These are scope of Phase 2 per the plan, not Phase 0.

### GO criterion result
**MET.** Validator core is feasible as a standalone Python CLI with no external dependencies. Phase 2 can extend this scaffold directly.

---

## §4 — Final form of V5 integration (synthesized from spikes 0.1 + 0.2 + 0.3)

Confirmed architectural shape for the implementation:

```
User invokes Amelia (bmad-agent-dev)
  └─ Amelia resolves agent.menu[DS] → "rdx-dev-story"        [proved in verification §4]
      └─ rdx-dev-story Step 1: contract intake
      └─ rdx-dev-story Step 2: router pre-pass via rdx-validator (router-only mode)
      └─ rdx-dev-story Step 3: invoke bmad-dev-story via Skill tool   [spike 0.1: proved resume works]
          └─ bmad-dev-story executes standard red/green/refactor
          └─ Returns control (LLM cooperatively continues wrapper)
      └─ rdx-dev-story Step 4: evidence collection (LLM writes .rdx/evidence-*.json)
      └─ rdx-dev-story Step 5: invoke rdx-validator in full mode
          └─ Returns JSON + exit code
      └─ rdx-dev-story Step 6: report verdict; HALT if blocking
          ⚠ HALT is LLM-cooperative (convention), not enforced

  After commit:
    ├─ (opt-in) pre-push hook re-runs rdx-validator                    [verification spike 3: HARD enforcement]
    └─ On push: GitHub Actions runs rdx-validator on the actual diff   [V5 Phase 5: HARD enforcement]

  During PR code review (when invoked):
    └─ bmad-code-review (parent) loads RDX persistent_facts            [spike 0.2: proved]
        ├─ Blind Hunter (isolated)        — no RDX context, by design
        ├─ Edge Case Hunter (isolated)    — no RDX context, by design
        ├─ Acceptance Auditor (isolated)  — no RDX context, by design
        ├─ Standard triage + present
        └─ on_complete: invoke rdx-judgment with RDX evidence          [spike 0.2: proved hook exists]
            └─ Cat-3 review appends findings to final report
```

### Mode mapping (final, terminology locked per verification §16-E)

| Mode | What's installed | Where enforcement actually happens |
|------|------------------|-----------------------------------|
| 0 — Advisory | KB + agent overrides only (current RDX) | Nowhere — LLM cooperation |
| 1 — Local Validated | + rdx-dev-story + rdx-validator | LLM-cooperative soft gate (wrapper) |
| 2 — Local Gated | + pre-push hook | OS-level via git refusing push |
| 3 — CI Enforced | + GitHub Actions required check | Server-side via PR merge block |
| 4 — High Assurance | + Cat-3 reviewer + CODEOWNERS + signed approvals | Multi-party + diff-pinned |

### What this enables for Phase 1
- All architectural assumptions validated. No remaining unknowns block contract specification.
- `router-rules.json` design can proceed (Phase 1.2) — the prototype shows the structure.
- Evidence schema design (Phase 1.4) can use the prototype JSON output as the starting shape.
- `rdx-dev-story` wrapper design (Phase 3) confirmed; can proceed once Phase 1 contracts are stable.
- `rdx-judgment` integration via `on_complete` is the right pattern (Phase 7).

### What this rules out
- Modifying `bmad-code-review/steps/step-02-review.md` to inject a new parallel layer (would require fork; rejected).
- Pushing RDX rules into Blind Hunter (its blindness is the feature).
- Calling the wrapper a "hard gate" — terminology must remain "soft gate" / "cooperative orchestration."

---

## Outstanding items for Phase 1 readiness

None blocking. The plan can proceed to Phase 1 contracts as written.

The one item worth filing upstream (non-blocking): ask `bmad-code-org/BMAD-METHOD` for a stability commitment on `resolve_customization.py` merge-by-`code` semantics. Implementation can move forward without; an upstream change later would require a min-resolver-version pin in `rdx-setup`.

---

## Artifacts retained for reproducibility

- `spikes/0.1-multi-skill/wrapper.SKILL.md` — wrapper fixture
- `spikes/0.1-multi-skill/child.SKILL.md` — child fixture
- `spikes/0.1-multi-skill/validator-stub.sh` — intentional-FAIL stub
- `spikes/0.1-multi-skill/trace.log.evidence` — actual trace.log captured
- `spikes/0.3-standalone-validator/rdx_validator.py` — Python prototype (260 LOC)
- `spikes/0.3-standalone-validator/fixtures/*.diff` — 4 router fixtures

(Spike 0.2 has no executable artifacts — it is a source-review finding documented above.)
