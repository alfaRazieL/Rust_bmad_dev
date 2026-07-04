# ADR-007 — RDX rule-operation pilot (goal reframing)

Status: ACCEPTED (D3.4.0)
Date: 2026-07-04
Extends: ADR-006-AUTH-PRESERVING-RUNTIME-ISOLATION

## Context

Earlier D-stage material sometimes framed D3.4 as "prove RDX is
measurably better than ordinary TEA". That framing is wrong for what
must be established before a master implementation plan. Comparative
benefit is noisy, expensive, and not the load-bearing claim.

The load-bearing claim is **operational correctness**: that RDX rules
are stably and verifiably selected, projected, and enforced inside
real BMAD TEA workflows.

## Decision

1. **D3.4 goal = rule-operation correctness and stability.** The chain
   we prove is:

       rule selection → active packs → rule bundle → wrapper
       invocation → child TEA workflow → artifacts → sidecars →
       verifier → admissible evidence.

2. **Baseline is a control arm, not the value criterion.** The
   baseline (direct `/bmad-testarch-*`) exists to prove isolation and
   the absence of RDX contamination — no wrapper, no RDX bundle, no
   RDX sidecars, no RP-* obligation leakage. It is NOT used to argue
   RDX is "better".

3. **Candidate success is deterministic.** A candidate run succeeds
   when: correct pack activation, expected rule conditions present, no
   forbidden packs activated, real structured wrapper + child Skill
   events, artifacts present, one sidecar per artifact, verifier PASS,
   workspace-delta consistency PASS, artifact-consistency PASS, and the
   v4 admission gate admits it. These criteria are precommitted in
   `rdx-tea/evals/D3_4_RULE_OPERATION_CRITERIA.v1.yaml`.

4. **Comparative / LLM grading is an optional diagnostic.** It may
   inspect sanitised artifact quality, but it CANNOT override a
   deterministic rule-operation pass/fail and is NOT required to claim
   the rules are operational.

5. **Rules must be TRIGGERED, not hand-fed.** Latent fixtures describe
   natural product requirements without naming RDX rules or detector
   phrases; routing is still precommitted via tags/diff. A candidate
   proves rule-operation by projecting obligations the story never
   spelled out.

## Rationale for the non-obvious choices

- **Forbidden packs judged by ACTIVE packs, not prose.** An
  active-context bundle legitimately CROSS-REFERENCES other packs'
  rules in exception text ("ABI details remain owned by RP-FFI-003").
  A raw prose scan would wrongly flag those. The forbidden check uses
  only the ACTIVE pack names and the sidecar's active rule ids.

- **Artifact-consistency judged against reality.** Duplicate
  frontmatter keys are recorded as warnings; the hard failure is a
  declared generated file that does NOT exist (or a phantom file
  claim), because that is the fabrication we must catch. A run whose
  file claims match the workspace delta is consistent even if the
  child skill emitted a second frontmatter block.

- **Workspace delta is preserved AND verified.** The D3.3.3 admissible
  smoke declared two generated `.rs` files that existed on disk but
  were never copied into evidence. v4 collects the full delta,
  verifies declared files exist (or are precommitted planned), and
  copies them under `workspace-delta/`.

- **Schedule binding at runtime.** Prompt/fixture/criteria/schema/
  schedule-sha are recomputed and compared before a live run; any
  drift is `SCHEDULE_DRIFT` (inadmissible), so a locked schedule
  cannot silently diverge from what is actually sent.

## Consequences

- The D3.4 rule-operation pilot is resumable and audit-correct: a
  failed/partial run is never counted as a rule-operation pass, and
  the deterministic grader alone decides the verdict.
- A candidate that does not complete the RDX finalize lifecycle is an
  honest WORKFLOW_FAILURE, not a masked pass. (The D3.4.0 paired
  candidate needed a strengthened finalize instruction to complete
  reliably on the longer latent story.)
- Overall D3 stays `D3_PARTIALLY_PROVEN` until the multi-run
  rule-operation pilot is executed.

## Alternatives considered

- **Keep the "better than TEA" framing** — rejected; it makes a noisy
  comparative signal the gate for a correctness claim.
- **Let the LLM grader decide rule-operation** — rejected; the primary
  verdict must be deterministic and reproducible.
- **Dedupe artifacts only in the evidence collector** — rejected; the
  source `run-report.json` must be clean so downstream consumers are
  not misled.
