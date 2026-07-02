# STAGE-02 — Router replay + per-workflow scope filter

Fresh-context stub. **Full stage brief:** PROOF_COMPLETION_PLAN §Stage 02.

## Non-negotiable pre-read
- rdx-tea/architecture/ADR-001-INTEGRATION-ARCHITECTURE.md
- rdx-tea/research/BUILDER_TEA_RECONCILIATION.md §3
- rdx-tea/implementation-plan/GLOBAL_GUARDRAILS.md
- rdx-tea/evidence/final/FINAL_VERIFICATION.json

## Entry gate
See PROOF_COMPLETION_PLAN §Stage 02 "Entry gate".

## Exit gate
G3 → PASS. Update rdx-tea/evidence/final/FINAL_VERIFICATION.json.

## Rules
- rdx-tea-integration branch only.
- Test-first (RED → GREEN), evidence saved per GLOBAL_GUARDRAILS §Test discipline.
- Do not touch files outside the "Scope allowed" list in
  PROOF_COMPLETION_PLAN §Stage 02.

## Handoff
Commit with message
`rdx-tea stage 02: <verb> <what>`.
