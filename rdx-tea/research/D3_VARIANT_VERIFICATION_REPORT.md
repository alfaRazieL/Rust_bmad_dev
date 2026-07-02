# D3_VARIANT_VERIFICATION_REPORT — What was proved, what remains open

**Verdict:** `D3_PARTIALLY_PROVEN`.
**Architecture:** Variant D3 — Sequential Active-Bundle Adapter (`ADR-002`).
**Full gate matrix:** `rdx-tea/evidence/final/D3_FINAL_VERIFICATION.json`.

## 1. What is now proven at runtime

### 1.1 The two D3 seams are official and byte-verified

`activation_steps_prepend` runs BEFORE `persistent_facts` — confirmed
by upstream v1.19.0 `bmad-testarch-test-design/SKILL.md`
`§"On Activation"` Step 2 → Step 3 (source-verified in
`D3_SOURCE_LOCK_ADDENDUM §2.1`).

`workflow.on_complete` runs AS THE FINAL TERMINAL INSTRUCTION —
confirmed by every terminal step file
(e.g. `bmad-testarch-test-design/steps-c/step-05-generate-output.md:232-236`
which explicitly calls `resolve_customization.py --key workflow.on_complete`
and executes its value).

Both seams are exercised end-to-end by:

- `test_l4_upstream_customization.py` (9/9): real upstream
  `resolve_customization.py` merges the D3 overlay into the workflow
  block; prepend command lands; bundle path lands in `persistent_facts`;
  binder lands in `on_complete`; user overlay preserved; skill root
  unchanged.

### 1.2 Semantic projection (G2 upgrade)

`rdx_parser.py` extracts the full normative body of every canonical
rule. `RP-ASYNC-005` — the specific example the D3 prompt calls out —
now carries verbatim "cancel-safe, not cancel-safe, or intentionally
lossy" wording, "partial-progress state and cleanup ownership",
"Cancellation, timeout, and shutdown tests", exceptions, and sources.
This is the semantic knowledge D2 lacked.

Verification: 11 parser tests including `test_l1_parser_v2_rp_async_005_is_semantic`.

### 1.3 Dynamic active bundle (G3 upgrade)

`prepare.py` imports `rdx_validator.router.replay` directly (no fork),
applies the workflow obligation matrix, and writes an atomically-
replaced deterministic bundle. Router parity to the RDX validator is
asserted directly by `test_l2_d07`.

The bundle is workflow-scoped: `trace` never receives `unsafe`
(`test_l2_d09`), and non-Rust diffs produce empty bundles
(`test_l2_d03`, `test_l7_f04`).

### 1.4 Deterministic sidecar (G8 partial)

`binder.py` writes `<artefact>.rdx-tea.json` per
`rdx-tea/architecture/rdx-tea-run.v1.schema.json`. The schema forbids
verdict fields via `additionalProperties: false`. Verified against
tampered artefacts, tampered bundles, and absent prepare manifests
(`test_l7_f01..f03`, `test_l4_e01..e05`).

### 1.5 Falsification cycle passes

Eight falsification tests attempt to break D3 v1 invariants. All eight
correctly detect the failure mode or refuse to proceed
(`test_l7_d3_falsification.py`).

## 2. What was intentionally NARROWED, not proven

### 2.1 Subagent support

Rejected by design for D3 v1. Both Phase-2 reviews and the D3 audit
confirm the subagent context does not inherit `persistent_facts`, and
no supported seam exists to inject a fragment into the child. G6F is
therefore `UNSUPPORTED_BY_DESIGN` — this is a **contractual boundary**
of v1, not an evidence gap.

Wrappers (§9 of ADR-002) request `sequential` explicitly and fail
closed on any other resolved mode. Wrapper implementation itself is
deferred to a production stage; the *manifest* already records
`execution_mode: sequential`.

### 2.2 Framework / CI stack detection

D2's `{detected_stack}`-in-prepend proposal is rejected: the variable
does not exist at prepend time. D3's prepare uses only
`Cargo.toml`, `rust-toolchain`, changed `.rs`, story tags, and RDX
Router input — all available before workflow body variables.

The current PoC ships the obligation matrix but not the environment
sniffer; a workflow named `framework` therefore returns whatever the
Router says intersected with the framework matrix. Production stack-
detection code is a stub in the plan.

## 3. What remains NOT_RUN or BLOCKED

### 3.1 Behavioural benefit (G7 NOT_RUN)

No baseline-vs-D3 LLM eval executed. The prompt asks for N≥10 (normal)
and N≥20 (critical) runs. This is the single biggest reason the
verdict is `D3_PARTIALLY_PROVEN` and not `D3_PROVEN`.

### 3.2 RDX validator extension (G8 partial)

The sidecar is proven. The `rdx-tea-validate` subcommand that
consumes it and emits an `rdx-evidence.v1` envelope is designed
(ADR-002 §9-§11) but not implemented.

### 3.3 Modes / hooks / CI (G9 BLOCKED)

MODE_0..MODE_4 tie-in, pre-push hook, and CI required-check are
BLOCKED behind G7 and G8. Doing them earlier would gate a knowledge
plane that isn't fully proven.

### 3.4 Fresh install / uninstall / rollback / version mismatch fail-closed
(G4 partial, G11 partial)

Only idempotent re-prepare, atomic replace, `.user.toml` survival,
stale bundle replacement are covered. Full installer plumbing deferred.

## 4. Downgrade / retraction summary

| Original claim | Was | Now | Anchor |
|---|---|---|---|
| G1 role-review = official confirmation | PASS | PASS via upstream tag lock + real resolver run | §1.1 |
| G2 metadata projection sufficient | PASS | superseded by G2 semantic (real PASS) | §1.2 |
| Subagent seed via filename injection works | ADR-001 §7 | REJECTED; G6F UNSUPPORTED_BY_DESIGN | ADR-002 §7 |
| `{detected_stack}` in prepend | ADR-001 §6 | REJECTED; environment-only detection | ADR-002 §4 |
| Parallel `rdx-tea-index.csv` is the loading channel | ADR-001 §6 | REJECTED; static file + prepend seams | ADR-002 §5 |
| Active-packs frontmatter injected into TEA outputs by adapter | PROOF_COMPLETION §Stage 05 | REJECTED; sidecar owns machine metadata | ADR-002 §9 |
| `_bmad/custom/` is home for generated fragments | D2 | REJECTED; `_bmad/rdx-tea/` is | D3_CORRECTION_AUDIT §3.7 |

## 5. Recommended next action

Continue with `D3_PROOF_PLAN.md`. Do NOT write a production
`MASTER_IMPLEMENTATION_PLAN.md` — the verdict does not permit it
(D3 prompt §11).
