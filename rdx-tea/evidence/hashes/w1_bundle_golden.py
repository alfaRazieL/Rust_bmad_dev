#!/usr/bin/env python3
"""W1 golden-bundle signature harness (G-DET / G-W1-NOBEHAVIOUR).

Drives the PRODUCTION `prepare.prepare()` deterministically across every
workflow in the obligation matrix and a fixed set of representative
inputs, then prints a sorted, byte-stable signature:

    <sha256(active-context.md)>  <sha256(run-manifest.json)>  <case-id>

The signature is a pure function of the canonical KB + generator logic.
It does NOT depend on `VERSION` (which no generator reads). Run this
before and after any Wave-1 change; the two outputs MUST be identical,
or runtime behaviour changed and the change must be reverted.

Usage:
    RDX_TEA_FAKE_NOW=2020-01-01T00:00:00+00:00 \
        python rdx-tea/evidence/hashes/w1_bundle_golden.py

Determinism is enforced by `RDX_TEA_FAKE_NOW` (stamps `prepared_at`) and
a fixed identity/run_id. No wallclock, no randomness.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

# Locate the production install-tree scripts (never live-harness/evals).
HERE = Path(__file__).resolve()
RDX_TEA_DIR = HERE.parent.parent.parent  # rdx-tea/
INSTALL_SCRIPTS = (
    RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"
)
sys.path.insert(0, str(INSTALL_SCRIPTS))

import prepare as prepare_mod  # noqa: E402
from obligation_matrix import all_workflows  # noqa: E402

IDENTITY = {
    "base_sha": "1" * 40,
    "head_sha": "2" * 40,
    "diff_digest": "",  # computed by prepare
    "rdx_source_sha": "d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d",
    "tea_source_sha": "8734d51f24071ddbcb3617390b5fcddb4128ef77",
}

# Representative inputs. Each exercises a distinct region of the
# generator's behaviour: no activation (docs-only), a Rust change that
# activates multiple packs, and an unsafe change — across rust_scope
# on/off. Diffs are literal so the harness is self-contained.
DIFF_ASYNC_API = (
    "diff --git a/src/lib.rs b/src/lib.rs\n"
    "--- a/src/lib.rs\n"
    "+++ b/src/lib.rs\n"
    "@@ -1,1 +1,3 @@\n"
    "+pub async fn handler() -> Result<(), Error> {\n"
    "+    tokio::spawn(async { work().await });\n"
    "+}\n"
)
DIFF_UNSAFE = (
    "diff --git a/src/ffi.rs b/src/ffi.rs\n"
    "--- a/src/ffi.rs\n"
    "+++ b/src/ffi.rs\n"
    "@@ -1,1 +1,3 @@\n"
    "+unsafe fn raw() {\n"
    "+    let p = std::ptr::null_mut::<u8>();\n"
    "+}\n"
)
DIFF_DOCS_ONLY = (
    "diff --git a/README.md b/README.md\n"
    "--- a/README.md\n"
    "+++ b/README.md\n"
    "@@ -1,1 +1,2 @@\n"
    "+documentation only, no code\n"
)

CASES = [
    ("async-api", DIFF_ASYNC_API, ["needs:api"], True),
    ("unsafe", DIFF_UNSAFE, [], True),
    ("docs-only-scoped-out", DIFF_DOCS_ONLY, [], False),
    ("docs-only-rust-repo", DIFF_DOCS_ONLY, [], None),
]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    os.environ.setdefault("RDX_TEA_FAKE_NOW", "2020-01-01T00:00:00+00:00")
    rows: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        proj.mkdir()
        # Make the project a Rust repo so autodetect (rust_scope=None) is
        # meaningful and deterministic.
        (proj / "Cargo.toml").write_text("[package]\nname='x'\n", encoding="utf-8")
        (proj / "src").mkdir()
        (proj / "src" / "lib.rs").write_text("// lib\n", encoding="utf-8")

        for wf in all_workflows():
            for case_id, diff_text, tags, rust_scope in CASES:
                diff_p = Path(td) / "diff.patch"
                diff_p.write_text(diff_text, encoding="utf-8")
                tags_p = Path(td) / "tags.txt"
                tags_p.write_text("\n".join(tags) + ("\n" if tags else ""), encoding="utf-8")
                out_root = Path(td) / "out" / wf / case_id
                manifest = prepare_mod.prepare(
                    project_root=proj,
                    workflow=wf,
                    identity=dict(IDENTITY),
                    run_id="golden-run-0001",
                    diff_path=diff_p,
                    tags_path=tags_p,
                    output_root=out_root,
                    rust_scope=rust_scope,
                )
                bundle_sha = _sha((out_root / "active-context.md").read_bytes())
                manifest_sha = _sha((out_root / "run-manifest.json").read_bytes())
                # Cross-check: manifest's own bundle_sha256 must agree.
                assert manifest["bundle_sha256"] == bundle_sha, (wf, case_id)
                rows.append(f"{bundle_sha}  {manifest_sha}  {wf}/{case_id}")

    for line in sorted(rows):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
