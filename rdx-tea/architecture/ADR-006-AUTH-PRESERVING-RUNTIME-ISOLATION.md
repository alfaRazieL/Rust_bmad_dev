# ADR-006 — Auth-preserving runtime isolation and live admission

Status: ACCEPTED (D3.3.3)
Date: 2026-07-03
Extends: ADR-005-ARM-AWARE-PILOT-EXECUTION

## Context

The D3.3.2 corrected-ATDD live smoke never reached the model. The
`ClaudeIsolation` abstraction set `CLAUDE_CONFIG_DIR` to a temporary
directory to isolate MCP/memory/skills. Claude Code CLI stores its
subscription OAuth session in the real config dir, so pointing
`CLAUDE_CONFIG_DIR` at an empty temp dir made the CLI report
`apiKeySource: none` and terminate with `authentication_failed` before
any Skill ran. See `rdx-tea/research/D3_3_3_PRECONDITION_AUDIT.md` §4.

The user authenticates via a personal claude.ai Pro subscription
(`claude auth status` → `authMethod: claude.ai`, `firstParty`, `pro`).
There is no `ANTHROPIC_API_KEY` and no OAuth token in the environment.
The isolation must therefore preserve the existing OAuth session while
still removing project contamination.

## Decision

1. **Never override `CLAUDE_CONFIG_DIR`.** The new
   `ProjectRuntimeIsolation` replaces `ClaudeIsolation`. It inherits
   the caller's auth environment unchanged; `env()` adds only
   `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`. `preflight()` fails closed if
   `CLAUDE_CONFIG_DIR` was modified or if an API key / OAuth token is
   present in the isolation env.

2. **Isolate the PROJECT surface only.** A project `.claude/settings.json`
   (`disableBundledSkills`, `disableClaudeAiConnectors`,
   `autoMemoryEnabled: false`) plus `--setting-sources project`,
   `--strict-mcp-config --mcp-config <empty>`, and
   `--disallowedTools Task TaskOutput TaskStop`. Both auth preflights
   (normal-profile and project-isolated) proved auth survives this.

3. **Physical arm-specific skill install.** `prepare_workspace.prepare`
   takes an `arm` argument and installs exactly the arm's skills into
   `workspace/.claude/skills` (baseline = child only; candidate =
   wrapper + child), each exactly once, never the whole install-tree
   `.claude`. No skill is duplicated across a project dir and a config
   dir (there is no second config dir any more).

4. **Exact model identity.** The pilot default and the smoke pin the
   exact schedule model ID `claude-haiku-4-5-20251001`. `invoke_runtime`
   refuses aliases (`haiku`/`sonnet`/`opus`) when `require_exact_model`
   is set.

5. **Fail-closed runtime outcome.** After `invoke`, the transcript's
   terminal `result` event and any `authentication_failed` assistant
   event are parsed. `classify_run_outcome` returns the first failure
   in a fixed order (AUTH_FAILURE → TIMEOUT → RUNTIME_FAILURE →
   CONTAMINATION → RUN_ID_MISMATCH → WORKFLOW_FAILURE →
   VERIFIER_FAILURE → SCHEMA_FAILURE → SUCCESS). `apiKeySource: none`
   is NOT treated as a failure — auth is judged by the terminal
   outcome.

6. **Evidence v3 with admission semantics.**
   `live-evidence.v3.schema.json` adds `run_outcome`, `admissible`,
   `admission_reasons`, `auth_preflight_id`, and `runtime_result`. The
   schema forbids `admissible: true` when `exit_code != 0`,
   `contamination != ""`, `run_id mismatch`, `is_error`,
   `authentication_failed`, or (for candidate) a missing
   wrapper/child/bundle/verifier/OBSERVED_SEQUENTIAL. A failed run can
   never be a FINALIZED-admissible bundle.

7. **Cleanup measured after teardown.** `run_smoke` releases the lock
   and restores the overlay BEFORE `observe_cleanup`, so
   `lock_state == absent` reflects reality on a clean run.

8. **Structured admission gate.** `admit_bundle(bundle)` recomputes
   admissibility from the bundle's own fields (never trusting the
   recorded `admissible` flag) and is exposed via
   `run_live.py admit --bundle`.

9. **Admissibility-aware resume/status.** In `run_pilot`, `completed`
   means only an admissible SUCCESS bundle; `failed` / `invalid` are
   distinct; a retry preserves the failed bundle under a versioned
   attempt suffix and never deletes evidence.

## Rationale for the non-obvious choices

- **Keep `bypassPermissions`.** The wrapper runs Bash (python scripts,
  git). In headless `-p` mode the default permission mode would block
  those. The same value is used for both arms and the observed
  permission mode is recorded, so it does not distort comparability.
  Permission-mode is deliberately NOT part of the contamination diff
  (it is symmetric and CLI-normalised).

- **`--setting-sources project`, not `--bare`.** `--bare` disables
  OAuth (its help says auth becomes strictly `ANTHROPIC_API_KEY` /
  `apiKeyHelper`). `--setting-sources project` isolates settings
  without touching auth.

- **Task denied, TaskCreate/Get/List/Update tolerated.** The
  subagent-dispatch tool is `Task`; the todo-list tools
  `TaskCreate/TaskGet/TaskList/TaskUpdate` cannot spawn a subagent.
  `--disallowedTools Task TaskOutput TaskStop` removes the dispatch
  tools; the todo tools are recorded as runtime_builtins, identical
  for both arms.

- **`apiKeySource: none` is not an auth signal.** Both the early
  SUCCESSFUL smoke and the D3.3.2 FAILED smoke show
  `apiKeySource: none`; only the terminal result differed. Judging
  auth by `apiKeySource` would misclassify a valid subscription run.

## Consequences

- The corrected-ATDD live smoke can run under the user's existing
  OAuth without an API key and without touching `CLAUDE_CONFIG_DIR`.
- A failed live run is recorded honestly (non-admissible) instead of
  masquerading as `status: ok` / `FINALIZED`.
- Baseline and candidate workspaces physically contain only the arm's
  skills; the init `skills` list can be asserted against the arm.
- The admission gate and admissibility-aware resume/status make the
  future D3.4 pilot resumable and audit-correct.

## Alternatives considered

- **Copy the user's OAuth material into a temp config** — rejected by
  policy (§1.2): no credential copying, no Keychain reads, no token
  export.
- **Use `ANTHROPIC_API_KEY` / `setup-token`** — rejected by policy;
  the run must use the existing subscription OAuth.
- **`--bare`** — rejected; it disables OAuth and Skill discovery.
- **Trust the bundle's recorded `admissible` flag** — rejected; the
  admission gate recomputes from primitive fields so a dishonest
  bundle cannot self-admit.
