---
rdx_tea_bundle_version: 1
workflow: test-design
active_packs:
  - pack_id: async
    rule_ids:
      - RP-ASYNC-001
      - RP-ASYNC-002
      - RP-ASYNC-003
      - RP-ASYNC-004
      - RP-ASYNC-005
      - RP-ASYNC-006
      - RP-ASYNC-007
      - RP-ASYNC-008
      - RP-ASYNC-009
core_rules:
  - CORE-001
  - CORE-002
  - CORE-003
  - CORE-004
  - CORE-005
  - CORE-006
  - CORE-007
  - CORE-008
  - CORE-009
  - CORE-010
  - CORE-011
  - CORE-012
  - CORE-013
  - CORE-014
  - CORE-015
  - CORE-016
  - CORE-017
  - CORE-018
source_of_truth: canonical/router-rules.json + canonical/kb-sections/
---

# RDX active-context bundle for `test-design`

## Always-on Core rules

### `CORE-001` — Contract before code

**Exceptions:** Very small bugfixes may use a compact inferred contract; unspecified fields do not block work unless the missing information is material and cannot be resolved safely from authoritative local context.

**Required reasoning:** Identify which requirements come from the active task, project context/ADR policy, approved local customizations, reusable defaults, and generic model knowledge; resolve locally verifiable gaps from authoritative repository context, and escalate same-level conflicts or missing information only when they remain unresolved and materially affect safe execution under `CORE-016`.

**Risk:** The agent can invent missing requirements, lose protected-file boundaries, apply generic Rust defaults over local policy, or run the wrong validation when the task contract is implicit.

**Rule:** Before editing, establish a proportionate implementation contract from the active task and authoritative repository context: the goal and acceptance criteria, relevant scope and protected boundaries, expected error behavior, active risk tags, instruction priority, and applicable validation.

**Sources:** ['RUST-AGENT-002', 'RUST-AGENT-008', 'RUST-AGENT-012', 'audit minimal core item 1.']

**Trigger:** Always

**Validation:** The plan or work record lets review compare the actual diff and checks with the established contract; governance-specific evidence is required only when the task or project policy activates it.

### `CORE-002` — Repository model before patch

**Exceptions:** A purely local single-module fix may use a compact model, but it still needs the owning module, affected or observable call sites when any, and any external API/version assumption it relies on.

**Required reasoning:** Determine which crate owns the changed type or behavior, which callers observe it when any, which feature, cfg, target, or resolved-version assumptions are material to the patch, whether multiple resolved versions affect type identity, and whether newly introduced, materially changed, or uncertain external crate behavior requires version-matched authoritative evidence.

**Risk:** The agent can patch the wrong crate, call a nonexistent API, miss feature-gated code, or create incompatible cross-crate type flow when the repository and dependency graph are guessed.

**Rule:** Before implementation, reconstruct the smallest repository model sufficient for the changed behavior: the relevant workspace, package, module and type ownership, affected or observable call sites when any, and the feature/cfg/target or resolved-dependency-version boundaries material to the patch.

**Sources:** ['RUST-AGENT-005', 'RUST-CARGO-002', 'RUST-CARGO-007', 'audit minimal core item 2.']

**Trigger:** Always

**Validation:** The plan identifies the affected owner, affected or observable call sites when any, and feature, cfg, version, target, or API assumptions material to the patch; newly introduced or uncertain external API behavior has authoritative version-matched evidence.

### `CORE-003` — Ownership and lifecycle before implementation

**Exceptions:** Borrow-oriented APIs, callbacks, shared state, synchronization, and explicit read/fill/write-into APIs are valid when the caller-owned storage, lifecycle, thread domain, and mutation contract are explicit.

**Required reasoning:** Decide whether ownership should be returned as a value, borrowed, shared, transferred, or represented as mutation of caller-owned storage; whether sharing is single-threaded or cross-thread; whether `Rc`, `Arc`, `RefCell`, locks, atomics, or message passing match the mutability domain; and which path, event, or ownership condition ends the lifecycle.

**Risk:** Move errors, hidden leaks, unclear value flow, incorrect sharing primitives, and background-work bugs appear when ownership and lifecycle are discovered only after code is written.

**Rule:** Before implementing, identify the owner and lifecycle of each contract-relevant changed value, resource, and unit of background work; define, as applicable, how it is returned, moved, borrowed, shared, mutated, and eventually completed or released.

**Sources:** ['RUST-OWN-001', 'RUST-OWN-004', 'RUST-TYPE-004', 'audit minimal core item 3 and type-driven design section.']

**Trigger:** Always

**Validation:** Review can trace ownership and lifecycle for contract-relevant changed data, resources, and tasks, and can distinguish intentional clones, caller-owned outputs, sharing, or synchronization from mechanical compiler repairs, leaks, or globals.

### `CORE-004` — Root cause before borrow-checker cosmetics

**Exceptions:** Cloning, shared ownership, boxing, `'static`, and broad bounds are acceptable when they express the real API/lifecycle contract, spawn/callback/storage boundary, or a documented local invariant.

**Required reasoning:** Separate confirmed facts, deductions, and hypotheses; identify the real owner and lifetime relationship; prefer scoped borrows, operation reordering, ownership transfer, or API-shape fixes when those match the domain; distinguish `T: 'static` (all lifetime parameters carried by `T` outlive `'static`; therefore `T` cannot contain non-`'static` references tracked by the type system, but a particular value of `T` need not live for the whole program) from an actual `&'static T` or leaked/global value; justify any `clone`, sharing primitive, allocation, `'static` bound, or broad bound by the actual contract.

**Risk:** Blind `clone`, `Arc`, `Box`, `'static`, broad bounds, or ad hoc conversions can silence compiler feedback while making ownership, lifetime, API, or performance behavior worse.

**Rule:** Treat compiler and borrow-checker failures as design feedback: explain the semantic cause before introducing ownership-expanding repairs, stronger lifetime bounds or requirements for longer-lived data, broad trait bounds, or conversion glue.

**Sources:** ['RUST-AGENT-004', 'RUST-OWN-002` principle only', 'RUST-OWN-003', 'RUST-OWN-009', 'audit minimal core item 4. `RUST-OWN-002` extraction and allocation techniques are split into `REC-OWN-001` and `REC-PERF-001`.']

**Trigger:** Always

**Validation:** The repair record or review explains the cause, shows that any ownership-expanding construct is intentional rather than mechanical compiler appeasement, and rejects unnecessary `'static` bounds, leaks, or other stronger lifetime requirements that do not follow from the actual contract.

### `CORE-005` — Encode invariants in types

**Exceptions:** Independent flags, bitflag-style sets, simple local primitives, tightly scoped `if let` for one-branch handling, integer or `char` ranges, external `#[non_exhaustive]` enums, and defensive unknown-state handling are valid when the invariant is not improved by a new type or exhaustive enum match.

**Required reasoning:** Identify which invariant is being protected, where validation happens, whether constructors or fields must be private, whether the choice set is closed or externally extensible, whether each local enum match should enumerate variants or use a narrow single-branch form such as `if let`, and whether a simpler primitive remains clearer.

**Risk:** Primitive values, ambiguous booleans, and wildcard handling let invalid IDs, units, modes, and state transitions pass through code paths that the compiler could otherwise help constrain.

**Rule:** Use validated newtypes, enums, and closed domain states where they actually prevent invalid combinations or ambiguous call sites.

**Sources:** ['RUST-TYPE-001', 'RUST-TYPE-002', 'RUST-TYPE-008', 'audit minimal core item 5.']

**Trigger:** Always

**Validation:** API review and tests show invalid values are rejected at boundaries, call sites reveal semantic intent, and adding a variant to a locally owned closed enum forces review at match sites that must handle every state.

### `CORE-006` — Choose abstractions intentionally

**Exceptions:** Struct/enum definition bounds are valid when field storage, associated types, `?Sized` relaxation, or `Drop` coherence requires them; runtime extension points can justify trait objects; smart-pointer-like wrappers and guards can justify narrow unsurprising `Deref`.

**Required reasoning:** For abstraction mechanisms introduced, removed, or materially changed, determine whether an existing project or task contract already establishes the abstraction; whether the implementation set is open or closed; whether callers must name the concrete type; whether hidden `impl Trait` constraints are caller-visible; whether runtime dispatch or dyn compatibility is required; whether `Deref` expresses actual pointer or guard semantics; and whether each bound is needed at the type, impl, or method level. Load the public API pack for public `dyn`, return-position `impl Trait`, or `Deref` contract details when its router trigger matches.

**Risk:** Premature traits, misplaced generic bounds, `Any`-driven downcasts, coercion-driven `Deref` APIs, and wrong `dyn`/generic/`impl Trait` choices create over-constrained APIs, object-safety failures, runtime checks, hidden ownership/API boundaries, or needless layout/API churn.

**Rule:** Prefer an abstraction already established by the task or project contract; otherwise use the simplest representation that satisfies the current contract and observed call sites. Introduce, remove, or materially change traits, generics, trait objects, opaque return types, bounds, or `Deref` only when a concrete substitution, extension, ownership, dispatch, smart-pointer/guard, or public-contract need justifies it; place bounds at the narrowest site that needs them.

**Sources:** ['RUST-TRAIT-001', 'RUST-TRAIT-002', 'RUST-TRAIT-004', 'RUST-TRAIT-006', 'RUST-API-021', 'audit minimal core item 6 and traits/generics section.']

**Trigger:** Always

**Validation:** API and call-site review justify the abstraction and each non-trivial bound; compile checks verify the intended generic, dyn, and call-site forms, but compile success is not evidence that an abstraction or bound is necessary.

### `CORE-007` — Keep the diff scoped

**Exceptions:** A task may intentionally authorize broader refactors or boundary changes; a separate approval trail is required only when applicable project governance says so.

**Required reasoning:** Compare the planned patch against allowed files, protected files, risk tags, public surface, dependency/toolchain policy, and validation scope; if the necessary fix exceeds the authorized contract or enters a governed boundary, do not make boundary-crossing edits until the contract or required owner decision is updated; independent, reversible diagnosis, reproduction, and validation may continue only when they cannot prejudice or assume the pending decision.

**Risk:** Broad rewrites and unauthorized boundary changes hide regressions, invalidate review, and turn a local Rust repair into a dependency, public API, unsafe, schema, runtime, feature, toolchain, release, or governance change.

**Rule:** Limit edits to the task contract and do not cross a high-impact boundary unless the change is required and authorized by the task contract or project policy; when applicable governance requires a separate owner or specialist approval, escalate rather than self-approve.

**Sources:** ['RUST-AGENT-003', 'RUST-AGENT-009', 'RUST-ANTI-006', 'audit minimal core item 7 and anti-pattern section 22. Boundary-escalation routing details remain deferred to router/governance phases.']

**Trigger:** Always

**Validation:** Diff review can connect every changed file and behavior to the task contract, with the applicable task or project authorization or governance evidence for any boundary expansion.

### `CORE-008` — Errors are part of the specification

**Exceptions:** Application edges may use approved type-erased errors; tests and examples may use `unwrap`/`expect` under project policy; unreachable-by-construction cases are acceptable when the invariant is documented locally.

**Required reasoning:** Identify expected failure modes, external input boundaries, public API obligations, production versus test/example context, sensitive-data exposure in messages, whether a failure should be propagated, mapped, logged, returned, or explicitly treated as best-effort, and whether any panic path is a locally proven invariant rather than ordinary fallibility.

**Risk:** Stringly errors, hidden panics, erased public failures, and silently discarded `Result`s make callers unable to distinguish expected failure, programmer bugs, and operational faults.

**Rule:** Define the error contract for the changed boundary: use typed/domain failures where callers need to react, erase errors only at appropriate outer boundaries, preserve fallible results, and do not use `unwrap` or `expect` to handle external input or ordinary recoverable production failures; panic-based extraction is acceptable only after a narrow locally established invariant.

**Sources:** ['RUST-ERR-001', 'rewritten `RUST-ERR-002', 'RUST-ERR-004', 'audit minimal core item 8 and dangerous-rule note for `RUST-ERR-002`.']

**Trigger:** Always

**Validation:** Review and tests cover expected error paths; `Result`-producing calls are propagated, handled, logged with policy-approved context, returned, or intentionally justified as best-effort; any invariant-based production-path `unwrap` or `expect` is backed by a narrow locally established invariant, and `expect` messages avoid sensitive data.

### `CORE-009` — Make cleanup, cancellation, and task ownership explicit

**Exceptions:** Ordinary RAII/`Drop` remains appropriate for infallible local resource release and as a safety fallback; best-effort detached cleanup is acceptable only when loss semantics are explicit and not correctness-critical.

**Required reasoning:** For each lifecycle dimension actually touched, identify the resource or task owner, the explicit completion path, the fallback behavior on `Drop`, what cancellation may skip, whether the operation is cancel-safe, how each relevant long-lived task is awaited, stored, supervised, aborted, or intentionally detached, and where cleanup failures become visible.

**Risk:** Correctness-critical cleanup, cancellation, or background work can be skipped, detached, or fail invisibly when it is left to `Drop`, task-body fallthrough, or an untracked handle.

**Rule:** Treat fallible or protocol-significant `close`, `flush`, `commit`, `shutdown`, drain, join, cancellation, and task ownership as explicit lifecycle contracts when correctness depends on observing completion, failure, or accepted loss.

**Sources:** ['RUST-ERR-003', 'core parts of `RUST-ASYNC-003', 'RUST-ASYNC-004', 'RUST-ASYNC-021', 'RUST-OPS-007', 'audit minimal core item 9 and merge map. Async/ops pack details remain deferred to P9/P17.']

**Trigger:** Always

**Validation:** When the relevant lifecycle behavior is observable and a suitable harness exists, targeted cleanup, shutdown, cancellation, or lifecycle tests exercise it; otherwise focused integration or review evidence states how failure or accepted loss is surfaced and why executable validation was not feasible.

### `CORE-010` — Validate external boundaries

**Exceptions:** Internally bounded arithmetic, loop counters, constant expressions, and local primitives do not need extra ceremony when their bounds or overflow behavior follow from a proven local invariant or explicit project contract; explicitly lossy, saturating, or modular APIs are valid when their names and contract make that behavior clear.

**Required reasoning:** Identify which values originate outside the trusted domain; which boundary dimensions actually exist; whether invalid data should be rejected, reported, saturated, wrapped, normalized, resumed, rolled back, or accepted as lossy behavior; which integer operations can overflow or underflow; whether checked, saturating, wrapping, or ordinary arithmetic follows a proven contract; and whether a boundary-specific pack must supply stricter rules.

**Risk:** Invalid input, silent coercion, overflow, truncation, encoding ambiguity, or partial progress can cross a boundary and become harder to diagnose than an explicit rejection or documented lossy behavior.

**Rule:** For each changed external or unbounded data boundary, define the applicable invalid-input, numeric overflow or conversion, text or binary encoding, and partial-progress policies before accepting, transforming, or persisting boundary data.

**Sources:** ['RUST-TYPE-010', 'RUST-API-027', 'RUST-DATA-002', 'audit minimal core item 10. Detailed parser', 'binary', 'public API', 'and I/O policies remain deferred to P13/P16.']

**Trigger:** Always

**Validation:** Boundary tests or review cover representative cases only for dimensions present in the contract, such as invalid values, relevant zero or extreme values, narrowing, encoding failures, or observable partial progress; any lossy, saturating, wrapping, or checked-failure behavior is named and documented at the boundary.

### `CORE-011` — Keep the compiler in the loop

**Exceptions:** Pure documentation-only edits or mechanical metadata changes may use a lighter check when no Rust compilation surface changed; environment, toolchain, target, or dependency unavailability does not convert a required check into `PASS` or an implicit waiver.

**Required reasoning:** Determine the smallest coherent edit unit and compile/check target that exercise the changed code, whether failures are baseline or newly introduced, what evidence is needed before compounding the change, and whether environment, toolchain, target, or dependency constraints make the applicable gate unavailable.

**Risk:** Stacking patches over a new unexplained compiler failure turns design feedback into random-walk repair and can hide the first real cause.

**Rule:** After the smallest coherent non-trivial edit unit that can reasonably be checked, run the minimal relevant compile/check gate before compounding the change or starting an unrelated repair, and stop to understand any new red result in the story scope; if the applicable gate cannot be run, record it as `NOT RUN` with the reason and do not claim that it passed.

**Sources:** ['RUST-AGENT-001', 'audit minimal core item 11.']

**Trigger:** Always

**Validation:** The work record shows the relevant compile/check outcome or an explicit `NOT RUN` with reason, preserves baseline failures as evidence, and does not continue with unrelated repairs over a new unexplained failure.

### `CORE-012` — Compilation is not semantic correctness

**Exceptions:** A purely syntactic or type-only refactor may need no new runtime test, but the reason must be tied to the acceptance criteria and reviewed behavior surface.

**Required reasoning:** Identify which acceptance criteria, externally visible behaviors, failure modes, and active risk tags require semantic validation beyond compile success.

**Risk:** A green compile can still miss acceptance criteria, cancellation behavior, data compatibility, public contract changes, FFI/unsafe risks, and business or protocol semantics.

**Rule:** Treat the applicable compile/check gate selected under `CORE-011` as necessary implementation evidence, not as proof that the change satisfies the story or preserves observable behavior; select story-specific behavioral, review, or active-risk-pack evidence for the properties changed.

**Sources:** ['RUST-TEST-001', 'audit minimal core item 12.']

**Trigger:** Always

**Validation:** The verification plan pairs the applicable compile/check evidence from `CORE-011` with story-specific behavioral, review, or active-risk-pack evidence, or an explicit scoped reason when no additional semantic check is applicable.

### `CORE-013` — Derive the test oracle from the spec

**Exceptions:** Deterministic review checks may substitute for executable tests when the change is non-executable or the project lacks an applicable harness, but they still need a spec-derived oracle.

**Required reasoning:** Identify the expected behavior, negative and boundary cases, plausible wrong implementations, whether the proposed assertion checks observable behavior or only code shape/internal layout, and whether the test would fail against the known broken behavior rather than simply covering the new code shape.

**Risk:** Tests that mirror the implementation, assert incidental structure, or skip failing reproduction can pass while the requested behavior remains wrong.

**Rule:** Build test oracles from the story/spec and observable behavior; for bugfixes, reproduce the defect before the fix when feasible, and do not lock ordinary tests to incidental implementation structure when the contract is behavioral.

**Sources:** ['RUST-TEST-002', 'audit minimal core item 13.']

**Trigger:** Always

**Validation:** Tests or review assertions exercise externally visible outcomes and meaningful edge cases, expose useful mismatches when they fail, and do not rely only on private structure unless that structure is itself the reviewed contract; bugfix evidence includes a fail-before-fix reproduction or a documented reason it was not feasible.

### `CORE-014` — Do not make green by cheating

**Exceptions:** Explicitly requested scaffolding, placeholders, or test doubles are allowed only when that artifact is itself an acceptance criterion, its limitations are explicit, and no unimplemented production behavior is reported as complete; governance or customization tasks may change validation policy, and narrow temporary suppressions require applicable authorization, reason, scope, and removal path; correcting an invalid, obsolete, or flaky test oracle is not weakening verification when the change is grounded in the authoritative contract, preserves or improves defect-detection strength, and records the prior mismatch or flake evidence. A newly green result alone is not sufficient evidence that the oracle correction was valid.

**Required reasoning:** Determine whether a validation change is part of the requested governance or customization work or merely hides a failing implementation; for any suppression, scaffold, placeholder, or test double, identify the applicable task or governance authorization, scope, limitations, and expiry or removal path. Authorization must come from the active task or the owner mapped by applicable governance; the implementation agent's own justification is not authorization.

**Risk:** Weakening tests, CI, lints, validation commands, or implementation completeness can make the result appear successful while defects remain.

**Rule:** Do not make a story pass by weakening verification, adding vacuous tests, counting incomplete production behavior as complete, or applying suppressions outside an explicitly authorized narrow policy.

**Sources:** ['RUST-ANTI-002', 'RUST-ANTI-005', 'audit minimal core item 14.']

**Trigger:** Always

**Validation:** Diff review shows that verification infrastructure and test strength were preserved or intentionally changed under the task contract; no broad suppression, vacuous assertion, or unimplemented production behavior is counted as completed behavior.

### `CORE-015` — Load context by risk

**Exceptions:** Persistent core rules remain always available; context sharding is for specialized risk knowledge, not for forgetting baseline implementation behavior. After the initial router pass finds no matching positive or escalation signal in the available story, manifest, repository, touched-code, or planned-diff context, a compact recorded `no conditional pack activated` result is sufficient. Re-evaluate routing only when later inspection or the evolving diff introduces, removes, or materially changes a router signal.

**Required reasoning:** Match the available story, manifest, repository, touched-code, and planned or actual diff signals against the current risk router rather than a duplicated category list; identify the activated packs, applicable escalation triggers, and relevant validation families, and distinguish global rules, project policy, story contract, and specialist reference material.

**Risk:** Loading irrelevant specialist guidance can dilute active constraints, while missing or under-propagated risk context can drop active risk tags, allowed files, API constraints, or validation expectations.

**Rule:** Use the current risk router to load specialized Rust guidance only for signals tied to the story, manifests, repository, touched code, or planned or actual diff; re-evaluate routing whenever inspection or the evolving diff introduces, removes, or materially changes a router signal. When delegating, preserve the active risk tags, scope, constraints, and validation expectations needed by the worker.

**Sources:** ['RUST-AGENT-007', 'context-propagation part of `RUST-ANTI-004', 'audit minimal core item 15.']

**Trigger:** Always

**Validation:** The work record identifies the initial activated packs and matching signals, any later rerouting caused by inspection or diff changes, and the constraints and required evidence propagated into delegated work.

### `CORE-016` — Make uncertainty explicit

**Exceptions:** Low-impact local assumptions are acceptable when they are explicitly named, scoped, and checked by the next relevant validation step.

**Required reasoning:** Separate confirmed facts, deductions, hypotheses, and missing evidence; attempt available authoritative local checks before escalating, then decide whether the remaining uncertainty is harmless, locally testable, or requires owner or specialist judgment before proceeding.

**Risk:** Hidden assumptions about safety, data loss, public contracts, dependencies, or scope can turn a local repair into an unsound or unauthorized change.

**Rule:** Do not mask material uncertainty. Resolve or verify it from authoritative evidence when this can be done safely within the task constraints; escalate when a material uncertainty cannot be resolved without owner or specialist judgment. Otherwise record the smallest safe assumption and check it at the next relevant validation step.

**Sources:** ['uncertainty/escalation parts of `RUST-AGENT-004` and `RUST-AGENT-012', 'audit minimal core item 16.']

**Trigger:** Always

**Validation:** The work record shows each material assumption, attempted verification, resulting evidence, or escalation path instead of presenting a guess or unresolved hypothesis as fact.

### `CORE-017` — Require evidence for performance changes

**Exceptions:** Clear algorithmic complexity defects or hard resource budgets may justify action before full profiling, but the target, expected improvement, and correctness preservation must still be stated and validated afterward. Incidental performance effects of a correctness or clarity change do not by themselves require a benchmark.

**Required reasoning:** Identify the performance goal, representative workload and target environment, baseline behavior, measurement method, bottleneck or resource budget, tradeoffs, and why the proposed structural or allocation change follows from that evidence rather than style preference.

**Risk:** Folklore optimization can distort ownership, allocation strategy, crate topology, inline policy, or observable behavior without improving the measured bottleneck.

**Rule:** When performance is a goal, acceptance criterion, or claimed justification for a code or architecture change, make that change only from an explicit target plus evidence characterizing the current behavior or constraint: a measured baseline, profiling evidence, demonstrated algorithmic complexity at the relevant input scale, or a contractually defined bottleneck or resource budget.

**Sources:** ['RUST-PERF-001', 'principle parts of `RUST-PERF-007', 'RUST-PERF-010', 'audit minimal core item 17. Portability and target-capability work is routed through `RP-PERF-001', 'detailed allocation and crate-splitting techniques remain in the performance pack or recipes.']

**Trigger:** Always

**Validation:** Benchmarking, profiling, complexity evidence, or an explicit resource budget justifies the metric change; separate story- and risk-specific validation shows that observable behavior and correctness contracts were preserved.

### `CORE-018` — Keep sensitive data out of output surfaces

**Exceptions:** Restricted raw evidence is permitted only when the project-approved channel, readers, retention, and handling policy authorize it; shared summaries must remain redacted.

**Required reasoning:** Identify which values are sensitive, which surfaces may display or persist them, who can read each surface, and whether detailed diagnostics must be routed to a restricted channel instead of shared output.

**Risk:** Logs, errors, panic messages, debug output, snapshots, tests, telemetry, and agent evidence can expose secrets, PII, paths, raw input, or internal diagnostics.

**Rule:** Do not emit secrets, PII, or raw sensitive data to shared or unapproved output surfaces. Classify sensitive fields, redact or generalize outward-facing output, and route necessary raw diagnostics only to a project-approved restricted channel.

**Sources:** ['RUST-SEC-001', 'audit minimal core item 18.']

**Trigger:** Always

**Validation:** Review and tests cover redaction-sensitive paths such as `Debug`/`Display`, logs, error responses, snapshots, and validation evidence summaries when those surfaces are touched.

## Pack `async`

### `RP-ASYNC-001` — Async trait future contract

**Exceptions:** Private traits with only local static-dispatch call sites can keep simpler opaque async forms when the future bounds are not part of an external contract.

**Required reasoning:** Determine whether the trait is private or reusable/public, whether callers need dynamic dispatch, whether futures cross multi-threaded spawn boundaries, which lifetimes are captured, whether allocation/boxing is acceptable, and whether project MSRV or dependency policy allows helper patterns.

**Risk:** Trait async methods can hide returned-future auto-trait, lifetime, object-safety, allocation, and runtime-spawn contracts, creating `dyn Trait` incompatibility or downstream API traps.

**Rule:** Choose an async-trait strategy whose future contract is explicit for the intended use: private/static dispatch may use opaque futures when accepted by the local call sites, while reusable or public traits must document and validate `Send`, lifetime, object-safety, boxing/allocation, and runtime boundary expectations.

**Sources:** ['RUST-TRAIT-005', 'audit traits/generics/conversions section.']

**Trigger:** The diff introduces or changes `async fn` in a trait, a trait method returning `impl Future`, an associated-future trait pattern, boxed/erased trait futures, or a reusable/public async abstraction.

**Validation:** Compile checks exercise the intended trait use patterns, including static dispatch, `dyn` use when promised, and spawn-boundary `Send` requirements when the future is spawned; API review records the selected future strategy.

### `RP-ASYNC-002` — Spawned async trait futures need Send contract

**Exceptions:** Do not add `Send` for single-threaded runtimes, runtime-documented local task use, private non-spawned async traits, or implementations whose legitimate contract requires `!Send` state; route the broader strategy choice through `RP-ASYNC-001`.

**Required reasoning:** Determine whether the future is actually spawned on a multi-threaded executor or only used locally/single-threaded, which borrows are captured by the returned future, whether implementing types can satisfy `Send`, and which syntax or helper pattern is supported by the repository MSRV and dependency policy.

**Risk:** A trait async method can hide a `!Send` returned future until a spawn call site fails, leading agents to add shared-state wrappers or lifetime widening instead of expressing the actual future contract.

**Rule:** When an async trait future must be spawned on a multi-threaded runtime, make the `Send` requirement explicit in the trait future contract using the project-supported async-trait strategy.

**Sources:** ['downgraded `RUST-TRAIT-013', 'audit traits/generics/conversions section and special-correction row for `RUST-TRAIT-013`.']

**Trigger:** A trait method's returned future is intended to cross a multi-threaded runtime spawn boundary, such as a generic worker or reusable async trait method passed to `spawn`.

**Validation:** Compile/check exercises the intended spawn call site and at least one representative implementation; review shows the `Send` bound is part of the trait contract rather than a mechanical repair for unrelated shared state.

### `RP-ASYNC-003` — Keep blocking work off async workers

**Exceptions:** Short bounded CPU work can use a runtime-approved blocking mechanism when capacity is explicit; synchronous send operations whose channel contract is documented non-blocking may be used from async code; synchronous channels remain appropriate between OS-thread-only components with no async worker involvement.

**Required reasoning:** Determine what blocks, how long it can block, whether the work is sync-only or CPU-bound, which runtime/executor owns progress, whether a synchronous bridge must keep timers, spawned tasks, or connection maintenance progressing while the caller blocks, what concurrency bound applies, how results return to the async task, and whether a synchronous bridge has its own lifecycle and shutdown policy.

**Risk:** Blocking an async worker thread can starve unrelated tasks, hide deadlocks, exhaust a runtime blocking pool, or turn async progress into a thread-capacity bug.

**Rule:** Keep async workers available for cooperative async progress: use async-native APIs when available; isolate sync-only blocking work behind a bounded blocking or dedicated-thread policy; route long-lived blocking loops and heavy parallel CPU work to a project-approved non-worker design; and use async-aware channels on the async side instead of blocking receives.

**Sources:** ['RUST-ASYNC-001', 'RUST-ASYNC-024', 'audit async/concurrency section.']

**Trigger:** Async code performs or waits on synchronous I/O, sleep, blocking channel receive, CPU-heavy work, synchronous receive loops, runtime bridging, or work submitted from async tasks to another executor/thread pool.

**Validation:** Review changed async contexts for blocking calls and blocking channel receives; run compile/check plus behavior or load/shutdown tests appropriate to the touched runtime path; use tracing or overload evidence when runtime starvation is the risk being fixed.

### `RP-ASYNC-004` — Do not carry sync guards or !Send state across await

**Exceptions:** Explicit single-threaded/local executors can permit `!Send` futures at the runtime boundary, but they do not make synchronous locks across `.await` safe; short synchronous critical sections inside async code are acceptable when no await occurs while held and contention is bounded; third-party guard `Send` implementations still require runtime-progress review.

**Required reasoning:** Identify every value live across each `.await`, whether the future crosses a multi-threaded spawn boundary, whether a lock is synchronous or async-aware, whether control-flow temporaries extend guard lifetimes, whether contention can block runtime progress, and whether a single-threaded/local executor is an explicit architecture choice.

**Risk:** State kept alive across `.await` can make a future `!Send`, deadlock a runtime, starve worker threads, or preserve a lock/borrow longer than the code visually suggests.

**Rule:** End synchronous guard, borrow, and `!Send` lifetimes before suspension points; do not carry synchronous lock guards or implicit borrows across `.await`, and use async locks only when the guarded state truly must be held across an await and the critical section contract is bounded.

**Sources:** ['RUST-ASYNC-002', 'related reference `REC-OWN-002', 'audit async/concurrency section.']

**Trigger:** An async block/function/future uses `Rc`, `RefCell`, raw pointers, synchronous lock guards, async-runtime lock blocking methods, RAII guards, control-flow scrutinee temporaries, or spawn boundaries where `Send` is required.

**Validation:** Compile/check the intended spawn boundary when `Send` matters; manually review lock/borrow scope around awaits, `match`/`if let` scrutinees, and RAII parameters; add concurrency or shutdown tests when lock ordering, contention, or runtime progress is part of the behavior.

### `RP-ASYNC-005` — Cancellation safety and async cleanup are explicit

**Exceptions:** Not every future must be cancel-safe when dropped work is explicitly acceptable; recreating a fresh future per loop iteration is valid when restart semantics are intentional; runtime/API-specific claims about cancel-safe operations must be checked against the active runtime or trait documentation before becoming project policy.

**Required reasoning:** Determine which state changes before each suspension point, what is lost if the future is dropped, whether retryability also preserves partial progress, whether a one-shot future can be polled again, where async cleanup is guaranteed, and whether a spawned owner, explicit `close`/`shutdown`, synchronous fallback, or caller-visible error is the right lifecycle contract.

**Risk:** Dropping a future can silently lose partial logical progress, skip `.await`-dependent cleanup, or repoll a completed one-shot future in a way that panics or violates the event-loop contract.

**Rule:** State whether each cancellation-relevant operation is cancel-safe, not cancel-safe, or intentionally lossy; keep partial-progress state and cleanup ownership outside discardable branch futures when loss is not allowed; and provide an explicit recovery, shutdown, or accepted-loss path for futures that may be dropped before completion.

**Sources:** ['RUST-ASYNC-003', 'async-specific part of `RUST-ASYNC-021', 'related `CORE-009', 'audit async/concurrency section.']

**Trigger:** Async code uses `select!`, timeout/deadline racing, shutdown cancellation, dropped futures, abortable tasks, futures reused across loop iterations, or async resources that require close/commit/flush/rollback after partial progress.

**Validation:** Cancellation, timeout, and shutdown tests drop or abort the relevant future before normal completion; tests or review verify preserved partial progress, replacement of completed one-shot futures, and the documented cleanup guarantee or accepted loss.

### `RP-ASYNC-006` — Spawned tasks have owners and supervision

**Exceptions:** Intentional detachment is acceptable for best-effort work only when loss, shutdown, and error visibility semantics are explicit; single-threaded/local executors can relax `Send` only when the runtime contract says so; `RP-ASYNC-008` owns broader structured-concurrency shape.

**Required reasoning:** Determine who owns the task handle, whether dropping the handle detaches or cancels under the active runtime, whether the task is critical or best-effort, how panics/errors are observed, how shutdown reaches the task, whether captured state must be `Send` and `'static`, and whether a local executor is an explicit design rather than a repair.

**Risk:** Spawned work can detach, panic, stall, violate `Send`/`'static` expectations, or lose errors when the owner, handle policy, and supervision path are implicit.

**Rule:** Give every spawned or stored async task an explicit lifecycle: awaited, stored, supervised, aborted, joined, or intentionally detached; classify critical tasks and make failure visibility, restart/shutdown behavior, and spawn-boundary `Send`/`'static` requirements part of the contract.

**Sources:** ['RUST-ASYNC-004', 'RUST-ASYNC-009', 'RUST-ASYNC-011', 'related `CORE-009', 'audit async/concurrency section and special-correction row for `RUST-TRAIT-013`.']

**Trigger:** A change introduces or modifies `spawn`, `spawn_local`, long-lived workers, task handles, task groups, background result delivery, runtime callbacks, or stored async work.

**Validation:** Compile/check exercises the intended spawn boundary; lifecycle review accounts for every handle; shutdown and panic/error-observation tests cover critical workers or document accepted detachment for best-effort tasks.

### `RP-ASYNC-007` — Bound async queues and fan-out

**Exceptions:** Unbounded channels remain acceptable when the producer set and message count are inherently finite or when unbounded growth is a documented non-production/test-only tradeoff; non-blocking send with drop/coalesce behavior is valid when loss is part of the domain contract.

**Required reasoning:** Determine producer and consumer rates, maximum in-flight work, queue capacity rationale, full-queue behavior, memory budget, fairness/starvation concerns, cancellation behavior for queued work, and whether overload should wait, drop, shed, coalesce, retry, or surface an error.

**Risk:** Unbounded queues and unthrottled spawn loops hide overload until memory, latency, or downstream capacity fails under load.

**Rule:** Define backpressure for async message and fan-out paths: prefer bounded queues or bounded worker/concurrency designs unless producers are provably bounded and unbounded growth is an accepted contract; handle full queues and fan-out limits explicitly.

**Sources:** ['RUST-ASYNC-005', 'audit async/concurrency section.']

**Trigger:** Async code introduces or changes channels, producer/consumer queues, task fan-out loops, accept loops, worker dispatch, background work queues, or overload handling.

**Validation:** Queue/concurrency tests or load tests exercise overload behavior; review verifies a concrete capacity or bounded-producer proof and checks that `try_send`, drop, retry, or wait semantics match the story contract.

### `RP-ASYNC-008` — Prefer same-scope execution and structured task ownership

**Exceptions:** Detached service loops are valid when `RP-ASYNC-006` records supervision, failure visibility, and shutdown ownership; same-task combinators do not replace true CPU parallelism or independent service lifetime; storing a future without immediate polling is valid only when the later poll/await owner is explicit.

**Required reasoning:** Determine whether the operations need true parallelism, detached lifetime, or only cooperative same-task concurrency; whether branch futures can borrow local state without overlapping mutable borrows; who owns any child task group; what happens on parent cancellation or shutdown; whether a returned future is executed now, stored for later polling, or intentionally submitted to an executor; and which runtime-specific handle/drop semantics are authoritative.

**Risk:** Agents can add `Arc<Mutex<_>>`, clones, `'static` bounds, or detached task trees to satisfy ownership errors when the work could stay in one async scope, or they can construct a future that never runs because it is neither awaited, polled, nor spawned.

**Rule:** Prefer same-scope async concurrency when the work does not need independent task ownership; when spawning is required, keep child work in an owning scope, task group, join path, or approved supervisor, and make future execution explicit by awaiting, polling through a combinator, storing under a documented later-poll contract, or spawning under `RP-ASYNC-006`.

**Sources:** ['RUST-ASYNC-013', 'RUST-ASYNC-014', 'RUST-ASYNC-027', 'related `CORE-009', 'RP-ASYNC-005', 'RP-ASYNC-006', 'audit async/concurrency section.']

**Trigger:** Async code introduces or changes concurrent orchestration, request-scoped parallel work, `join!`/`select!`/future collections, background task trees, explicit shutdown paths, or async calls whose returned futures might be ignored, stored, spawned, or run later.

**Validation:** Control-flow and lifecycle review shows no discarded future or accidental detached work; compile/check exercises the intended borrow and spawn boundaries; async behavior, cancellation, shutdown, or error-propagation tests cover the changed orchestration path when observable behavior depends on it.

### `RP-ASYNC-009` — Channel send errors are lifecycle outcomes

**Exceptions:** Best-effort notifications and result delivery to an independently cancelled receiver may intentionally discard closed-receiver errors; channel-full or backpressure failures require their own overload policy under `RP-ASYNC-007`; panicking on receiver closure is acceptable only for a narrow invariant violation with non-sensitive diagnostics.

**Required reasoning:** Determine who owns the receiver lifecycle, whether receiver drop means cancellation, timeout, client disconnect, shutdown, invariant violation, or data loss; whether the failed send returns a payload that must be recovered; whether full-channel/backpressure errors are separate from receiver-closed errors; and whether the channel is best-effort, request-critical, or operationally monitored.

**Risk:** Blindly discarding send errors can hide lost results, while blindly propagating or unwrapping them can turn an expected receiver drop into a panic or incorrect upstream failure.

**Rule:** Treat receiver closure as part of the channel lifecycle contract: ignore a send error only when loss of that message is explicitly acceptable; otherwise propagate, log with approved context, return, retry, or surface the failure according to the boundary contract.

**Sources:** ['rewritten `RUST-ASYNC-031', 'related `CORE-008', 'CORE-009', 'RP-ASYNC-007', 'audit special-correction row for `RUST-ASYNC-031`.']

**Trigger:** Async or task-coordination code sends results, notifications, work items, shutdown signals, or responses through `oneshot`, `mpsc`, `broadcast`, `watch`, or another channel whose receiver can close independently.

**Validation:** Cancellation, timeout, shutdown, and receiver-drop tests exercise the relevant send sites; code review verifies that `let _ =`, `.unwrap()`, `.expect()`, `?`, retry, logging, and recovery choices match the documented lifecycle semantics.

