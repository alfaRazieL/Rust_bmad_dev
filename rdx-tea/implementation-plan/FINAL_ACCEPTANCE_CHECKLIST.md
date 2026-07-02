# FINAL_ACCEPTANCE_CHECKLIST

The following boxes ALL must be checked before the RDX-TEA adapter can
be considered ready for production release. Each box maps to a G-gate
or a threshold in `RELEASE_GATES.md`.

## Knowledge plane

- [ ] G0 baseline: RDX 1.1 suite green at the SHA in SOURCE_LOCK §1.
      (currently: **PASS** — 307/0/0)
- [ ] G1 official extension surface confirmed by Builder + TEA in
      independent contexts. (currently: **PASS**)
- [ ] G2 canonical projection: deterministic; every canonical rule ID
      preserved; full 14-verdict vocabulary imported; drift test green.
      (currently: **PASS** at contract layer)
- [ ] G3 Router parity: 12 × 13 fixtures replay against projection; FN
      ≤ 2% on strong-positive; FP ≤ 5% on negatives. (currently:
      **PARTIAL_PASS** — contract level only)
- [ ] G4 safe lifecycle: 12 install/uninstall/rollback scenarios pass;
      valid TOML; user customisation preserved. (currently: NOT_RUN)
- [ ] G5 real TEA workflows execute all 8 skills in sequential mode
      with adapter installed; artefacts contain `active_packs`
      front-matter. (currently: NOT_RUN)
- [ ] G6 subagent seed appears in `subagentContext.knowledge_fragments_loaded`
      for atdd + (optionally) test-review / trace / automate / nfr.
      Worker payload critical preservation ≥ 95%. (currently: NOT_RUN)
- [ ] G7 behavioural improvement over baseline: N ≥ 10 (ordinary) or
      N ≥ 20 (critical) runs; statistically explainable improvement;
      measured context overhead. (currently: NOT_RUN)

## Enforcement plane (blocked until knowledge plane above closes)

- [ ] G8 RDX validator extension consumes TEA front-matter and emits
      `rdx-evidence.v1` envelopes; Cat-1 authority preserved. (currently:
      BLOCKED)
- [ ] G9 MODE_0..MODE_4 tie-in has real behavioural differences;
      hook/CI test green. (currently: BLOCKED)
- [ ] G10 24 mutation scenarios: 100% detection. (currently: BLOCKED)
- [ ] G11 hash-mismatch upgrade path works; unsupported TEA version
      fails closed or degrades safely. (currently: BLOCKED)

## Housekeeping

- [ ] `evidence/final/FINAL_VERIFICATION.json` verdict = `PROVEN`.
- [ ] `evidence/final/RDX_TEA_VARIANT_D_PROOF.zip` archive built and
      committed (if not creating file duplication).
- [ ] Full RDX baseline regression re-run against final adapter still
      shows 307/0/0.
- [ ] `git diff --check` clean.
- [ ] Adapter, overlay generator, and validator extension documented
      in `README.md`.
- [ ] Commit history on `rdx-tea-integration` reads as one logical
      stage sequence (per DEVELOPMENT_WINDOW_INDEX).

Only when every box is checked may the maintainer consider promoting
verdict from `PARTIALLY_PROVEN` to `PROVEN`.
