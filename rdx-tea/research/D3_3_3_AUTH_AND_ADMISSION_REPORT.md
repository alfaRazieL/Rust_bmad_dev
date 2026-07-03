# D3.3.3 Auth-and-Admission Report

Scope: close the D3.3.2 blocker (isolated `CLAUDE_CONFIG_DIR` broke
OAuth) and execute one admissible corrected-ATDD candidate live smoke
under the user's existing CLI subscription auth. Nothing below is
stated more strongly than the committed evidence supports.

## 1. Auth policy actually followed

- Used ONLY the existing Claude Code CLI OAuth session
  (`claude auth status` → `loggedIn: true`, `authMethod: claude.ai`,
  `firstParty`, `pro`). email/orgId/orgName redacted from all evidence.
- Did NOT use `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`,
  `setup-token`, `apiKeyHelper`, a separate API billing, `--bare`, or
  automatic `/login`.
- Did NOT override `CLAUDE_CONFIG_DIR`. The user's shell already sets
  it; the harness inherits it unchanged. Only its presence and a
  SHA256 of the normalised path are recorded — never the value or the
  directory contents.
- The agent did NOT update / reinstall / brew-upgrade / npm-install
  Claude Code. Observed version: 2.1.191 (updated by the user).

## 2. Auth preflight (before any harness change)

- `claude auth status` — exit 0, loggedIn true.
- Normal-profile AUTH_OK (no config override): exit 0, is_error false,
  result `AUTH_OK`, model `claude-haiku-4-5-20251001`.
- Project-isolated AUTH_OK (`--setting-sources project` +
  `--strict-mcp-config --mcp-config <empty>` +
  `--disallowedTools Task TaskOutput TaskStop`, still no config
  override): exit 0, is_error false, result `AUTH_OK`; observed init
  `mcp_servers: []`, `plugins: []`, `skills: []` (bundled disabled),
  `Task`/`TaskOutput`/`TaskStop` absent from `tools`.

Both preflights are recorded (sanitised) in
`rdx-tea/evidence/auth-preflight/D3_3_3_AUTH_PREFLIGHT.json`. They
prove project isolation preserves OAuth when `CLAUDE_CONFIG_DIR` is not
overridden — the exact D3.3.2 failure mode is closed.

## 3. Harness changes

- `ProjectRuntimeIsolation` replaces `ClaudeIsolation`; never sets
  `CLAUDE_CONFIG_DIR`; env() adds only
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`; preflight fails closed on any
  config-dir modification or injected API key/token.
- Project isolation via workspace `.claude/settings.json`
  (`disableBundledSkills`, `disableClaudeAiConnectors`,
  `autoMemoryEnabled:false`), `--setting-sources project`,
  `--strict-mcp-config --mcp-config <empty>`,
  `--disallowedTools Task TaskOutput TaskStop`.
- `prepare_workspace` installs arm-specific skills only
  (baseline=child, candidate=wrapper+child), each once.
- Exact model ID enforced (aliases refused).
- memory_paths dict/list/str/null parsed (no false empty); extra init
  fields (apiKeySource/agents/analytics_disabled/output_style/
  fast_mode_state) recorded; `apiKeySource: none` is NOT treated as an
  auth failure.
- Fail-closed outcome classification + `live-evidence.v3` schema with
  `run_outcome`/`admissible`/`admission_reasons`/`auth_preflight_id`/
  `runtime_result`; schema forbids a dishonest admissible bundle.
- Cleanup observed AFTER lock release; `admit_bundle` recomputes
  admissibility from primitive fields; `run_pilot` resume/status use
  admissibility.

## 4. Live smoke findings (three attempts, all preserved)

The single corrected-ATDD candidate smoke required two harness fixes
discovered from real transcripts. All three attempts are preserved as
honest evidence.

### Attempt 1 — WORKFLOW_FAILURE (diagnostic)
Prompt named `/rdx-tea-atdd`. Claude Code 2.1.191 expanded the
slash-command skill INLINE and the model followed its steps via Bash;
the CHILD `bmad-testarch-atdd` was invoked via a structured `Skill`
tool_use but the WRAPPER produced no `Skill` tool_use event.
`wrapper_skill_invoked=false` → not admissible. Auth WORKED (no
authentication_failed) — the D3.3.2 blocker was already resolved.

Finding: a slash-command skill named in the prompt is expanded inline;
it does not emit a `Skill` tool_use. The prior D3.3 "successful"
smokes had the same structure (only the child appeared as a Skill
event) — the D3.3.2 free-text classifier masked this.

### Attempt 2 — VERIFIER_FAILURE (reader bug)
Prompt changed to instruct invocation via the Skill TOOL. The wrapper
AND child then both emitted structured `Skill` events;
`active_packs=[api,async]`, OBSERVED_SEQUENTIAL, one artifact + one
sidecar, no contamination, no Task. The only failure was
`verifier_all_pass=false` — a bug in the harness reader, which looked
for a top-level `status` field while the verifier records a top-level
`verdict` plus a `checks` array (all PASS, `failed_checks: []`). The
reader was corrected; re-deriving the bundle from attempt-2's REAL
captured transcript/run-report/artifacts yielded SUCCESS/admissible.

### Attempt 3 — SUCCESS / admissible (authoritative)
Clean end-to-end `run_smoke` with both fixes. Evidence committed at
`rdx-tea/evidence/live/smoke-atdd-api-corrected-v3/`:

    run_id                 smoke-atdd-corrected-d3-3-3
    exit_code              0
    result.is_error        false
    authentication_failed  false
    model (exp==obs)       claude-haiku-4-5-20251001
    mcp_servers            []
    plugins                []
    memory_paths           []            (auto memory disabled)
    skills                 [bmad-testarch-atdd, rdx-tea-atdd]  (arm only)
    Task in tools          false
    wrapper_skill_invoked  true          (structured Skill event)
    child_skill_invoked    true          (structured Skill event)
    task_tool_use_count    0
    observed_mode          OBSERVED_SEQUENTIAL
    run_id_handshake       mismatch=false
    active_packs           [api, async]
    RP-ASYNC-005           present in artifact
    RP-API rule            RP-API-004 and RP-API-005 present in artifact
                           (satisfies "RP-API-001 or a relevant API rule")
    artifacts / sidecars   1 / 1  (one sidecar per artifact)
    verifier               verdict PASS, 9/9 checks PASS
    contamination          ""
    cleanup observed       lock absent, overlay absent, run dir + transcript retained
    run_outcome            SUCCESS
    admissible             true

`run_live.py admit --bundle …` independently re-admits the bundle:
`admissible: true`.

## 5. Prompt change and schedule regeneration

`arm_prompt` (candidate) now instructs the model to invoke the wrapper
via the Skill tool rather than as a slash command, so the runtime
emits a structured wrapper Skill event. Because this changed the
candidate prompt, and NO live pilot run had occurred (only a dry-run
and the smoke), `D3_4_PILOT_RUNS.v2.json` prompt hashes were
regenerated pre-pilot. New schedule SHA256:
`31861b48ca51887cd57bef6d1673b93be25ac69021c029018ed4d59c968bfdb2`.
The 18-run deterministic dry-run still PASSes with 18 unique ids and
9/9 arm split.

## 6. What is proven vs not

- PROVEN: existing CLI OAuth authenticates a project-isolated run; the
  corrected-ATDD candidate workflow, under haiku, invokes the wrapper
  AND child as structured Skill events, activates `[api, async]`,
  cites RP-ASYNC-005 + RP-API rules, produces one artifact + one
  schema-valid sidecar, passes the verifier, runs sequentially with no
  Task dispatch and no runtime contamination, and is admissible under
  the v3 schema + admission gate.
- NOT proven here: the baseline arm behaviour on a live model, and the
  comparative behavioural benefit (G7). Those belong to the D3.4
  pilot, which is explicitly NOT executed in this stage.
