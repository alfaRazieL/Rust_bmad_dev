# rdx-tea/live-harness — headless live evaluation harness

Runs REAL model-driven TEA workflows in a disposable git worktree,
collects transcript + artefacts, and produces a schema-valid
verifier report.

## Layout

```
live-harness/
├── README.md                    # this file
├── runtime_discovery.py         # detect claude CLI + capabilities
├── prepare_workspace.py         # disposable worktree with adapter installed
├── invoke_runtime.py            # subprocess `claude -p` with skill invocation
├── collect_evidence.py          # pull run-report/sidecar/transcript together
├── run_live.py                  # orchestrator: discovery → prepare → invoke → collect
├── schemas/
│   └── live-evidence.v1.schema.json
├── fixtures/
│   ├── test-design-async/       # Rust async fixture
│   ├── atdd-api-async/          # Rust API + async fixture (story tag `api`)
│   └── docs-only-rust-repo/     # docs-only diff inside Rust repo (negative)
└── tests/
    └── test_harness_unit.py     # deterministic unit tests for the harness
```

## Runtime discovery

Before any live run:

```
python3 rdx-tea/live-harness/runtime_discovery.py
```

Prints the discovered CLI, version, model, and supported flags. Fails
closed if `claude --version` returns a version we do not know how to
drive.

## Model selection

Live runs default to a **cheap model** (Haiku / Sonnet) per the
project's cost policy — never Opus. The chosen model is recorded in
every evidence bundle under `model-metadata.json`.

## Rate limits + budget

Every invocation is called with `--max-budget-usd` and a strict
timeout so a runaway session cannot rack up cost.

## Isolation

`prepare_workspace.py` creates a fresh disposable git worktree, copies
the install-tree adapter, initialises an empty repo, and creates
per-run inputs. Two runs never share a worktree.

## Live vs simulator

The harness has NO simulator. If `runtime_discovery.py` reports the
CLI is missing or the version is unsupported, the harness refuses
to fabricate outputs — the live gate becomes `NOT_RUN` with a clear
blocker.

## Evidence

Each successful smoke saves everything the D3.3 prompt §7 lists under
`rdx-tea/evidence/live/<scenario>/<run-id>/`.
