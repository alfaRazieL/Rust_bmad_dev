# D3.3.3 — Precondition audit before auth-preserving live smoke

Independent re-verification of the auth-preserving-isolation and
live-admission gaps against the current Git HEAD, the actual installed
Claude Code CLI, and the committed transcripts. Nothing here trusts a
prior verdict without grounding it in a re-runnable command or a
committed byte.

## §0 Repository state at start

- START_HEAD: `c7829138a3d2e330c6745d886f77a8bf90947c2b` (matches handoff)
- `origin/main`: `d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d`
- Working tree clean apart from local `.agents/` scratch dir.

## §1 Claude Code CLI — actual installed version

- `which claude` → `/opt/homebrew/bin/claude`
- `claude --version` → `2.1.191 (Claude Code)` (the user updated it
  from 2.1.126; the agent did NOT update, reinstall, brew upgrade, or
  npm install anything).
- `claude auth --help` exposes: `login`, `logout`, `status`.
- `claude --help` confirms the isolation flags this stage needs all
  exist in 2.1.191: `--setting-sources`, `--strict-mcp-config`,
  `--mcp-config`, `--tools`, `--allowedTools`, `--disallowedTools`,
  `--settings`, `--disable-slash-commands`, `--permission-mode`,
  `--no-session-persistence`, `--add-dir`.

## §2 Auth is subscription OAuth, not an API key

- `claude auth status` (exit 0) reports `loggedIn: true`,
  `authMethod: "claude.ai"`, `apiProvider: "firstParty"`,
  `subscriptionType: "pro"`. (email / orgId / orgName redacted from
  all evidence.)
- `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` are BOTH unset in
  the shell.
- `CLAUDE_CONFIG_DIR` IS already set by the user's shell (to a value
  the agent does not record; only its presence and a SHA256 of the
  normalised path are stored). All auth preflights inherited this
  value unchanged and succeeded.

## §3 `apiKeySource: none` is NOT proof of missing OAuth

Direct comparison of committed transcripts:

| smoke | apiKeySource | terminal result | authed? |
|---|---|---|---|
| early success `smoke-td-async/td-20260702-193045` | `none` | real Skill invocation (`bmad-testarch-test-design`), 0 Task | YES |
| D3.3.2 fail `smoke-atdd-api-corrected-v2` | `none` | `authentication_failed`, `is_error: true` | NO |

Both show `apiKeySource: none`. The DIFFERENCE is the terminal
outcome, not the apiKeySource field. Therefore auth status must be
judged by the COMBINATION of {auth status command, exit code,
result.is_error, error type, actual model response} — never by
`apiKeySource` alone. This is the §10.2/§10.3 requirement.

## §4 Root cause of the D3.3.2 failed smoke — CONFIRMED

`ClaudeIsolation.env()` (run_live.py L262-269) sets:

    e["CLAUDE_CONFIG_DIR"] = str(self.config_dir)   # a temp dir

`_invoke` (L760-774) applies that env before calling the CLI. Pointing
`CLAUDE_CONFIG_DIR` at an empty temp dir makes Claude Code CLI stop
discovering the OAuth session stored in the user's real config; the
2.1.126 session terminated after one turn with
`error: authentication_failed`, `is_error: true`. Model never invoked
a Skill.

The early successful smokes did NOT override `CLAUDE_CONFIG_DIR`; they
inherited the user's real auth environment (and consequently also
inherited the user's MCP servers and dict `memory_paths` — the
contamination D3.3.2 was trying to remove when it broke auth).

The fix is therefore surgical: isolate PROJECT settings (MCP, memory,
skills, tools) WITHOUT touching `CLAUDE_CONFIG_DIR`. §5 preflights
below prove this works.

## §5 Auth preflight results (this stage, before any harness change)

- Normal-profile AUTH_OK (no config override, existing OAuth):
  exit 0, `is_error: false`, `result: "AUTH_OK"`, observed model
  `claude-haiku-4-5-20251001`. PASS.
- Project-isolated AUTH_OK (project `.claude/settings.json` +
  `--setting-sources project` + `--strict-mcp-config --mcp-config
  <empty>` + `--disallowedTools Task TaskOutput TaskStop`, still NO
  config override): exit 0, `is_error: false`, `result: "AUTH_OK"`,
  observed init surface `mcp_servers: []`, `plugins: []`, `skills: []`
  (disableBundledSkills honoured), `Task`/`TaskOutput`/`TaskStop`
  absent from `tools`, no `memory_paths` (autoMemoryEnabled=false).
  PASS.

Both preflights are recorded (sanitised) in
`rdx-tea/evidence/auth-preflight/D3_3_3_AUTH_PREFLIGHT.json`.

## §6 Current harness gaps (each confirmed in code)

### §6.1 Auth isolation still overrides CLAUDE_CONFIG_DIR

`ClaudeIsolation` (L216-269) sets `CLAUDE_CONFIG_DIR` and
`CLAUDE_MCP_CONFIG`. This is the auth-breaking abstraction. It must
be replaced by a project-only isolation that never touches
`CLAUDE_CONFIG_DIR`.

### §6.2 No fail-closed runtime outcome classification

`run_smoke` (L1169-1264) returns `{"status": "ok"}` whenever
`_finalize_evidence` does not raise. `invoke_runtime.invoke` returns
`exit_code` but nothing downstream converts a non-zero exit,
`result.is_error == true`, or an `authentication_failed` terminal
event into a FAILED run. The D3.3.2 v2 bundle proves this: it recorded
`cleanup.state = "FINALIZED"` and the CLI exited non-zero, yet the
orchestrator returned `status: ok`. This violates the §11 fail-closed
requirement.

### §6.3 Evidence bundle has no admission semantics

`live-evidence.v2.schema.json` records `cleanup.state` as an enum but
has no `run_outcome`, `admissible`, `admission_reasons`,
`auth_preflight_id`, or `runtime_result`. A failed run and a
successful run are indistinguishable at the schema level.

### §6.4 Cleanup measured before lock release

`run_smoke` calls `_finalize_evidence` (which calls
`observe_cleanup`) at L1241 and releases the lock afterwards at
L1244-1247. So `cleanup.observed.lock_state` is measured while the
harness still owns the lock → it reports `owned-still-present` even on
a clean run. The §13 requirement is to release the lock first, then
observe.

### §6.5 memory_paths dict collapses to a false empty list

`_extract_runtime_init` (L419-426) only assigns `memory_paths` when
`isinstance(v, list)`. The real init event emits
`memory_paths: {"auto": "..."}` (a dict), so the parser silently
records `[]`. Confirmed against
`smoke-td-async/td-20260702-193045` (memory_paths type = dict).

### §6.6 Model alias, not exact ID

`invoke_runtime.DEFAULT_MODEL = "haiku"` and `FORBIDDEN_MODELS`
lower-cases the model before checking. The pilot must pin the exact
schedule model `claude-haiku-4-5-20251001` and reject any alias with
`RUN_INVALID_MODEL_MISMATCH`.

### §6.7 Whole `.claude` tree copied into workspace

`prepare_workspace.prepare` copies the entire install-tree `.claude`
(both wrapper AND child skills) into every workspace regardless of
arm, then `ClaudeIsolation.bootstrap` copies the arm subset into a
SECOND location (the temp config dir). Result: a baseline workspace
still physically contains the RDX wrapper skill on disk, and every
skill exists twice. §7 requires arm-specific physical install with
one skill exactly once.

### §6.8 resume()/status() treat any bundle as completed

`run_pilot.resume` skips a run when `live-evidence.v2.json` exists,
and `status` counts it as done — even if that bundle recorded a
failed/authentication-failed run. §15 requires completed = only an
admissible SUCCESS bundle.

### §6.9 No Task/subagent denial

The current invocation passes `--permission-mode bypassPermissions`
with no `--disallowedTools`. The init event of a real run lists the
`Task` subagent tool as available. §9 requires it denied.

## §7 What this audit does NOT claim

- It does NOT claim the D3.3.3 live smoke will PASS. The auth
  preflight PASSes, but the corrected ATDD candidate smoke can still
  fail on wrapper/child invocation, pack activation, or the verifier.
  The admission gate will decide honestly.
- It does NOT record any token, credential, email, orgId, session id,
  or the value of `CLAUDE_CONFIG_DIR`.
- It does NOT treat `apiKeySource: none` as an auth failure — §3
  disproves that reading.
