# RDX ↔ TEA Production Implementation — Wave Index

Compact index of all D4 productionization waves. Execute each in a fresh
CLI context using the matching prompt in `WAVE_PROMPTS.md`. Full detail
in `../MASTER_IMPLEMENTATION_PLAN.md` §6.6. Gates in `ACCEPTANCE_GATES.md`.

- Branch: `rdx-tea-integration` (never `main`).
- D4 pre-plan baseline (D3.4.1): `1cd5b11b20ba8cea92101d47967665d44cea7e97`.
- Wave-0 execution START (D4.0 plan final head): `8b4ba3a53971f97b40cd997a77f019cf075c8ea8`.
- Owner-authoritative wave handoff chain (local; not yet pushed at W2 start):
  - W0 FINAL_HEAD: `bed1b30babd3ad71b3894ff631e60154f820c18f`.
  - W1 FINAL_HEAD / W2 required START: `b56e9e0c18be5583643327612744054516b7cf8e`.
  - W2 starts from the pre-W2 hygiene commit layered on `b56e9e0…`.
- Basis: `D3_RULE_OPERATION_PROVEN` (D3.4.1).
- Plane order: knowledge plane (W2–W5) → admission/runtime (W6) →
  packaging/CI/docs/e2e (W7–W10). Enforcement plane is deferred backlog.

| Wave | Goal | Plane | Depends on | Status | Expected artifact outputs | Owner checkpoint |
|---|---|---|---|---|---|---|
| **W0** | Plan validation & repo hygiene | meta | START_HEAD | ☑ complete | wave-index status update; validation notes (`evidence/logs/W0_VALIDATION.md`) | HEAD == 8b4ba3a (plan-pack; `1cd5b11` = pre-plan baseline); split matches disk; all W0 gates PASS |
| **W1** | Production layout & source boundaries | meta | W0 | ☑ complete | VERSION reconciled; boundary/import test; adapter classification; install-tree README | golden hashes unchanged; boundary enforceable; FINAL_HEAD `b56e9e0`; all W1 gates PASS |
| **W2** | Rule KB & router productionization | knowledge | W1 | ☐ pending | router parity + activation-matrix tests; canonical snapshot hash pin | starts from W1 FINAL_HEAD `b56e9e0c18be5583643327612744054516b7cf8e` (+ pre-W2 hygiene commit); pack activation deterministic; forbidden-by-active-packs |
| **W3** | Active-context bundle builder | knowledge | W2 | ☐ pending | byte-determinism + identity + schema tests; golden bundle hashes | bundle byte-identical; identity fail-closed |
| **W4** | Wrapper Skills & non-interactive lifecycle | knowledge | W3 | ☐ pending | external-project slice; sequential/lock/overlay tests | sequential-only; Task 0; child not simulated |
| **W5** | Binder, sidecars, workspace delta, artifact consistency | knowledge | W4 | ☐ pending | one-sidecar test; promoted delta/consistency module + tests | reality-checked finalize; no eval import |
| **W6** | Verifier / admission & failure semantics | admission | W5 | ☐ pending | per-check mutation tests; admission recompute tests | fail-closed; failed run never admissible |
| **W7** | Installer / bootstrap & project settings | packaging | W6 | ☐ pending | project installer; settings template; lifecycle tests | no auth material; no CLAUDE_CONFIG_DIR override; idempotent |
| **W8** | CI gates & source-lock | packaging | W7 | ☐ pending | CI boundary + golden-hash jobs; ci_check tests | green; no skips; scope + boundary enforced |
| **W9** | Documentation & operator workflows | docs | W7 | ☐ pending | `rdx-tea/docs/**`; doc-lint | operator can run from docs alone |
| **W10** | End-to-end acceptance & release/merge plan | release | W8, W9 | ☐ pending | acceptance + rollback tests; D4 release-readiness verification; merge proposal | all gates PASS; awaits owner merge authorization |

Status legend: ☐ pending · ◐ in progress · ☑ complete · ✗ blocked.

## Dependency graph

```
W0 → W1 → W2 → W3 → W4 → W5 → W6 → W7 → W8 ┐
                                     └→ W9 ┴→ W10
```

W9 (docs) depends on W7 (installer surface) and may run in parallel with
W8. W10 requires both W8 (CI) and W9 (docs).

## Deferred (NOT waves — enforcement-plane backlog)

- `rdx-tea-validate` verdict in `rdx-validator/rdx_tea/` (STAGE-08).
- Modes / hooks / CI-gate / judgment / Cat-4 approval (STAGE-09).
- Subagent / agent-team worker propagation (`G6F`).
- G7 behavioural benefit vs baseline (out of scope, not claimed).

## Per-wave owner checkpoint protocol

After each wave completes in its fresh context, the owner:
1. Reads the wave's final-response block.
2. Confirms the wave's acceptance gates are PASS in `ACCEPTANCE_GATES.md`.
3. Updates this table's Status cell.
4. Only then launches the next wave's prompt in a new context.
