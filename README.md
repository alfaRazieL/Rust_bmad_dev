# Rust Dev eXpert (RDX) — BMad Module

A [BMad](https://github.com/bmad-co) expansion module that injects production-grade Rust engineering expertise into your existing BMad agents — without replacing them.

**No new agents. No new personas.** RDX layers a structured Rust knowledge base directly on top of Developer (Amelia), Architect (Winston), and Product Manager (John) using BMad's team-override mechanism, then wraps story execution with a deterministic verifier so the team's evidence trail survives an LLM's good intentions.

---

## What it does

RDX has two layers. The Rust KB layer is what RDX 1.0 shipped; the verifier layer is what RDX 1.1+ adds on top.

| Agent | KB layer (RDX 1.0) |
|-------|--------------------|
| **Amelia** (Developer) | Always loads 18 Always-on Core rules (CORE-001..018) + the Risk Router table. Must consult the router before writing any story code and load the matching conditional pack (async, unsafe, FFI, macros, etc.) when triggered. |
| **Winston** (Architect) | Loads CORE-001/005/006 for strict contract design + the full Governance section for public API / SemVer / FFI / DB boundary rules. |
| **John** (PM) | Loads the Governance section and enforces "Contract before code" (CORE-001) in every PRD and story. Grades Developer behavior — not just the output artifact. |

The verifier layer (validator + wrapper + hook + CI) is described under [Architecture overview](#architecture-overview) and onwards.

### Knowledge Base structure

The KB is organized into four loadable sections installed at `_bmad/rust-kb/`:

```
section-4-core.md        ← 18 Always-on Core rules (Amelia + Winston)
section-5-router.md      ← Risk Router: 12 conditional packs with triggers
section-6-packs.md       ← All 12 packs: async, unsafe, FFI, macros, API,
                            Cargo, testing, data/sec/IO, DB, time, ops, perf
section-8-governance.md  ← Builder/evaluator governance (Winston + John)
```

The Risk Router (§5) is the key KB mechanism: Amelia checks it before every story and loads only the relevant conditional pack from §6 — async rules only when there's `async fn`, unsafe rules only when there's `unsafe {}`, etc. No bloat, no over-loading.

---

## Architecture overview

RDX 1.1+ ships five cooperating pieces. Each is independently testable and each enforces a different boundary.

```
┌───────────────┐   ┌────────────────┐   ┌───────────────┐   ┌──────────────────┐
│ rdx-dev-story │ → │  rdx-validator │ ← │ rdx-hooks     │ ← │ .github/         │
│ (wrapper,     │   │  (deterministic│   │ (pre-push,    │   │  workflows/      │
│  Mode 1 soft) │   │   Cat-1/2)     │   │  Mode 2 gate) │   │  rdx-gate.yml    │
└───────────────┘   └────────────────┘   └───────────────┘   │  (Mode 3 CI      │
        ↓                  ↑   ↑                  ↑          │   required check)│
┌───────────────┐          │   │                  │          └──────────────────┘
│ rdx-judgment  │ ─────────┘   │                  │                    ↓
│ (Cat-3        │              │                  │          ┌──────────────────┐
│  evaluator)   │              │                  │          │ approvers.yaml + │
└───────────────┘              │                  │          │ approvals/<sha>  │
        ↑                      │                  │          │ (Mode 4 Cat-4)   │
┌───────────────┐              │                  │          └──────────────────┘
│ rdx-code-     │ ─────────────┘                  │
│ review (R2    │                                 │
│  wrapper)     │                                 │
└───────────────┘                                 │
                                                  │
                            evidence.json envelope ┘
                            (RDX evidence schema v1)
```

- **`rdx-validator`** — standalone Python package. BMAD-independent. Reads the diff, replays the Risk Router, runs deterministic Cat-1/Cat-2 checks, emits an evidence envelope conforming to `tests/contracts/schemas/rdx-evidence.v1.schema.json`. This is the single source of verdict truth.
- **`rdx-dev-story`** — soft-gate wrapper around BMAD's story-execution skill. Halts on validator FAIL. Soft gate means the LLM cooperates; it is workflow UX, not a programmatic boundary.
- **`rdx-hooks`** — opt-in pre-push git hook. Refuses pushes when the validator emits FAIL/REVIEW_REQUIRED/APPROVAL_REQUIRED. Documents `git push --no-verify` as the recorded bypass.
- **`.github/workflows/rdx-gate.yml`** — required-check CI workflow. Loads the validator from the target branch (Option B in `RDX_TEST_STRATEGY.md` §7) so a malicious PR head cannot tamper with its own verdict. This is the actual enforcement boundary.
- **`rdx-code-review` + `rdx-judgment`** — Cat-3 review layer. The R2 wrapper runs the BMAD code-review skill, then hands the output to `rdx-judgment` for rule-scoped judgment. Findings conform to `tests/contracts/schemas/rdx-judgment-finding.v1.schema.json` and cannot upgrade a Cat-1 verdict to PASS.
- **`approvers.yaml` + `approvals/<diff_digest>.json`** — Cat-4 specialist approval. The validator blocks Cat-4 diffs until a properly-pinned approval JSON is committed by an authorised role member.

### Cat-1 / Cat-2 / Cat-3 / Cat-4 framework

RDX classifies every rule by how the verdict is reached. The category determines who can mark a rule PASS and where the enforcement happens.

| Cat | Name | Verdict reached by | PASS authority |
|-----|------|--------------------|----------------|
| Cat-1 | Deterministic | A command (cargo, clippy, miri, custom check) with an exit code and an output digest | Validator only; LLM cannot set Cat-1 PASS (schema-enforced) |
| Cat-2 | Evidence verification | Validator checks that the claimed evidence matches the diff | Validator |
| Cat-3 | Judgment review | `rdx-judgment` evaluator reviews scoped findings | LLM (`rdx-judgment` Cat-3 verdict only — never Cat-1) |
| Cat-4 | Specialist approval | Named role member (CODEOWNERS / approvers.yaml) signs off | Approver, recorded in `approvals/<diff_digest>.json`, pinned to the diff |

This is the load-bearing taxonomy. RDX does not prove correctness of all Rust decisions; it routes the verdict to the layer that can actually answer the question.

---

## Mode comparison ("what enforces what")

The single source of truth for mode definitions is [`.claude/skills/rdx-setup/assets/modes.md`](.claude/skills/rdx-setup/assets/modes.md). The validator stamps the mode label into every evidence envelope so a downstream reviewer can see what gate produced the verdict.

| Mode | Label | What it actually does | Bypass | Enforcement boundary |
|------|-------|-----------------------|--------|----------------------|
| MODE_0 | Advisory | Validator runs; verdicts recorded; nothing blocks. Exit code 0 always. | n/a (by design) | None — informational |
| MODE_1 | Local Validated | Wrapper `rdx-dev-story` runs the validator after the child skill and halts the workflow on FAIL. Soft gate, LLM-cooperative. | Yes — the LLM can skip steps; the wrapper is workflow UX, not a programmatic boundary | None at the system layer |
| MODE_2 | Local Gated | Pre-push git hook runs the validator before push. Push is rejected on FAIL. | Yes — `git push --no-verify` is the documented bypass (recorded in evidence) | Developer machine, on push |
| MODE_3 | CI Enforced | `.github/workflows/rdx-gate.yml` is a required check. The validator is loaded from the target branch / pinned release, not from PR head. PR cannot merge without green. | No — required check + branch protection | CI runners. This is where enforcement lives. |
| MODE_4 | Specialist Approval | Cat-4 rules require an `approvals/<diff_digest>.json` signed by a CODEOWNERS / approvers.yaml role member. Stale approvals auto-invalidate on diff change. | No — approval is diff-pinned and re-verified on every CI run | CI + approver review |

### Mode 2 is a release-quality option in its own right

Mode 2 (Local Gated, no-CI) is a release-quality target for solo developers and small teams that do not run GitHub Actions. The validator that runs in the pre-push hook is the *same* validator that runs in CI; the only differences are (a) where the failure is surfaced and (b) the documented `--no-verify` bypass. Shipping under Mode 2 is a legitimate, supported configuration — it is **not** a stepping stone to Mode 3.

Teams should pick Mode 3 when they want a non-bypassable required check before merge. Teams that do not have that pressure can ship at Mode 2 indefinitely.

### Honest framing

- MODE_0 and MODE_1 are NOT hard enforcement. They depend on the LLM honoring the SKILL.md prose, and a distracted or non-cooperative LLM can skip steps. The wrapper's value is UX + the happy-path evidence trail, not a programmatic boundary.
- MODE_2 is genuine local enforcement, with a documented bypass.
- MODE_3 is the actual enforcement boundary for V5; only the CI required check sits between a FAIL verdict and a merge.
- MODE_4 layers specialist approval on top of MODE_3 for changes a deterministic check cannot evaluate alone.

The wrapper is workflow UX. CI is the source of enforcement. RDX does not guarantee that an arbitrary LLM session followed every rule; it guarantees that the evidence written down was produced by the validator and that, in Mode 3, no diff merged without a green validator verdict.

---

## Requirements

- [BMad](https://github.com/bmad-co) installed in your project with the `bmm` module (provides Amelia, Winston, John).
- Claude Code CLI (the wrapper SKILL.md prose is Claude-Code-shaped).
- Python 3.11+ on the developer machine (and CI runner). Required for the standalone validator package.
- Git 2.30+.
- Cargo / rustc (stable).

The full per-OS / per-Python matrix is in [`tests/compatibility/matrix.md`](tests/compatibility/matrix.md) — that file is machine-readable and is the source of truth for what RDX claims to support.

---

## Installation

### 1. Copy the skill into your project

```bash
git clone https://github.com/alfaRazieL/Rust_bmad_dev.git
cp -r Rust_bmad_dev/.claude/skills/rdx-setup YOUR_PROJECT/.claude/skills/
```

### 2. Run the setup skill

Open Claude Code in your project and run:

```
/rdx-setup
```

The skill will:

1. Prompt for the operating mode (Advisory / Local Validated / Local Gated / CI Enforced / Specialist Approval). Default is **MODE_1 (Local Validated)**.
2. Register the `rdx` module in your `_bmad/config.yaml` and write `[modules.rdx].enforcement_level`.
3. Copy KB section files to `_bmad/rust-kb/`.
4. Create or merge agent overrides in `_bmad/custom/`.
5. Install the `DS` (rdx-dev-story) and `CR` (rdx-code-review) menu entries on Amelia.
6. Seed the Cat-4 artefacts (`_bmad/rdx/approvers.schema.json`, `approval.v1.schema.json`, `approvers.yaml.example`, `approvals/` dir) so Mode 4 is one edit away from being live.

### 3. (Mode 2 only) install the pre-push hook

```bash
python .claude/skills/rdx-setup/scripts/install-hook.py --project-root .
```

The hook chains with any pre-existing pre-push hook and refuses pushes that would emit FAIL/REVIEW_REQUIRED/APPROVAL_REQUIRED. To uninstall, see [Uninstall](#uninstall).

### 4. (Mode 3 only) add the CI required check

Copy `.github/workflows/rdx-gate.yml` into your repo and mark the workflow as a required check in your branch protection rules. Concrete step-by-step setup is in [Using RDX with GitHub Actions Free plan](#using-rdx-with-github-actions-free-plan) below.

### 5. Restart your agents

Close and reopen any active Amelia / Winston / John sessions. The new `persistent_facts` take effect on the next activation.

---

## Update

```bash
git -C Rust_bmad_dev pull
cp -r Rust_bmad_dev/.claude/skills/rdx-setup YOUR_PROJECT/.claude/skills/
/rdx-setup            # re-runs install; preserves your enforcement_level choice
```

`install.py` is bytewise idempotent for the RDX-managed config block; user-owned settings outside that block are preserved verbatim.

If you bumped from RDX 1.0 → 1.1+:

- Mode selection prompt appears on the first run after upgrade.
- The standalone validator package (`rdx-validator/`) is new — `cd rdx-validator && pip install -e .` if you want a global `rdx-validator` entry point; otherwise the wrapper invokes it via `python rdx-validator/rdx_validator/cli.py`.

---

## Uninstall

```bash
# Remove the pre-push hook (Mode 2 only)
python .claude/skills/rdx-setup/scripts/uninstall-hook.py --project-root .

# Remove RDX-managed config + KB files
python .claude/skills/rdx-setup/scripts/uninstall.py --project-root .
```

The uninstall script restores `_bmad/config.yaml` and any merged overrides to their pre-RDX byte-equal state when possible. The hook installer's foreign-hook chaining is reversed too — a pre-existing hook you had before installing RDX is restored.

---

## Evidence schema and status semantics

Every validator run emits a single JSON evidence envelope. The schema is `tests/contracts/schemas/rdx-evidence.v1.schema.json` (Draft 2020-12). Each entry pins:

- The rule id (e.g. `CORE-007`).
- The category (Cat-1 / Cat-2 / Cat-3 / Cat-4).
- The verdict (status from the taxonomy below).
- For Cat-1: the exact command, exit code, and a digest of the output.
- The `mode_label` of the run.
- The `diff_digest` (stable over whitespace; recomputed in CI).

### Status verdicts (taxonomy is fixed)

The full set lives in `tests/contracts/status-definitions.json`. The verdicts the user is most likely to see:

- **PASS** — the rule was checked and passed. Cat-1 PASS requires the command + exit_code + digest.
- **FAIL** — the rule was checked and failed.
- **REVIEW_REQUIRED** — Cat-3 rule; the deterministic layer cannot answer; routed to `rdx-judgment`.
- **APPROVAL_REQUIRED** — Cat-4 rule; needs a CODEOWNERS / approvers.yaml signature.
- **EVIDENCE_MISSING** — claimed evidence absent or malformed.
- **TOOL_UNAVAILABLE** — a required tool (cargo, miri, etc.) is not on PATH.
- **BASELINE_BLOCKS_VALIDATION** — `--baseline` comparison rejected the run.
- **NOT_RUN** — the rule was not triggered by the diff and was not run.

Exit-code taxonomy (per `RDX_TEST_STRATEGY.md` §5.3):

| Exit code | Meaning |
|-----------|---------|
| 0 | All applicable verdicts PASS / NOT_RUN / Mode 0 informational |
| 1 | One or more FAIL |
| 2 | TOOL_UNAVAILABLE / ENVIRONMENT_UNAVAILABLE / BASELINE_BLOCKS_VALIDATION |
| 3 | APPROVAL_REQUIRED unresolved |
| 4 | REVIEW_REQUIRED unresolved |

WARNING is a severity, not a verdict; verdicts can carry warnings without changing exit-code class.

---

## Exception model

Per-story policy exceptions are declared in `_bmad/rdx/policy.yaml` (or via the wrapper's `--policy-config`) and parsed by `rdx-validator/rdx_validator/policy.py`. An exception scopes one rule to one path and carries:

- The story / ticket id that authorised it.
- An optional expiry date after which the exception lapses and the rule re-fires.
- A free-text rationale that surfaces in the evidence envelope.

Exceptions never silently change a Cat-1 PASS. They at most demote a FAIL to a recorded warning (and the warning is visible to reviewers). The validator's exception parser is unit-tested by `tests/unit/validator/test_exceptions.py`.

---

## Hook behavior

The pre-push hook (`.claude/skills/rdx-hooks/assets/pre-push.sh`) runs the validator against the about-to-be-pushed range:

1. If a pre-existing pre-push hook was present, RDX moved it aside and chains to it first. RDX's gate fails the push if either the chained hook OR the RDX validator returns non-zero.
2. RDX runs `rdx-validator` against the diff between the local HEAD and the remote ref the push targets.
3. On FAIL / REVIEW_REQUIRED / APPROVAL_REQUIRED: the push is refused and the evidence envelope is written to `.rdx/last-evidence.json` so the developer can inspect it.
4. The hook never auto-resolves a failing verdict. The only escape hatches are: fix the diff, add a properly scoped exception, obtain a Cat-4 approval JSON, or use the explicit bypass below.

### Documented bypass: `git push --no-verify`

```bash
git push --no-verify origin my-branch
```

This is the recorded, documented bypass for Mode 2. The evidence trail captures that `--no-verify` was used (CI re-runs the validator on the PR head, so Mode 3 still catches it). Use it deliberately, not casually.

---

## CI setup

The required-check workflow is `.github/workflows/rdx-gate.yml`. It pins the validator to the target branch via `--validator-ref` so a PR cannot rewrite its own validator before computing its own verdict (the "Option B" tamper-resistance pattern). The workflow declares `permissions: contents: read` only — no secrets are needed and it is safe to run on fork-PRs.

To enable Mode 3:

1. Copy `.github/workflows/rdx-gate.yml` into your repo.
2. Push to `main` so GitHub registers the workflow.
3. Branch protection → Required status checks → add `RDX gate / rdx-gate`.
4. Optionally, restrict who can edit `.github/workflows/**` via CODEOWNERS (see [`docs/branch-protection.md`](docs/branch-protection.md)).

---

## Review integration

Two related skills:

- **`rdx-code-review`** — the R2 wrapper. Reorders the BMAD code-review skill so it runs as a child of an RDX BEFORE→CHILD→AFTER envelope. After the child finishes, the wrapper invokes `rdx-judgment` and emits a unified report. The wrapper is a soft-gate cooperative orchestrator (Cat-3 layer) — real enforcement still lives in the validator + CI.
- **`rdx-judgment`** — the Cat-3 evaluator. Scope-locks findings to the active conditional packs (see Risk Router), forbids overturning Cat-1 verdicts (schema-enforced), classifies docs as governance vs ordinary so it does not flag the README as a Rust code smell. Findings conform to `tests/contracts/schemas/rdx-judgment-finding.v1.schema.json`.

The R1 control variant (`on_complete = rdx-judgment` in the workflow definition) ships alongside as the documented fallback when the R2 wrapper is unavailable in a given Claude Code session.

---

## Specialist approvals (Cat-4)

The Cat-4 flow lives in `_bmad/rdx/`:

```
_bmad/rdx/approvers.yaml           ← canonical roles + path patterns + identities
_bmad/rdx/approvers.schema.json    ← schema for the above
_bmad/rdx/approval.v1.schema.json  ← schema for individual approval files
_bmad/rdx/approvals/<diff_digest>.json   ← committed approvals, pinned to the diff
```

1. Author or copy `approvers.yaml` from the seeded `approvers.yaml.example` template. Define roles like `unsafe-reviewers`, `ffi-reviewers`, `governance` and which GitHub identities sit in each.
2. Run `python .claude/skills/rdx-setup/scripts/sync_codeowners.py --project-root .` to project those rules into `.github/CODEOWNERS` (idempotent, only edits the RDX-managed marker block).
3. When a Cat-4 diff is opened, the validator emits APPROVAL_REQUIRED. The named role member commits `_bmad/rdx/approvals/<diff_digest>.json` (schema: `approval.v1.schema.json`) with their identity and a `decision: approved`.
4. CI re-validates on every push. If the diff changes, the digest changes, and the approval lapses — preventing approval reuse across substantive edits (T-L7-APPROVAL-REUSE-001).

Optional HMAC signing of approvals is reserved in the schema but not required in V6; the threat model (`docs/threat-model.md` §7) documents why HMAC was deferred and what would re-open the question.

---

## Compatibility matrix

The canonical matrix is [`tests/compatibility/matrix.md`](tests/compatibility/matrix.md). Summary:

- Supported: Python 3.11/3.12/3.13 on Ubuntu / macOS.
- Not yet supported: Python ≤ 3.10 (no `tomllib`), Windows native (degrades to Mode 0 advisory), web-only Claude (no shell), Codex CLI / Cursor wrapper (standalone validator works; wrapper does not).

The matrix file embeds a machine-readable JSON block consumed by `tests/compatibility/test_compat_matrix.py`. Bump both together.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `/rdx-setup` is not visible in Claude Code | Skill not copied or Claude Code not restarted | Re-copy `rdx-setup`; reload the project in Claude Code |
| Validator reports `TOOL_UNAVAILABLE` for cargo | `cargo` not on PATH in the wrapper / hook / CI environment | Install Rust stable; on CI runners use `dtolnay/rust-toolchain@stable` |
| Validator reports `BASELINE_BLOCKS_VALIDATION` | A `--baseline` was supplied but does not match the current diff | Recompute the baseline or drop the flag |
| Hook fires but emits exit 4 (`REVIEW_REQUIRED`) | A Cat-3 rule triggered and no judgment evidence was recorded | Run `/rdx-code-review` (the R2 wrapper) to produce judgment findings |
| Hook fires but emits exit 3 (`APPROVAL_REQUIRED`) | A Cat-4 rule triggered and no approval JSON for the current diff_digest is committed | Obtain a sign-off and commit `_bmad/rdx/approvals/<diff_digest>.json` |
| Hook bypassed by mistake | `git push --no-verify` was used | CI (Mode 3) will re-validate; if not on Mode 3, re-validate locally and force a fresh push |
| Mode 3 CI fails but local Mode 2 succeeded | Hook is using your local validator; CI loads validator from the target branch | Reconcile with `python rdx-validator/rdx_validator/cli.py --diff-file ... --validator-ref origin/main` |
| Forbidden-phrase test fails | A docs change introduced one of the banned framings from `tests/acceptance/test_doc_honesty.py` in a non-negated form | Move the phrase into a negated sentence (e.g. prefix with "is not" or "does not") or rephrase to avoid the framing entirely; see the test for the exact phrase list |

---

## Limitations

- RDX does not prove correctness of all Rust decisions. It routes verdicts to the layer that can actually answer (deterministic command, evidence check, judgment review, or human approval), and refuses to merge a diff when the layer says no.
- The wrapper (`rdx-dev-story`) is a soft-gate cooperative orchestrator. It is workflow UX, not a programmatic boundary. The system-level enforcement boundary is the CI required check (Mode 3); Mode 2 is the strongest local boundary.
- Cat-3 judgment quality depends on the underlying LLM. The evaluator skill (`rdx-judgment`) scope-locks findings and refuses Cat-1 overturns, but it cannot prove that every Cat-3 verdict matches a human reviewer's intuition.
- The deterministic Cat-1/Cat-2 checks cover the rules listed in `tests/contracts/rule-check-map.json`. Rules outside that map (and not classified Cat-3 / Cat-4) are not currently validated.
- Windows native is not supported (degrades to Mode 0).
- Non-Claude CLIs (Codex CLI, Cursor) can run the standalone validator but cannot run the SKILL.md wrappers.

---

## Using RDX with GitHub Actions Free plan

GitHub Actions on the **Free** plan gives you **2,000 CI minutes per month** for private repositories, and unlimited minutes for public ones. The 2,000-minute budget is counted **per account or organization owner**, summed across every private repository that owner controls — not per-repo.

A typical Rust + RDX project consumes **5–15 CI-minutes per pull request** (cargo fetch + cargo check + L0/L1 contract tests + the validator). That means a Free-tier owner can land **roughly 130 PRs/month** before approaching the budget cap, which is comfortable headroom for solo developers and small teams.

If you do not want to spend CI minutes at all, **Mode 2 (Local Gated, pre-push hook) is the fully free, no-CI alternative**. The hook runs the same validator the CI workflow would run, and refuses to push on FAIL. Mode 2 is a supported, release-quality target — shipping under Mode 2 is a legitimate end state, not a "stepping stone" to Mode 3.

### Step-by-step setup on GitHub Free with `rdx-gate.yml` as a required check

1. **Install RDX in the project** (see [Installation](#installation) above) and choose **MODE_3 (CI Enforced)** when `/rdx-setup` prompts.
2. **Copy the workflow** — `cp .github/workflows/rdx-gate.yml YOUR_PROJECT/.github/workflows/` (the file ships in this repo).
3. **Push to `main`** so GitHub registers the workflow run for the default branch.
4. **Open a throwaway PR** and confirm the workflow runs. The job name will appear in the PR checks list as `RDX gate / rdx-gate`.
5. **Enable branch protection** — Repository Settings → Branches → Add rule for `main` → enable "Require status checks to pass before merging" and add `RDX gate / rdx-gate` to the required-check list.
6. **(Recommended)** add a CODEOWNERS rule that restricts `.github/workflows/**` to a trusted reviewer set so PRs cannot rewrite the gate itself ([`docs/branch-protection.md`](docs/branch-protection.md) walks through this).

Once the required check is set, no PR can merge to `main` without a green RDX verdict. The validator is loaded from the target branch (`--validator-ref`), so a PR cannot edit its own validator and observe a green verdict.

---

## When you need more than 2,000 minutes — switching to paid

If you outgrow the Free tier, you have three paths. Pick the one that matches how the project is owned.

### Step-by-step: move the repo into a GitHub organization

A personal account's Free tier is per-user. Moving the repo into a GitHub **organization** lets multiple maintainers share a single billing entity and opens the door to higher-tier plans.

1. **Create or pick an organization** — github.com/organizations/new (Free organization is fine to start).
2. **Repository Settings → Transfer ownership** → enter the organization handle. The repo, issues, PRs, and workflow runs move over.
3. **Re-add CODEOWNERS / approvers.yaml entries** to point at organization team handles (`@org/unsafe-reviewers`) instead of personal handles, so role membership stays stable as the team grows.
4. **Run `python .claude/skills/rdx-setup/scripts/sync_codeowners.py --project-root .`** to regenerate the `.github/CODEOWNERS` block from `approvers.yaml`.
5. **Set up billing** — Organization Settings → Billing and plans → upgrade to the tier below.

### Tier comparison

Approximate figures as of the plan-lock date; verify the current GitHub pricing page before budgeting.

| Plan | Cost | Included CI minutes/month (private) | When to pick it |
|------|------|-------------------------------------|-----------------|
| GitHub **Free** (org) | $0 / user | 2,000 | Same budget as personal Free; useful only for the team-management features. |
| GitHub **Pro** (personal) | ~$4 / user / month | 3,000 (Free 2,000 + Pro 1,000) | A solo maintainer who needs ~50% more headroom. |
| GitHub **Team** (org) | ~$4 / user / month | 3,000 | Small team that wants shared billing + protected branches. |
| GitHub **Enterprise** | Custom (~$21+ / user / month) | 50,000 | Teams with significant CI consumption or compliance requirements. |

### Self-hosted runners (zero additional GitHub cost)

GitHub Actions itself is free when you provide the runner. Spin up a self-hosted runner on infrastructure you already pay for (a spare VM, an on-prem box, a small cloud instance) and minutes consumed on that runner are not charged against your GitHub account. You pay only the infrastructure cost.

```yaml
# in rdx-gate.yml
jobs:
  rdx-gate:
    runs-on: self-hosted   # was: ubuntu-latest
```

Self-hosted runners require a hardened registration on the org or repo (see GitHub's "Adding self-hosted runners" docs); do not register a self-hosted runner on a public repo without isolation, as PRs from forks would be able to execute code on your runner.

### Suggested cost calculator

```
monthly_minutes_used  =  typical_PR_minutes  ×  monthly_PRs_landed
                      +  scheduled_jobs_minutes_per_run  ×  runs_per_month

projected_overage     =  max(0, monthly_minutes_used − plan_included_minutes)
projected_cost        =  plan_cost  +  projected_overage  ×  per_minute_overage_rate
```

For RDX-typical PRs (5–15 CI-min each) the calculator is dominated by `monthly_PRs_landed`. If your projected_overage is small (a few hundred minutes), Pro/Team is usually cheaper than Enterprise. If it is in the tens of thousands of minutes, Enterprise or self-hosted runners are the practical choices.

---

## Repository structure

For users, the map below is the whole thing. For maintainers or agents extending RDX, start at [`docs/AGENT_MAINTENANCE_GUIDE.md`](docs/AGENT_MAINTENANCE_GUIDE.md) — it explains where to add checks, how the test taxonomy works, and where every design decision was made.

```
README.md                               ← this file
CHANGELOG.md                            ← per-release notes
LICENSE

.claude/skills/
├── rdx-setup/                          ← installer, modes selector, Cat-4 seed
├── rdx-dev-story/                      ← soft-gate wrapper (Mode 1)
├── rdx-hooks/                          ← pre-push hook installer (Mode 2)
├── rdx-code-review/                    ← R2 wrapper (Cat-3 review)
└── rdx-judgment/                       ← Cat-3 evaluator (rule auditor)

rdx-validator/                          ← standalone Python package, BMAD-independent

_bmad/rdx/                              ← runtime config surface
├── approvers.schema.json
├── approval.v1.schema.json
└── approvers.yaml.example

docs/                                   ← living documentation
├── AGENT_MAINTENANCE_GUIDE.md          ← start here to extend RDX
├── branch-protection.md                ← GitHub-side CODEOWNERS / required-checks recipe
├── threat-model.md                     ← formal threat model (Mode 4 rationale + §8 triggers)
└── doc-review-checklist.md             ← run before each release

.github/workflows/
├── rdx-gate.yml                        ← the ONE workflow users copy into their own project
└── (10 internal workflows)             ← this repo's own CI — see AGENT_MAINTENANCE_GUIDE §5.4

tests/                                  ← 307-test regression suite (L0–L8 + acceptance)

archive-docs-dev/                       ← historical planning artefacts, frozen at 1.1 release
                                          (read-only; see archive-docs-dev/README.md for the index)
```

---

## License

MIT — see [LICENSE](LICENSE).
