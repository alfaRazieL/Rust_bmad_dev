# D3.3 Blockers

## §1 — Transcript path handshake

The harness's `invoke_runtime.py` saves the stream JSONL at
`<workspace>/_bmad/rdx-tea/runtime/<workflow>/<harness-run-id>/transcript.stream.jsonl`.

The wrapper's `finalize-run` computes `observed_mode` from a transcript
at `runtime/<workflow>/<wrapper-run-id>/transcript.stream.jsonl`.

The wrapper generates its own run_id inside its Step 1 (defaults to
`td-YYYYMMDD-HHMMSS`), which never matches the harness's scenario-based
id. Result: `_infer_observed_mode` returns `INFERRED_ABSENT` even when
a valid transcript exists at the sibling path.

Fix options:
- Harness moves the transcript into the wrapper's run dir after
  invocation (small copy). Simplest.
- Wrapper's `_infer_observed_mode` searches all sibling run dirs
  for a transcript. Broader change.
- Wrapper accepts an env var / --external-transcript-path override.

Recommended: harness fix. One-line change to `invoke_runtime.py`.

## §2 — Docs-only fixture missing story.md

The `docs-only-rust-repo` fixture lacks a `story.md`; the model
refused to run without it (defensive behaviour). Add a story that
describes a docs-only change.

## §3 — Independent smoke isolation

Each smoke is run in its own disposable git worktree with its own
runtime dir and identity. There is no cross-smoke coupling other than
the shared install-tree adapter bytes. This is by design so that a
mass eval later can parallelise arms without contention.

## Non-blockers

- Deterministic side is fully green (428 pytest nodes; run-specific
  overlay proven with real upstream resolver; workspace isolation
  test; pre-bind boundary; docs-only-in-Rust bundle empty; ATDD
  wrapper self-contained; oracle YAML matches matrix; CSV byte
  equality).
- Runtime discovery works; cheap-model policy enforced.
- Smoke A produced real TEA artefacts that cite RP-ASYNC-005 by
  ID and paraphrase.
