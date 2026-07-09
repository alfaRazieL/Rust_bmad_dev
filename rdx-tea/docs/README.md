# RDX-TEA operator documentation

Operator-facing guide for installing and running the **RDX ↔ BMAD TEA
adapter** (D4 v1). This documentation covers the *validated* wrapper path
only: install the adapter into a project, run a TEA workflow through the
RDX-TEA wrapper Skill, inspect the evidence a run produces, and
troubleshoot the common refusals.

These docs describe the shipped runtime (the adapter installed into your
project) and the wrapper Skills. They do **not** describe the internal
research/evaluation tooling, and they never ask you to configure any
credential.

## Contents

| Guide | Purpose |
|---|---|
| [INSTALL.md](INSTALL.md) | Install / update / uninstall the adapter into a project; project-surface isolation; how authentication is preserved. |
| [RUN_WORKFLOWS.md](RUN_WORKFLOWS.md) | Run `rdx-tea-test-design` / `rdx-tea-atdd` through the wrapper Skill: sequential requirement, `prepare-run → child skill → finalize-run`, and the run-report. |
| [EVIDENCE_INSPECTION.md](EVIDENCE_INSPECTION.md) | Read `run-report.json`, the per-artefact sidecars, the verifier checks, the workspace delta, artifact consistency, and the admission block. |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Resolve the common refusals: non-sequential mode, empty delta, lock held, overlay restoration, verifier/consistency failures, admission not admissible, installer version refusal. |

## The validated path in one picture

```
rdx-tea-setup install --project <project>     # install the adapter (auth untouched)
        │
        ▼
configure TEA sequential mode                 # _bmad/tea/config.yaml: tea_execution_mode: sequential
        │
        ▼
invoke the wrapper Skill                       # rdx-tea-test-design  OR  rdx-tea-atdd
        │
        ├─ prepare-run    (deterministic: active-context bundle, identity, lock, snapshot)
        ├─ child TEA skill (SAME session, Task/TaskOutput/TaskStop disabled)
        └─ finalize-run   (deterministic: delta, sidecars, verifier, admission)
        │
        ▼
inspect evidence                               # run-report.json, sidecars, verifier, admission block
```

Direct invocation of the child `bmad-testarch-*` skill **without** the
wrapper is **unvalidated** — it produces no active-context bundle, no
sidecar, and no verifier result. Always go through the wrapper Skill.

## What these docs deliberately do not claim

- No behavioural benefit versus a baseline is claimed. The adapter is a
  deterministic wrapper around a proven sequential lifecycle; it is not a
  quality benchmark.
- The docs do not present any research/evaluation-only flag as an
  operator step.
- The docs give no credential-configuration instructions. Authentication
  is preserved by leaving it entirely untouched (see
  [INSTALL.md](INSTALL.md#authentication-is-preserved-by-doing-nothing)).

## Not included in D4 v1 (deferred backlog — not operator steps)

The following are **deferred backlog**, not shipped operator commands.
They are listed here only so operators know they are intentionally absent;
do not attempt to run them.

- `rdx-tea-validate` — the enforcement-plane verdict command. **Deferred;
  it does not exist as a production operator command.** The shipped
  verifier is a behavioural integrity check inside `finalize-run`, not an
  enforcement verdict.
- Modes / hooks / CI-gate / Cat-4 approval judgment — deferred.
- Subagent / agent-team worker propagation — deferred (the validated path
  is strictly single-session sequential).
- Any comparative behavioural-benefit claim versus a baseline — out of
  scope, not claimed.
