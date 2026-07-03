# Story — public async API with cancellation semantics (corrected)

Add a public asynchronous user-registration surface to the crate's
public API. The change ships in `src/lib.rs` so downstream crates can
import it, and introduces both a public data type (`pub struct User`)
and a public async function (`pub async fn create_user`).

## Story tags

Precommitted STORY_TAG_REQUIRED tags per canonical router-rules.json:

- `publish=true` — activates the `api` pack (published crate contract).
- `async` — activates the `async` pack.

## Acceptance criteria

- `pub struct User` is exposed from `src/lib.rs`.
- `pub async fn create_user(name: String) -> Result<User, ApiError>`
  is exposed from `src/lib.rs` and documents cancellation semantics.
- Cancellation, timeout, and graceful-shutdown behaviour are covered
  in the ATDD checklist.
- API boundary tests cover invalid input, oversize input, and Unicode
  edge cases as negative paths.
- Partial-progress preservation is documented — no torn writes when
  cancellation strikes mid-way through user creation.
- Task-lifecycle ownership is stated (who spawns, who joins, who
  cleans up on cancel).

## Non-goals

- No database wiring in this story.
- No auth / permissions surface — only the create call and its error
  type.
