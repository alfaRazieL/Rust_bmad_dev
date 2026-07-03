# Story — public async API with cancellation semantics

Expose `create_user(name)` as a public async API in `src/api.rs`.

Acceptance criteria:

- The public function returns `Result<u64, String>` and is `pub async fn`.
- Cancellation semantics are explicit.
- Timeouts respected.
- Tests cover API boundary, async cancel, API validation failure.
