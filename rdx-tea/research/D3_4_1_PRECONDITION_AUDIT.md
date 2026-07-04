# D3.4.1 — Precondition Audit (12-run RDX Rule-Operation Pilot)

Recorded before any live pilot run. Every value re-verified against the
current Git HEAD and authoritative files — not from prior-window memory.

## 1. Repository identity

| Field | Value |
|---|---|
| Repository | https://github.com/alfaRazieL/Rust_bmad_dev |
| Branch | `rdx-tea-integration` |
| Actual START_HEAD | `b3f4b47a43f21bd9fd412a8bb32382cdd46b8c44` |
| Expected START_HEAD | `b3f4b47a43f21bd9fd412a8bb32382cdd46b8c44` — MATCH |
| `origin/rdx-tea-integration` | `b3f4b47a43f21bd9fd412a8bb32382cdd46b8c44` — MATCH (fast-forward, no drift) |
| `origin/main` | `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d` — MATCH |
| Working tree | clean within `rdx-tea/**` scope; only untracked non-scope items: `.agents/` (pre-existing, not touched) and the fresh `rdx-tea/evals/results/d3_4_1_dry_run/` produced by this audit |

No unexpected commits ahead of the pinned START_HEAD. No reset / force
checkout performed.

## 2. D3.4.0 final-verification identity (authoritative predecessor)

Read from `rdx-tea/evidence/final/D3_4_0_FINAL_VERIFICATION.json`:

| Field | Value |
|---|---|
| verification_version | `v6-d3.4.0` |
| tested_subject_sha | `f145c14bd7d3ec20143cb48ea76b9cab3feddb80` |
| evidence_commit_sha | `fdbbb9ac683527973e6ba4af50382c3fb859106f` |
| github_actions_run_id | `28694381995` |
| github_actions_conclusion | `success` |
| pytest unique | 561 collected / 561 passed / 0 failed / 0 skipped; source_lock PASS |
| verdict | `D3_4_0_PASS` |
| readiness | `D3_4_RULE_OPERATION_PILOT_READY` |
| overall D3 | `D3_PARTIALLY_PROVEN` |

The current START_HEAD `b3f4b47` is the D3.4.0 pointer-closure commit
directly on top of `fdbbb9a` (evidence-commit) → `f145c14`
(tested-subject). Chain intact.

## 3. Schedule + criteria integrity (locked)

| Artifact | Expected SHA256 | Observed SHA256 | Result |
|---|---|---|---|
| `rdx-tea/evals/runs/D3_4_RULE_OPERATION_RUNS.v3.json` | `0b2cd8eede3c8ae6c7d6d02cd98f464a7cfb119012caed41d0b59f3844abc97d` | `0b2cd8eede3c8ae6c7d6d02cd98f464a7cfb119012caed41d0b59f3844abc97d` | MATCH |
| `rdx-tea/evals/D3_4_RULE_OPERATION_CRITERIA.v1.yaml` | `3288de4fb4cdce54050d4811105e9520e2952d0cf14b41cd18d51b5188530920` | `3288de4fb4cdce54050d4811105e9520e2952d0cf14b41cd18d51b5188530920` | MATCH |

- schedule `locked: true`, `schema_version: rdx-tea-rule-operation-runs.v3`.
- criteria pinned inside the schedule (`criteria_sha256`) equals the
  standalone criteria SHA256 above — no post-hoc criteria mutation.
- evidence schema version: `rdx-tea-live-evidence.v4`.

Note: the historical `d3_4_0_dry_run/MANIFEST.json` records
`schedule_sha256 = a62fa7cc…`; that is the PRE-strengthening schedule.
Commit `34ecbcf` (require candidate finalize-run completion; regen
schedule v3) regenerated the schedule to the current locked
`0b2cd8ee…`. D3.4.1 binds against the current locked value, which is the
one pinned by `D3_4_0_FINAL_VERIFICATION.json`. This is expected, not a
drift.

## 4. Run counts

| Metric | Value |
|---|---|
| total runs | 12 |
| candidate rule-operation runs | 9 (3 scenarios × 3 repetitions) |
| baseline/control isolation runs | 3 (1 per scenario) |
| model (all runs) | `claude-haiku-4-5-20251001` (exact dated ID; aliases refused) |
| unique run ids | 12 |
| unique fixture hashes | 3 |
| unique prompt hashes | 4 (candidate-test-design, candidate-atdd, candidate/baseline variants) |

### Scenario map

| order | run_id | arm | scenario | fixture | workflow |
|---|---|---|---|---|---|
| 1 | ruleop-cand-001-test-design-async-rep01 | candidate | test-design-async | test-design-async-latent | test-design |
| 2 | ruleop-cand-002-test-design-async-rep02 | candidate | test-design-async | test-design-async-latent | test-design |
| 3 | ruleop-cand-003-test-design-async-rep03 | candidate | test-design-async | test-design-async-latent | test-design |
| 4 | ruleop-cand-004-atdd-api-async-corrected-rep01 | candidate | atdd-api-async-corrected | atdd-api-async-latent | atdd |
| 5 | ruleop-cand-005-atdd-api-async-corrected-rep02 | candidate | atdd-api-async-corrected | atdd-api-async-latent | atdd |
| 6 | ruleop-cand-006-atdd-api-async-corrected-rep03 | candidate | atdd-api-async-corrected | atdd-api-async-latent | atdd |
| 7 | ruleop-cand-007-docs-only-rust-repo-rep01 | candidate | docs-only-rust-repo | docs-only-rust-repo-control | test-design |
| 8 | ruleop-cand-008-docs-only-rust-repo-rep02 | candidate | docs-only-rust-repo | docs-only-rust-repo-control | test-design |
| 9 | ruleop-cand-009-docs-only-rust-repo-rep03 | candidate | docs-only-rust-repo | docs-only-rust-repo-control | test-design |
| 10 | ruleop-ctrl-010-test-design-async-rep01 | baseline | test-design-async | test-design-async-latent | test-design |
| 11 | ruleop-ctrl-011-atdd-api-async-corrected-rep01 | baseline | atdd-api-async-corrected | atdd-api-async-latent | atdd |
| 12 | ruleop-ctrl-012-docs-only-rust-repo-rep01 | baseline | docs-only-rust-repo | docs-only-rust-repo-control | test-design |

Expected active packs per criteria v1: test-design-async → `[async]`;
atdd-api-async-corrected → `[api, async]`; docs-only-rust-repo → `[]`
(forbidden prefix `RP-` — no pack may activate).

## 5. Authentication status (sanitized preflight)

| Check | Result |
|---|---|
| `which claude` | `/opt/homebrew/bin/claude` |
| `claude --version` | `2.1.191 (Claude Code)` (matches D3.4.0) |
| runtime discovery | READY (headless surface `--print` / `--output-format stream-json` present) |
| `ANTHROPIC_API_KEY` | unset |
| `CLAUDE_CODE_OAUTH_TOKEN` | unset |
| `ANTHROPIC_AUTH_TOKEN` | unset |
| `apiKeyHelper` in user settings | absent |
| `CLAUDE_CONFIG_DIR` | SET to `/Users/m33tball/.claude-lion` = the **existing** user/session config dir (populated: sessions/projects/tasks). NOT set or overridden by this task; inherited unchanged. Harness `isolation.env()` never mutates it (`config_dir_overridden=false`). |
| functional auth query | `claude -p "Return exactly AUTH_OK"` → returned exactly `AUTH_OK`, exit 0, via existing OAuth, model `claude-haiku-4-5-20251001`, no API key |

**AUTH_PREFLIGHT_STATUS: PASS.** Auth policy honored: existing CLI OAuth
only; no API key, no `CLAUDE_CODE_OAUTH_TOKEN`, no `setup-token`, no
`apiKeyHelper`, no `/login`, no `CLAUDE_CONFIG_DIR` override. No secrets,
email, orgId, or environment dump recorded.

## 6. Deterministic dry-run status

Command:
```
python3 rdx-tea/evals/run_rule_operation.py dry-run \
  --schedule rdx-tea/evals/runs/D3_4_RULE_OPERATION_RUNS.v3.json \
  --out-root rdx-tea/evals/results/d3_4_1_dry_run
```

Result: **status PASS**, exit 0.

| Acceptance clause | Observed |
|---|---|
| 12 runs | 12 |
| 9 candidate | 9 |
| 3 baseline/control | 3 |
| unique run ids | 12 |
| no path collisions | collisions = 0; unique workspace dirs 12; unique evidence dirs 12 |
| candidate/control paths separate | true |
| prompt hashes match | PASS (runner raises on drift; none raised) |
| fixture hashes match | PASS (3 unique fixture hashes verified) |
| criteria version match | `rdx-tea-rule-operation-criteria.v1` |
| schema version match | `rdx-tea-live-evidence.v4` |
| schedule locked | true |
| schedule sha recorded | `0b2cd8ee…` (matches locked) |

Manifest: `rdx-tea/evals/results/d3_4_1_dry_run/MANIFEST.json`.

## 7. No existing live-pilot evidence collisions

- Live pilot output root `rdx-tea/evals/results/d3_4_rule_operation/`
  does **not** exist yet → no pre-existing bundles to overwrite.
- No `live-evidence.v4.json` present under any `d3_4_rule_operation*`
  path. Fresh, collision-free start.

## 8. Retry policy (precommitted, from schedule)

```
max_retries_per_run_id: 1
admissible_reasons: [INFRA_FAILURE, RUNTIME_FAILURE]
never_replace_silently: true
```

A genuine INFRA/RUNTIME failure may be retried once. Every failed
attempt is preserved on disk (harness `abort-run` writes `aborted.json`
and never overwrites; a successful retry references, never erases, the
failed attempt). Failures classed AUTH_FAILURE, SCHEDULE_DRIFT,
RUN_ID_MISMATCH, CONTAMINATION, TASK_DISPATCH, SCHEMA_FAILURE,
RULE_OPERATION_FAILURE, CONTROL_LEAKAGE, VERIFIER_FAILURE,
ARTIFACT_DECLARATION_FAILURE are NOT silently converted into infra
retries.

## 9. Stop conditions (armed)

Execution halts immediately with `D3_4_1_REJECTED` /
`RULE_OPERATION_INVALID` if any of: auth preflight fails; schedule SHA
drifts; criteria SHA drifts; fixture/prompt hash drifts;
`CLAUDE_CONFIG_DIR` overridden; API key/token used; baseline/control
sees RDX wrapper/bundle/sidecars/RP leakage; candidate stops invoking
wrapper+child; Task/subagent dispatch occurs; a failed attempt is
overwritten or lost; evidence schema/admission contradicts primitive
facts; verifier fails due to real rule-binding/canonical-source problem;
workspace-delta claims cannot be reconciled.

## 10. Precondition verdict

```
START_HEAD .............. b3f4b47 (matches expected)
D3.4.0 identity ......... intact (f145c14 / fdbbb9a / CI 28694381995 success)
schedule SHA256 ......... MATCH (0b2cd8ee…)
criteria SHA256 ......... MATCH (3288de4f…)
evidence schema ......... v4
run counts .............. 12 (9 candidate + 3 control)
auth preflight .......... PASS (existing OAuth; no API key; config dir not overridden)
dry-run ................. PASS (0 collisions)
evidence collisions ..... none
```

**PRECONDITION_AUDIT: PASS → cleared to execute the locked 12-run
rule-operation pilot in schedule order_index 1…12.**
