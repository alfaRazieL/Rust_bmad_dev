"""L2 dynamic active-context bundle tests (Phase D of the D3 proof).

Every test exercises the real `prepare.py` PoC against a controlled diff
+ story fixture and asserts the resulting bundle behaves per ADR-002
§5.3–§5.4:

  * Router-selected packs, not a static glob
  * Workflow obligation matrix applied
  * Deterministic bytes
  * No RDX verdict vocabulary in the bundle
  * Atomic replace on rerun
  * No leakage between runs
  * Router parity with rdx_validator/router.replay
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = RDX_TEA_DIR.parent
# D3.1: use the production-layout install tree.
INSTALL_SCRIPTS = RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"


def _load_prepare():
    if str(INSTALL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(INSTALL_SCRIPTS))
    import importlib
    if "rdx_parser" in sys.modules:
        del sys.modules["rdx_parser"]
    if "prepare" in sys.modules:
        del sys.modules["prepare"]
    return importlib.import_module("prepare")


prepare_mod = _load_prepare()


DEFAULT_IDENTITY = {
    "base_sha":  "1" * 40,
    "head_sha":  "2" * 40,
    "diff_digest": "",   # computed by prepare
    "rdx_source_sha": "d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d",
    "tea_source_sha": "8734d51f24071ddbcb3617390b5fcddb4128ef77",
}


# ---------------------------------------------------------------- helpers
def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ASYNC_POSITIVE_DIFF = """diff --git a/src/lib.rs b/src/lib.rs
index abc..def 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,10 @@
+use tokio::task;
+
+pub async fn run() -> Result<(), std::io::Error> {
+    let handle = tokio::spawn(async {
+        // heavy work
+    });
+    handle.await.unwrap();
+    Ok(())
+}
"""

DOC_ONLY_DIFF = """diff --git a/README.md b/README.md
index abc..def 100644
--- a/README.md
+++ b/README.md
@@ -0,0 +1,3 @@
+# Notes
+
+This project uses `tokio::spawn` internally. This paragraph is documentation only.
"""

UNSAFE_POSITIVE_DIFF = """diff --git a/src/lib.rs b/src/lib.rs
index abc..def 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,5 @@
+unsafe fn touch_raw(p: *const u8) {
+    unsafe {
+        std::ptr::read(p);
+    }
+}
"""

NON_RUST_DIFF = """diff --git a/config.yaml b/config.yaml
index abc..def 100644
--- a/config.yaml
+++ b/config.yaml
@@ -0,0 +1,1 @@
+setting: value
"""

# --------------------------------------------------------------------- tests

@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "_bmad-run").mkdir()
    return tmp_path


def _prepare_run(project: Path, workflow: str, diff: str, story: str = "",
                 tags: list[str] | None = None, run_id: str = "test-run-01"):
    tags_path = None
    if tags:
        p = project / "_bmad-run" / "tags.txt"
        p.write_text("\n".join(tags), encoding="utf-8")
        tags_path = p
    diff_path = project / "_bmad-run" / "diff.patch"
    _write(diff_path, diff)
    story_path = project / "_bmad-run" / "story.md"
    _write(story_path, story or "# Rust story")
    # D3.2: emulate rust-scope by writing Cargo.toml unless the diff is
    # a doc-only or non-Rust fixture.
    if diff and "src/lib.rs" in diff:
        (project / "Cargo.toml").write_text("[package]\nname='p'\nversion='0'\n",
                                            encoding="utf-8")
    manifest = prepare_mod.prepare(
        project_root=project,
        workflow=workflow,
        identity=dict(DEFAULT_IDENTITY),
        run_id=run_id,
        story_path=story_path,
        diff_path=diff_path,
        tags_path=tags_path,
        rust_scope=True if "src/lib.rs" in diff or "async" in workflow else False,
    )
    return manifest, (
        project / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id / "active-context.md"
    ).read_text(encoding="utf-8")


def test_l2_d01_async_diff_activates_async_pack_and_includes_obligations(project: Path) -> None:
    m, body = _prepare_run(project, "test-design", ASYNC_POSITIVE_DIFF)
    ids = [p["pack_id"] for p in m["active_packs"]]
    assert "async" in ids
    assert "RP-ASYNC-005" in m["active_packs"][ids.index("async")]["rule_ids"]
    assert "cancel-safe" in body    # rule body text present
    assert "Cancellation, timeout, and shutdown" in body


def test_l2_d02_doc_only_diff_excludes_async_pack(project: Path) -> None:
    m, body = _prepare_run(project, "test-design", DOC_ONLY_DIFF)
    ids = [p["pack_id"] for p in m["active_packs"]]
    assert "async" not in ids, f"doc-only diff should not activate async: {ids}"


def test_l2_d03_non_rust_diff_produces_empty_bundle(project: Path) -> None:
    m, body = _prepare_run(project, "test-design", NON_RUST_DIFF)
    assert not m["active_packs"], f"non-Rust diff should activate no packs: {m['active_packs']}"
    assert "_No RDX pack activated" in body


def test_l2_d04_bundle_never_contains_rdx_verdict_vocabulary(project: Path) -> None:
    """D3.1: precise check. The bundle carries KB rule bodies which
    include natural English `PASS`/`FAIL` uses (e.g. "type-check passes").
    The invariant we need is that the bundle never emits a *verdict
    field* the LLM can be baited into filling: no `verdict:` YAML key,
    no `cat1_verdict`, no `rdx_verdict`, no leading verdict token."""
    m, body = _prepare_run(project, "test-design", ASYNC_POSITIVE_DIFF)
    banned_keys = (
        "verdict:", "verdict :", "rdx_verdict:", "cat1_verdict:",
        "cat2_verdict:", "cat3_verdict:", "cat4_verdict:",
    )
    for k in banned_keys:
        assert k not in body, f"bundle leaked verdict field {k!r}"
    # And the schema-forbidden verdicts must not appear as YAML values
    # on any line ("- PASS", "  PASS", etc.).
    for line in body.splitlines():
        stripped = line.lstrip("- ").strip()
        assert stripped not in ("PASS", "FAIL", "APPROVAL_REQUIRED",
                                "REVIEW_REQUIRED", "EVIDENCE_REQUIRED",
                                "REGRESSION_FAILURE"), (
            f"bundle line looks like a verdict value: {line!r}"
        )


def test_l2_d05_bundle_bytes_deterministic(project: Path) -> None:
    os.environ["RDX_TEA_FAKE_NOW"] = "2026-07-02T00:00:00+00:00"
    try:
        m1, body1 = _prepare_run(project, "test-design", ASYNC_POSITIVE_DIFF)
        m2, body2 = _prepare_run(project, "test-design", ASYNC_POSITIVE_DIFF)
        assert body1 == body2
        assert m1["bundle_sha256"] == m2["bundle_sha256"]
    finally:
        os.environ.pop("RDX_TEA_FAKE_NOW", None)


def test_l2_d06_stale_bundle_atomically_replaced(project: Path) -> None:
    m1, body1 = _prepare_run(project, "test-design", ASYNC_POSITIVE_DIFF)
    m2, body2 = _prepare_run(project, "test-design", NON_RUST_DIFF)
    assert body1 != body2
    assert m1["bundle_sha256"] != m2["bundle_sha256"]
    # After the second run, bundle path holds body2 only.
    disk = (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
            / "test-run-01" / "active-context.md").read_text()
    assert disk == body2
    # No leakage of previous packs.
    ids = {p["pack_id"] for p in m2["active_packs"]}
    assert "async" not in ids


def test_l2_d07_router_parity_with_rdx_validator(project: Path) -> None:
    """D3.1: exact equality between (Router ∩ obligation-matrix) and
    the packs emitted by prepare. No `subset` slack."""
    if str(REPO_ROOT / "rdx-validator") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "rdx-validator"))
    from rdx_validator.router import RouterRules, activated_pack_names, replay
    from obligation_matrix import matrix_for   # via install-tree scripts path
    router = RouterRules.load(REPO_ROOT / "tests" / "contracts" / "router-rules.json")
    canonical = set(activated_pack_names(replay(ASYNC_POSITIVE_DIFF, router, [])))
    m, _ = _prepare_run(project, "test-design", ASYNC_POSITIVE_DIFF)
    prepared = set(p["pack_id"] for p in m["active_packs"])
    expected = canonical & matrix_for("test-design")["packs"]
    assert prepared == expected, (
        f"parity break: prepared={prepared} vs expected={expected} "
        f"(canonical={canonical})"
    )


def test_l2_d08_manifest_carries_source_hashes(project: Path) -> None:
    """D3.1: manifest carries a deterministic snapshot hash across ALL
    canonical files, plus KB per-file map. Identity block is mandatory."""
    m, _ = _prepare_run(project, "test-design", ASYNC_POSITIVE_DIFF)
    assert m["rdx_canonical_snapshot_sha256"], "canonical snapshot sha missing"
    assert m["rdx_kb_source_hashes"], "KB sha map missing"
    for k in m["rdx_kb_source_hashes"]:
        assert k.endswith(".md")
    idn = m["identity"]
    for k in ("base_sha", "head_sha", "diff_digest",
              "rdx_source_sha", "tea_source_sha"):
        assert idn[k] and len(idn[k]) >= 40, f"identity.{k} missing/short"


def test_l2_d09_workflow_obligation_matrix_applied(project: Path) -> None:
    """`trace` workflow only cares about `testing` pack even if `unsafe`
    activates."""
    m, _ = _prepare_run(project, "trace", UNSAFE_POSITIVE_DIFF)
    ids = {p["pack_id"] for p in m["active_packs"]}
    # unsafe was Router-activated but trace's matrix filters it out
    assert "unsafe" not in ids, "trace must not carry unsafe rules"


def test_l2_d10_story_tag_required_pack_gated_on_tag(project: Path) -> None:
    """D3.1: `api` is STORY_TAG_REQUIRED. Behaviour must be exact:
      - without the tag → NOT activated
      - with the tag    → activated
    No `or True` escape hatch."""
    api_diff = """diff --git a/src/lib.rs b/src/lib.rs
index a..b 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,3 @@
+pub fn public_api(x: i32) -> i32 {
+    x + 1
+}
"""
    m_no_tag, _ = _prepare_run(project, "test-design", api_diff)
    ids_no_tag = {p["pack_id"] for p in m_no_tag["active_packs"]}
    assert "api" not in ids_no_tag, (
        f"api must NOT activate without story tag, got {ids_no_tag}"
    )

    m_with_tag, _ = _prepare_run(project, "test-design", api_diff,
                                  tags=["api"])
    ids_with_tag = {p["pack_id"] for p in m_with_tag["active_packs"]}
    assert "api" in ids_with_tag, (
        f"api MUST activate with story tag `api`, got {ids_with_tag}"
    )


def test_l2_d11_multiple_packs_both_appear(project: Path) -> None:
    diff = ASYNC_POSITIVE_DIFF + UNSAFE_POSITIVE_DIFF
    m, body = _prepare_run(project, "test-design", diff)
    ids = {p["pack_id"] for p in m["active_packs"]}
    assert "async" in ids
    assert "unsafe" in ids
    assert "cancel-safe" in body
    assert "SAFETY" in body or "unsafe" in body


def test_l2_d12_bundle_atomic_write_no_tmp_leftover(project: Path) -> None:
    _prepare_run(project, "test-design", ASYNC_POSITIVE_DIFF)
    tmp = list((project / "_bmad" / "rdx-tea" / "runtime" / "test-design").glob("*.tmp"))
    assert not tmp, f"tmp file leftover: {tmp}"


def test_l2_d13_manifest_schema_present(project: Path) -> None:
    m, _ = _prepare_run(project, "test-design", ASYNC_POSITIVE_DIFF)
    assert m["schema_version"] == "rdx-tea-run.v1"
    assert m["execution_mode"] == "sequential"
