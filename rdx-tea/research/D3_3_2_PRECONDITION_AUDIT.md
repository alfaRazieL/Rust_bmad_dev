# D3.3.2 — Precondition audit before pilot execution closure

Independent verification of the eleven execution-validity gaps flagged
against D3.3.1. Every finding below is grounded in the current Git
HEAD, live-harness code, downloaded CI artifacts, and re-runnable
commands. Nothing here trusts a prior verdict merely because it was
recorded.

## §0 Repository state at start

- START_HEAD: `ffb2801750beb75a5cbc418969ed7a67b994f14c`
  (matches the handoff expectation)
- `origin/main`: `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d`
- Working tree clean apart from local `.agents/` scratch dir.
- `claude` CLI: `/opt/homebrew/bin/claude` v2.1.126 (present but
  live smoke deferred until §17 of the D3.3.2 handoff is met).

## §1 Baseline and candidate use identical execution paths — CONFIRMED

`rdx-tea/live-harness/invoke_runtime.py::build_prompt(workflow)` takes
no `arm` parameter and emits a candidate-style prompt unconditionally:

    Invoke the /rdx-tea-{workflow} skill on the current project.
    Follow every activation step in the wrapper's SKILL.md.

`rdx-tea/live-harness/run_live.py` L700 hard-codes the wrapper skill
name into the isolated config regardless of arm:

    project_skills=[f"rdx-tea-{spec.workflow}"]

Consequence: a "baseline" invocation would still boot the RDX wrapper
via the same prompt. There is no direct-child path yet. All existing
harness code assumes candidate semantics.

## §2 Schedule-owned run_id not used end-to-end — CONFIRMED

`prepare_workspace.prepare()` (line 107) always generates its own id:

    run_id = f"{scenario}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

`run_live.RunSpec.run_id` field exists but is empty by default and
overridden by `_prepare()` (which returns `prep["run_id"]` from
`prepare_workspace`). The precommitted `D3_4_PILOT_RUNS.json`
schedule assigns explicit run_ids (`pilot-001-...` through
`pilot-018-...`), but no code path passes them into the wrapper or
workspace. Wrapper's SKILL.md instructs the model to generate a
`td-YYYYMMDD-HHMMSS`/`atdd-YYYYMMDD-HHMMSS` id from within the LLM
session, not to read a schedule.

## §3 Evidence schema is candidate-oriented — CONFIRMED

`schemas/live-evidence.v1.schema.json` requires:

    hashes.bundle           (rdx bundle sha256)
    observation.wrapper_skill_invoked
    observation.child_skill_invoked

A baseline run has no bundle to hash and no wrapper to invoke. The
schema does not branch on arm; a legitimate baseline evidence file
would fail schema validation, so the harness would either lie
(hash an empty bundle) or refuse to emit valid baseline evidence.

## §4 Free-text Skill classifier — CONFIRMED

`run_live._walk_for_invocations` (lines ~354-370) walks every JSON
node and falls back to substring matching on plain strings:

    elif isinstance(node, str):
        s = node.lower()
        if wrapper_skill in s:
            counters["wrapper"] = True
        if child_skill in s:
            counters["child"] = True

An assistant message like `"I would invoke rdx-tea-atdd next"` — or
even a user prompt that mentions the skill — sets `wrapper` to true
without a real tool_use event. The current classifier can grade a
non-invocation as `OBSERVED_SEQUENTIAL` if wrapper AND child names
both appear in prose.

## §5 34 mandatory upstream tests silently skipped — CONFIRMED

Downloaded `pytest-baseline.junit.xml` from CI run 28645768546. First
skip:

    rdx-tea.tests.bmad-tea.test_l4_d31_external_project_slice
    :: test_l4_d31_e01_two_phase_wrapper_end_to_end
    skip message: "upstream TEA missing — run bootstrap"

`rdx-tea/tests/bmad-tea/test_l4_d31_external_project_slice.py` (line
29) computes `UPSTREAM_TEA = WORKSPACE / "upstream" / "bmad-method-
test-architecture-enterprise"` where `WORKSPACE = REPO_ROOT.parent`.
In CI that resolves to `/home/runner/work/upstream/…` but the
bootstrap step clones into `rdx-workspace/upstream/…` (inside the
repo). Path disagreement → 34 fixture-time skips.

`refuse-mandatory-skips` in the workflow uses `--collect-only`,
which fires the fixture only in collection mode. That never sees a
fixture-body `pytest.skip()`; it only catches
`@pytest.mark.skip` decorators. The workflow was therefore green
even while every upstream-dependent test was skipped.

## §6 533 PASS count is a re-execution sum — CONFIRMED

JUnit XML counts:

    pytest-baseline    : 461 tests (427 passed, 34 skipped)
    pytest-adapter     : 121 tests (87 passed,  34 skipped)
    pytest-live-harness:  19 tests (19 passed,   0 skipped)

The set of test IDs in `pytest-adapter` is a strict subset of the
set in `pytest-baseline` (|baseline∩adapter| == 121 == |adapter|),
because the adapter step is `pytest rdx-tea/tests` which is already
collected by the root `pytest` run. Sum-of-executions = 601. Unique
node IDs across all three = 461. Unique passed = 427 (or 446 if
we count baseline's 427 plus live-harness's 19). "533 passed" is
not the unique test count.

## §7 source-lock report is a masked argparse error — CONFIRMED

Downloaded `source-lock-report.txt` from the same CI run:

    usage: bootstrap.py [-h] --target-dir TARGET_DIR [--sources-lock ...]
    bootstrap.py: error: unrecognized arguments: --verify-only

`bootstrap.py` never grew a `--verify-only` flag. The workflow's
`|| echo "verify-only flag unavailable; falling back to bootstrap
output"` swallowed the non-zero and let CI proceed. No actual
source-lock check happened.

## §8 Runtime evidence records expected surface not observed — CONFIRMED

`run_live._finalize_evidence` sets:

    "mcp_servers": []                             # constant
    "available_tools": sorted(runtime.get("surface", {}).keys())
    "available_skills": sorted(isolation.project_skills)
    "permission_mode": isolation.permission_mode

`isolation.project_skills` is what we PLANNED to install, not what
`claude` actually reported. `runtime.get("surface", ...)` comes from
runtime_discovery (--help parsing), not from a live init event. If
the model session sees additional MCP servers or the user's plugins,
we record `[]` and never notice.

## §9 Cleanup state written as constant — CONFIRMED

`_finalize_evidence` writes:

    "cleanup": {"state": "FINALIZED",
                "lock_released": True,
                "overlay_restored": True}

These are constants — the actual state of the lock file, overlay
file, and run dir on disk is not re-inspected before serialisation.
If cleanup partially failed and only the marker line ran, evidence
would still record success.

`abort_run` does return an observed dict, but the success path's
FINALIZED bundle never reads it.

## §10 Rubric decision rule references 3 positive scenarios — CONFIRMED

`evals/D3_4_PILOT_RUBRIC.yaml` line 252:

    - comparative_artifact_quality: on ≥ 2 of 3 positive scenarios
      candidate shows a persistent improvement…

Line 267 repeats "≥ 2 of 3 positive scenarios" for the negative rule.
But the rubric itself defines three scenarios:
`test-design-async`, `atdd-api-async-corrected`, and
`docs-only-rust-repo` — where `docs-only-rust-repo` is a NEGATIVE
control (own section `docs_only_control`). So there are only TWO
positive scenarios, not three. The decision rule as-written is
either arithmetically impossible or forces a false-negative floor.

## §11 Grader and schedule executor missing — CONFIRMED

Directory `rdx-tea/evals/grading/` exists but contains only a legacy
detector script from D2:

    $ ls rdx-tea/evals/grading/
    detectors.py

There is no `rdx-tea/evals/run_pilot.py` and no
`rdx-tea/evals/grading/grade_pilot.py`. The pilot rubric is
therefore a contract with no enforcer.

## Verdicts table before D3.3.2 code changes

| Gap | Handoff § | Confirmed by | Closed after cycle? |
|---|---|---|---|
| §1 baseline path | 5 | grep of invoke_runtime.py + run_live.py | YES — arm-specific runner + skill install |
| §2 schedule run_id ignored | 6 | prepare_workspace L107 + wrapper SKILL.md | YES — invocation.json contract + wrapper reads it |
| §3 candidate-only schema | 7 | live-evidence.v1 required fields | YES — live-evidence.v2 with oneOf branches |
| §4 free-text classifier | 8 | run_live._walk_for_invocations | YES — structured tool_use only |
| §5 34 mandatory skips | 11 | pytest-baseline.junit.xml + test file line 29 | YES — RDX_TEA_UPSTREAM_ROOT env + JUnit-based skip gate |
| §6 count-sum vs unique | 11 | JUnit tests= counts + IDs set difference | YES — canonical single collection |
| §7 source-lock error masked | 12 | source-lock-report.txt | YES — real bootstrap.py --verify-only |
| §8 runtime evidence constant | 9 | run_live._finalize_evidence | YES — init-event parser + surface diff |
| §9 cleanup constant | 13 | run_live._finalize_evidence + abort_run mismatch | YES — observed cleanup dict, structured lock JSON |
| §10 impossible decision rule | 14 | rubric YAML lines 252/267 | YES — rubric v3 with 2 positive scenarios |
| §11 grader/executor missing | 15/16 | ls of grading dir | YES — run_pilot.py + grade_pilot.py |

## Stop conditions the handoff enumerates

None of the "immediately stop before live smoke" conditions are
satisfied at START_HEAD (all eleven gaps still open). The corrected
ATDD live smoke MUST NOT be executed until §5 through §16 of the
D3.3.2 handoff have landed and are proven by tests.

## What this audit does NOT claim

- It does NOT declare `D3_3_2_PASS`. That verdict is only issued once
  every §20 acceptance clause holds AND the corrected ATDD smoke has
  produced verifiable schema-v2 evidence in this cycle. All eleven
  code deliverables are the prerequisite.
- It does NOT claim the historical D3.3 evidence is fabricated. The
  three D3.3 transcripts have 0 `Task` tool_use events (verified in
  D3.3.1 audit). The concern is that under the CURRENT harness the
  free-text classifier could later produce a false OBSERVED_SEQUENTIAL
  in a NEW run without a real Skill event — a forward-looking risk,
  not a backward-looking accusation.
