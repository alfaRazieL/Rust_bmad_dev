# BEHAVIORAL_EVAL_PLAN

Per prompt §12 L5. Owned by PROOF_COMPLETION_PLAN Stage 7.

## Rubric (fixed before any run — prompt §11.2)

Metrics recorded per run (JSON per transcript):

- `rule_recall` — matching rule IDs mentioned in outputs / expected active packs.
- `precision` — matching / total mentioned.
- `false_positive_rate` — irrelevant packs mentioned on negative-control fixtures.
- `false_negative_rate` — expected packs missing on strong-positive fixtures.
- `router_compliance` — boolean: did the agent explicitly consult Router?
- `test_strategy_quality` — 0..4 rubric.
- `rust_command_correctness` — count of hallucinated cargo/rustc flags.
- `test_oracle_quality` — 0..4 rubric.
- `negative_coverage` — presence of negative / adversarial tests.
- `traceability` — active_packs + rule IDs present in artefact frontmatter.
- `self_attested_cat1_pass` — count (target: 0).
- `subagent_knowledge_loss` — count of missing seed rules in child artefact.
- `context_cost_tokens` — token count of loaded facts (from `subagentContext.knowledge_fragments_loaded` size sum).
- `runtime_ms` — end-to-end.

## Sample sizes

| Claim | N |
|---|---|
| Router never skipped | 20 |
| No self-attested Cat-1 PASS | 20 |
| Unsafe / FFI escalation always raised | 20 |
| No irrelevant pack on negative controls | 20 |
| Worker payload preservation | 20 |
| Test strategy quality | 10 |
| Rust command correctness | 10 |
| Ordinary claim (per workflow) | 10 |

If runtime cost prevents reaching the threshold, the corresponding G-gate
stays `NOT_RUN` or `INCONCLUSIVE` — prompt §12 L5 last sentence.

## Model / prompt / fixture / config identity

Baseline vs candidate MUST hold constant:
- model (single Claude / Codex model version)
- prompt (the workflow's own preflight)
- fixture (rdx-tea/fixtures/stories/rust-{scenario}.md)
- runtime (single CLI / IDE, no cross-tool comparison)
- config (`_bmad/tea/config.yaml` untouched except for `tea_execution_mode`)
- workspace state (clean git tree at head; disposable copy)

Only the presence/absence of the RDX-TEA overlay changes across arms.

## Fixture set (initial, extendable)

Per prompt §13 minimum. Each fixture is a story markdown + a real
Rust project skeleton under `rdx-tea/fixtures/rust-projects/`:

- `async-cancel-shutdown`
- `lock-across-await`
- `unsafe-safety-contract`
- `ffi-panic-boundary`
- `public-api-semver`
- `cargo-features-workspace-msrv`
- `panic-discipline`
- `property-fuzz-compile-fail`
- `serde-untrusted-input`
- `db-transaction-idempotency`
- `time-retry-config-reload`
- `ops-tracing-sensitive-output`
- `performance-with-benchmark`
- `macro-proc-macro-build-script`
- `no-rust-doc-only-control`
- `safe-trivial-control`

For each fixture, run every applicable TEA workflow:

- test-design (all)
- framework (project-shape-specific)
- ci (project-shape-specific)
- atdd (async / test heavy)
- automate (test heavy)
- test-review (test heavy)
- nfr (perf / DB / security heavy)
- trace (all)

## Grading harness

Located under `rdx-tea/evals/grading/` (to build in Stage 7):

- Reads the transcript JSON.
- Applies the rubric.
- Emits a per-run row into `rdx-tea/evals/{arm}/{workflow}/{scenario}/{n}.json`.
- Aggregator merges rows and emits confidence intervals.

No numeric score is invented; every metric traces back to a boolean or a
count.
