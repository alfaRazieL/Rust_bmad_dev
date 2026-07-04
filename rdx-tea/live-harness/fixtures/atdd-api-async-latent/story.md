# Story — public async user-registration API

We are shipping a small library crate that other teams will depend on.
It exposes a public asynchronous function to register a new user and
return a stable identifier.

## Product context

- The crate is published to our internal registry; downstream teams
  compile against its public surface.
- Registration runs asynchronously because it talks to a slow backend.
- Callers may abandon a registration in progress (the user closes the
  tab, the request is superseded, the caller's own deadline elapses).

## Acceptance criteria

- Expose `create_user(name) -> Result<User, ApiError>` from the crate
  root so downstream crates can call it.
- `User` and `ApiError` are part of the published surface.
- Empty or invalid names are rejected.
- The function must behave sensibly when the caller stops waiting for
  the result before it finishes.
- Provide acceptance tests that a reviewer could run to confirm the
  public behaviour.

## Out of scope

- Persistence layer wiring.
- Authentication / permissions.
