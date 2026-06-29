# Compatibility Matrix

Cross-cutting tests for environment variation.

## Matrix (V5 target)

| OS | Python | Rust | BMAD | Status |
|----|--------|------|------|--------|
| Ubuntu 24.04 | 3.11 | stable | v6.9.0 | smoke-tested |
| Ubuntu 24.04 | 3.12 | stable | v6.9.0 | smoke-tested |
| Ubuntu 24.04 | 3.13 | stable | v6.9.0 | smoke-tested |
| Ubuntu 24.04 | 3.11 | MSRV (stable - 4) | v6.9.0 | smoke-tested |
| macOS 14 | 3.11 | stable | v6.9.0 | smoke-tested |
| macOS 15 | 3.13 | stable | v6.9.0 | smoke-tested |
| Windows native | 3.11 | stable | v6.9.0 | smoke-tested (Mode 1–3) |
| WSL | 3.11 | stable | v6.9.0 | smoke-tested |

## V5 minimums

- Python 3.11+ (required for `tomllib` stdlib)
- Git 2.30+
- Rust stable (cargo + rustc)
- BMAD with resolver-stable agent.menu merge

## Not supported in V5

- Python 3.10 and earlier
- Web-only Claude (no shell access — degrades to Advisory mode)
- Codex CLI / Cursor (V7 — standalone validator works; wrapper does not)

See `matrix.md` (to be authored Phase 6) for the canonical machine-readable list.
