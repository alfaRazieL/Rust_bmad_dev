# D3.4.0 — Precondition audit before the rule-operation pilot

Independent re-verification of the validity gaps that remain after
D3.3.3, grounded in the current Git HEAD, the committed live smoke
evidence, and the harness/wrapper code. Every finding is backed by a
command or a committed byte — none is a rewording.

## §0 Goal reframing (authoritative for this stage)

D3.4 is NOT "prove RDX is better than ordinary TEA". The goal is to
prove **RDX rule-operation correctness and stability** inside real
BMAD TEA workflows:

    rule selection → active packs → rule bundle → wrapper invocation
    → child TEA workflow → artifacts → sidecars → verifier → admissible.

Baseline is a control arm (isolation / no-RDX-contamination), not the
primary value criterion. Comparative/LLM scoring is an optional
diagnostic that cannot override deterministic rule-operation gates.

## §1 Repository state

- START_HEAD: `a1f98d8085aef30fbd25d1412aca614e1eeb611d` (matches handoff)
- `origin/main`: `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d`
- Working tree clean apart from local `.agents/` scratch dir.
- Claude Code CLI: 2.1.191 (unchanged; agent did not update).
- `claude auth status`: loggedIn true, authMethod claude.ai, pro. No
  `ANTHROPIC_API_KEY`; `CLAUDE_CONFIG_DIR` present (inherited, not
  overridden).

## §2 D3.3.3 claims confirmed against evidence

`rdx-tea/evidence/live/smoke-atdd-api-corrected-v3/live-evidence.v3.json`:
- run_outcome SUCCESS, admissible true;
- wrapper_skill_invoked true, child_skill_invoked true;
- task_tool_use_count 0; observed_mode OBSERVED_SEQUENTIAL;
- active_packs [api, async]; verifier verdict PASS;
- config_dir_overridden false; contamination "".
Auth blocker is closed with NO API key (auth-preflight evidence +
smoke transcript apiKeySource none but is_error false).

## §3 Validity gaps (each confirmed in code / evidence)

### §3.1 run-report.json has duplicate artifact/sidecar/verifier entries
`run-report.json` of the admissible v3 smoke:

    new_artefacts: [<same path>, <same path>]   # len 2, unique 1
    sidecars: 2
    verifier: 2

Root cause: `rdx_tea_wrapper._output_dirs()` returns a set containing
BOTH `_bmad-output` and `_bmad-output/test-artifacts` (the latter
nested under the former). `_delta_outputs()` rglob-scans both, so a
file under `test-artifacts` is discovered twice; `finalize_run` then
binds it twice → duplicate sidecars and verifier entries.

### §3.2 Top-level v3 dedupes, source report does not
`run_live._finalize_evidence_v3` dedupes via `_walk_artefacts` +
`_canonicalize_output_roots`, so the v3 bundle's
`candidate.sidecars` is length 1. But the source-of-truth
`run-report.json` (the wrapper's own output) is still polluted with
the duplicates. The dedup must be fixed at the wrapper source, not
only in the evidence collector (handoff §6).

### §3.3 Grader looks for v2, D3.3.3 uses v3
`grade_pilot._walk_pilot_evidence` globs `live-evidence.v2.json`
(line 119). D3.3.3 emits `live-evidence.v3.json`. The grader would
therefore find zero pilot bundles.

### §3.4 grade-llm is dry-run only
`grade_pilot.grade_llm(..., dry_run=True)` writes `status: NOT_RUN`
per sample; no live LLM grading is performed.

### §3.5 report() always returns PILOT_INCONCLUSIVE
`grade_pilot.report` sets `verdict = "PILOT_INCONCLUSIVE"`
unconditionally (line 329). There is no deterministic rule-operation
verdict path.

### §3.6 Fixtures hand-feed the expected obligations
`fixtures/atdd-api-async-corrected/story.md` explicitly says
"cancellation semantics", "graceful-shutdown", "Partial-progress
preservation", "cleanup" — i.e. the exact detector phrases the grader
looks for. `fixtures/test-design-async/story.md` similarly leaks
detector phrases. This is fine for an apparatus smoke but invalid for
proving rules are TRIGGERED from tags/diff/story rather than copied
from the prompt. Latent fixtures are required (handoff §11).

### §3.7 Baseline live lifecycle not yet proven
Only the candidate arm has an admissible live bundle. No baseline
live run exists; the baseline path is proven only deterministically
(arm skills/prompt/schema).

### §3.8 Evidence inventory does not preserve/verify all declared files
An ATDD checklist can declare generated Rust test files
(`generatedTestFiles: ...`), but the harness collects only
`_bmad-output/**` and does not (a) collect the full workspace delta,
(b) verify declared generated files exist, or (c) preserve them in
evidence. A checklist could claim files that were never written and
still be admissible (handoff §7).

### §3.9 Expected API-rule criterion decided post-hoc
Rubric v3 lists `expected_rp_ids: [RP-ASYNC-005, RP-API-001]` but the
admissible smoke cited `RP-API-004` / `RP-API-005` (also relevant).
The "which API rule counts" decision was made after the run. It must
be precommitted as an `any_of` set (handoff §10).

### §3.10 Schedule hash binding not enforced at runtime
`D3_4_PILOT_RUNS.v2.json` records `prompt_hash` / `fixture_hash` per
run, but no runtime gate recomputes them and compares against the
schedule + a pinned schedule SHA before a live run. A prompt/fixture/
criteria/schema drift would go undetected (handoff §13).

## §4 What this audit does NOT claim

- It does NOT claim the baseline or paired smokes will pass — those
  are executed later in this stage and judged by the v4 admission gate.
- It does NOT weaken the D3.3.3 verdict; the candidate apparatus is
  proven. The gaps here are about source-report cleanliness, workspace
  delta, precommitted criteria, latent fixtures, and schedule binding
  — the validity scaffolding for a real rule-operation pilot.
- It records NO token/credential/PII.
