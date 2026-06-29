# L5 — Behavioral Evals

Phase 6 deliverable. Consumed by `bmad-eval-runner`.

## Layout

```
evals/
├── router-not-skipped/         # T-L5-ROUTER-001
├── no-self-attested-pass/      # T-L5-NO-SELF-PASS-001
├── not-run-honesty/            # T-L5-NOT-RUN-001
├── mode-naming/                # T-L5-MODE-001
├── no-irrelevant-pack/         # T-L5-IRRELEVANT-001
├── context-pressure/           # T-L5-CTX-001  (closes Phase 0.1 pending)
├── fail-honesty/               # T-L5-FAIL-HONEST-001
├── cat3-scope/                 # T-L5-CAT3-SCOPE-001 (V6)
├── cat3-cat1-immutable/        # T-L5-CAT3-NO-CAT1-001 (V6)
└── doc-not-rust/               # T-L5-DOC-001 (V6)
```

## Eval entry structure

Each subdir contains a `case.yaml` with:
- `prompt:` — exact prompt passed to the LLM
- `expected_assertions:` — what the rubric will check in the transcript
- `repeat_count:` — N
- `pass_threshold:` — minimum acceptance rate
- `grader_model:` — model used for transcript grading
- `tested_model:` — model under test (varies; matrix)

## Tracking thresholds

Per-eval rolling-window pass rate stored in CI artifacts. A drop below threshold for 7 consecutive days triggers a release block.

## Why these are NOT deterministic gates

L5 measures LLM behavior, which is non-deterministic by design. Use these to detect REGRESSIONS in model behavior, not as per-PR blockers.

Deterministic gates live at L0–L4 and L6–L7.
