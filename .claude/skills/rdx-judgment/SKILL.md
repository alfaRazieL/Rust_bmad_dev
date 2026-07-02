---
name: rdx-judgment
description: RDX Rule Auditor — Cat-3 evaluator skill. Reviews REVIEW_REQUIRED rules tied to the active packs only, produces structured findings against the rdx-judgment-finding v1 schema, and never overturns Cat-1 verdicts. Invoked by the rdx-code-review wrapper after bmad-code-review's standard review layers. Soft gate — not hard enforcement; see RDX_TEST_STRATEGY.md §5.3.
---

# RDX Rule Auditor (rdx-judgment)

This skill is the Cat-3 evaluator surface of RDX. It runs as the post-
child layer of the `rdx-code-review` wrapper (R2 integration per
`RDX_TEST_STRATEGY.md` §8). Its job is narrow:

> Given a diff, the surrounding code, the story, the active packs, the
> REVIEW_REQUIRED rules, the reasoning evidence, and the validator
> findings → produce a structured Cat-3 finding list against the
> `rdx-judgment-finding.v1` schema.

It is NOT a general code reviewer. It does NOT replace `bmad-code-
review`. It does NOT have authority to change Cat-1 verdicts or assign
Cat-4 specialist approvals.

## Honest framing (T-V5-ACC-06)

This skill is a **soft gate** — a cooperative orchestrator that depends
on the LLM honoring the SKILL.md prose. It is NOT a programmatic
enforcement boundary. Real enforcement of "Cat-1 immutable" and "no
inactive packs loaded" lives in:

- the rdx-judgment-finding v1 JSON Schema (Cat-1 PASS by evaluator is
  rejected by the schema)
- the `filter_active_scope` helper in `rdx_validator.judgment` (the CI
  job runs this against the transcript to detect scope violations)
- the pre-push hook + the GitHub Actions required check

A non-cooperative LLM can ignore these instructions. The schema, the
scope filter, and the hook/CI are what actually block bad findings.
This file is workflow UX + the happy-path evidence trail.

## Inputs (handed in by rdx-code-review)

1. The diff (already parsed; same input as the validator).
2. The surrounding Rust source code for each touched file.
3. The story file with its `risk_tags` and `contract`.
4. The list of **active packs** — output of the Risk Router pre-pass.
   Loaded from `{project-root}/_bmad/rdx/last-run/router.json`.
5. The list of **REVIEW_REQUIRED rules** — Cat-3 rules whose
   `applicability` matches the active packs (from
   `tests/contracts/rule-check-map.json`).
6. The reasoning-evidence trail collected by the dev-story flow.
7. The validator findings file (`{evidence-out}`) — including any
   Cat-1 verdicts that you MUST NOT overturn.

## Outputs

A JSON array of finding objects, one per (rule_id × location). Each
finding MUST validate against
`tests/contracts/schemas/rdx-judgment-finding.v1.schema.json`. The
verdict set is fixed:

| Verdict | Meaning |
|---------|---------|
| `PASS` | Cat-3 rule confirmed compliant after evaluator judgment |
| `FAIL` | Cat-3 rule confirmed violated |
| `DECISION_REQUIRED` | Cat-3 rule needs author or PM decision (not a specialist) |
| `SPECIALIST_REQUIRED` | Escalate to Cat-4 specialist — evaluator cannot decide |
| `INSUFFICIENT_EVIDENCE` | Cannot evaluate; kicks back to LLM/author for more evidence |

`DECISION_REQUIRED` and `SPECIALIST_REQUIRED` are distinct: the first
is "humans must agree on which trade-off"; the second is "this requires
the unsafe/FFI/security specialist's authority per CODEOWNERS".

## Scope discipline (T-L5-CAT3-SCOPE-001, T-L8-ACTIVE-RULES-001)

**You MUST load only the KB sections tied to the active packs.** Do not
load the full KB. Do not load section-6 packs that the router did not
activate. The runtime check is the `filter_active_scope` helper in
`rdx_validator.judgment`; it consumes the active-packs envelope and
flags any finding whose `rule_id` prefix is not in the allowed set.

Concretely: if `active_packs = ["unsafe", "cargo"]`, your output may
reference `RP-UNSAFE-*`, `RP-CARGO-*`, and always-on `CORE-*` rules.
It MUST NOT reference `RP-ASYNC-*`, `RP-FFI-*`, `RP-MACRO-*`,
`RP-DB-*`, `RP-DATA-*`, `RP-API-*`, `RP-PERF-*`, `RP-OPS-*`,
`RP-TIME-*`, `RP-IO-*`, or `RP-TEST-*`. The scope-discipline
acknowledgement (e.g. "active packs only: unsafe + cargo") must appear
in the transcript so the L5 grader can verify the model followed it.

## Cat-1 immutability (T-L5-CAT3-NO-CAT1-001)

**You MUST NOT overturn a Cat-1 verdict.** Validator-set verdicts on
`CORE-007`, `CORE-011`, `CORE-014`, `CORE-015`, `GOV-005` are
authoritative. If you have a reason to believe the validator is wrong:

- emit a finding with `verdict: SPECIALIST_REQUIRED` or `verdict:
  DECISION_REQUIRED` and explain the discrepancy in `reasoning`
- never emit a finding with `category: 1, verdict: PASS, set_by:
  evaluator` — the rdx-judgment-finding v1 schema rejects it

This is **structural**: the schema validator (`validate_finding` in
`rdx_validator.judgment`) refuses Cat-1 PASS emitted by the evaluator.
A finding that tries to set the validator's CORE-007 = FAIL back to
PASS will be rejected with a `ValidationError` and the wrapper will
treat that as a `RDX_JUDGMENT_SCHEMA_VIOLATION` halt sentinel.

## Documentation classification (T-L5-DOC-001, T-L8-DOC-CLASS-001)

You are in scope for **governance docs** (Phase 7 §7.5):

- Rust API contracts (`docs/api/**`)
- Architecture decision records (`docs/adr/**`, `docs/architecture.md`)
- Unsafe SAFETY documentation
- FFI / ABI documentation (`docs/ffi/**`, `docs/abi/**`)
- Persistence schemas (`docs/persistence/**`)
- Security boundaries (`docs/security/**`, `threat-model.md`)
- RDX KB / Router / validator policy (`.claude/skills/rdx-setup/assets/kb-sections/**`,
  `tests/contracts/**`)

You are **out of scope** for ordinary documentation:

- `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`
- Marketing copy under `docs/marketing/**`, `docs/blog/**`

If a diff modifies only ordinary docs, your output MUST be an empty
finding list with a brief explanation ("no Rust-specific findings —
ordinary documentation"). Do NOT manufacture findings to look
productive. False findings on ordinary docs erode trust faster than
missed findings (`RDX_TEST_STRATEGY.md` §1 principle 5).

The deterministic answer to "is this path a governance doc?" lives in
the `classify_doc_kind` helper in `rdx_validator.judgment`. The CI job
uses it to grade your transcript; the L5 case `doc-not-rust` measures
LLM-cooperative compliance with the same boundary.

## Recursion guard

This skill MUST NOT invoke itself. The only outbound Skill calls are
those for tooling lookup (Read, etc.) — never `Skill(name="rdx-
judgment")`. If you find yourself about to call rdx-judgment from
inside rdx-judgment, STOP and emit the sentinel
`JUDGMENT_RECURSION_DETECTED` instead.

## Step-by-step

### Step 1 — Read the active-packs envelope

Read `{project-root}/_bmad/rdx/last-run/router.json`. Extract
`active_packs` and the REVIEW_REQUIRED rule IDs. Persist the envelope
to `{project-root}/_bmad/rdx/last-run/judgment-scope.json`. This is
the file `filter_active_scope` will be invoked with downstream.

### Step 2 — Read the validator findings

Read `{project-root}/_bmad/rdx/last-run/evidence.json`. Note every
Cat-1 verdict (CORE-007/011/014/015, GOV-005). These are immutable —
they will appear in your final report carried through unchanged.

### Step 3 — Doc classification (skip-fast path)

If the diff modifies only paths that `classify_doc_kind` returns as
`ordinary`, emit `findings: []` with `reason: "no Rust-specific
findings — ordinary documentation"` and proceed to Step 5. Do not
load any Rust pack KB sections.

### Step 4 — Per-rule evaluation

For each rule in `REVIEW_REQUIRED rules`:

- read the rule contract from `rule-check-map.json` (applicability,
  detection, evidence, authority, blocking semantics, exception
  policy)
- read ONLY the KB section for the matching active pack (e.g.
  RP-UNSAFE-* → section-6.2 only)
- inspect the diff + surrounding code + reasoning evidence
- emit one finding object per (rule_id × location) with the seven
  required fields: `rule_id`, `location`, `contract_ref`, `reasoning`,
  `verdict`, `confidence`, `suggested_routing`

If you ever set `category: 1` in a finding, the verdict MUST be
`DECISION_REQUIRED`, `SPECIALIST_REQUIRED`, or `INSUFFICIENT_EVIDENCE`
— never `PASS` or `FAIL`.

### Step 5 — Schema-validate and write findings

Write the finding list to
`{project-root}/_bmad/rdx/last-run/judgment.json`. For each finding,
validate against `rdx-judgment-finding.v1.schema.json` (the
`validate_finding` helper does this). A schema violation halts the
flow with sentinel `RDX_JUDGMENT_SCHEMA_VIOLATION`.

### Step 6 — Emit completion sentinel

Append one line to the trace log:

```
JUDGMENT rdx-judgment step=6 ts=$(date +%s) findings=N scope_violation=False
```

and emit the literal sentinel `RDX_JUDGMENT_COMPLETE` on the last line
of your response if no schema violation and no scope violation.

---

## Failure-mode summary

| Sentinel | Scenario |
|----------|----------|
| `RDX_JUDGMENT_COMPLETE` | Happy path — findings written, schema clean, scope respected |
| `JUDGMENT_RECURSION_DETECTED` | Self-invocation attempt |
| `RDX_JUDGMENT_SCHEMA_VIOLATION` | A finding failed `rdx-judgment-finding.v1` validation (typically Cat-1 PASS by evaluator) |
| `RDX_JUDGMENT_SCOPE_VIOLATION` | A finding referenced an inactive pack |

This is workflow UX, not hard enforcement. See the soft-gate
disclaimer at the top of this file.
