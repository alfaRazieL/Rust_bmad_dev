# D3.3.2 Blockers

## §1 Corrected ATDD live smoke — candidate arm

- Status: NOT_RUN in this window.
- What's needed: one live invocation via
  `python3 rdx-tea/live-harness/run_live.py run-smoke \
      --scenario atdd-api-async-corrected --arm candidate \
      --workspace-dir /tmp/rdx-tea-live-smoke-atdd-corrected \
      --run-id smoke-atdd-corrected-<timestamp>`
  against `/opt/homebrew/bin/claude` v2.1.126 in an isolated
  `CLAUDE_CONFIG_DIR`. Expected observables per handoff §18:
    - `active_packs == [api, async]`;
    - `RP-ASYNC-005` AND `RP-API-001` present in bundle;
    - wrapper structured Skill event == true;
    - child structured Skill event == true;
    - Task tool_use == 0;
    - `observed_mode == OBSERVED_SEQUENTIAL`;
    - single exact run_id end-to-end;
    - no output duplicates; one artifact → one sidecar;
    - verifier PASS; runtime contamination none; cleanup PASS;
    - `live-evidence.v2.json` validates.
- Why deferred: this stage is scoped to deterministic closure only.
  The corrected ATDD live smoke is documented in `stops-only-after`
  clauses so it can be executed by a follow-up window without
  reopening the audit.

## §2 D3.4 pilot execution

- Status: NOT_RUN.
- What's needed: 18 model-driven runs per
  `rdx-tea/evals/runs/D3_4_PILOT_RUNS.v2.json` (schedule sha256
  `29b57ee5a5fd98fdd66e3bb0484453da9992fa57f027aea57b158eedb600d5c6`),
  followed by the blinded grader passes.
- Precondition (STOP): D3.3.2 must be PASS (not PARTIAL) — i.e.
  §1 must close first — and the deterministic dry-run PASS must be
  preserved.

## §3 Blinded LLM grader live run

- Status: DRY_RUN_ONLY. `grade_pilot.py grade-llm` is fully
  implemented; running it against real samples requires the D3.4
  pilot artifacts (blocked by §2) AND API credentials for the
  cheap-model policy (`claude-haiku-4-5-20251001` or
  `claude-sonnet-4-6`).

## §4 Structured D3.4 admission gate

- Status: TO_BE_ADDED. A future `run_pilot.py admit` mode should
  fail closed if:
    - `D3_3_2_FINAL_VERIFICATION.json.verdict != D3_3_2_PASS`;
    - schedule sha256 has drifted from the recorded value;
    - any run in the schedule already has a bundle under
      `rdx-tea/evals/results/d3_4_pilot/` (would violate immutability
      before pilot is admitted).
  This is intentionally scoped OUT of D3.3.2 because a live-smoke
  gate check that references a not-yet-PASS verdict is a chicken-
  and-egg problem; it will land alongside the D3.4 execution window.

## §5 Isolated CLAUDE_CONFIG_DIR breaks OAuth token discovery

- Status: OPEN — discovered by the D3.3.2 live smoke attempt on
  FINAL_HEAD 3adcc78.
- What happened: `run_live.py run-smoke --arm candidate
  --scenario atdd-api-async-corrected --model haiku` was executed
  against real Claude Code CLI 2.1.126. The init event in
  `rdx-tea/evidence/live/smoke-atdd-api-corrected-v2/transcript.stream.jsonl`
  reports `apiKeySource: "none"` and the session terminated after one
  turn with `error: "authentication_failed"` and result text
  `"Not logged in · Please run /login"`. Model never got to invoke a
  Skill. `observed_mode = INFERRED_ABSENT`; `active_packs = []`.
- Also observed: the init event still lists user-side skills
  (`update-config, debug, simplify, batch, fewer-permission-prompts,
  loop, claude-api`) alongside the arm-installed rdx-tea /
  bmad-testarch pair. So `CLAUDE_CONFIG_DIR` did NOT scope the
  full skill discovery — additional skills leaked in from another
  source (`~/.claude/skills` and/or user-global plugin dir).
- Root cause: setting `CLAUDE_CONFIG_DIR` to an empty temporary dir
  makes Claude Code CLI stop discovering the OAuth token stored in
  the user's real config, and reports `apiKeySource: "none"`. There
  is no `ANTHROPIC_API_KEY` in scope, no `--settings`-provided
  `apiKeyHelper`, and no `--login` interactive step available in
  a headless subprocess.
- Fix path: extend `ClaudeIsolation.bootstrap()` to (a) require
  `ANTHROPIC_API_KEY` (or a settings file with `apiKeyHelper`) in the
  environment, (b) call `claude --strict-mcp-config
  --setting-sources project` so only the isolated dir's settings are
  read, and (c) enumerate the actual skill-discovery paths and
  restrict them explicitly. Until this fix lands, the corrected ATDD
  live smoke cannot produce a fair test.
- Consequence: D3.3.2 verdict is `D3_3_2_PARTIAL` and pilot readiness
  is `D3_4_NOT_READY`. Evidence of the failed attempt is committed at
  `rdx-tea/evidence/live/smoke-atdd-api-corrected-v2/` so a follow-up
  can start from the real trace, not from a fabricated summary.

## Non-blockers (closed in this cycle)

- Baseline/candidate execution divergence — closed via arm_prompt /
  arm_installed_skills + arm-aware v2 schema.
- Schedule-owned run_id — closed via invocation contract + wrapper
  enforcement + handshake check.
- Free-text Skill detection — deleted.
- Init event parsing — implemented + tested.
- Isolation preflight — implemented + tested.
- CI mandatory-skip gate + unique count — implemented and validated
  against the D3.3.1 CI artifacts.
- Real bootstrap `--verify-only` — implemented and wired into the
  workflow without `|| echo` masking.
- Structured JSON lock + observed cleanup evidence — implemented.
- Rubric v3 + schedule v2 — locked, superseded predecessors retained
  on disk.
- Pilot executor + blinded grader — implemented with 10 grader tests
  + 23 v2 harness tests.
- Dry-run of the 18-run pilot — PASS with zero collisions and
  arm-command divergence recorded.
