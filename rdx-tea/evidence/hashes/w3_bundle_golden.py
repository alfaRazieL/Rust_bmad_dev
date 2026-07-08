#!/usr/bin/env python3
"""W3 golden-bundle signature pin (G-W3-DETERMINISM / G-DET).

Drives the PRODUCTION ``prepare.prepare()`` across every workflow in the
obligation matrix and a fixed set of representative inputs, then compares a
sorted, byte-stable signature to the pin in ``w3_bundle_golden.txt``:

    <sha256(active-context.md)>  <sha256(run-manifest.json)>  <case-id>

DIFFERENCE FROM W1: this harness runs CLOCK-FREE. It explicitly UNSETS
``RDX_TEA_FAKE_NOW`` and relies on ``prepare`` being wall-clock/random free
(W3 made the manifest byte-deterministic with no env injection). The pinned
manifest hashes therefore prove *production* determinism — reproducible in
two independent processes with no magic environment. This is a strictly
stronger guarantee than the W1 signature, which fixed the clock via
``RDX_TEA_FAKE_NOW``.

The signature is a pure function of the canonical KB + generator logic. Run
this before and after any Wave-3+ change touching the bundle builder; the
output MUST match the pin, or runtime behaviour changed.

Usage:
    python rdx-tea/evidence/hashes/w3_bundle_golden.py            # verify
    python rdx-tea/evidence/hashes/w3_bundle_golden.py --print    # print rows
    python rdx-tea/evidence/hashes/w3_bundle_golden.py --write    # re-pin
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
RDX_TEA_DIR = HERE.parent.parent.parent  # rdx-tea/
INSTALL_SCRIPTS = (
    RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"
)
PIN_FILE = HERE.parent / "w3_bundle_golden.txt"

sys.path.insert(0, str(INSTALL_SCRIPTS))
for _m in ("rdx_parser", "prepare", "obligation_matrix"):
    sys.modules.pop(_m, None)
import prepare as prepare_mod  # noqa: E402
from obligation_matrix import all_workflows  # noqa: E402

IDENTITY = {
    "base_sha": "1" * 40,
    "head_sha": "2" * 40,
    "diff_digest": "",  # computed by prepare
    "rdx_source_sha": "d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d",
    "tea_source_sha": "8734d51f24071ddbcb3617390b5fcddb4128ef77",
}

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


def compute_rows() -> list[str]:
    # Clock-free: prove determinism WITHOUT env injection.
    os.environ.pop("RDX_TEA_FAKE_NOW", None)
    rows: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        proj.mkdir()
        (proj / "Cargo.toml").write_text("[package]\nname='x'\n", encoding="utf-8")
        (proj / "src").mkdir()
        (proj / "src" / "lib.rs").write_text("// lib\n", encoding="utf-8")
        for wf in all_workflows():
            for case_id, diff_text, tags, rust_scope in CASES:
                diff_p = Path(td) / "diff.patch"
                diff_p.write_text(diff_text, encoding="utf-8")
                tags_p = Path(td) / "tags.txt"
                tags_p.write_text("\n".join(tags) + ("\n" if tags else ""),
                                  encoding="utf-8")
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
                assert manifest["bundle_sha256"] == bundle_sha, (wf, case_id)
                # Clock-free manifest: no wall-clock stamp leaked.
                assert manifest["prepared_at"] == "", (wf, case_id)
                rows.append(f"{bundle_sha}  {manifest_sha}  {wf}/{case_id}")
    return sorted(rows)


def read_pin_rows() -> list[str] | None:
    if not PIN_FILE.exists():
        return None
    rows = []
    for ln in PIN_FILE.read_text(encoding="utf-8").splitlines():
        ln = ln.rstrip()
        if not ln or ln.startswith("#"):
            continue
        rows.append(ln)
    return sorted(rows)


def render_pin(rows: list[str]) -> str:
    header = (
        "# W3 golden-bundle signature pin (G-W3-DETERMINISM / G-DET).\n"
        "#\n"
        "# <sha256(active-context.md)>  <sha256(run-manifest.json)>  <workflow>/<case>\n"
        "#\n"
        "# Computed CLOCK-FREE (RDX_TEA_FAKE_NOW unset) by the PRODUCTION\n"
        "# prepare.prepare(). The manifest hash is reproducible across two\n"
        "# independent processes with NO env injection — prepare is\n"
        "# wall-clock/random free (W3). Re-pin with --write only on an\n"
        "# intentional generator change; a canonical/ change also needs a\n"
        "# source-lock re-pin + SOURCE_LOCK addendum. Verify: w3_bundle_golden.py\n"
    )
    return header + "\n".join(rows) + "\n"


def main(argv: list[str]) -> int:
    rows = compute_rows()
    if "--print" in argv:
        print("\n".join(rows))
        return 0
    if "--write" in argv:
        PIN_FILE.write_text(render_pin(rows), encoding="utf-8")
        print(f"pinned {len(rows)} rows -> {PIN_FILE.name}")
        return 0
    pinned = read_pin_rows()
    if pinned is None:
        print(f"NO PIN present at {PIN_FILE.name}", file=sys.stderr)
        return 2
    if pinned != rows:
        print("DRIFT: computed golden signature != pinned", file=sys.stderr)
        computed = set(rows)
        pin = set(pinned)
        for extra in sorted(computed - pin):
            print(f"  + {extra}", file=sys.stderr)
        for missing in sorted(pin - computed):
            print(f"  - {missing}", file=sys.stderr)
        return 1
    print(f"OK W3 golden bundle signature ({len(rows)} rows) matches pin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
