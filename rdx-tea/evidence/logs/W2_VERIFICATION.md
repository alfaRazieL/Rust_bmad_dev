# Wave 2 — Rule KB & router productionization — verification

Knowledge-plane wave. Harden the KB + router: deterministic pack
activation from tags/diff; forbidden packs judged by ACTIVE packs (never
prose); canonical snapshot hash pinned; NO router logic fork.

- Branch: `rdx-tea-integration` (never `main`).
- START_HEAD (pre-W2 hygiene commit): `f68e8c9135546a300b69590206dd81eaa5da3c16`.
- Env: `rdx-tea/.venv-baseline/bin/python` (CPython 3.14.4, pytest 9.1.1);
  cwd = repo root `.../rdx-workspace/Rust_bmad_dev`.

## What changed (test/evidence only — ZERO runtime change)

| File | Kind | Class |
|---|---|---|
| `tests/unit/test_l2_w2_router_activation_matrix.py` | new W2 test module | TEST-ONLY |
| `evidence/hashes/w2_canonical_snapshot.txt` | canonical snapshot hash pin | HISTORICAL (evidence) |
| `evidence/hashes/w2_canonical_snapshot.py` | re-pin/verify helper | HISTORICAL (evidence tooling) |

No file under `canonical/`, `scripts/` (router.py, diff.py, prepare.py,
obligation_matrix.py), or any generator was modified. Therefore:

- **No router fork** — `scripts/router.py` untouched (STOP condition N/A).
- **No canonical change** → no source-lock re-pin / SOURCE_LOCK addendum
  required (STOP condition "canonical hash changes without an addendum" N/A;
  the pin records the *unchanged* production hash).
- **G-W1-NOBEHAVIOUR preserved** — W1 golden bundle signature byte-identical.

## Router is already correct; W2 locks it with tests

The production `prepare.prepare()` computes emitted packs as
`sorted(router_active ∩ obligation_matrix[workflow].packs)` when
`rust_scope`, else `[]` (`scripts/prepare.py`). The router (`scripts/router.py`,
vendored from RDX `rdx_validator/router.py`) skips the over-broad
`**/*.rs` path glob and never scans markdown for code signals. W2 adds a
self-contained test module that proves these invariants on the
criteria-v1 fixtures, plus the canonical snapshot pin.

## Task-by-task

1. **Router parity (exact set equality, all fixtures).**
   `test_w2_router_parity_exact_set_equality` — three-way `==` (no `<=`
   slack): `prepare emitted == router∩matrix == criteria-v1 expected` for
   each of `[async]` (test-design), `[api, async]` (atdd), `[]`
   (docs-only). Also `test_w2_required_rules_projected` asserts criteria-v1
   `required_rule_conditions` (RP-ASYNC-005; any_of RP-API-001/004/005)
   are projected into ACTIVE packs.
2. **Over-broad `**/*.rs` guard kept.** `test_w2_over_broad_rs_glob_guard_holds`
   — 4 packs (`async`, `data-security-io`, `macro`, `unsafe`) carry the
   bare `**/*.rs` glob (negative control: guard is load-bearing), yet a
   bare `.rs` edit with no positive signal activates `set()`.
   `test_w2_bare_rs_path_glob_is_skipped_in_source` asserts the skip is in
   the router source.
3. **Docs-only diff activates `[]`.** `test_w2_docs_only_activates_empty`
   — the docs-only fixture's prose NAMES `tokio::spawn` and `pub fn`
   (prose-bait); `rust_scope=False`, `active_packs==[]`, zero RP- rule ids.
   Forbidden `[RP-]` therefore holds by construction.
4. **Forbidden judged by ACTIVE packs, never prose.**
   `test_w2_forbidden_judged_by_active_packs` inspects the manifest's
   `active_packs[].rule_ids` (the projected obligations) — no id starts
   with a scenario's forbidden prefix. Per-pack × signal matrix
   (`test_w2_pack_activation_matrix`, 12 packs) + STORY_TAG_REQUIRED
   gating (`test_w2_story_tag_required_pack_gated`).
5. **Canonical snapshot hash pinned.**
   `evidence/hashes/w2_canonical_snapshot.txt` pins
   `a97d9f8590bc9e3a68ec7926c4b2887a219c71b783aa0821d6b339f6bfc5e8d8`
   (= `prepare._canonical_snapshot_hash()` = the manifest's
   `rdx_canonical_snapshot_sha256`). `test_w2_canonical_snapshot_hash_pinned`
   and `test_w2_manifest_stamps_pinned_canonical_snapshot` verify recompute
   == pin. Deterministic across two processes.

**No router fork (extra proof).** `test_w2_router_no_logic_fork_from_rdx`
— AST of `scripts/router.py` minus docstring/imports == AST of
`rdx-validator/rdx_validator/router.py` (they differ ONLY in docstring +
an import-compat shim). `test_w2_router_no_behavioural_fork_from_rdx` —
RDX's own router yields identical active packs on every scenario diff.

## Gate results

| Gate | Command | Result |
|---|---|---|
| **G-W2-PARITY** | `pytest rdx-tea/tests -k router_parity -q` | **PASS** — 4 passed |
| **G-W2-FORBIDDEN** | `pytest rdx-tea/tests -k "forbidden or docs_only" -q` | **PASS** — 5 passed |
| **G-W2-CANON** | `python rdx-tea/evidence/hashes/w2_canonical_snapshot.py` | **PASS** — recomputed == pinned, exit 0 |
| **G-DET** | canonical hash across 2 processes; W1 golden diff | **PASS** — identical; W1 golden byte-identical (94dffb95…) |
| **G-SCOPE** | `git diff --name-only origin/main..HEAD \| grep -Ev '^rdx-tea/\|^rdx-validator/rdx_tea/\|^\.github/workflows/rdx-tea-'` | **PASS** — empty |
| **G-SPLIT-IMPORT** | `pytest rdx-tea/tests -k boundary -q` | **PASS** — 11 passed (shipped surface clean) |

## Test runs

```
$ python -m pytest rdx-tea/tests/unit/test_l2_w2_router_activation_matrix.py -q
29 passed in 0.68s                       (RED first: 2 failed pre-pin, 27 passed)

$ python -m pytest rdx-tea/tests -q
166 passed in 8.39s                      (137 prior + 29 new)

$ python -m pytest rdx-tea/tests -k router_parity -q
4 passed, 162 deselected

$ python -m pytest rdx-tea/tests -k "forbidden or docs_only" -q
5 passed, 161 deselected

$ python rdx-tea/evidence/hashes/w2_canonical_snapshot.py
OK canonical snapshot a97d9f8590bc9e3a68ec7926c4b2887a219c71b783aa0821d6b339f6bfc5e8d8 matches pin
```

## STOP conditions — none hit

- router forks from RDX → NO (router.py untouched; AST + behavioural parity proven).
- forbidden judged from prose → NO (judged from manifest `active_packs[].rule_ids`).
- canonical hash changes without an addendum → N/A (canonical unchanged; pin records the current hash).
