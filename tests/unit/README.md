# L1 — Unit Tests

Phase 2 entry-gate deliverable.

## Layout

```
unit/
└── validator/
    ├── test_diff_parser.py        # T-L1-DIFF-001..003
    ├── test_digest.py             # T-L1-DIGEST-001/002
    ├── test_comment_filter.py     # T-L1-COMMENT-001
    ├── test_exception_parser.py   # T-L1-EXC-001/002
    ├── test_aggregator.py         # T-L1-AGG-001..003
    ├── test_exit_codes.py         # T-L1-EXIT-001..005
    ├── test_baseline.py           # T-L1-BASE-001..004
    └── test_policy.py             # T-L1-POL-001
```

## Conventions

- One pytest function per YAML test case
- Function docstring starts with the test ID: `"""T-L1-DIFF-001: parse_added_lines extracts only + lines..."""`
- Fixtures imported from `tests/fixtures/`, not inlined except for trivial cases marked in YAML as `fixture: inline`
- Use `pytest.mark.parametrize` when multiple fixtures share the same logic
