"""L7 W6 — per-check verifier mutation (G-W6-VERIFIER).

The behavioural verifier (`rdx_tea_validator.verify`) performs 9 checks, each
bound to a hashed input. G-W6-VERIFIER requires that mutating each hashed
input flips EXACTLY that check to FAIL (and the aggregate verdict to FAIL),
i.e. every check fails closed and none can be bypassed.

Strategy: build ONE passing run once (module-scoped, via the shipped wrapper's
env-gated fake-artefact path — NO live model, NO subagent/Task dispatch), then
for each check copy the whole project, apply a SURGICAL mutation to that
check's hashed input, and re-run the shipped validator CLI as a subprocess
(clean per-copy canonical/source-lock resolution). Each mutation is designed to
be isolated: exactly one check flips.

  schema:               add an unknown property (additionalProperties:false)
  manifest_hash:        rewrite run-manifest.json bytes (non-snapshot field)
  bundle_hash:          tamper active-context.md
  artifact_hash:        tamper the artefact bytes
  base_head_exist:      point base_sha at an all-zero (nonexistent) commit
  diff_digest_recomputed: tamper diff.patch
  canonical_snapshot:   tamper a canonical KB source file
  source_lock:          change rdx_source_sha in sources.lock
  artifact_boundary:    replace the artefact with a symlink (identical bytes,
                        so ONLY the boundary check flips)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
INSTALL_TREE = RDX_TEA_DIR / "poc" / "install-tree"
VENV_PY = Path(sys.executable)
WORKFLOW = "test-design"
RUN_ID = "w6-verifier-01"
ARTEFACT_NAME = f"{WORKFLOW}-{RUN_ID}-artifact.md"

ALL_CHECKS = (
    "schema", "manifest_hash", "bundle_hash", "artifact_hash",
    "base_head_exist", "diff_digest_recomputed", "canonical_snapshot",
    "source_lock", "artifact_boundary",
)

ASYNC_DIFF = """diff --git a/src/lib.rs b/src/lib.rs
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,4 @@
+pub async fn f() {
+    let h = tokio::spawn(async {});
+    h.await.unwrap();
+}
"""


def _run(cmd, cwd, env=None):
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd),
                          capture_output=True, text=True, env=env, check=False)


def _env():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("RDX_TEA_FAKE_NOW", None)
    env["RDX_TEA_ALLOW_FIXTURE_DIFF"] = "1"
    env["RDX_TEA_ALLOW_TEST_ARTEFACT"] = "1"
    return env


@pytest.fixture(scope="module")
def built_run(tmp_path_factory) -> Path:
    """A single PASSING run; copied per test so mutations never interfere."""
    proj = tmp_path_factory.mktemp("w6verif") / "proj"
    proj.mkdir()
    shutil.copytree(INSTALL_TREE / "_bmad", proj / "_bmad")
    (proj / "_bmad-run").mkdir()
    (proj / "_bmad-output" / "test-artifacts").mkdir(parents=True)
    (proj / ".claude" / "skills" / "bmad-testarch-test-design").mkdir(parents=True)
    (proj / "_bmad" / "tea").mkdir(exist_ok=True)
    (proj / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: sequential\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n", encoding="utf-8")
    (proj / "Cargo.toml").write_text("[package]\nname='p'\nversion='0'\n",
                                     encoding="utf-8")
    (proj / "_bmad-run" / "story.md").write_text("# Rust async story\n",
                                                 encoding="utf-8")
    (proj / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF, encoding="utf-8")
    for c in (
        ["git", "init", "-q"], ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        assert _run(c, cwd=proj).returncode == 0
    head = _run(["git", "-C", str(proj), "rev-parse", "HEAD"], cwd=proj).stdout.strip()
    wrap = proj / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"
    skill = proj / ".claude" / "skills" / "bmad-testarch-test-design"
    r1 = _run([VENV_PY, wrap, "prepare-run", "--workflow", WORKFLOW,
               "--project-root", proj, "--run-id", RUN_ID, "--skill-dir", skill,
               "--base-sha", head, "--head-sha", head,
               "--allow-fixture-diff", proj / "_bmad-run" / "diff.patch"],
              cwd=proj, env=_env())
    assert r1.returncode == 0, r1.stderr
    r2 = _run([VENV_PY, wrap, "finalize-run", "--workflow", WORKFLOW,
               "--project-root", proj, "--run-id", RUN_ID,
               "--test-write-fake-artefact"], cwd=proj, env=_env())
    assert r2.returncode == 0, r2.stderr
    return proj


@pytest.fixture
def work(built_run, tmp_path) -> Path:
    dst = tmp_path / "work"
    shutil.copytree(built_run, dst, symlinks=True)
    return dst


def _paths(work: Path) -> dict:
    run_dir = work / "_bmad" / "rdx-tea" / "runtime" / WORKFLOW / RUN_ID
    # The canonical output root collapses `_bmad-output/test-artifacts` into
    # its parent `_bmad-output`, so the fake artefact lands directly there.
    art = work / "_bmad-output" / ARTEFACT_NAME
    return {
        "run_dir": run_dir,
        "sidecar": art.parent / (art.name + ".rdx-tea.json"),
        "artifact": art,
        "manifest": run_dir / "run-manifest.json",
        "bundle": run_dir / "active-context.md",
        "diff": run_dir / "diff.patch",
        "canonical_kb": (work / "_bmad" / "rdx-tea" / "canonical"
                         / "kb-sections" / "section-4-core.md"),
        "sources_lock": work / "_bmad" / "rdx-tea" / "bootstrap" / "sources.lock",
    }


def _verify(work: Path, p: dict) -> dict:
    # Pass --artifact explicitly: the sidecar records an absolute artifact_path
    # pinned to the template dir, which is outside this per-test copy.
    validator = work / "_bmad" / "rdx-tea" / "scripts" / "rdx_tea_validator.py"
    r = _run([VENV_PY, validator, "--sidecar", p["sidecar"],
              "--project-root", work, "--workflow", WORKFLOW, "--run-id", RUN_ID,
              "--artifact", p["artifact"], "--source-lock", p["sources_lock"]],
             cwd=work, env=_env())
    return json.loads(r.stdout)


def _status(result: dict, check: str) -> str:
    for c in result["checks"]:
        if c["check"] == check:
            return c["status"]
    raise AssertionError(f"check {check} not present in {result}")


def test_w6_verifier_baseline_all_checks_pass(work: Path) -> None:
    p = _paths(work)
    result = _verify(work, p)
    assert result["verdict"] == "PASS", result
    for check in ALL_CHECKS:
        assert _status(result, check) == "PASS", (check, result)


def _apply_mutation(check: str, p: dict) -> None:
    if check == "schema":
        sc = json.loads(p["sidecar"].read_text())
        sc["__tamper__"] = True  # additionalProperties:false → schema FAIL
        p["sidecar"].write_text(json.dumps(sc, sort_keys=True))
    elif check == "manifest_hash":
        m = json.loads(p["manifest"].read_text())
        m["__tamper__"] = 1  # changes manifest bytes, keeps valid JSON+snapshot
        p["manifest"].write_text(json.dumps(m, sort_keys=True))
    elif check == "bundle_hash":
        p["bundle"].write_text(p["bundle"].read_text() + "\n<tamper>\n")
    elif check == "artifact_hash":
        p["artifact"].write_text(p["artifact"].read_text() + "\n<tamper>\n")
    elif check == "base_head_exist":
        sc = json.loads(p["sidecar"].read_text())
        sc["base_sha"] = "0" * 40  # valid hex, nonexistent commit
        p["sidecar"].write_text(json.dumps(sc, sort_keys=True))
    elif check == "diff_digest_recomputed":
        p["diff"].write_text(p["diff"].read_text() + "\n<tamper>\n")
    elif check == "canonical_snapshot":
        p["canonical_kb"].write_text(
            p["canonical_kb"].read_text() + "\n<!-- tamper -->\n")
    elif check == "source_lock":
        lock = yaml.safe_load(p["sources_lock"].read_text())
        lock["rdx_source_sha"] = "0" * 40
        p["sources_lock"].write_text(yaml.safe_dump(lock))
    elif check == "artifact_boundary":
        # Symlink whose target has IDENTICAL bytes, so artifact_hash still
        # PASSES and only the boundary check flips.
        original = p["artifact"].read_bytes()
        target = p["artifact"].parent / "boundary_target.md"
        target.write_bytes(original)
        p["artifact"].unlink()
        p["artifact"].symlink_to(target)
    else:
        raise AssertionError(f"unknown check {check}")


@pytest.mark.parametrize("check", ALL_CHECKS)
def test_w6_verifier_check_fails_closed_on_mutation(work: Path, check: str) -> None:
    """Mutating each hashed input flips EXACTLY that check to FAIL and the
    aggregate verdict to FAIL — no check can be bypassed."""
    p = _paths(work)
    _apply_mutation(check, p)
    result = _verify(work, p)
    assert _status(result, check) == "FAIL", (check, result)
    assert result["verdict"] == "FAIL", (check, result)
    assert check in result["failed_checks"], (check, result)
    # Isolation: the mutation flips ONLY the targeted check.
    for other in ALL_CHECKS:
        if other == check:
            continue
        assert _status(result, other) == "PASS", (
            f"mutation of {check} unexpectedly flipped {other}", result)
