# L3 — Cargo Integration Tests

Phase 2 deliverable.

## Layout

```
integration/
└── cargo/
    └── (drivers that consume fixtures from ../../fixtures/cargo-projects/)
```

Cargo project fixtures themselves live at `../fixtures/cargo-projects/`:

- `green-crate/`             — T-L3-CRATE-001
- `compile-fail-crate/`      — T-L3-CRATE-002
- `baseline-red/`            — T-L3-CRATE-003
- `regression-introduced/`   — T-L3-CRATE-004
- `unsafe-no-safety/`        — T-L3-CRATE-005
- `workspace/`               — T-L3-CRATE-006
- `with-build-rs/`           — T-L3-CRATE-007

## Cargo cache assumption

Tests assume `~/.cargo` is available and persistent across runs. Cold runs OK to take ≤ 5 min; cached runs MUST complete in ≤ 90s. Track with `--duration=10` in pytest.

## Toolchain pinning

Cargo fixtures use `rust-toolchain.toml` to pin a specific rustc version. Update is a tracked event (eval re-run, release re-gate).
