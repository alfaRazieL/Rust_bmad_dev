# Risk Register — RDX ↔ TEA Production Implementation

Actionable risk register for D4. Each risk has a **detection signal**, a
**mitigation** tied to a wave/gate, and a **residual** note. Kept
distinct from `MASTER_IMPLEMENTATION_PLAN.md` §6.8 (which is the summary):
this file adds detection + residual + owner.

Likelihood (L) / Impact (I): Low / Med / High.

| ID | Risk | L | I | Detection signal | Mitigation (wave · gate) | Residual |
|---|---|---|---|---|---|---|
| R1 | **Auth isolation breakage** — adapter/installer sets or overrides `CLAUDE_CONFIG_DIR`, or introduces an API key / OAuth token | Low | **High** | grep hit in shipped surface; `auth_preflight` fails; `apiKeySource` becomes key-based | Never touch auth env; installer no-auth assertion (W4,W7 · G-AUTH,G-W7-NOAUTH) | With gate + CI grep, near-zero. Manual review each wave. |
| R2 | **Shipping eval artifacts as production** — install-tree imports `live-harness`/`evals` or bundles evidence | Med | **High** | boundary grep hit; installer copies an eval path | Boundary/import test + CI job (W1,W8 · G-SPLIT-IMPORT) | Promoted delta/consistency (W5) must be re-implemented, not imported. |
| R3 | **prompt_hash vs prompt_template_hash confusion** | Med | Low | someone treats the schedule's template hash as a per-run hash and flags false drift | Keep eval-only; document in D4.0 audit §6; optional rename in a future schedule version (NOT D4) | Cosmetic; eval-side only. |
| R4 | **Baseline interactive gating misread as a production requirement** — someone demands baseline artefacts | Low | Med | a wave adds a baseline-artefact gate | Production admission never requires baseline artefacts (W6 doc) | Documented in audit §6 caveat 1. |
| R5 | **Duplicate artefacts/sidecars regression** — nested output roots rediscovered | Med | Med | >1 sidecar per artefact; 2 verifier entries | Canonical output roots; dedupe by resolved path (W5 · G-W5-SIDECAR) | Covered by test; watch on new output roots. |
| R6 | **Task/subagent dispatch regression** | Low | High | `task_tool_use_count > 0`; observed mode `OBSERVED_SUBAGENT` | `--disallowedTools Task TaskOutput TaskStop` in documented invoke; Task-0 assertion (W4,W8 · G-W4-NOTASK) | Sequential-only is proven; subagent is deferred `G6F`. |
| R7 | **Forbidden packs detected from prose** instead of active packs | Low | Med | docs-only fixture flags a pack from a cross-reference | Judge by ACTIVE pack names + sidecar rule ids only (W2 · G-W2-FORBIDDEN) | Held in D3.4.1 (docs-only → []). |
| R8 | **Missed workspace delta / declared generated files** — declared file never verified/preserved | Med | Med | declared file absent but run admitted | Declared-file verification fail-closed; preserve delta (W5 · G-W5-DELTA) | The D3.3.3 gap that v4 closed; keep in production finalize. |
| R9 | **Absolute path leakage in evidence** | High | Low | absolute machine paths in bundles | Prefer project-relative paths where practical (W6,W9) | Cosmetic; no secrets. Non-blocking. |
| R10 | **Source-lock drift** — upstream tag/hash changes silently | Low | High | `bootstrap --verify-only` FAIL; hash mismatch | `--verify-only` in CI + SOURCE_LOCK addendum discipline (W2,W8 · G-W8-SOURCELOCK) | Fail-closed by design. |
| R11 | **Installer overwriting user config** — clobbers `.user.toml` or `.claude/settings.json` | Med | High | user content lost after update | `.user.toml` preservation + idempotency + backup (W7 · G-W7-IDEMPOTENT) | Uninstall keeps user content; test-covered. |
| R12 | **Unclear / lossy rollback** | Med | Med | uninstall leaves adapter files or drops user overrides | Uninstall smoke restoring user content (W7,W10 · G-W10-ROLLBACK) | Adapter-owned files are the only delete surface. |
| R13 | **Non-determinism creep** — wallclock/random in a generator | Med | High | bundle bytes differ across runs; golden hash mismatch | Byte-identity tests; golden re-pin on any change (W3 · G-DET,G-W3-DETERMINISM) | `RDX_TEA_FAKE_NOW` used only in tests. |
| R14 | **Layout move breaks CI/tests/bootstrap** — physically relocating the install-tree | Med | High | CI path-not-found; bootstrap fails | Recommend NOT moving install-tree in v1; pointer/README only (W1) | Deferred to a post-v1 cleanup with its own hash re-pin. |
| R15 | **Upstream TEA update breaks the overlay/persistent_facts seam** | Low | High | overlay not merged; child ignores bundle | Upstream file-hash lock + overlay round-trip test (W4,W8) | Fragility noted in ADR-001 §"Consequences". |
| R16 | **Scope escape** — a change outside `rdx-tea/` sneaks in | Low | High | `no-main-modifications` CI job fails; `git add -A` captured `.agents/` | Stage by explicit path; CI scope guard (all · G-SCOPE) | CI fail-closed. |
| R17 | **Enforcement-plane scope creep into D4 v1** — someone starts `rdx-tea-validate`/modes/hooks | Med | Med | a wave edits `rdx-validator/rdx_tea/` or adds a gate workflow | Deferred backlog is explicit; knowledge-plane-first guardrail (plan §Deferred) | Only start with owner sign-off. |
| R18 | **Overclaiming G7 benefit** — a report claims RDX beats TEA | Low | Med | any "better than baseline" language in evidence | G7 is OUT_OF_SCOPE_NOT_CLAIMED; keep isolation-control framing (all · plan §6.11) | Enforced by review. |

## Highest-priority watch list (High impact, ≥ Med likelihood)

- **R2** (eval-as-production) — the defining discipline of D4.
- **R11** (installer clobbers user config) — user-visible data loss.
- **R13** (non-determinism) — silently invalidates golden gates.
- **R14** (layout move) — avoid the move entirely in v1.
- **R15** (upstream seam) — pin hashes; test the overlay round-trip.

## Standing controls (every wave)

1. `grep` the shipped surface for auth env + eval imports before commit.
2. Re-verify golden bundle/canonical hashes after any generator touch.
3. Stage files by explicit path; never `git add -A`.
4. Preserve — never overwrite — any failed attempt or prior evidence.
5. Keep the verdict deterministic; the LLM diagnostic never gates.
