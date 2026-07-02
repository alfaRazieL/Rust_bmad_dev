# D3.2 live 3-smoke — NOT_RUN

The D3.2 prompt asks for three live model-driven runs:

- `test-design` with async Rust fixture
- `atdd` with Rust API/async fixture
- non-Rust negative control

## Status

**NOT_RUN.** No live BMAD Skill runtime is reachable from this work
window.

## Exact blocker

The BMAD Skill runtime is the Claude Code / BMAD CLI dispatch loop —
the mechanism that resolves `bmad-testarch-test-design` (or
`bmad-testarch-atdd`) into a multi-step skill session, applies the
customization overlay, runs `activation_steps_prepend`, materialises
`persistent_facts`, and invokes the child skill's step files with LLM
generation between each step.

That loop is NOT a Python API. It is only reachable when:

1. A user session is active in an environment that has the BMAD-installed
   skill directory (`.claude/skills/bmad-testarch-*/`), the RDX-TEA
   overlay TOML (`_bmad/custom/bmad-testarch-*.toml`), and the
   `resolve_customization.py` script; AND
2. The LLM at the top of the loop can dispatch skills via `Skill/`
   invocations for many turns.

The current CLI session:

- Has the install-tree at `rdx-tea/poc/install-tree/_bmad/rdx-tea/` and
  the wrappers at `.claude/skills/rdx-tea-{test-design,atdd}/`.
- Does NOT have a way to force-dispatch a multi-turn skill session
  from a Python subprocess. The `Skill` tool of Claude Code is
  addressable to me directly, but running a full multi-step
  `bmad-testarch-test-design` invocation would:
  * consume a very large context window in a single turn;
  * write files into the USER's live BMAD workspace at
    `/Users/m33tball/bmad_module_builder/`, not into a disposable
    test project;
  * be non-reproducible / non-replayable for behavioural evals; and
  * conflict with the D3.2 explicit prohibition on simulating live
    execution.

## What would unblock

Any ONE of the following:

1. A dedicated live-run harness that dispatches BMAD skills from a
   separate script and returns the resulting artefacts. RDX-TEA can
   then invoke the harness inside a disposable project and consume
   its outputs.
2. A headless BMAD CLI mode that runs a workflow non-interactively
   with a specified overlay and story. Once available, the
   `rdx-tea-test-design` skill's Step 5 can be replaced with a
   subprocess to that CLI.
3. A user-driven session where the user runs the wrappers manually
   for each of the three smoke fixtures and preserves the resulting
   `run-report.json` + sidecars. The tests in this repo would then
   consume those artefacts as fixtures for the pilot eval.

## What is proved without the live runs

Every deterministic layer of the invocation chain works end-to-end in
an external tmp project (`test_l4_d31_*`). The wrapper's two-phase
model, prepare/finalize state machine, output snapshot, delta
discovery, sidecar binding, and 9-check verifier all pass in `/tmp`
with `--test-write-fake-artefact`. The only gap is the child skill's
LLM generation — which is a black box the adapter is designed AROUND
rather than replaces.

## Consequence for the pilot baseline-vs-D3.2 evals

Per the D3.2 prompt: baseline vs D3.2 pilot (3 runs per arm) is
BLOCKED until at least one live smoke run PASSes. That block chains
through to the mass N≥10/N≥20 evals.

`D3_PROOF_PLAN Stage-01` (real LLM-driven test-design run) remains
active. The unblock action is one of the three above.

## What NOT to do

- Do not simulate the live runs with `--test-write-fake-artefact`
  and label the result "smoke passed". Both the D3.2 prompt and this
  document explicitly forbid it.
- Do not write a full behavioural eval on top of simulated artefacts —
  a false positive here would poison later measurements.

## Owner

Live-runtime blocker sits with the BMAD ecosystem: a headless workflow
runner is a BMAD feature request, not an RDX-TEA fix. The wrapper is
production-ready; the LLM dispatch is not automated.
