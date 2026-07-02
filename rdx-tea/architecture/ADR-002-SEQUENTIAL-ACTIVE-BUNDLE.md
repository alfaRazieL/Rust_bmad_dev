# ADR-002 — Variant D3: Sequential Active-Bundle Adapter

**Status:** proposed (D3_PARTIALLY_PROVEN per `D3_FINAL_VERIFICATION.json`)  
**Supersedes:** `ADR-001-INTEGRATION-ARCHITECTURE.md` (Variant D2).  
**Governs:** D3_PROOF_PLAN.md, all rdx-tea/tests/ integrations, prepare/binder PoC.  
**Depends on:** `D3_SOURCE_LOCK_ADDENDUM.md`, `D3_CORRECTION_AUDIT.md`,
`BUILDER_TEA_RECONCILIATION.md §3.3`.

## 0. Framing

D2 relied on two seams that Phase-2 reviews and the D3 correction audit
proved either non-existent (subagent context propagation) or misused
(agent-level overlay for workflow-scoped knowledge). D3 keeps only the
seams that are *actually* documented and byte-verified in upstream
BMAD-METHOD 6.8.0 and BMAD TEA v1.19.0
(`D3_SOURCE_LOCK_ADDENDUM §1`).

The architecture is deliberately narrower:

- **Sequential-only** execution. Subagent / agent-team support is a
  future concern (`G6F`) with an explicit fail-closed guard on v1.
- **Two official seams:** `activation_steps_prepend`
  (SKILL.md Step 2) and `on_complete` (per-workflow terminal step).
- **One stable persistent-facts entry** per workflow, pointing at a
  file the prepend step writes.
- **A semantic rule parser** whose output IS the bundle content — no
  more metadata-only projection.

## KNOWLEDGE PLANE

### 1. Canonical source

Same set as D2 (`SOURCE_LOCK.md §5`), but the parser now consumes the
NORMATIVE bodies of `section-4-core.md`, `section-6-packs.md`, and
`section-8-governance.md`, not only their headings. See
`rdx-tea/poc/adapter/rdx_parser.py` and
`rdx-tea/tests/unit/test_l1_rdx_parser_v2.py`.

### 2. Normalized rule IR

Every rule is parsed into a dict with keys:

```
rule_id, title, layer, importance, trigger, risk, rule,
required_reasoning, validation, exceptions, sources,
pack_id, source_file, source_line
```

Failure to parse any mandatory field raises `RdxParseError`
(fail-closed). The IR carries the rule *text*, not a paraphrase, and
retains a byte hash of the source file
(`source_hashes()` — pinned by `test_l1_parser_v2_source_hash_stable`).

### 3. Router replay uses the shipped RDX validator

`rdx-tea/poc/adapter/prepare.py` does NOT duplicate Router semantics.
It imports `rdx_validator.router.RouterRules.load` +
`rdx_validator.router.replay` verbatim and treats their output as
canonical. This directly addresses D3 prompt §3.3 ("no manual Router
drift"). Router parity is verified end-to-end by
`test_l2_d07_router_parity_with_rdx_validator`.

### 4. Workflow obligation matrix

Per-workflow filter of packs. Source: `BUILDER_TEA_RECONCILIATION §3.3`
+ TEA Phase-2 review §7. Encoded as
`prepare.WORKFLOW_OBLIGATION_MATRIX` and documented per-cell in
`rdx-tea/architecture/WORKFLOW_OBLIGATION_MATRIX.csv`. Regression:
`test_l2_d09_workflow_obligation_matrix_applied` — `trace` never
receives `unsafe` even when the diff activates it.

### 5. Active-context bundle

Output of `prepare.py`:

```
{project-root}/_bmad/rdx-tea/runtime/<workflow>/
    active-context.md
    run-manifest.json
```

The bundle contains only the rules that (a) the Router activated for
this diff/story/tags AND (b) the obligation matrix allows for the
workflow. Deterministic bytes (proven twice: intra-process by
`test_l2_d05_bundle_bytes_deterministic`; cross-process by
`test_l7_f07_prepare_output_deterministic_across_two_processes`).
Atomic replace via `os.replace` — `test_l2_d12` verifies no `.tmp`
leftovers.

### 6. Overlay topology (official seams only)

Per workflow, exactly one file:

```
_bmad/custom/bmad-testarch-<workflow>.toml
```

Content skeleton:

```toml
[workflow]

activation_steps_prepend = [
  "Run: python3 {project-root}/_bmad/rdx-tea/scripts/prepare.py --workflow <workflow> --project-root {project-root}. HALT on non-zero exit.",
]

persistent_facts = [
  "file:{project-root}/_bmad/rdx-tea/runtime/<workflow>/active-context.md",
]

on_complete = "Run: python3 {project-root}/_bmad/rdx-tea/scripts/binder.py --workflow <workflow> --project-root {project-root} --artifact <the artefact path>"
```

Verified end-to-end against **upstream v1.19.0** `resolve_customization.py`
by the 9-test `test_l4_upstream_customization.py` suite (Phase C).
The resolver's output:

- appends the prepend command to `activation_steps_prepend`;
- appends the bundle path to `persistent_facts` while preserving the
  base `file:{project-root}/**/project-context.md` entry;
- override-wins on the `on_complete` scalar;
- preserves any user `.user.toml` override;
- leaves the skill root byte-identical.

### 7. Sequential execution enforcement

D3 v1 rejects `subagent` and `agent-team` modes by design. Wrappers
(§9) request `sequential` explicitly. If the runtime resolves any
other mode, wrappers fail closed. The `prepare.run-manifest.json`
records `execution_mode: sequential` and the `binder`-emitted sidecar
propagates it verbatim
(`test_l4_e05_execution_mode_recorded_as_sequential`).

### 8. Semantic content of the bundle

Every rule that lands in the bundle carries `Trigger`, `Risk`, `Rule`,
`Required reasoning`, `Validation`, `Exceptions` verbatim from the KB.
See `_render_bundle` in `prepare.py`. RP-ASYNC-005's cancel-safe
phrasing appears verbatim in `test_l2_d01_async_diff_activates_async_pack_and_includes_obligations`.

## ENFORCEMENT PLANE

### 9. Sidecar as the binder output

`binder.py` runs as `workflow.on_complete` after the TEA workflow
writes its artefact. It writes `<tea-artifact>.rdx-tea.json` following
the schema at `rdx-tea/architecture/rdx-tea-run.v1.schema.json`.

The sidecar contains no LLM-set verdict — only:

```
schema_version = "rdx-tea-run.v1"
workflow, execution_mode = "sequential"
active_packs = [...]
artifact_path, artifact_sha256
prepare_manifest_sha256
projection_hash (= sha256 of the bundle)
prepared_at, bound_at
completed = true
optional: base_sha, head_sha, diff_digest, rdx_source_sha, tea_source_sha
```

`additionalProperties: false` in the JSON schema forbids introducing
verdict fields the LLM could write to.

### 10. Cat authority preservation

Not implemented at PoC level. The sidecar is the boundary at which an
external RDX validator will later derive the `rdx-evidence.v1`
envelope. Cat-1 remains `Validator: WRITE` (unchanged from RDX 1.1);
the LLM never writes a Cat-1 verdict — the sidecar has no field for it
by schema.

### 11. TEA gate vs RDX verdict

Kept separate: TEA's own gate vocabulary
(`PASS/CONCERNS/FAIL/WAIVED`) stays inside TEA outputs and is not
mirrored into the sidecar. `rdx-evidence.v1`'s 14-verdict enum is the
downstream RDX-side vocabulary and is not required inside the
adapter-owned files.

### 12. Modes and CI

Deferred to production stages. The current PoC does not implement
MODE_0..MODE_4 tie-in, pre-push hook, or `rdx-tea-gate.yml`. This is
explicitly BLOCKED behind G0..G7 PASS in `D3_FINAL_VERIFICATION.json`.

### 13. Lifecycle

- Install writes the overlay + PoC scripts under `_bmad/rdx-tea/`
  and `_bmad/custom/`. Nothing under `.claude/skills/**` is touched.
- Update = idempotent re-generation of scripts + hash of canonical
  contracts. Overlay TOMLs remain unless the schema changed.
- Uninstall removes `_bmad/rdx-tea/**` and `_bmad/custom/bmad-testarch-*.toml`
  but not `.user.toml` (user content).
- Compatibility pin: BMAD 6.8.0 + TEA v1.19.0 exact-tag or later
  where `resolve_customization.py` merge semantics remain unchanged.

Real installer implementation deferred to a future stage. Current
lifecycle proof covers idempotent prepare, atomic replace, and
`.user.toml` survival across resolver invocations
(`test_l4_d3_lifecycle.py`).

### 14. Rollback / upgrade

Rollback: remove owned files (single command). Upgrade: hash-mismatch
on RDX source or on `resolve_customization.py` triggers a version
compatibility check; behaviour is DESIGNED, tests deferred.

## 15. Failed / rejected alternatives (retained for auditability)

- **Uniform overlay across all 8 workflows** — rejected: obligation
  matrix requires per-workflow scope.
- **Parallel `rdx-tea-index.csv`** — rejected. Not consumed by any TEA
  step. Regression: `test_l7_f06_no_global_rdx_tea_index_consumed`.
- **`activation_steps_prepend` gated on `{detected_stack}`** — rejected:
  the variable does not exist at prepend time.
  Detection must use `Cargo.toml` / `rust-toolchain` / changed `.rs` /
  story tags / RDX Router.
- **Subagent seed via filename injection** — rejected. Seed filename in
  a list does not force a child to load the file.
- **LLM-written `active_packs` frontmatter in TEA outputs** — rejected.
  The sidecar carries the authoritative machine block; the TEA artefact
  stays in TEA's own format.
- **Metadata-only projection (D2 PoC)** — rejected. Retained as a
  deterministic regression test but no longer the primary artefact.

## 16. Consequences

- Cost: two ~200-line Python scripts (`prepare.py`, `binder.py`),
  one ~250-line parser, one 50-line CSV obligation matrix, one JSON
  schema for the sidecar, one overlay TOML per workflow.
- Blast radius: overlay TOML files; uninstall = file delete. No
  production RDX or upstream BMAD/TEA file is patched.
- Fragility: bounded to upstream API stability of
  `resolve_customization.py` and the workflow `on_complete` execution
  contract. Both are verified against upstream v6.8.0 and v1.19.0
  (`D3_SOURCE_LOCK_ADDENDUM.md`).
- What's not covered by this PoC: real LLM-driven TEA execution,
  behavioural evals, hook/CI/validator extension, MODE_0..MODE_4
  tie-in, judgment/Cat-4. All enumerated in `D3_PROOF_PLAN.md`.
