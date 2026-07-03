---
rdx_tea_bundle_version: 1
workflow: atdd
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

