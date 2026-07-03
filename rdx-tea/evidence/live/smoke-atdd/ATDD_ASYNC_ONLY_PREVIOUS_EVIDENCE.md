# ATDD_ASYNC_ONLY_PREVIOUS_EVIDENCE

The evidence bundle at `atdd-20260703-084412/` documents a D3.3 smoke
run that used the `atdd-api-async` fixture with story tags
`["api", "async"]`.

Independent re-verification in D3.3.1 confirmed that this tag set does
**not** activate the canonical `api` pack:

- Canonical `api` pack policy: `STORY_TAG_REQUIRED`.
- Required tag values: `publish=true | library-crate | stable-cli-contract`.
- The bare tag `api` is treated as a shortcut for pack-name activation
  but still requires at least one matching positive_signal / path_signal.
- The old fixture's diff (`src/api.rs` with `pub async fn`) contains no
  matching signal because router positive signals check `pub fn`,
  `pub struct`, `pub enum`, `pub trait`, `pub use`, `pub mod`,
  `#[deprecated` — none of which appear in `pub async fn create_user`.
- The `path_signals` are `**/lib.rs` and `**/src/lib.rs` only; the old
  diff modifies `src/api.rs`.

Result:

- `active_packs = [async]` — API pack did NOT activate.
- `RP-API-*` obligations are missing from the run-manifest.
- The smoke bundle is retained as historical reference only. It does
  **not** prove `api + async` propagation.

The corrected fixture is at
`rdx-tea/live-harness/fixtures/atdd-api-async-corrected/`. It uses
`publish=true` + `async` tags and diffs `src/lib.rs` with an actual
`pub struct` / `pub enum` / `pub async fn` surface, so both path and
code signals for the `api` pack match. Re-verification proved
`active_packs = [api, async]` deterministically (see
`rdx-tea/live-harness/tests/test_harness_unit.py::test_corrected_atdd_activates_api_pack`).

Live model-driven evidence with the corrected fixture is stored under
`rdx-tea/evidence/live/smoke-atdd-api-corrected/` once the harness is
run end-to-end.
