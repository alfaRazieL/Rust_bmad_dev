# D3 addendum to SOURCE_LOCK — upstream BMAD / Builder / TEA SHAs

**Written:** 2026-07-02T12:50:54Z  
**Branch:** rdx-tea-integration  
**HEAD when written:** bdf3f31965aad33288ac66938ebb36fd5be5fcb2  
**Governing prompt:** `RDX_TEA_D3_proof_correction_prompt.md` §3.1.  
**Supersedes / amends:** `rdx-tea/research/SOURCE_LOCK.md §4` "PENDING" rows.

## 1. Upstream repositories

### 1.1 BMAD-METHOD

- URL: `https://github.com/bmad-code-org/BMAD-METHOD`
- Clone destination (this work window): `/Users/m33tball/bmad_module_builder/rdx-workspace/upstream/BMAD-METHOD`
- `origin/main` HEAD at fetch: `67f4499e31304f3c889f88b833dbef49d432e07e`
  - subject: `fix(dev-auto): write frontmatter status explicitly at Finalize (#2536)`
  - author date: 2026-05-19–2026-06 range (24 commits ahead of v6.9.0)
- `v6.9.0` tag: `6ac4c26b699579cbc64c296ac1fddfecfc405d72`
  - date: 2026-06-22T05:15:11Z
- `v6.8.0` tag: `3bcd6c3cce6e381b759e23185b099081496567a5`
  - date: 2026-05-25T21:47:24Z
  - **This tag matches the host installation** — see §2.

### 1.2 BMad Builder

- Builder skills (`bmad-module-builder`, `bmad-agent-builder`,
  `bmad-workflow-builder`, `bmad-bmb-setup`, `bmad-customize`,
  `bmad-eval-runner`) all ship *inside* the BMAD-METHOD monorepo under
  `src/skills/…` or `src/modules/…`. There is no separate Builder
  repository at the URL originally suggested in `SOURCE_LOCK.md §4`.
  The correct SHA is therefore the BMAD-METHOD SHA above.
- Path anchor inside the repo (v6.9.0):
  `src/modules/bmb/agents/bmad-agent-builder/` and siblings — verified
  by `find . -name "SKILL.md" -path "*builder*"`.

### 1.3 BMAD TEA

- URL: `https://github.com/bmad-code-org/bmad-method-test-architecture-enterprise`
- Clone destination: `/Users/m33tball/bmad_module_builder/rdx-workspace/upstream/bmad-method-test-architecture-enterprise`
- `origin/main` HEAD at fetch: `8734d51f24071ddbcb3617390b5fcddb4128ef77`
  - subject: `release: bump to v1.19.0 [skip ci]`
  - date: 2026-05-19T20:05:09Z
  - **Identical to the `v1.19.0` tag** (last committed release).
- `v1.19.0` tag: `8734d51f24071ddbcb3617390b5fcddb4128ef77`
- Package version: `1.19.0` (per `package.json`)
- Prior tags observed and fetched: v1.10.0 … v1.19.0.

## 2. Host installation ↔ upstream mapping

The host BMAD 6.8.0 installation lives at `/Users/m33tball/bmad_module_builder/`.
Cross-check of authoritative files against upstream tags:

| Host file | Upstream tag | SHA-256 | Verdict |
|---|---|---|---|
| `_bmad/scripts/resolve_customization.py` | BMAD `v6.8.0` | `a56abc64ffc8924f8ded95562c7ef3f6d7f1b18f0724289fd3b95fda3567dab4` | IDENTICAL |
| `_bmad/scripts/resolve_customization.py` | BMAD `v6.9.0` | `23fb9040b08c7eb975aeabc4245ef50e158516f5082eebc9ae41700641338498` | drift — docstring only (uv→python3) — merge logic byte-identical |
| `.claude/skills/bmad-tea/customize.toml` | TEA `v1.19.0` | `2864b07f57c631473380fb4e7cac49282e7585d191e266088337314c8e2b7937` | IDENTICAL |
| `.claude/skills/bmad-testarch-test-design/customize.toml` | TEA `v1.19.0` | `c83a85c3de1ee5ff9acc94b9b8a96c563d9573520ea791c54d35f468568c6695` | IDENTICAL |
| `.claude/skills/bmad-testarch-test-design/SKILL.md` | TEA `v1.19.0` | `78636f43137dd33260994df1b2f91a392fb9ccddbb448a5fbcbcfa8c4cc8745e` | IDENTICAL |

Machine-readable listing: `rdx-tea/evidence/hashes/D3_UPSTREAM_LOCK.txt`.

### 2.1 Version stack summary

The user's live installation is:

```
BMAD-METHOD 6.8.0  →  upstream tag 3bcd6c3c (2026-05-25)
BMAD TEA  1.19.0   →  upstream tag 8734d51f (2026-05-19)
BMad Builder       →  ships inside BMAD-METHOD, therefore tracks 6.8.0
```

An RDX-TEA adapter targeting this host must therefore **support** at
minimum the v6.8.0 resolver semantics and the v1.19.0 TEA workflow
shapes, and MUST detect when the host BMAD major/minor version diverges
from the range it was tested against.

## 3. Diff between BMAD 6.8.0 and 6.9.0 that matters for D3

- `resolve_customization.py` — docstring drift only. Merge functions
  (`deep_merge`, `_merge_arrays`, `_detect_keyed_merge_field`,
  `load_toml`) are byte-identical between v6.8.0 and v6.9.0. This is
  the load-bearing surface for D3's TOML overlay path. Its stability
  across the minor version bump is a favourable data point.
- The TEA workflow schema (`customize.toml`
  `activation_steps_prepend / persistent_facts / on_complete`) is
  unchanged between v1.14.0 and v1.19.0 for `bmad-tea/customize.toml`.
  Between v1.18.0 and v1.19.0 the agent-level customize file changed
  (host matches the v1.19.0 shape).

## 4. Consequences for existing verdicts

- `SOURCE_LOCK.md §4` "PENDING" rows for BMAD Core / Builder / TEA are
  now filled by §1 of this addendum.
- `FINAL_VERIFICATION.json` G1 was `PASS` on the strength of a role-
  playing subagent review, which per the D3 prompt §3.1 is
  insufficient. Downgrade to `PARTIAL_PASS` recorded in
  `D3_CORRECTION_AUDIT.md`.
- Regardless of upstream SHA, the **structural** claim in
  `BMAD_CORE_EXTENSION_SURFACE.md` §1 (three-layer TOML merge, deep +
  keyed) is now source-verified against `v6.8.0/src/scripts/resolve_customization.py`
  and `v6.9.0` shows only cosmetic drift. That specific claim graduates
  from MEDIUM to HIGH confidence in `D3_CLAIM_EVIDENCE_MATRIX.md`.
- Activation order documented in every `bmad-testarch-*/SKILL.md`
  (Step 2 prepend → Step 3 persistent_facts → … → terminal step
  `on_complete`) is source-verified against upstream v1.19.0 and is
  the load-bearing precondition for D3 seams A and B.

## 5. What upstream SHAs still remain PENDING

- Nothing at this checkpoint. Both authoritative repositories are
  cloned, tagged, and their relevant files hash-compared to the host.
- Future fetches after user push may return a different `origin/main`
  HEAD. In that case update this file, do not silently move the
  reference.
