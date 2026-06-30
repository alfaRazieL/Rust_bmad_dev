# R2 Code-Review Integration — T-V6-ACC-03 fixture

End-to-end claim: when a user runs `/bmad-agent-dev` and selects the CR
menu code, the rdx-code-review wrapper is invoked (not the bare
bmad-code-review skill). The wrapper then:

1. Runs `bmad-code-review` as a child skill — the standard 3 review
   layers (Blind / Edge Case / Acceptance) produce findings.
2. Runs `rdx-judgment` as the RDX Rule Auditor layer — Cat-3 findings
   are added before triage.
3. Emits a unified final report containing BOTH layer sets.

Phase 7 ships this as a structural contract (the L4 tests in
`tests/bmad/code-review/test_code_review_wrappers.py`). A real,
LLM-cooperative end-to-end run is the same surface as the Phase 3
wrapper-resume contract — explicitly the job of the L5 evals + a
one-shot Claude Code session per `RDX_TEST_STRATEGY.md` §2 ("L4 ...
LLM-cooperative where wrapper-resume; one-shot manual session for
resume").

T-V6-ACC-03 in this acceptance file asserts that:
- the rdx-code-review SKILL.md exists with the correct frontmatter
- the CR menu override is wired correctly
- the rdx-judgment SKILL.md exists with the correct frontmatter
- no false "hard enforcement" claims appear in either skill
