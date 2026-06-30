# Compatibility Matrix — V5 (canonical, machine-readable)

Authored as the Phase 6 deliverable promised by `tests/compatibility/README.md`.
The trailing JSON block is the source of truth read by
`tests/compatibility/test_compat_matrix.py`. Edit both together.

## V5 minimums (must hold for any supported row)

- Python 3.11+ (`tomllib` stdlib required)
- Git 2.30+
- Rust stable (cargo + rustc)
- BMAD with resolver-stable `agent.menu` merge

## Supported rows

| OS            | Python | Rust   | BMAD     | CI gates run                  |
|---------------|--------|--------|----------|-------------------------------|
| ubuntu-latest | 3.11   | stable | v6.9.0   | L0 + L1 + L2                  |
| ubuntu-latest | 3.12   | stable | v6.9.0   | L0 + L1 + L2 + L3 + L4 + L6/L7|
| ubuntu-latest | 3.13   | stable | v6.9.0   | L0 + L1 + L2                  |
| macos-latest  | 3.11   | stable | v6.9.0   | L0 + L1 + L2                  |
| macos-latest  | 3.12   | stable | v6.9.0   | L0 + L1 + L2                  |
| macos-latest  | 3.13   | stable | v6.9.0   | L0 + L1 + L2                  |

## Not supported in V5

- Python 3.10 and earlier (no `tomllib`)
- Windows native (degrades to Mode 0 advisory; deferred to V6)
- Web-only Claude (no shell — Mode 0 only)
- Codex CLI / Cursor (standalone validator works; wrapper does not — V7)

<!-- machine-readable-block-begin -->
```json
{
  "version": "v5",
  "minimums": {
    "python": "3.11",
    "git": "2.30",
    "rust": "stable",
    "bmad": "v6.9.0"
  },
  "rows": [
    {"os": "ubuntu-latest", "python": "3.11", "rust": "stable", "bmad": "v6.9.0", "gates": ["L0", "L1", "L2"]},
    {"os": "ubuntu-latest", "python": "3.12", "rust": "stable", "bmad": "v6.9.0", "gates": ["L0", "L1", "L2", "L3", "L4", "L6", "L7"]},
    {"os": "ubuntu-latest", "python": "3.13", "rust": "stable", "bmad": "v6.9.0", "gates": ["L0", "L1", "L2"]},
    {"os": "macos-latest",  "python": "3.11", "rust": "stable", "bmad": "v6.9.0", "gates": ["L0", "L1", "L2"]},
    {"os": "macos-latest",  "python": "3.12", "rust": "stable", "bmad": "v6.9.0", "gates": ["L0", "L1", "L2"]},
    {"os": "macos-latest",  "python": "3.13", "rust": "stable", "bmad": "v6.9.0", "gates": ["L0", "L1", "L2"]}
  ],
  "unsupported": [
    "python<3.11",
    "windows-native",
    "claude-web-only",
    "codex-cli-wrapper",
    "cursor-wrapper"
  ]
}
```
<!-- machine-readable-block-end -->
