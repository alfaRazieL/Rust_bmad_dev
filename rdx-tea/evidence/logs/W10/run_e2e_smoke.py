#!/usr/bin/env python3
"""W10 bounded non-interactive E2E smoke driver (evidence plane).

Performs the single bounded non-interactive smoke required by G-W10-E2E:

  1. clean install of the shipped surface into a fresh disposable project
     (via ``installer/project_installer.py`` -- exactly what an operator
     receives), then
  2. drives the INSTALLED wrapper through prepare-run -> (env-gated
     deterministic fake child) -> finalize-run, then
  3. recomputes admissibility with the INSTALLED admission CLI.

The "child" is the env-gated deterministic fake-artefact path
(``RDX_TEA_ALLOW_TEST_ARTEFACT=1``): NO live Claude model call, NO
subagent/Task dispatch. A live-model child run is a SEPARATELY
owner-authorized rung (§6.9 rung 6) and is deliberately NOT performed here
(LIVE_SMOKE_STATUS = NOT_RUN_OWNER_AUTH_REQUIRED).

Writes an honest evidence record to ``rdx-tea/evidence/live/W10_E2E_SMOKE.json``.
Uses a throwaway temp dir; nothing outside the evidence dir is mutated.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
RDX_TEA_DIR = REPO_ROOT / "rdx-tea"
INSTALLER_PY = RDX_TEA_DIR / "installer" / "project_installer.py"
LIVE_DIR = RDX_TEA_DIR / "evidence" / "live"
PY = sys.executable
WORKFLOW = "test-design"

ASYNC_DIFF = """diff --git a/src/lib.rs b/src/lib.rs
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -0,0 +1,4 @@
+pub async fn f() {
+    let h = tokio::spawn(async {});
+    h.await.unwrap();
+}
"""


def _load_installer():
    spec = importlib.util.spec_from_file_location("w10_smoke_installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _env() -> dict:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("RDX_TEA_FAKE_NOW", None)
    env["RDX_TEA_ALLOW_FIXTURE_DIFF"] = "1"
    env["RDX_TEA_ALLOW_TEST_ARTEFACT"] = "1"
    return env


def _run(cmd, cwd, env=None):
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd),
                          capture_output=True, text=True, env=env, check=False)


def main() -> int:
    pi = _load_installer()
    steps = []
    with tempfile.TemporaryDirectory(prefix="rdx-tea-w10-smoke-") as td:
        project = Path(td) / "disposable-project"

        # 1) clean install
        install_result = pi.install(project)
        installed_scripts = sorted(
            p.name for p in (project / "_bmad/rdx-tea/scripts").glob("*.py"))
        steps.append({
            "step": "clean_install",
            "mode": install_result["mode"],
            "adapter_version": install_result["adapter_version"],
            "file_count": install_result["file_count"],
            "installed_scripts": installed_scripts,
            "settings_json_present": (project / ".claude/settings.json").is_file(),
        })

        # user-owned run inputs (never installer-owned)
        (project / "_bmad-run").mkdir(parents=True, exist_ok=True)
        (project / "_bmad-output" / "test-artifacts").mkdir(parents=True, exist_ok=True)
        (project / ".claude" / "skills" / "bmad-testarch-test-design").mkdir(
            parents=True, exist_ok=True)
        (project / "_bmad" / "tea").mkdir(parents=True, exist_ok=True)
        (project / "_bmad" / "tea" / "config.yaml").write_text(
            "tea_execution_mode: sequential\n"
            "test_artifacts: '{project-root}/_bmad-output/test-artifacts'\n"
            "output_folder: '{project-root}/_bmad-output'\n"
            "project_name: w10-smoke\n", encoding="utf-8")
        (project / "Cargo.toml").write_text(
            "[package]\nname='p'\nversion='0'\n", encoding="utf-8")
        (project / "_bmad-run" / "story.md").write_text(
            "# Rust async story\n", encoding="utf-8")
        (project / "_bmad-run" / "diff.patch").write_text(ASYNC_DIFF, encoding="utf-8")
        for c in (["git", "init", "-q"], ["git", "add", "-A"],
                  ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                   "commit", "-q", "-m", "init"]):
            assert _run(c, cwd=project).returncode == 0
        head = _run(["git", "-C", str(project), "rev-parse", "HEAD"],
                    cwd=project).stdout.strip()

        wrapper = project / "_bmad/rdx-tea/scripts/rdx_tea_wrapper.py"
        admission = project / "_bmad/rdx-tea/scripts/admission.py"
        run_id = "w10-e2e-smoke"
        run_dir = project / "_bmad/rdx-tea/runtime" / WORKFLOW / run_id

        # 2) prepare
        prep = _run([PY, wrapper, "prepare-run", "--workflow", WORKFLOW,
                     "--project-root", project, "--run-id", run_id,
                     "--skill-dir", project / ".claude/skills/bmad-testarch-test-design",
                     "--base-sha", head, "--head-sha", head,
                     "--allow-fixture-diff", project / "_bmad-run/diff.patch"],
                    cwd=project, env=_env())
        steps.append({"step": "prepare_run",
                      "command": "python _bmad/rdx-tea/scripts/rdx_tea_wrapper.py "
                                 "prepare-run --workflow test-design ...",
                      "exit_code": prep.returncode})
        if prep.returncode != 0:
            return _fail("prepare-run failed", steps, prep)

        # child = env-gated deterministic fake artefact (NO live model)
        fin = _run([PY, wrapper, "finalize-run", "--workflow", WORKFLOW,
                    "--project-root", project, "--run-id", run_id,
                    "--test-write-fake-artefact"], cwd=project, env=_env())
        report = json.loads(fin.stdout) if fin.stdout.strip().startswith("{") else {}
        steps.append({
            "step": "finalize_run",
            "command": "python _bmad/rdx-tea/scripts/rdx_tea_wrapper.py "
                       "finalize-run --workflow test-design ... "
                       "--test-write-fake-artefact",
            "exit_code": fin.returncode,
            "workflow": report.get("workflow"),
            "execution_mode": report.get("execution_mode"),
            "observed_mode": report.get("observed_mode"),
            "sidecar_count": len(report.get("sidecars", [])),
            "verifier_all_pass": bool(report.get("verifier")) and all(
                v["verdict"] == "PASS" for v in report.get("verifier", [])),
            "recorded_admission": report.get("admission"),
        })
        if fin.returncode != 0:
            return _fail("finalize-run failed", steps, fin)

        # 3) INSTALLED admission CLI recompute from primitives
        adm = _run([PY, admission, "admit",
                    "--report", run_dir / "run-report.json",
                    "--state", run_dir / "run-state.json"],
                   cwd=project, env=_env())
        adm_out = json.loads(adm.stdout) if adm.stdout.strip().startswith("{") else {}
        steps.append({
            "step": "admission_recompute",
            "command": "python _bmad/rdx-tea/scripts/admission.py admit "
                       "--report <run-report.json> --state <run-state.json>",
            "exit_code": adm.returncode,
            "admissible": adm_out.get("admissible"),
            "run_outcome": adm_out.get("run_outcome"),
        })

        admissible = adm.returncode == 0 and adm_out.get("admissible") is True

    record = {
        "schema": "rdx-tea-w10-e2e-smoke.v1",
        "stage": "W10 bounded non-interactive E2E smoke (G-W10-E2E)",
        "install_source": "installer/project_installer.py -> clean disposable project",
        "child_kind": "env-gated deterministic fake artefact "
                      "(RDX_TEA_ALLOW_TEST_ARTEFACT=1); NO live model; "
                      "NO subagent/Task dispatch",
        "live_model_call": False,
        "live_smoke_status": "NOT_RUN_OWNER_AUTH_REQUIRED",
        "auth": {
            "api_key_used": False,
            "claude_code_oauth_token_used": False,
            "setup_token_used": False,
            "api_key_helper_used": False,
            "claude_config_dir_overridden": False,
        },
        "steps": steps,
        "smoke_admissible": admissible,
        "verdict": "E2E_SMOKE_ADMISSIBLE" if admissible else "E2E_SMOKE_FAILED",
    }
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    (LIVE_DIR / "W10_E2E_SMOKE.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"smoke_admissible": admissible,
                      "verdict": record["verdict"]}, indent=2))
    return 0 if admissible else 1


def _fail(msg, steps, proc):
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    (LIVE_DIR / "W10_E2E_SMOKE.json").write_text(json.dumps({
        "schema": "rdx-tea-w10-e2e-smoke.v1",
        "verdict": "E2E_SMOKE_FAILED",
        "error": msg,
        "steps": steps,
        "stderr_tail": proc.stderr[-2000:],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SMOKE FAILED: {msg}\n{proc.stderr[-1000:]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
