# Changelog

All notable changes to RDX (Rust Dev eXpert) are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.1.0] — 2026-07-02

RDX moves from a knowledge-base-only module into a **hybrid system**: the KB still runs the LLM side, but a deterministic validator, an opt-in git hook, a CI required-check, an LLM-driven Cat-3 evaluator, and a Cat-4 specialist-approval layer now cover the "did the agent actually follow the rules?" question that KB-only enforcement can't answer.

### Added

- **`rdx-validator` — standalone Python package.** BMAD-independent. Reads the diff, replays the Risk Router, runs deterministic Cat-1 / Cat-2 checks, emits a schema-conformant evidence envelope. Runs anywhere `python3` runs.
- **`rdx-dev-story` — soft-gate wrapper skill** around BMAD's story-execution skill (Mode 1 Local Validated). Halts on validator FAIL. LLM-cooperative.
- **`rdx-hooks` — opt-in pre-push git hook** (Mode 2 Local Gated). Refuses pushes when the validator returns a blocking verdict. `git push --no-verify` is the documented bypass and is recorded in the evidence envelope.
- **`.github/workflows/rdx-gate.yml` — required-check CI workflow** (Mode 3 CI Enforced). Loads the validator from the target branch (Option B, trust-model boundary). PRs cannot merge without green.
- **`rdx-code-review` + `rdx-judgment` — R2 wrapper + Cat-3 evaluator** (Mode 4 + Cat-3 layer). Wraps `bmad-code-review`, then invokes `rdx-judgment` for rule-scoped judgment findings. Findings conform to `rdx-judgment-finding.v1` schema and cannot upgrade a Cat-1 verdict.
- **Cat-4 specialist approvals** via `_bmad/rdx/approvers.yaml` (A3 hybrid canonical YAML + `rdx-setup sync-codeowners` renders GitHub's native CODEOWNERS) and `_bmad/rdx/approvals/<diff_digest>.json` files (B1 in-repo storage pinned to the diff).
- **Evidence envelope schema (`rdx-evidence.v1`).** 14-verdict + 3-severity taxonomy. Schema rejects LLM-set Cat-1 PASS.
- **Formal threat model** at `docs/threat-model.md` covering 4 threat actors, bypass-path taxonomy for V5 + V6 + HA-specific, and §8 triggers-to-revisit for deferred hardening (HMAC, immutable-tag source, etc.).
- **Doc-review checklist** at `docs/doc-review-checklist.md` for each release.
- **Agent maintenance guide** at `docs/AGENT_MAINTENANCE_GUIDE.md` for future extension work.
- **`archive-docs-dev/`** folder holding every planning / verification / test-design artefact used to build 1.1, organised by topic and indexed by its own README.
- **307-test regression suite** covering L0 through L8 layers with fixture-based, integration, behavioural-eval, and adversarial coverage.
- **GH Actions Free-plan cost documentation** in the README (`Using RDX with GitHub Actions Free plan` + `When you need more than 2,000 minutes`).
- **Mode 2 positioned as release-quality** — no-CI free-tier enforcement for solo developers is a first-class option, not a stepping stone.

### Changed

- Every RDX skill is now discoverable via BMAD's `agent.menu` — `DS` dispatches to `rdx-dev-story` and `CR` dispatches to `rdx-code-review` via `_bmad/custom/bmad-agent-dev.toml` overrides. No BMAD core modification.
- The README is a full rewrite: architecture overview, per-mode enforcement table, evidence flow, and the Cat-1/2/3/4 framework are now explicit.
- The KB itself (sections 4–8) is unchanged from 1.0.

### Not adopted (deferred with documented triggers)

Phase 9 evaluated five "if real demand exists" candidates. All resolved via documentation rather than code:

- **HMAC-signed attestations** — not adopted. `docs/threat-model.md` §7 explains why CI re-run is sufficient. Trigger to revisit is documented in §8.
- **Protected-validator source (immutable release tag, Option C)** — already opt-in via `--validator-ref`. Ship as operational guidance.
- **Provenance evidence** — already recorded in every envelope.
- **Audit-trail retention policy** — operational guidance in `docs/threat-model.md` §10.
- **Organisation-level required workflows** — documented in `docs/branch-protection.md`.

### Migration from 1.0

Users of 1.0 need do nothing to keep the existing KB behaviour. To enable the 1.1 validator layer, install a mode:

```
/rdx-setup
```

The setup skill prompts for a mode (0 Advisory / 1 Local Validated / 2 Local Gated / 3 CI Enforced / 4 Specialist Approval) and provisions only what that mode requires.

---

## [1.0.0] — 2026-06-27

Initial release. Rust knowledge base as a BMAD expansion module.

### Added

- Knowledge base sections at `_bmad/rust-kb/`:
  - `section-4-core.md` — 18 Always-on Core rules (CORE-001..018)
  - `section-5-router.md` — Risk Router table
  - `section-6-packs.md` — 12 conditional packs
  - `section-8-governance.md` — Governance section
- Agent overrides at `_bmad/custom/`:
  - `bmad-agent-dev.toml` — Amelia loads Always-on Core + Risk Router
  - `bmad-agent-architect.toml` — Winston loads contract-design + governance
  - `bmad-agent-pm.toml` — John loads governance + grades developer behaviour
- `rdx-setup` installer skill.
- Marketplace manifest for BMAD distribution.
