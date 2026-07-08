# RDX-TEA production runtime (install-tree)

This subtree is the **production runtime** of the RDX ↔ TEA adapter — the
sole surface the installer (Wave 7) copies into a user project. It is
self-contained: it vendors its router and resolves the canonical KB
without the RDX dev repository.

## Location is intentional (NOT moved in v1)

The illustrative D4 layout suggested hoisting this tree to a top-level
`rdx-tea/runtime/`. **Wave 1 deliberately does not move it.** This path is
embedded in the branch CI workflow, the bootstrap, the test suite, and
the proven D3.4.1 pilot; a physical move is a high-risk, zero-behaviour
change. This README is the pointer that stands in for that move. Any
future hoist is a post-v1 cleanup that must re-pin the golden bundle
hashes (see `w1_bundle_golden.txt` in the repo's evidence hashes tree).

## What ships (the shipped surface)

```
_bmad/rdx-tea/
├── canonical/     # RDX rule KB; source-locked; sole projection input
├── scripts/       # prepare, wrapper, binder, validator, parser,
│                  #   obligation_matrix, router (vendored), diff
├── bootstrap/     # bootstrap.py + sources.lock (identity stamp)
└── VERSION        # adapter version — pinned to sources.lock:adapter_version
.claude/skills/rdx-tea-*/SKILL.md   # wrapper Skills (LLM-facing contract)
```

`VERSION` is reconciled to **0.3.2**, equal to
`bootstrap/sources.lock:adapter_version` (Wave 1, gate `G-W1-VERSION`).
`VERSION` is a stamp only — no generator reads it, so changing it cannot
alter any bundle byte.

## Boundary invariant (enforced)

This surface **must not** import the eval-only `live-harness` or `evals`
modules, and **must not** reference any path under the `live-harness`,
`evals`, or `evidence` trees. Those directories never ship. The invariant
is enforced by:

- `rdx-tea/tests/contracts/test_l0_boundary_split_import.py` (gate
  `G-W1-BOUNDARY`), and
- the `G-SPLIT-IMPORT` CI grep (Wave 8).

Full classification of every directory as production / eval / historical
/ test-only lives in `rdx-tea/implementation/PRODUCTION_EVAL_SPLIT.md`.
The legacy dev-coupled PoC in `rdx-tea/poc/adapter/` is reference-only and
never ships — see its own README.
