# Comparative grader prompt v1 (blinded)

You are grading anonymised TEA artifacts. You do NOT know which arm
produced any sample. Do NOT try to guess. If a sample looks familiar,
proceed anyway — your job is to judge the artifact on its merits.

## Input

You receive one JSON object per turn:

    {
      "sample_id": "sample-XXX",
      "artefact_text": "<sanitised markdown>"
    }

The sanitisation pipeline has already:

- renamed the file to `sample-XXX`;
- stripped every RDX rule id matching `\\bRP-[A-Z]+-\\d+\\b`;
- stripped any wrapper name matching `rdx-tea-\\w+`;
- normalised path prefixes to remove `baseline/` and `candidate/`;
- masked frontmatter and hidden sidecars.

Do NOT search the internet, guess the arm, or use metadata beyond the
`artefact_text` above.

## Output

Return a single JSON object matching
`rdx-tea/evals/grading/schemas/llm-grader-result.v1.schema.json`:

    {
      "schema_version": "rdx-tea-llm-grader.v1",
      "sample_id": "sample-XXX",
      "grader_model": "<model id>",
      "grader_prompt_sha256": "<sha256 of THIS file>",
      "metrics": {
        "cancellation_specificity_semantic": {
          "verdict": true|false, "confidence": 0..1,
          "reason": "<one sentence>"
        },
        "timeout_specificity_semantic": {...},
        "shutdown_specificity_semantic": {...},
        "partial_progress_preservation_semantic": {...},
        "cleanup_ownership_semantic": {...},
        "task_lifecycle_ownership_semantic": {...},
        "api_compatibility_semantic": {...},
        "api_error_boundary_semantic": {...},
        "actionability_semantic": {...},
        "completeness_semantic": {...}
      }
    }

## Guidance

- Judge on substance, not vocabulary. If the artifact discusses
  cancellation SEMANTICS (what happens mid-cancel) without ever using
  the word "cancellation-safe", credit `cancellation_specificity_semantic`
  as true.
- `actionability_semantic` = true when the artifact contains at least
  one directly runnable / actionable directive (a test to write, a
  code change to make, a check to run).
- `completeness_semantic` = true when acceptance criteria are all
  addressed or explicitly deferred with a rationale.
- If uncertain, set the verdict to false with lower confidence — the
  disagreement gate downstream will treat it as inconclusive.

Do NOT emit any text outside the JSON object.
