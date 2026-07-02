# D3_CORRECTION_AUDIT — honest downgrades to the D2 evidence

**Purpose:** address prompt `RDX_TEA_D3_proof_correction_prompt.md` §3.
Every subsection below records one overclaim, the specific artefact
where it appears, the corrected status, and the follow-up work that
must close the gap.

Nothing here retracts real evidence. Only labels change. Test logs,
hash manifests, and the two Phase-2 review transcripts remain in
`rdx-tea/evidence/` untouched.

---

## §3.1 — G1 was overclaimed as `PASS`

**Where:** `rdx-tea/evidence/final/FINAL_VERIFICATION.json`
`gates.G1_official_extension_surface.status = "PASS"`.

**Why wrong:**

1. `SOURCE_LOCK.md §4` recorded BMAD / Builder / TEA upstream SHAs as
   `PENDING`. A `PASS` verdict cannot coexist with a `PENDING` source
   lock — the prompt (§3.1) explicitly rules that out.
2. `phase2-builder-review.md` and `phase2-tea-review.md` are role-
   playing subagent transcripts, not official Builder / TEA tool
   executions. They constitute *source-grounded review* (which they
   are — every claim carries a file:line reference), but they are NOT
   "official BMAD Builder / TEA workflow output".

**Corrected status:** `PARTIAL_PASS`.

**Newly-passing sub-claims (as of this addendum):**

- Upstream BMAD-METHOD SHA locked to `67f4499e…` (main HEAD) and
  `3bcd6c3c…` (v6.8.0 tag, matches host installation bit-exact) —
  see `D3_SOURCE_LOCK_ADDENDUM.md §1.1`.
- Upstream TEA SHA locked to `8734d51f…` (v1.19.0 tag, matches host)
  — see `D3_SOURCE_LOCK_ADDENDUM.md §1.3`.
- Host `resolve_customization.py` byte-identical to upstream v6.8.0.
- Host `bmad-testarch-test-design/customize.toml`,
  `bmad-tea/customize.toml`, `bmad-testarch-test-design/SKILL.md`
  byte-identical to upstream v1.19.0.

**Still open for G1 → full `PASS`:**

- Live invocation of the *real* Builder / TEA agents (not a role-
  playing subagent) against the RDX-TEA overlay design. Deferred to
  the D3 proof plan.
- Evidence from an actual `bmad-eval-runner` run over the RDX-TEA
  overlay (structural test — not the behavioural eval of §3.7).

---

## §3.2 — G2 was overclaimed: metadata projection, not semantic

**Where:** `rdx-tea/evidence/final/FINAL_VERIFICATION.json`
`gates.G2_canonical_projection.status = "PASS"`, plus
`rdx-tea/poc/adapter/projection.py` and
`rdx-tea/tests/contracts/test_l0_projection.py`
`test_l0_projection_generator_reads_only_canonical_inputs`.

**Why wrong:**

- `projection.py::CANONICAL_INPUTS` declares 8 files (router-rules.json,
  status-definitions.json, rule-check-map.json, authority-matrix.json,
  section-4-core.md, section-5-router.md, section-6-packs.md,
  section-8-governance.md).
- The current implementation only calls `_load_router()` and
  `_load_status()`. It **never parses** `section-4-core.md`,
  `section-6-packs.md`, `section-8-governance.md`.
- The emitted `rdx-tea-async.md` contains the pack's ID and signal
  lists but no normative rule body. `RP-ASYNC-005` appears only as a
  bullet under "Related canonical rule IDs" — none of the
  Rule/Required-reasoning/Validation text from the KB is present.
- TEA receiving these fragments learns rule *names*, not rule
  *content*.

**Corrected status:** `PARTIAL_PASS` — the current PoC is a
**metadata projection**, not a **semantic knowledge projection**.

**Follow-up (Phase B of the D3 proof plan):** implement a semantic
rule parser that produces the full normative IR per prompt §5.2:

```json
{
  "rule_id": "RP-ASYNC-005",
  "title": "Cancellation safety and async cleanup are explicit",
  "layer": "RISK_PACK",
  "importance": "COMMON",
  "trigger": "…",
  "risk": "…",
  "rule": "…",
  "required_reasoning": "…",
  "validation": "…",
  "exceptions": "…",
  "sources": ["…"],
  "pack_id": "async"
}
```

Corresponding RED tests are written in
`rdx-tea/tests/unit/test_l1_rdx_parser_v2.py` (Phase B).

**Retained honest sub-claims:**

- Router pack list, activation policies, confidence classes, rule
  IDs, and 14-verdict vocabulary are preserved verbatim across the
  projection — see the 9 currently-green L0 contract tests and the
  L1 tests for `_load_router` / `_load_status` / `render_index_csv`.
  These now belong to the *metadata* subset of G2, not the whole
  gate.

---

## §3.3 — Current `_tier_for` contradicts the accepted D2 reconciliation

**Where:** `rdx-tea/poc/adapter/projection.py::_tier_for` and
`rdx-tea/tests/unit/test_l1_projection_unit.py::test_l1_tier_matches_expected_packs`.

Current mapping:

```python
STRONG → core
MEDIUM → extended
WEAK   → specialized
```

But `BUILDER_TEA_RECONCILIATION.md §3.3` — the authoritative Variant
D2 constraint — says:

```
default = specialized
RP-TEST-* may be extended
nothing is core
```

The current L1 tests **enforce** the wrong mapping and are therefore
part of the problem, not evidence.

**Corrected action:**

1. RED regression tests demonstrating the contradiction are added to
   `rdx-tea/tests/unit/test_l1_regressions_d3.py`
   (`test_l1_regression_no_rdx_pack_is_tea_core`,
   `test_l1_regression_default_tier_is_specialized`,
   `test_l1_regression_only_test_pack_may_be_extended`).
2. `_tier_for` is rewritten to the correct policy.
3. `test_l1_tier_matches_expected_packs` is either updated to the new
   policy or removed as an artefact of the rejected assumption.
4. Emitted index CSV is regenerated; SHA-256 pin is updated in
   `evidence/hashes/PHASE4_projection_output.txt` alongside the old
   one for auditability.

## §3.4 — Global `rdx-tea-index.csv` is not TEA loading proof

**Where:** `rdx-tea/poc/projections/rdx-tea-index.csv`.

**Why wrong:** the generator writes a parallel CSV whose header matches
TEA's `tea-index.csv` schema. That header identity is trivial and does
NOT demonstrate:

- that TEA reads this file;
- that a workflow overlay can extend the per-workflow index safely;
- that a TEA workflow picks fragments from this list via its own
  tag-matching logic.

`BUILDER_TEA_RECONCILIATION.md §3.7` explicitly rejects the "parallel
index" approach as originally proposed. The Variant D3 design
(§5.3–§5.4 of the D3 prompt) replaces the parallel index with a **single
run-scoped active-context bundle** referenced by a static
`persistent_facts` entry. This eliminates the CSV entirely for v1.

**Corrected action:** the parallel `rdx-tea-index.csv` is retained as
historic evidence, but the D3 architecture (`ADR-002`) does not use it.
The `test_l0_projection_generator_emits_rdx_tea_index_row_per_pack`
test is downgraded from a design guarantee to a "metadata projection
still deterministic" regression.

---

## §3.5 — Static `persistent_facts` glob was called "JIT loading"

**Where:** `rdx-tea/architecture/ADR-001-INTEGRATION-ARCHITECTURE.md`
§6 wording: "workflow-level loading via `[workflow].persistent_facts`
overlay".

**Why wrong:** a static glob loads *every* matching file on every
activation. That is workflow-startup loading, not
Router-selected-pack-per-run JIT loading. It reintroduces exactly the
"context bloat" that RDX's Router was designed to prevent, and it
misrepresents the RDX contract to TEA.

**Corrected action:** Variant D3 replaces the static glob with an
activation-time `activation_steps_prepend` script that runs *before*
`persistent_facts` (verified by upstream TEA v1.19.0
`bmad-testarch-test-design/SKILL.md` steps 2 → 3). The script writes a
single stable file `_bmad/rdx-tea/runtime/<workflow>/active-context.md`
containing only the packs the RDX Router selected for the current
story/diff, and `persistent_facts` references that stable path.

---

## §3.6 — Framework/CI design used `{detected_stack}` before it exists

**Where:** `ADR-001-INTEGRATION-ARCHITECTURE.md` §6 (framework/ci
branch), `BUILDER_TEA_RECONCILIATION.md §3.1` bullet 2.

**Why wrong:** upstream v1.19.0 activation order
(`bmad-testarch-test-design/SKILL.md` §"On Activation" — verified
`Step 1 Resolve` → `Step 2 Prepend` → `Step 3 Persistent Facts` → `Step
4 Load Config` → `Step 5 Greet` → `Step 6 Append`) puts `Step 2
Prepend` BEFORE any workflow-body variables are resolved. A prepend
step cannot legally reference `{detected_stack}` because that variable
is populated later inside the workflow body.

**Corrected action:** the D3 prepare script uses only environment-
level detection: `Cargo.toml`, `rust-toolchain[.toml]`, changed `.rs`
files, story metadata, RDX Router input. All of those are readable
without a workflow variable.

---

## §3.7 — Subagent seed mechanism had no supported seam

**Where:** `ADR-001-INTEGRATION-ARCHITECTURE.md` §7.

**Why wrong:** `subagentContext = { … }` is a JS-shaped literal inside
skill-owned `steps-c/*.md`. Sparse TOML overlays do not modify literal
JS inside step markdown. Adding a filename to a list does not force a
child to load that file. Both Phase-2 reviews flagged this.

**Corrected action:** Variant D3 v1 **does not claim subagent
support**. Wrappers explicitly request `sequential` mode, verify the
resolved mode, and fail closed if TEA still resolves subagent. Optional
future subagent support becomes `G6F` (non-blocking). This is a
substantial narrowing of scope, not a downgrade of proof.

---

## §3.8 — `active_packs` frontmatter had no supported injection seam

**Where:** `PROOF_COMPLETION_PLAN.md` Stage 05 acceptance criterion
"TEA output contains `active_packs` frontmatter".

**Why wrong:** `workflow.yaml` and `steps-c/*.md` are read-only; sparse
overlays do not edit output templates.

**Corrected action:** Variant D3 replaces this with a **deterministic
sidecar** `<tea-artifact>.rdx-tea.json` produced by an `on_complete`
binder (upstream-verified seam — see §5.3 of this document).

---

## §3.9 — FINAL_VERIFICATION.json referenced a non-existent schema

**Where:** `rdx-tea/evidence/final/FINAL_VERIFICATION.json` line 2
`"$schema": "…/rdx-tea/architecture/final-verification.schema.json"`.

**Corrected action:** create the schema
(`rdx-tea/architecture/final-verification.schema.json`) and add a
schema-validation test. Alternatively remove the ghost reference. This
audit chooses **create**, because the schema is genuinely useful for
downstream automation.

---

## §3.10 — Local pytest logs were being called "CI-verified"

**Where:** `rdx-tea/evidence/logs/*.log`, `FINAL_VERIFICATION.json`
gate descriptions.

**Corrected action:** logs are called `local-runtime-evidence`, not
`ci-verified`. GitHub Actions status for `bdf3f319…` was not consulted
in the previous work window. If a check-suite exists at push time it
is separately recorded; otherwise this gap remains open.

---

## Summary of downgrades

| Gate | Was | Now | Reason |
|---|---|---|---|
| G1 | PASS | PARTIAL_PASS | role-review ≠ official; source lock now closes the upstream-SHA gap but not the live-run gap |
| G2 | PASS | PARTIAL_PASS | metadata-only projection, semantic parser not yet written |
| G3 | PARTIAL_PASS | PARTIAL_PASS | unchanged (contract layer proven, fixture replay + scope filter still pending) |
| — | — | new | Add G6F non-blocking future subagent-support gate |
| G6 | NOT_RUN | superseded | replaced by `G6_v1_context_continuity_sequential` per prompt §5.1 |

Downstream artefacts (`ADR-002`, `D3_PROOF_PLAN.md`,
`D3_FINAL_VERIFICATION.json`) reflect these corrections.
