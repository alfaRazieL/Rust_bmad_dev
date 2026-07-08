# `poc/adapter/` — classification: **KEEP-AS-REFERENCE** (do not ship, do not delete)

Decided in **Wave 1** (D4 productionization). See
`rdx-tea/implementation/PRODUCTION_EVAL_SPLIT.md` §1/§3/§4 and
`rdx-tea/research/D3_1_PRODUCTION_LAYOUT_AUDIT.md` §4.

## What this is

The original, **dev-coupled** proof-of-concept adapter:

```
poc/adapter/
├── projection.py     # RDX → TEA projection generator (PoC)
├── rdx_parser.py     # early KB parser
├── prepare.py        # early bundle prepare
└── binder.py         # early sidecar binder
```

It predates the self-contained production runtime in
`poc/install-tree/_bmad/rdx-tea/`. It is **superseded for runtime**: the
install-tree vendors its own `router.py`/`diff.py` and resolves the
canonical KB without the RDX dev tree, so it is the only thing the
installer ships. This adapter is **not** on the shipped surface and the
Wave-1 boundary test (`tests/contracts/test_l0_boundary_split_import.py`)
does not scan it.

## Why KEEP-AS-REFERENCE (not retire-later)

1. **It is dev-coupled by design and must never ship.** `prepare.py`
   does `sys.path.insert(0, REPO_ROOT / "rdx-validator")` and
   `from rdx_validator.router import ...`. That direct import is exactly
   why it cannot be installed into a user project — and exactly why the
   production install-tree exists instead. Being eval/reference-plane, it
   is *allowed* to read the RDX validator (boundary invariant:
   EVAL/HISTORICAL MAY read production; PRODUCTION MUST NOT depend on
   eval).

2. **It is still a live oracle for the L0/L1 contract layer.** These
   passing tests reference it directly and would break if it were
   removed:
   - `tests/contracts/test_l0_projection.py` — golden projection
     contract for `poc/adapter/projection.py` (regenerate goldens with
     `python rdx-tea/poc/adapter/projection.py --emit-hashes`).
   - `tests/unit/test_l1_projection_unit.py` — L1 unit tests for
     `poc/adapter/projection.py`.
   - `tests/unit/test_l1_rdx_parser_v2.py` — parser contract driven
     against `poc/adapter/rdx_parser.py`.

   (43 tests as of Wave 1; all green.)

## Retirement condition (future cleanup, NOT a D4 v1 wave)

Retire `poc/adapter/` only after the L0/L1 projection & parser contract
tests above are migrated to (or re-pointed at) the production
install-tree equivalents, with the golden hashes re-pinned under
`rdx-tea/evidence/hashes/`. Until then it stays. **D4.0/D4-Wave-1 delete
nothing** (`PRODUCTION_EVAL_SPLIT.md`: "D4.0 deletes nothing").

## Boundary status

- Not shipped by the installer.
- Not imported by any file under `poc/install-tree/`.
- Reference/eval-plane only; may import `rdx_validator`.
