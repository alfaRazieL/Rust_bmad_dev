# Spike 0.2 — Review propagation into bmad-code-review

**Question:** Can RDX add a Cat-3 review layer to `bmad-code-review` without forking BMM step files?

**Verdict:** DOC VERIFIED — yes, via `on_complete` + `persistent_facts` customization, without touching step files.

## Findings (no executable artifacts — source-review spike)

1. **`bmad-code-review` exposes a `[workflow]` customization block** with `persistent_facts`, `activation_steps_*`, and `on_complete` — same shape as agent customization.

2. **Subagent context isolation is hardcoded in `step-02-review.md`** and is intentional:
   - Blind Hunter: diff only
   - Edge Case Hunter: diff + project read
   - Acceptance Auditor: diff + spec + context

3. **RDX persistent_facts injected on `bmad-code-review`** propagate to:
   - The parent reviewer (orchestrator of all steps)
   - The triage step (step-03)
   - The present step (step-04)
   - Any `on_complete` invocation

   They do **NOT** propagate to Blind/EdgeCase/Acceptance subagents (those are isolated by design).

## Integration recipe (planned for Phase 7)

`_bmad/custom/bmad-code-review.toml`:

```toml
[workflow]
persistent_facts = [
  "file:{project-root}/_bmad/rust-kb/section-4-core.md",
  "Rust risk packs active for this review come from .rdx/evidence-{story-id}.json activated_packs",
]

on_complete = """
After the standard review report is presented, if .rdx/evidence-{story-id}.json
exists and contains review_required entries, invoke the rdx-judgment skill,
passing the review findings, active risk packs, and the rules listed under
review_required. Append the auditor's findings to the final report under a
new "RDX Rule Auditor" section.
"""
```

The hook adds RDX Rule Auditor as a **post-pass on the standard report**, not as a parallel layer. This is the cleanest integration: zero modification of step files, no fork of bmad-code-review.

## Constraint that must be respected

The three existing review subagents (Blind / Edge Case / Acceptance) **cannot be augmented with RDX context**. Their isolation is a feature. RDX Rule Auditor runs as a separate post-layer, not embedded in the parallel-review phase.
