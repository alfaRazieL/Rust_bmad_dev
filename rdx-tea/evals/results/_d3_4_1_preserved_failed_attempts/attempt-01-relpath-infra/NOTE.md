# Preserved failed attempt 01 — operator infra misconfiguration (relative --out-root)

Class: **INFRA_FAILURE** (pre-invocation; NOT a rule-operation failure).

## What happened
The first D3.4.1 execution passed a **relative** `--out-root`
(`rdx-tea/evals/results/d3_4_rule_operation`) to
`run_rule_operation.py run-one`. The harness `invoke_runtime.invoke`
runs the `claude` CLI with `cwd=<workspace>` while passing
`--settings`, `--add-dir`, `--mcp-config` as the same relative path.
Because cwd was changed into the (relative-resolved) workspace, the
relative `--settings` argument no longer resolved, so the CLI exited
immediately:

```
Error: Settings file not found: rdx-tea/evals/results/d3_4_rule_operation/workspaces/<run_id>/.claude/settings.json
```

## Evidence that no live model ran
- All 12 `transcript.stream.jsonl` files are **0 bytes**.
- `init_event_seen = false`, `model_turn_seen = false`,
  `authentication_failed = false`.
- `invocation.exit_code = 1`, whole batch finished in ~6 seconds.
- No tokens spent; no TEA artifacts produced.

This is an operator/apparatus configuration defect, not a candidate
rule-operation or auth failure. The committed D3.4.0 smokes used
**absolute** workspace paths (e.g. `/tmp/rdx-baseline-ctrl-ws`),
confirming the harness requires absolute paths.

## Resolution
Retried per precommitted policy (`admissible_reasons` includes
`INFRA_FAILURE`, `max_retries_per_run_id: 1`) with an **absolute**
`--out-root`. No source, schedule, criteria, fixture, or tested-subject
file was changed — only the CLI argument value (relative → absolute).

These 12 bundles are preserved here (moved, never overwritten or
silently replaced). The disposable workspaces held only empty
transcripts and were removed after their (empty) evidence was captured.
