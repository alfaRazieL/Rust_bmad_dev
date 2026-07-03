# D3.3_PRECONDITION_AUDIT — honest downgrade before live invocation

**Governing prompt:** `RDX_TEA_D3_3_headless_live_harness_prompt.md` §3.
**Prior HEAD (D3.2 verdict):** `17263f9de88eaceb563f2248bee741c3ca295dfd`.

Before attempting live model-driven runs, this audit downgrades two
D3.2 gates that were over-claimed and enumerates the deterministic
gaps closed in this D3.3 cycle. Test logs and hash manifests remain
in `rdx-tea/evidence/` untouched.

## §3.1 — G13_live_invocation_closure_deterministic_side

**D3.2 status:** `PASS`.  
**D3.3 corrected status:** `PARTIAL_PASS`.

**Why wrong:** the D3.2 install-tree tests never sent the run-scoped
bundle path through the ACTUAL upstream `resolve_customization.py`.
The D3.1 overlay text still contained a hard-coded static path
`_bmad/rdx-tea/runtime/<workflow>/active-context.md` (no `<run_id>`),
so a real TEA workflow would read the wrong file. Nothing in D3.2
proves the new run-scoped path is what the resolver emits.

**Corrective action (this cycle):** generate the overlay TOML per run
inside `prepare-run` and prove via a subprocess call to
`resolve_customization.py` that the resulting merged workflow block
contains the exact `<run_id>` path. See §4.1 of the D3.3 prompt and
the new tests `test_l4_d33_run_specific_overlay_*`.

## §3.2 — G6_v1_context_continuity_sequential

**D3.2 status:** `PASS`.  
**D3.3 corrected status:** `PARTIAL_PASS`.

**Why wrong:** the D3.2 wrapper reads `_bmad/tea/config.yaml:tea_execution_mode`
and refuses non-`sequential`. That is the REQUESTED mode. The actual
OBSERVED mode is only knowable from a real workflow transcript — did
any subagent / worker dispatch happen? Config value alone cannot
prove observed execution.

**Corrective action:** split `requested_mode` (config-side) from
`observed_mode` (transcript-derived surrogate). Wrapper emits
`observed_mode="sequential"` only when a transcript parser finds no
subagent/agent-team dispatch events across the whole child run. If
no transcript is available, `observed_mode="INFERRED_ABSENT"`. See §4.5
of the prompt.

## §3.3 — G5 and G14

**D3.2 status:**
- G5 `PARTIAL_PASS` (vertical slice via `--test-write-fake-artefact`)
- G14 `NOT_RUN` (no live LLM)

**D3.3:** unchanged pending three real smoke runs.

## §3.4 — G7

**D3.2 status:** `NOT_RUN`.  
**D3.3:** unchanged pending pilot eval. Pilot itself remains blocked
behind 3/3 successful smoke.

## Verdicts table after this audit

| Gate | D3.2 | D3.3 (after §3 corrections) |
|---|---|---|
| G13 | PASS | **PARTIAL_PASS** |
| G6  | PASS | **PARTIAL_PASS** |
| G5  | PARTIAL_PASS | PARTIAL_PASS |
| G7  | NOT_RUN | NOT_RUN |
| G14 | NOT_RUN | NOT_RUN |

These are re-recorded in `evidence/final/D3_3_FINAL_VERIFICATION.json`
without touching D3_FINAL_VERIFICATION.json.

## New gates introduced by this cycle

- `G15_run_specific_overlay_proved` — real resolver returns run-scoped
  path.
- `G16_workspace_isolation_proved` — active-run lock; two-worktree
  adversarial test.
- `G17_pre_bind_boundary_proved` — symlink/outside-project rejection.
- `G18_rust_relevance_split_proved` — docs-only in Rust repo yields
  empty bundle.
- `G19_atdd_wrapper_self_contained` — SKILL.md has no external read.
- `G20_obligation_oracle_and_csv_byte_equality` — YAML oracle +
  CSV regen equality.
- `G21_ci_real_run` — real GH Actions run ID + conclusion recorded.

These new gates are addressed by the deterministic code + tests
landing in this cycle; runtime evidence is either the pytest suite
or a real subprocess invocation of upstream tooling.

The live gates (G22 headless-runtime, G23 smoke A/B/C, G24 pilot)
are attempted only after the deterministic gates close and are
labelled honestly as PASS / NOT_RUN / SMOKE_FAIL.
