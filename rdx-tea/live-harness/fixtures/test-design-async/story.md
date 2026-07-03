# Story — async cancellation contract for `tokio::spawn`

**Goal:** implement `run_task(input: Input) -> Result<Output, Error>` that
launches a `tokio::spawn` background worker and returns success only once
the worker completes.

Cancellation semantics:

- The caller may drop the returned future at any await point.
- When dropped, the background task must abort promptly and no partial
  progress may be observable.
- On graceful shutdown, the task should complete an in-flight iteration
  and then exit.

The reviewer should call out RP-ASYNC-005-relevant contract details:
cancel-safe vs not cancel-safe vs intentionally lossy semantics,
partial-progress state, cleanup ownership, and the test suite that
proves cancellation, timeout, and shutdown behaviour.
