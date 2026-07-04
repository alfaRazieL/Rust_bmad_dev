# Story — background task runner

We are adding an internal background task runner to our service. It
spawns asynchronous work and lets the owner wait for completion.

## Product context

- The runner drives a long-running background job.
- The owner of the runner starts the job and later awaits its result.
- The service is redeployed frequently, so a job may still be running
  when the owner decides to stop waiting.

## Acceptance criteria

- Provide a `Runner` type with an async `run` method that starts the
  background job and returns its outcome.
- The runner must behave predictably if the owner stops waiting before
  the job finishes.
- Produce a test-design plan a reviewer could use to validate the
  runner's behaviour under normal and abandoned conditions.

## Out of scope

- Public API / crate publication (this is an internal type).
- Persistence.
