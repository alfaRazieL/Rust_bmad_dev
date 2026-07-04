---
rdx_tea_bundle_version: 1
workflow: atdd
active_packs:
  - pack_id: api
    rule_ids:
      - RP-API-001
      - RP-API-002
      - RP-API-003
      - RP-API-004
      - RP-API-005
      - RP-API-006
      - RP-API-007
      - RP-API-008
      - RP-API-009
      - RP-API-010
      - RP-API-011
      - RP-API-012
      - RP-API-013
      - RP-API-014
      - RP-API-015
      - RP-API-016
      - RP-API-017
      - RP-API-018
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
  - CORE-004
  - CORE-009
source_of_truth: canonical/router-rules.json + canonical/kb-sections/
---

# RDX active-context bundle for `atdd`

## Always-on Core rules

### `CORE-001` — Contract before code

**Exceptions:** Very small bugfixes may use a compact inferred contract; unspecified fields do not block work unless the missing information is material and cannot be resolved safely from authoritative local context.

**Required reasoning:** Identify which requirements come from the active task, project context/ADR policy, approved local customizations, reusable defaults, and generic model knowledge; resolve locally verifiable gaps from authoritative repository context, and escalate same-level conflicts or missing information only when they remain unresolved and materially affect safe execution under `CORE-016`.

**Rule:** Before editing, establish a proportionate implementation contract from the active task and authoritative repository context: the goal and acceptance criteria, relevant scope and protected boundaries, expected error behavior, active risk tags, instruction priority, and applicable validation.

**Validation:** The plan or work record lets review compare the actual diff and checks with the established contract; governance-specific evidence is required only when the task or project policy activates it.

### `CORE-004` — Root cause before borrow-checker cosmetics

**Exceptions:** Cloning, shared ownership, boxing, `'static`, and broad bounds are acceptable when they express the real API/lifecycle contract, spawn/callback/storage boundary, or a documented local invariant.

**Required reasoning:** Separate confirmed facts, deductions, and hypotheses; identify the real owner and lifetime relationship; prefer scoped borrows, operation reordering, ownership transfer, or API-shape fixes when those match the domain; distinguish `T: 'static` (all lifetime parameters carried by `T` outlive `'static`; therefore `T` cannot contain non-`'static` references tracked by the type system, but a particular value of `T` need not live for the whole program) from an actual `&'static T` or leaked/global value; justify any `clone`, sharing primitive, allocation, `'static` bound, or broad bound by the actual contract.

**Rule:** Treat compiler and borrow-checker failures as design feedback: explain the semantic cause before introducing ownership-expanding repairs, stronger lifetime bounds or requirements for longer-lived data, broad trait bounds, or conversion glue.

**Validation:** The repair record or review explains the cause, shows that any ownership-expanding construct is intentional rather than mechanical compiler appeasement, and rejects unnecessary `'static` bounds, leaks, or other stronger lifetime requirements that do not follow from the actual contract.

### `CORE-009` — Make cleanup, cancellation, and task ownership explicit

**Exceptions:** Ordinary RAII/`Drop` remains appropriate for infallible local resource release and as a safety fallback; best-effort detached cleanup is acceptable only when loss semantics are explicit and not correctness-critical.

**Required reasoning:** For each lifecycle dimension actually touched, identify the resource or task owner, the explicit completion path, the fallback behavior on `Drop`, what cancellation may skip, whether the operation is cancel-safe, how each relevant long-lived task is awaited, stored, supervised, aborted, or intentionally detached, and where cleanup failures become visible.

**Rule:** Treat fallible or protocol-significant `close`, `flush`, `commit`, `shutdown`, drain, join, cancellation, and task ownership as explicit lifecycle contracts when correctness depends on observing completion, failure, or accepted loss.

**Validation:** When the relevant lifecycle behavior is observable and a suitable harness exists, targeted cleanup, shutdown, cancellation, or lifecycle tests exercise it; otherwise focused integration or review evidence states how failure or accepted loss is surfaced and why executable validation was not feasible.

## Pack `api`

### `RP-API-001` — Conversion traits match semantic contracts

**Exceptions:** Local helper functions or explicitly named methods may express domain-specific conversions when trait semantics would overpromise; performance-sensitive borrowed views still need separate evidence before optimizing allocation behavior.

**Required reasoning:** Identify whether the conversion can fail, narrow, normalize, allocate, clone, panic, or change identity/order; whether callers observe ownership transfer or a borrowed view; whether collection lookup semantics require owned and borrowed keys to compare identically; and whether a method name accurately communicates the ownership and cost model at the call site.

**Rule:** Choose conversion traits and named conversion helpers by their semantic contract: `From`/`Into` only for infallible non-lossy conversions, `TryFrom`/`TryInto` for fallible or narrowing conversions, `AsRef` for cheap borrowed views, `Borrow` only when equality, hashing, and ordering semantics match the owned key, and `FromStr` for ordinary string parsing. For named methods, use `as_` for cheap borrowed or primitive views, `to_` for borrowed-to-owned conversions that may allocate or clone, and `into_` for consuming owned-`self` conversions; when those prefixes would misdescribe the cost or ownership semantics, choose a more specific verb instead.

**Validation:** API review and tests cover invalid or narrowing inputs when `TryFrom` is used, collection lookup behavior when `Borrow` is implemented, method naming against `wrong_self_convention` and call-site semantics where applicable, and call sites that would be misled by a lossy or panic-prone `From`.

### `RP-API-002` — Deref wrapper method-resolution collisions

**Exceptions:** Non-`Deref` types are outside this rule; private wrappers with fixed local call sites may keep receiver methods when review shows no meaningful method-resolution ambiguity; `CORE-006` remains the rule that decides whether `Deref` itself is justified.

**Required reasoning:** Determine whether the wrapper is public/reusable or strictly local, which target methods and deref coercions are visible at affected call sites, whether a future target-method addition would change behavior, and whether the operation semantically belongs to the wrapper or the deref target.

**Rule:** For `Deref` wrappers, add inherent receiver methods only when method-resolution review shows they are part of the wrapper's own API and unlikely to collide with the target; prefer associated functions or explicitly named helper methods when collision risk is material.

**Validation:** API and call-site review cover representative method calls on the wrapper and target; public/reusable wrappers record why receiver methods are non-confusing or why associated functions are used instead.

### `RP-API-003` — Trait impls need a legal local boundary

**Exceptions:** If an existing local covering type already makes the impl legal, do not add a new wrapper; private integration adapters may use a narrow local newtype when its conversion and ownership behavior are contained.

**Required reasoning:** Determine which crate owns the trait, which crate owns the self type and any covering local type, whether a fundamental-wrapper exception or existing local boundary applies, and whether a new wrapper changes API, ownership, conversion, or SemVer behavior.

**Rule:** Before adding a cross-crate trait impl, identify the local trait or local self type that makes the impl legal; when the desired impl has no legal local boundary, introduce a deliberate local newtype/adapter or choose another reviewed design.

**Validation:** Compile/check and trait-surface review confirm the impl is legal for the actual crate graph and that any wrapper or adapter is intentional rather than a mechanical orphan-rule workaround.

### `RP-API-004` — Public error types are caller contracts

**Exceptions:** Application edges may use approved type-erased errors; standard-library or intentionally stable public dependency errors may be exposed; narrower thread-local or borrowed error models are valid when documented as part of the API.

**Required reasoning:** Determine whether the boundary is an application edge or reusable/public API, whether callers need pattern matching, downcasting, source chaining, cross-thread/task use, or stable rustdoc-visible conversions, and whether `From<ForeignError>`/`#[from]` would expose an internal dependency.

**Rule:** For public or reusable boundaries, choose an error representation that states the caller contract: prefer typed/domain errors when callers must react, avoid `()` and bare `String` as public error types, document any intentionally non-`Send`, non-`Sync`, or non-`'static` error model, and expose foreign error conversions only when the dependency is an intentional public commitment.

**Validation:** API/rustdoc review and compile checks show the intended public error contract, including source chaining or conversion behavior where relevant, and no accidental foreign-error conversion appears in the public surface.

### `RP-API-005` — Rustdoc examples expose the public contract

**Exceptions:** Private implementation examples, intentionally non-runnable snippets, and hidden boilerplate are acceptable when the visible contract still states required imports, features, setup, safety preconditions, and error behavior.

**Required reasoning:** Identify which public behavior the docs promise, whether examples compile under the documented features/targets, which hidden lines are essential contract versus boilerplate, whether intra-doc links and examples are part of acceptance, and whether a panic or `unwrap` in an example is intentional.

**Rule:** Keep rustdoc and examples aligned with the actual public contract: document errors, panics, safety and feature/setup requirements where they matter; keep examples runnable where practical; use hidden rustdoc lines only for non-essential boilerplate; and prefer fallible example harnesses over panic-shaped `.unwrap()` examples unless the panic is the subject.

**Validation:** Rustdoc review, doctests or example reproduction under the relevant feature/target surface, and link/lint checks under the project's rustdoc policy show that visible documentation matches the real API contract.

### `RP-API-006` — Public construction controls preserve invariants

**Exceptions:** Internal binaries, explicit wire-only DTOs, and shared test fixtures may use public fields when the contract is documented; conceptually closed public enums should avoid unnecessary `#[non_exhaustive]`; retroactive `#[non_exhaustive]` or field privatization needs compatibility review.

**Required reasoning:** Determine whether downstream users must construct or pattern-match the type directly, which invariants require a private constructor path, whether a field-level contract is intentionally public, whether the type is conceptually closed or extensible, and whether hidden-public items would still be public compatibility commitments.

**Rule:** For stable or reusable public types, expose construction deliberately: prefer targeted re-exports, private fields plus constructors/accessors for validated invariants, and `#[non_exhaustive]` only for public surfaces intentionally designed to evolve from the start.

**Validation:** API/rustdoc review and downstream-style compile checks cover construction, pattern matching, and re-export paths; invariant tests show invalid states cannot be constructed through the public surface.

### `RP-API-007` — Public traits and dependency types are API commitments

**Exceptions:** The application-mode policy in `6.5` applies to private applications, prototypes, and explicitly unstable internal surfaces; `std` and `core` types need no re-export; deriving is acceptable when field structure exactly matches the public contract; exposing a dependency type is acceptable when the library policy treats that dependency as public semver surface.

**Required reasoning:** Identify which public trait impls and auto traits callers can observe, whether `Debug`/`Display`/logs can expose sensitive fields or become empty and non-diagnostic, which fields define equality/hash/default/clone semantics, whether an ecosystem derive would create an unnecessary default dependency commitment, whether the type crosses thread or async task boundaries, whether any third-party type becomes part of the public signature, and whether the surface is private/prototype, explicitly unstable, or stable/publishable.

**Rule:** Expose only trait impls, auto traits, and dependency types that are intended API commitments: compile-test expected public auto traits, derive or manually implement public traits only when their semantics are true, keep optional ecosystem derives behind an intentional reviewed feature boundary rather than treating them as default surface, make manual `Debug` output visibly informative for empty/default states when callers can observe it, follow `CORE-018` when public `Debug` or `Display` can expose sensitive data, and wrap dependency types unless exposing and re-exporting the dependency is an intentional public-version contract.

**Validation:** API and rustdoc review cover public trait semantics and dependency exposure; compile assertions or downstream compile checks exercise expected `Send`, `Sync`, `Unpin`, and exposed dependency import paths where relevant; tests or review verify non-empty manual `Debug` output for empty/default states when applicable, `CORE-018`-owned redaction behavior when sensitive output is part of the surface, equality/hash identity, and feature-on/feature-off behavior for optional ecosystem derives where those are part of the contract.

### `RP-API-008` — Return-position impl Trait captures are caller contracts

**Exceptions:** Private local functions can rely on local call-site evidence; broader captures are acceptable when intended and documented; pre-2024 free/inherent RPIT lifetime capture rules differ from Rust 2024, while type and const generics are still captured implicitly in all editions; precise-capturing support has toolchain and item-form constraints that must be checked before prescribing it.

**Required reasoning:** Identify all in-scope type, const, and lifetime parameters, whether the returned hidden type or future actually needs each capture, whether the item is a free/inherent function, trait method/RPITIT, trait impl method, or `async fn`, which Rust edition and MSRV semantics apply, and which downstream borrow patterns, `'static` bounds, or SemVer promises are part of the API contract.

**Rule:** For public or reusable return-position `impl Trait`, determine the crate edition, toolchain support, and intended capture set before changing the signature; preserve or intentionally change captures with the edition-appropriate capture rules and reviewed precise-capturing support where applicable, and do not confuse RPIT's callee-chosen hidden concrete type with a caller-chosen generic return type.

**Validation:** Public API and SemVer review cover the signature; compile call-site tests hold returned values alongside relevant borrows and exercise expected `'static` or non-`'static` use; edition migration uses a reviewed capture-migration path suited to the active toolchain; downstream compile checks run when the public surface is stable or published.

### `RP-API-009` — Public compatibility changes are downstream work

**Exceptions:** The application-mode policy in `6.5` applies to private applications, prototypes, and explicitly unstable internal surfaces; MSRV bump policy, additive `std` feature strategy, exact SemVer taxonomy, and tool invocation details are project policy and must not be universalized.

**Required reasoning:** Determine whether the surface is stable, unstable, private, or application-only; which downstream users, targets, feature subsets, `no_std`/`std` promises, generic/lifetime bounds, lint fallout, and migration notes are in scope; and which compatibility taxonomy the project follows for minor versus breaking changes.

**Rule:** Treat stable public compatibility as downstream work: identify the promised surface and compatibility policy, review likely downstream call sites and target/feature matrices, document migration impact, and use SemVer tooling only as scoped evidence rather than final proof.

**Validation:** API review, downstream-style compile checks, feature/target matrix checks where relevant, release-note or migration-note review, and any project-approved SemVer tooling with its skipped-feature and blind-spot limits recorded.

### `RP-API-010` — Public traits have an extension policy

**Exceptions:** New traits can choose their initial extension model; traits explicitly limited to static dispatch need not preserve object safety, but that limitation must be documented; cfg-gating the entire trait is different from adding cfg-gated required methods to an existing base trait.

**Required reasoning:** Identify downstream impl expectations, sealing status, existing blanket impls, object-safety contract, feature/additivity behavior, whether convenience behavior can be derived from a smaller required primitive surface, whether trait-bound failures are predictable enough to justify reviewed diagnostic guidance, and whether new methods should be required, defaulted, extension-only, or placed on a new trait.

**Rule:** Decide whether each public trait is open for downstream implementation or intentionally sealed; keep the required primitive surface as small as the real contract allows, provide derivable convenience behavior as default methods where that preserves clarity, add new required surface only under the compatibility policy, keep object-safety changes explicit when `dyn Trait` is supported, and put feature-specific behavior in extension traits or defaulted methods rather than cfg-gating required base-trait methods.

**Validation:** API review and downstream compile checks exercise representative external impls, minimal implementations that only define the intended required primitives, `dyn Trait` use when supported, and feature combinations with and without the relevant feature; when compile-fail diagnostic UX is part of the contract, pair it with reviewed tool-specific checks rather than hand-waving compiler output.

### `RP-API-011` — Deprecation and behavioral breaks need migration paths

**Exceptions:** The application-mode policy in `6.5` applies to internal or explicitly unstable surfaces; emergency release response may bypass ordinary deprecation timing under `RP-API-013`; pure bugfixes that restore the documented contract do not require artificial type or name changes.

**Required reasoning:** Determine the old documented behavior, replacement path, deprecation window, compatibility policy, whether the change is a bugfix restoring the original contract or a new behavior, and whether existing call sites would still compile unchanged.

**Rule:** Add the replacement and migration note before removal when normal release policy applies; for incompatible behavioral changes that could keep the same signature, force an explicit type, name, or call-site change so downstream code fails to compile instead of silently adopting new semantics.

**Validation:** Release, docs, changelog, and migration-note review cover the transition; downstream-style compile checks verify that behavior-breaking changes require an explicit caller edit.

### `RP-API-012` — docs.rs reflects the supported public surface

**Exceptions:** The application-mode policy in `6.5` applies to private crates, unpublished prototypes, and docs-only local examples; exact metadata keys, lint levels, and docs.rs build command details are Cargo/toolchain policy and must be verified locally before prescribing commands.

**Required reasoning:** Identify which features and targets are part of the supported documentation contract, whether `all-features` is valid, which APIs are hidden by cfg, how `std`/`alloc`/`no_std` support is presented, and whether docs.rs metadata is a Cargo packaging concern or an API documentation concern for this change.

**Rule:** Define the docs.rs policy for the actual supported public surface: document cfg-gated APIs, configure docs.rs metadata only for real supported feature/target combinations, and keep README, rustdoc, examples, and package metadata aligned.

**Validation:** Rustdoc/docs.rs review or equivalent docs build covers the relevant feature/target surface, doctests/examples match the documented configuration, and broken-link/lint policy is applied under project tooling.

### `RP-API-013` — Yank is a release response, not a default fix

**Exceptions:** Emergency incidents may compress the normal communication sequence, but published story-level yanks still need release-owner approval and an explicit downstream communication plan; the application-mode policy in `6.5` applies to ordinary internal-only fixes.

**Required reasoning:** Determine whether the version is published, who can approve the public release response, what downstream users need to know or do, whether a replacement release or advisory is required, and whether resolver, lockfile, registry, or containment mechanics also activate `RP-CARGO-005`.

**Rule:** Treat yank as a reviewed public release-response decision, not the default fix: keep maintainer approval, expected downstream effect, and any replacement release, advisory, or migration communication explicit; route resolver, lockfile, registry-action, and incident-containment mechanics through `RP-CARGO-005`.

**Validation:** Release review references the governing approval trail for the required maintainer approval, records expected downstream effect, replacement/advisory/migration communication where applicable, and any `RP-CARGO-005` evidence needed for resolver, lockfile, registry, or containment impact.

### `RP-API-014` — Public repr and layout are compatibility contracts

**Exceptions:** Private types and purely internal refactors are outside this rule unless they cross a documented layout boundary; raw cross-language ABI details remain owned by `RP-FFI-003`, and edition/exported-symbol syntax remains owned by `RP-UNSAFE-003`.

**Required reasoning:** Identify whether callers rely on layout, ABI, FFI, serialization, alignment, transparent wrapper behavior, or only ordinary Rust construction; whether the type is private or public/stable; and whether FFI/plugin ABI review owns the raw boundary.

**Rule:** Treat public representation as a compatibility contract: do not remove or change established public `repr`, reorder `repr(C)` fields, or add packed/ABI-sensitive representation without explicit compatibility and boundary review; additive representation attributes are reviewed against the project's SemVer policy and the actual downstream layout contract.

**Validation:** Public API and downstream-layout review cover the changed type; FFI/layout checks, size/offset assertions, or cross-target checks are used only when layout is part of the contract; SemVer tooling is supporting evidence, not a complete layout proof.

### `RP-API-015` — Meaningful ignored-result contracts use reviewed `#[must_use]`

**Exceptions:** Side-effect-first APIs, intentionally ignorable best-effort helpers, and foreign or standard-library return types that cannot be annotated directly may use no annotation or a function-level annotation when that is the only available reviewed boundary.

**Required reasoning:** Determine whether the API's main effect is in the returned value or in side effects, whether callers legitimately ignore the result in normal use, whether the returned type is local and can carry the annotation, and whether adding `#[must_use]` on a stable public API is a reviewed compatibility change rather than an incidental patch.

**Rule:** Apply `#[must_use]` only when ignoring the result is realistically a bug, and prefer annotating the returned type itself over relying only on a function-level annotation when the type is local and represents the real contract.

**Validation:** API review and compiler or Clippy `unused_must_use` feedback cover representative direct discard sites; do not assume either function-level or type-level `#[must_use]` catches control-flow scrutinee uses such as `if`, `if let`, or `match` without extra reviewed lint/tooling support.

### `RP-API-016` — Borrowed-view and I/O parameter forms match actual ownership needs

**Exceptions:** Always-mutating or always-storing APIs may use owned values or mutable borrows directly; plain borrowed views are simpler than `Cow` on always-read-only paths; boxed/shared ownership parameters remain valid when recursion, pinning, ABI, or lifecycle semantics require them; and traits without the relevant blanket impls should not cargo-cult the by-value `Read`/`Write` pattern.

**Required reasoning:** Determine whether the boundary only reads, mutates, stores, or takes ownership; whether the common path borrows or owns; whether `Cow` removes a real conditional-allocation branch instead of adding type noise; and whether the chosen I/O trait actually has the blanket impl coverage that makes a by-value generic parameter more ergonomic than `&mut R`.

**Rule:** Use borrowed view types for strictly read-only access, reserve `Cow` for boundaries that usually borrow but sometimes must own due to normalization, escaping, mutation, or lifetime extension, and take generic `Read`/`Write`-style bounds by value when the trait's blanket impls already let callers pass either owned values or `&mut` references.

**Validation:** API review, call-site compile checks, and allocation/performance review where relevant show that representative callers can pass the intended borrowed or owned forms cleanly and that the chosen parameter shape matches the actual storage and mutation contract.

### `RP-API-017` — External import surfaces keep provenance explicit

**Exceptions:** Standard or ecosystem preludes explicitly designed for glob import, and localized `use super::*` inside test modules, remain acceptable; generated code or macro expansion internals can use the owning mechanism's reviewed import strategy when hand-written explicit imports would not be the real source of truth.

**Required reasoning:** Identify whether the import comes from an external crate or a deliberately glob-friendly prelude, whether the scope is a localized test module or a broader shared surface, and whether the convenience of a glob import outweighs the provenance and collision cost in that module.

**Rule:** Import external items explicitly by name instead of using wildcard imports, unless the imported module is a reviewed prelude intentionally designed for glob use.

**Validation:** Code review and compiler name-resolution checks confirm that symbol origins remain legible and that the import style does not depend on accidental upstream namespace stability.

### `RP-API-018` — Collection-like public types support standard iterator construction

**Exceptions:** Domain types that only incidentally contain a collection, builders that require staged validation before insertion, or types whose contract intentionally forbids arbitrary bulk extension do not need these traits merely for style symmetry.

**Required reasoning:** Determine whether the type's primary semantics are collection-like rather than merely containing an internal collection field, whether item ingestion has a reviewed ordering or validation policy, and whether rejecting generic bulk extension is an intentional surface constraint rather than an accidental omission.

**Rule:** When a type semantically behaves like a collection, implement `FromIterator` for bulk construction and `Extend` for incremental addition unless the API intentionally rejects unconstrained bulk ingestion as part of its documented contract.

**Validation:** API review and compile checks show that representative `iter.collect::<Type>()` and `value.extend(iter)` call sites work for the intended item type, or that the omission is explicitly documented and justified by the contract.

## Pack `async`

### `RP-ASYNC-001` — Async trait future contract

**Exceptions:** Private traits with only local static-dispatch call sites can keep simpler opaque async forms when the future bounds are not part of an external contract.

**Required reasoning:** Determine whether the trait is private or reusable/public, whether callers need dynamic dispatch, whether futures cross multi-threaded spawn boundaries, which lifetimes are captured, whether allocation/boxing is acceptable, and whether project MSRV or dependency policy allows helper patterns.

**Rule:** Choose an async-trait strategy whose future contract is explicit for the intended use: private/static dispatch may use opaque futures when accepted by the local call sites, while reusable or public traits must document and validate `Send`, lifetime, object-safety, boxing/allocation, and runtime boundary expectations.

**Validation:** Compile checks exercise the intended trait use patterns, including static dispatch, `dyn` use when promised, and spawn-boundary `Send` requirements when the future is spawned; API review records the selected future strategy.

### `RP-ASYNC-002` — Spawned async trait futures need Send contract

**Exceptions:** Do not add `Send` for single-threaded runtimes, runtime-documented local task use, private non-spawned async traits, or implementations whose legitimate contract requires `!Send` state; route the broader strategy choice through `RP-ASYNC-001`.

**Required reasoning:** Determine whether the future is actually spawned on a multi-threaded executor or only used locally/single-threaded, which borrows are captured by the returned future, whether implementing types can satisfy `Send`, and which syntax or helper pattern is supported by the repository MSRV and dependency policy.

**Rule:** When an async trait future must be spawned on a multi-threaded runtime, make the `Send` requirement explicit in the trait future contract using the project-supported async-trait strategy.

**Validation:** Compile/check exercises the intended spawn call site and at least one representative implementation; review shows the `Send` bound is part of the trait contract rather than a mechanical repair for unrelated shared state.

### `RP-ASYNC-003` — Keep blocking work off async workers

**Exceptions:** Short bounded CPU work can use a runtime-approved blocking mechanism when capacity is explicit; synchronous send operations whose channel contract is documented non-blocking may be used from async code; synchronous channels remain appropriate between OS-thread-only components with no async worker involvement.

**Required reasoning:** Determine what blocks, how long it can block, whether the work is sync-only or CPU-bound, which runtime/executor owns progress, whether a synchronous bridge must keep timers, spawned tasks, or connection maintenance progressing while the caller blocks, what concurrency bound applies, how results return to the async task, and whether a synchronous bridge has its own lifecycle and shutdown policy.

**Rule:** Keep async workers available for cooperative async progress: use async-native APIs when available; isolate sync-only blocking work behind a bounded blocking or dedicated-thread policy; route long-lived blocking loops and heavy parallel CPU work to a project-approved non-worker design; and use async-aware channels on the async side instead of blocking receives.

**Validation:** Review changed async contexts for blocking calls and blocking channel receives; run compile/check plus behavior or load/shutdown tests appropriate to the touched runtime path; use tracing or overload evidence when runtime starvation is the risk being fixed.

### `RP-ASYNC-004` — Do not carry sync guards or !Send state across await

**Exceptions:** Explicit single-threaded/local executors can permit `!Send` futures at the runtime boundary, but they do not make synchronous locks across `.await` safe; short synchronous critical sections inside async code are acceptable when no await occurs while held and contention is bounded; third-party guard `Send` implementations still require runtime-progress review.

**Required reasoning:** Identify every value live across each `.await`, whether the future crosses a multi-threaded spawn boundary, whether a lock is synchronous or async-aware, whether control-flow temporaries extend guard lifetimes, whether contention can block runtime progress, and whether a single-threaded/local executor is an explicit architecture choice.

**Rule:** End synchronous guard, borrow, and `!Send` lifetimes before suspension points; do not carry synchronous lock guards or implicit borrows across `.await`, and use async locks only when the guarded state truly must be held across an await and the critical section contract is bounded.

**Validation:** Compile/check the intended spawn boundary when `Send` matters; manually review lock/borrow scope around awaits, `match`/`if let` scrutinees, and RAII parameters; add concurrency or shutdown tests when lock ordering, contention, or runtime progress is part of the behavior.

### `RP-ASYNC-005` — Cancellation safety and async cleanup are explicit

**Exceptions:** Not every future must be cancel-safe when dropped work is explicitly acceptable; recreating a fresh future per loop iteration is valid when restart semantics are intentional; runtime/API-specific claims about cancel-safe operations must be checked against the active runtime or trait documentation before becoming project policy.

**Required reasoning:** Determine which state changes before each suspension point, what is lost if the future is dropped, whether retryability also preserves partial progress, whether a one-shot future can be polled again, where async cleanup is guaranteed, and whether a spawned owner, explicit `close`/`shutdown`, synchronous fallback, or caller-visible error is the right lifecycle contract.

**Rule:** State whether each cancellation-relevant operation is cancel-safe, not cancel-safe, or intentionally lossy; keep partial-progress state and cleanup ownership outside discardable branch futures when loss is not allowed; and provide an explicit recovery, shutdown, or accepted-loss path for futures that may be dropped before completion.

**Validation:** Cancellation, timeout, and shutdown tests drop or abort the relevant future before normal completion; tests or review verify preserved partial progress, replacement of completed one-shot futures, and the documented cleanup guarantee or accepted loss.

### `RP-ASYNC-006` — Spawned tasks have owners and supervision

**Exceptions:** Intentional detachment is acceptable for best-effort work only when loss, shutdown, and error visibility semantics are explicit; single-threaded/local executors can relax `Send` only when the runtime contract says so; `RP-ASYNC-008` owns broader structured-concurrency shape.

**Required reasoning:** Determine who owns the task handle, whether dropping the handle detaches or cancels under the active runtime, whether the task is critical or best-effort, how panics/errors are observed, how shutdown reaches the task, whether captured state must be `Send` and `'static`, and whether a local executor is an explicit design rather than a repair.

**Rule:** Give every spawned or stored async task an explicit lifecycle: awaited, stored, supervised, aborted, joined, or intentionally detached; classify critical tasks and make failure visibility, restart/shutdown behavior, and spawn-boundary `Send`/`'static` requirements part of the contract.

**Validation:** Compile/check exercises the intended spawn boundary; lifecycle review accounts for every handle; shutdown and panic/error-observation tests cover critical workers or document accepted detachment for best-effort tasks.

### `RP-ASYNC-007` — Bound async queues and fan-out

**Exceptions:** Unbounded channels remain acceptable when the producer set and message count are inherently finite or when unbounded growth is a documented non-production/test-only tradeoff; non-blocking send with drop/coalesce behavior is valid when loss is part of the domain contract.

**Required reasoning:** Determine producer and consumer rates, maximum in-flight work, queue capacity rationale, full-queue behavior, memory budget, fairness/starvation concerns, cancellation behavior for queued work, and whether overload should wait, drop, shed, coalesce, retry, or surface an error.

**Rule:** Define backpressure for async message and fan-out paths: prefer bounded queues or bounded worker/concurrency designs unless producers are provably bounded and unbounded growth is an accepted contract; handle full queues and fan-out limits explicitly.

**Validation:** Queue/concurrency tests or load tests exercise overload behavior; review verifies a concrete capacity or bounded-producer proof and checks that `try_send`, drop, retry, or wait semantics match the story contract.

### `RP-ASYNC-008` — Prefer same-scope execution and structured task ownership

**Exceptions:** Detached service loops are valid when `RP-ASYNC-006` records supervision, failure visibility, and shutdown ownership; same-task combinators do not replace true CPU parallelism or independent service lifetime; storing a future without immediate polling is valid only when the later poll/await owner is explicit.

**Required reasoning:** Determine whether the operations need true parallelism, detached lifetime, or only cooperative same-task concurrency; whether branch futures can borrow local state without overlapping mutable borrows; who owns any child task group; what happens on parent cancellation or shutdown; whether a returned future is executed now, stored for later polling, or intentionally submitted to an executor; and which runtime-specific handle/drop semantics are authoritative.

**Rule:** Prefer same-scope async concurrency when the work does not need independent task ownership; when spawning is required, keep child work in an owning scope, task group, join path, or approved supervisor, and make future execution explicit by awaiting, polling through a combinator, storing under a documented later-poll contract, or spawning under `RP-ASYNC-006`.

**Validation:** Control-flow and lifecycle review shows no discarded future or accidental detached work; compile/check exercises the intended borrow and spawn boundaries; async behavior, cancellation, shutdown, or error-propagation tests cover the changed orchestration path when observable behavior depends on it.

### `RP-ASYNC-009` — Channel send errors are lifecycle outcomes

**Exceptions:** Best-effort notifications and result delivery to an independently cancelled receiver may intentionally discard closed-receiver errors; channel-full or backpressure failures require their own overload policy under `RP-ASYNC-007`; panicking on receiver closure is acceptable only for a narrow invariant violation with non-sensitive diagnostics.

**Required reasoning:** Determine who owns the receiver lifecycle, whether receiver drop means cancellation, timeout, client disconnect, shutdown, invariant violation, or data loss; whether the failed send returns a payload that must be recovered; whether full-channel/backpressure errors are separate from receiver-closed errors; and whether the channel is best-effort, request-critical, or operationally monitored.

**Rule:** Treat receiver closure as part of the channel lifecycle contract: ignore a send error only when loss of that message is explicitly acceptable; otherwise propagate, log with approved context, return, retry, or surface the failure according to the boundary contract.

**Validation:** Cancellation, timeout, shutdown, and receiver-drop tests exercise the relevant send sites; code review verifies that `let _ =`, `.unwrap()`, `.expect()`, `?`, retry, logging, and recovery choices match the documented lifecycle semantics.

