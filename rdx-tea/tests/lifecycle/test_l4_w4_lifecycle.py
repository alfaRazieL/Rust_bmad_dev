"""L4 W4 — wrapper Skills & non-interactive lifecycle (productionization).

Self-contained lifecycle tests for the two-phase wrapper. Unlike the
`bmad-tea/` slice tests these do NOT require an upstream TEA clone — the
wrapper's `prepare-run`/`finalize-run` only need the shipped install-tree
(`_bmad/rdx-tea/**`) plus a real git repo. `--skill-dir` is accepted but
not dereferenced, so a placeholder path is fine.

W4 focus (WAVE_4_PROMPT / ACCEPTANCE_GATES G-W4-NOTASK, G-W4-SEQUENTIAL):

  * invocation-contract handshake (run_id verbatim; candidate-only;
    `_bmad-run/rdx-tea-invocation.json`);
  * `tea_execution_mode == "sequential"` fail-closed on both phases;
  * empty-delta fail-closed (no new artefact -> error);
  * production paths never accept `--simulate-child`, and
    `--test-write-fake-artefact` / `--allow-fixture-diff` stay env-gated
    (RDX_TEA_ALLOW_TEST_ARTEFACT / RDX_TEA_ALLOW_FIXTURE_DIFF — tests only);
  * NO Task/subagent dispatch — the wrapper is pure Python orchestration
    and the child skill is documented as invoked with
    `--disallowedTools Task TaskOutput TaskStop`;
  * overlay backup/restore + active-run lock acquire/release;
  * W3 compatibility: `prepared_at == ""` by default (no wall-clock in the
    hashed run-manifest); wrapper accepts it; honest wall-clock audit stamps
    live only in the (non-hashed) run-report `created_at` and sidecar
    `bound_at`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
INSTALL_TREE = RDX_TEA_DIR / "poc" / "install-tree"
VENV_PY = Path(sys.executable)
WRAPPER_REL = Path("_bmad") / "rdx-tea" / "scripts" / "rdx_tea_wrapper.py"

ASYNC_DIFF = """diff --git a/src/lib.rs b/src/lib.rs
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,4 @@
+pub async fn f() {
+    let h = tokio::spawn(async {});
+    h.await.unwrap();
+}
"""


def _run(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          env=env, check=False)


def _base_env(**gates: str) -> dict:
    """Fresh env with a clean slate for the deterministic-manifest guard.

    `RDX_TEA_FAKE_NOW` is popped so `prepared_at` defaults to "" and the
    honest wall-clock `created_at`/`bound_at` audit stamps are exercised.
    Only the requested env gates are set, so negative env-gating tests can
    withhold a specific gate.
    """
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("RDX_TEA_FAKE_NOW", None)
    for k in ("RDX_TEA_ALLOW_FIXTURE_DIFF", "RDX_TEA_ALLOW_TEST_ARTEFACT"):
        env.pop(k, None)
    env.update(gates)
    return env


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Fresh rust-flavoured git project carrying only the shipped tree."""
    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copytree(INSTALL_TREE / "_bmad", proj / "_bmad")
    (proj / "_bmad-run").mkdir()
    (proj / "_bmad-output" / "test-artifacts").mkdir(parents=True)
    # Placeholder child-skill dir (wrapper accepts --skill-dir but does not
    # dereference it, so no upstream clone is required).
    (proj / ".claude" / "skills" / "bmad-testarch-test-design").mkdir(parents=True)
    (proj / "_bmad" / "tea").mkdir(exist_ok=True)
    (proj / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: sequential\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n"
        "project_name: w4\n",
        encoding="utf-8",
    )
    (proj / "Cargo.toml").write_text("[package]\nname='p'\nversion='0'\n",
                                     encoding="utf-8")
    (proj / "_bmad-run" / "story.md").write_text("# story\n", encoding="utf-8")
    (proj / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF, encoding="utf-8")
    for c in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        r = _run(c, cwd=proj)
        assert r.returncode == 0, r.stderr
    return proj


def _head(project: Path) -> str:
    return _run(["git", "-C", str(project), "rev-parse", "HEAD"], cwd=project).stdout.strip()


def _prepare(project: Path, run_id: str, *, env: dict | None = None,
             extra: list[str] | None = None,
             use_fixture: bool = True) -> subprocess.CompletedProcess:
    env = env if env is not None else _base_env(RDX_TEA_ALLOW_FIXTURE_DIFF="1")
    head = _head(project)
    cmd = [str(VENV_PY), str(project / WRAPPER_REL), "prepare-run",
           "--workflow", "test-design",
           "--project-root", str(project),
           "--run-id", run_id,
           "--skill-dir", str(project / ".claude" / "skills" / "bmad-testarch-test-design"),
           "--base-sha", head, "--head-sha", head]
    if use_fixture:
        cmd += ["--allow-fixture-diff", str(project / "_bmad-run" / "diff.patch")]
    if extra:
        cmd += extra
    return _run(cmd, cwd=project, env=env)


def _finalize(project: Path, run_id: str, *, env: dict | None = None,
              fake_artefact: bool = True,
              extra: list[str] | None = None) -> subprocess.CompletedProcess:
    env = env if env is not None else _base_env(RDX_TEA_ALLOW_TEST_ARTEFACT="1")
    cmd = [str(VENV_PY), str(project / WRAPPER_REL), "finalize-run",
           "--workflow", "test-design",
           "--project-root", str(project),
           "--run-id", run_id]
    if fake_artefact:
        cmd += ["--test-write-fake-artefact"]
    if extra:
        cmd += extra
    return _run(cmd, cwd=project, env=env)


# ================================================ 1. invocation contract


def _write_contract(project: Path, **fields: str) -> None:
    (project / "_bmad-run" / "rdx-tea-invocation.json").write_text(
        json.dumps(fields, sort_keys=True), encoding="utf-8")


def test_l4_w4_invocation_contract_run_id_used_verbatim(project: Path) -> None:
    """When the harness pins a run_id in the invocation contract, the
    wrapper proceeds only when --run-id matches it verbatim."""
    _write_contract(project, run_id="ic-verbatim-01", workflow="test-design",
                    arm="candidate")
    r = _prepare(project, "ic-verbatim-01")
    assert r.returncode == 0, r.stderr
    manifest = json.loads(
        (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
         / "ic-verbatim-01" / "run-manifest.json").read_text())
    assert manifest["run_id"] == "ic-verbatim-01"


def test_l4_w4_invocation_contract_run_id_mismatch_fails_closed(project: Path) -> None:
    _write_contract(project, run_id="ic-pinned", workflow="test-design",
                    arm="candidate")
    r = _prepare(project, "ic-different")
    assert r.returncode != 0
    assert "run_id" in (r.stderr + r.stdout).lower()


def test_l4_w4_invocation_contract_non_candidate_arm_refused(project: Path) -> None:
    """Wrapper is candidate-only; a baseline (or any non-candidate) arm
    must be refused."""
    _write_contract(project, run_id="ic-arm-01", workflow="test-design",
                    arm="baseline")
    r = _prepare(project, "ic-arm-01")
    assert r.returncode != 0
    assert "candidate" in (r.stderr + r.stdout).lower()


def test_l4_w4_invocation_contract_workflow_mismatch_fails_closed(project: Path) -> None:
    _write_contract(project, run_id="ic-wf-01", workflow="atdd",
                    arm="candidate")
    r = _prepare(project, "ic-wf-01")
    assert r.returncode != 0
    assert "workflow" in (r.stderr + r.stdout).lower()


def test_l4_w4_invocation_contract_absent_falls_back_to_cli_run_id(project: Path) -> None:
    """No contract file present — the wrapper falls back to the --run-id
    argument and still runs."""
    assert not (project / "_bmad-run" / "rdx-tea-invocation.json").exists()
    r = _prepare(project, "ic-absent-01")
    assert r.returncode == 0, r.stderr
    assert (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
            / "ic-absent-01" / "run-manifest.json").exists()


# ================================================ 2. sequential fail-closed


@pytest.mark.parametrize("mode", ["auto", "subagent", "agent-team", "parallel"])
def test_l4_w4_prepare_rejects_non_sequential_mode(project: Path, mode: str) -> None:
    """Every mode that resolves to something other than `sequential` fails
    closed: `auto`, `subagent`, `agent-team`, `parallel`. (Case/whitespace
    variants of `sequential` normalise to sequential and stay admitted.)"""
    (project / "_bmad" / "tea" / "config.yaml").write_text(
        f"tea_execution_mode: '{mode}'\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n",
        encoding="utf-8",
    )
    r = _prepare(project, "seq-neg-01")
    assert r.returncode != 0
    assert "sequential" in (r.stderr + r.stdout).lower()


def test_l4_w4_finalize_rejects_non_sequential_mode(project: Path) -> None:
    """Even if prepare ran under sequential, a config flipped to a
    non-sequential mode before finalize fails closed."""
    r = _prepare(project, "seq-fin-01")
    assert r.returncode == 0, r.stderr
    (project / "_bmad" / "tea" / "config.yaml").write_text(
        "tea_execution_mode: subagent\n"
        "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
        "output_folder: '{project-root}/_bmad-output'\n",
        encoding="utf-8",
    )
    r2 = _finalize(project, "seq-fin-01")
    assert r2.returncode != 0
    assert "sequential" in (r2.stderr + r2.stdout).lower()


# ================================================ 3. empty-delta fail-closed


def test_l4_w4_empty_delta_fails_closed(project: Path) -> None:
    """If the child skill wrote nothing, finalize must fail closed —
    never report a successful run with no artefact."""
    r = _prepare(project, "empty-01")
    assert r.returncode == 0, r.stderr
    # finalize WITHOUT the fake-artefact path and no child output at all.
    r2 = _finalize(project, "empty-01", fake_artefact=False)
    assert r2.returncode != 0
    assert "no new artefact" in (r2.stderr + r2.stdout).lower()


# ============================== 4. test-only flags stay env-gated / no sim


def test_l4_w4_simulate_child_flag_does_not_exist(project: Path) -> None:
    """`--simulate-child` was removed in D3.2 — argparse must reject it on
    both phases so no production path can ever simulate the child."""
    r_prep = _prepare(project, "sim-01", extra=["--simulate-child"])
    assert r_prep.returncode != 0
    assert "unrecognized arguments" in (r_prep.stderr + r_prep.stdout).lower() \
        or "simulate-child" in (r_prep.stderr + r_prep.stdout).lower()
    # And on finalize.
    r_prep2 = _prepare(project, "sim-02")
    assert r_prep2.returncode == 0, r_prep2.stderr
    r_fin = _finalize(project, "sim-02", fake_artefact=False,
                      extra=["--simulate-child"])
    assert r_fin.returncode != 0
    assert "unrecognized arguments" in (r_fin.stderr + r_fin.stdout).lower() \
        or "simulate-child" in (r_fin.stderr + r_fin.stdout).lower()


def test_l4_w4_test_write_fake_artefact_requires_env_gate(project: Path) -> None:
    """`--test-write-fake-artefact` is refused unless
    RDX_TEA_ALLOW_TEST_ARTEFACT=1 — production never sets it."""
    r = _prepare(project, "gate-art-01")
    assert r.returncode == 0, r.stderr
    # env WITHOUT the gate.
    r2 = _finalize(project, "gate-art-01", env=_base_env(), fake_artefact=True)
    assert r2.returncode != 0
    assert "RDX_TEA_ALLOW_TEST_ARTEFACT" in (r2.stderr + r2.stdout)


def test_l4_w4_allow_fixture_diff_requires_env_gate(project: Path) -> None:
    """`--allow-fixture-diff` is refused unless RDX_TEA_ALLOW_FIXTURE_DIFF=1."""
    # env WITHOUT the fixture gate.
    r = _prepare(project, "gate-diff-01", env=_base_env(), use_fixture=True)
    assert r.returncode != 0
    assert "RDX_TEA_ALLOW_FIXTURE_DIFF" in (r.stderr + r.stdout)


# ================================================ 5. no Task / subagent dispatch


def test_l4_w4_no_task_dispatch_observed_in_run(project: Path) -> None:
    """A full deterministic run never observes a Task/subagent dispatch —
    observed_mode is the sequential/absent surrogate, never
    OBSERVED_SUBAGENT (Task dispatch count == 0)."""
    r = _prepare(project, "notask-01")
    assert r.returncode == 0, r.stderr
    r2 = _finalize(project, "notask-01")
    assert r2.returncode == 0, r2.stderr
    report = json.loads(r2.stdout)
    assert report["observed_mode"] != "OBSERVED_SUBAGENT"
    assert report["observed_mode"] in ("INFERRED_ABSENT", "OBSERVED_SEQUENTIAL")
    assert report["execution_mode"] == "sequential"


def test_l4_w4_wrapper_source_never_dispatches_subagents(project: Path) -> None:
    """The shipped wrapper is pure Python orchestration: it never spawns a
    Claude subagent / Task worker. The only mentions of Task/subagent in
    the wrapper are lower-cased *detection* tokens in the observed-mode
    transcript scanner — never a dispatch call."""
    src = (project / WRAPPER_REL).read_text(encoding="utf-8")
    # No agent/Task dispatch API is referenced by the runtime wrapper.
    for banned in ("TaskCreate", "TaskOutput(", "TaskStop(",
                   "agent_dispatch(", "spawn_subagent", "dispatch_subagent"):
        assert banned not in src, f"wrapper appears to dispatch a worker: {banned}"


def test_l4_w4_skills_document_disallowed_tools_and_no_prod_test_flags() -> None:
    """Both wrapper Skills must (a) document invoking the child with
    `--disallowedTools Task TaskOutput TaskStop`, and (b) never present the
    test-only flags as production run steps (G-W4-NOTASK SKILL.md grep)."""
    for slug in ("rdx-tea-test-design", "rdx-tea-atdd"):
        p = INSTALL_TREE / ".claude" / "skills" / slug / "SKILL.md"
        text = p.read_text(encoding="utf-8")
        assert "--disallowedTools Task TaskOutput TaskStop" in text, (
            f"{slug} SKILL.md must document Task/subagent-disabled child invoke")
        # The production guard sentence must be present.
        assert "in a production session" in text
        # No command line (starts with `python`) may carry a test-only flag.
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("python"):
                assert "--simulate-child" not in stripped, f"{slug}: prod cmd uses --simulate-child"
                assert "--test-write-fake-artefact" not in stripped, (
                    f"{slug}: prod cmd uses --test-write-fake-artefact")
                assert "--allow-fixture-diff" not in stripped, (
                    f"{slug}: prod cmd uses --allow-fixture-diff")


# ================================================ 6. overlay + lock lifecycle


def test_l4_w4_overlay_backup_and_restore(project: Path) -> None:
    overlay = project / "_bmad" / "custom" / "bmad-testarch-test-design.toml"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text("[workflow]\npersistent_facts = [\"file:PRE-EXISTING\"]\n",
                       encoding="utf-8")
    r = _prepare(project, "ovl-w4-01")
    assert r.returncode == 0, r.stderr
    # Overlay replaced by the run-scoped one; original backed up.
    assert "ovl-w4-01" in overlay.read_text()
    backup = (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
              / "ovl-w4-01" / "overlay-backup.toml")
    assert backup.exists() and "PRE-EXISTING" in backup.read_text()
    r2 = _finalize(project, "ovl-w4-01")
    assert r2.returncode == 0, r2.stderr
    # Restored verbatim.
    assert "PRE-EXISTING" in overlay.read_text()


def test_l4_w4_overlay_removed_when_none_preexisting(project: Path) -> None:
    overlay = project / "_bmad" / "custom" / "bmad-testarch-test-design.toml"
    assert not overlay.exists()
    r = _prepare(project, "ovl-w4-02")
    assert r.returncode == 0, r.stderr
    assert overlay.exists() and "ovl-w4-02" in overlay.read_text()
    r2 = _finalize(project, "ovl-w4-02")
    assert r2.returncode == 0, r2.stderr
    # No pre-existing overlay -> the rdx-tea-owned one is removed on finalize.
    assert not overlay.exists()


def test_l4_w4_active_run_lock_acquire_refuse_release(project: Path) -> None:
    lock = project / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"
    r1 = _prepare(project, "lock-w4-01")
    assert r1.returncode == 0, r1.stderr
    assert lock.exists(), "prepare must acquire the active-run lock"
    data = json.loads(lock.read_text())
    assert data["run_id"] == "lock-w4-01" and data["workflow"] == "test-design"
    # Second concurrent run refused (structured JSON, no substring semantics).
    r2 = _prepare(project, "lock-w4-02")
    assert r2.returncode != 0
    assert "active" in (r2.stderr + r2.stdout).lower()
    # Finalize releases the lock.
    r3 = _finalize(project, "lock-w4-01")
    assert r3.returncode == 0, r3.stderr
    assert not lock.exists(), "finalize must release the active-run lock"
    # A fresh run is now admitted.
    r4 = _prepare(project, "lock-w4-03")
    assert r4.returncode == 0, r4.stderr


# ================================================ 7. prepared_at / audit stamps


def test_l4_w4_prepared_at_empty_by_default_no_wallclock_in_manifest(project: Path) -> None:
    """W3 invariant: the hashed run-manifest carries no wall-clock —
    `prepared_at` is "" by default (no RDX_TEA_FAKE_NOW injected)."""
    r = _prepare(project, "pa-01")  # _base_env pops RDX_TEA_FAKE_NOW
    assert r.returncode == 0, r.stderr
    manifest_path = (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
                     / "pa-01" / "run-manifest.json")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["prepared_at"] == "", manifest["prepared_at"]
    # No wall-clock audit keys leaked into the hashed manifest.
    for banned in ("created_at", "bound_at", "finalized_at"):
        assert banned not in manifest, f"manifest leaked audit stamp {banned}"


def test_l4_w4_wrapper_accepts_empty_prepared_at_through_finalize(project: Path) -> None:
    """The full lifecycle succeeds with prepared_at == "" — the wrapper and
    binder remain compatible with the default empty stamp."""
    r = _prepare(project, "pa-02")
    assert r.returncode == 0, r.stderr
    r2 = _finalize(project, "pa-02")
    assert r2.returncode == 0, r2.stderr
    # Sidecar carries prepared_at == "" (schema-valid empty string).
    report = json.loads(r2.stdout)
    assert report["sidecars"], "no sidecar produced"
    assert report["sidecars"][0]["prepared_at"] == ""


def test_l4_w4_run_report_created_at_is_audit_stamp_outside_hashed_manifest(project: Path) -> None:
    """Honest wall-clock audit stamp lives in the (non-hashed) run-report
    `created_at`, never in the hashed run-manifest."""
    r = _prepare(project, "ca-01")
    assert r.returncode == 0, r.stderr
    r2 = _finalize(project, "ca-01")
    assert r2.returncode == 0, r2.stderr
    report = json.loads(r2.stdout)
    assert report.get("created_at"), "run-report must carry a created_at audit stamp"
    assert "T" in report["created_at"], "created_at should be an ISO timestamp"
    manifest = json.loads(
        (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
         / "ca-01" / "run-manifest.json").read_text())
    assert "created_at" not in manifest


def test_l4_w4_sidecar_bound_at_is_audit_stamp_outside_hashed_manifest(project: Path) -> None:
    r = _prepare(project, "ba-01")
    assert r.returncode == 0, r.stderr
    r2 = _finalize(project, "ba-01")
    assert r2.returncode == 0, r2.stderr
    report = json.loads(r2.stdout)
    sc = report["sidecars"][0]
    assert sc.get("bound_at"), "sidecar must carry a bound_at audit stamp"
    manifest = json.loads(
        (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
         / "ba-01" / "run-manifest.json").read_text())
    assert "bound_at" not in manifest
