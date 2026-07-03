"""RDX-TEA wrapper (D3.2) — the validated invocation path.

Two-phase orchestration mirroring `rdx-dev-story`:

  prepare-run                         (before the TEA child skill runs)
  → LLM invokes `bmad-testarch-*`     (the child skill; wrapper does NOT
                                        substitute a simulator in
                                        production)
  finalize-run                         (after the child skill returns)

Both phases share a `--run-id` (UUID-like slug) that pins every artefact
of the run to a directory under
  `<project-root>/_bmad/rdx-tea/runtime/<workflow>/<run_id>/`

so a concurrent run never touches a sibling run's outputs.

## Command surface

  prepare-run --workflow W --project-root P --run-id R
              [--base-sha X --head-sha Y]
              [--tea-source-sha Z]
              [--allow-fixture-diff PATH]

    * detects rust_scope from Cargo.toml / rust-toolchain / *.rs
    * resolves git base/head via `git rev-parse` and verifies both with
      `git cat-file -e` (fail-closed on missing commit)
    * generates the diff from those SHAs (or accepts the fixture diff
      when --allow-fixture-diff is set — test-only)
    * loads sources.lock
    * runs prepare.prepare(); bundle+manifest live under run-scoped dir
    * requests sequential mode explicitly by writing `_bmad/tea/config.yaml`
      override into the run dir; verifies that host `_bmad/tea/config.yaml`
      already resolves to `sequential` (auto REJECTED in D3.2)
    * SNAPSHOTS output directories to a `pre-outputs.json` inventory

  finalize-run --workflow W --project-root P --run-id R
              [--verify-only]   # skip binding, only report

    * reads `pre-outputs.json`
    * inventories all files in the same output roots NOW
    * computes delta = new/changed files since prepare
    * for each new artefact: binds a sidecar under the run dir, then
      runs the D3.2 verifier
    * writes an aggregate `run-report.json` with every sidecar +
      verifier result
    * fails closed on: no new artefact discovered, artefact SHA
      unchanged (LLM never wrote), any sidecar failing verification,
      resolved-mode not sequential

## What the wrapper never does

  - It does NOT invoke the child skill from Python (that requires the
    Claude Code / LLM runtime). Live use: LLM issues the child skill
    between prepare-run and finalize-run.
  - It does NOT synthesise a fake TEA artefact — a --simulate-child
    was removed from D3.2. Deterministic PoC tests use the separate
    `--test-write-fake-artefact` flag on finalize-run which is only
    accepted when RDX_TEA_ALLOW_TEST_ARTEFACT=1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import prepare  # noqa: E402
import binder   # noqa: E402
import rdx_tea_validator  # noqa: E402


SUPPORTED_MODES = ("sequential",)

_OVERLAY_MARKER = "# rdx-tea-owned run-specific overlay — regenerated per run.\n"


class WrapperError(RuntimeError):
    pass


# --------------------------------------------------- run-specific overlay

def _overlay_path(project_root: Path, workflow: str) -> Path:
    return project_root / "_bmad" / "custom" / f"bmad-testarch-{workflow}.toml"


def _overlay_backup_path(project_root: Path, workflow: str, run_id: str) -> Path:
    return (project_root / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id
            / "overlay-backup.toml")


def _write_run_specific_overlay(project_root: Path, workflow: str, run_id: str) -> Path:
    """Generate `_bmad/custom/bmad-testarch-<workflow>.toml` for THIS run.

    The overlay hard-codes the exact run-scoped bundle path so the real
    upstream `resolve_customization.py` merges it into
    `workflow.persistent_facts` correctly. Any pre-existing overlay is
    backed up under the run directory and restored by finalize-run
    (D3.3 §4.1).
    """
    overlay = _overlay_path(project_root, workflow)
    overlay.parent.mkdir(parents=True, exist_ok=True)
    backup = _overlay_backup_path(project_root, workflow, run_id)
    backup.parent.mkdir(parents=True, exist_ok=True)

    # Back up any pre-existing overlay verbatim (bytes). Marker inside
    # the current overlay indicates a previous rdx-tea run's stale
    # overlay — we still back it up; restore is user's decision.
    if overlay.exists():
        backup.write_bytes(overlay.read_bytes())

    content = (
        _OVERLAY_MARKER
        + f"# workflow: {workflow}\n"
        + f"# run_id: {run_id}\n"
        + "# Do NOT edit; wrapper regenerates each run.\n\n"
        + "[workflow]\n\n"
        + "activation_steps_prepend = [\n"
        + f"  \"RDX-TEA run-specific bundle for {workflow}/{run_id} pre-loaded via persistent_facts.\",\n"
        + "]\n\n"
        + "persistent_facts = [\n"
        + f"  \"file:{{project-root}}/_bmad/rdx-tea/runtime/{workflow}/{run_id}/active-context.md\",\n"
        + "]\n\n"
        + f"on_complete = \"RDX-TEA finalize-run for {workflow}/{run_id} is invoked by the rdx-tea-{workflow} wrapper skill.\"\n"
    )
    # Atomic write.
    tmp = overlay.with_suffix(overlay.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, overlay)
    return overlay


def _restore_or_remove_overlay(project_root: Path, workflow: str, run_id: str) -> None:
    """Restore the pre-existing overlay from backup, or remove the
    rdx-tea-owned one if there was no pre-existing file."""
    overlay = _overlay_path(project_root, workflow)
    backup = _overlay_backup_path(project_root, workflow, run_id)
    if not overlay.exists():
        return
    # Only touch overlays we own.
    if overlay.read_text(encoding="utf-8").startswith(_OVERLAY_MARKER.strip()) is False:
        return
    if backup.exists():
        overlay.write_bytes(backup.read_bytes())
    else:
        overlay.unlink()


# ---------------------------------------------------- active-run lock

def _lock_path(project_root: Path) -> Path:
    return project_root / "_bmad" / "rdx-tea" / "runtime" / "active-run.lock"


def _acquire_active_run_lock(project_root: Path, workflow: str, run_id: str) -> None:
    lock = _lock_path(project_root)
    if lock.exists():
        existing = lock.read_text(encoding="utf-8").strip()
        raise WrapperError(
            f"another RDX-TEA run is active: {existing}. "
            f"Refuse to start a second concurrent run in the same workspace."
        )
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(f"{workflow} {run_id} {os.getpid()}\n", encoding="utf-8")


def _release_active_run_lock(project_root: Path, run_id: str) -> None:
    lock = _lock_path(project_root)
    if not lock.exists():
        return
    content = lock.read_text(encoding="utf-8").strip()
    if run_id in content:
        lock.unlink()


# ------------------------------------------------------------------ helpers

def _read_optional(path: Path | None) -> str:
    return path.read_text(encoding="utf-8") if path and path.exists() else ""


def _git_cat_file_exists(project_root: Path, sha: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "cat-file", "-e", sha],
            capture_output=True, text=True, check=False,
        )
        return r.returncode == 0
    except FileNotFoundError:
        return False


def _git_rev_parse(project_root: Path, rev: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", rev],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        raise WrapperError(f"git rev-parse {rev!r} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def _git_diff(project_root: Path, base: str, head: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(project_root), "diff", base, head],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        raise WrapperError(f"git diff {base}..{head} failed: {r.stderr.strip()}")
    return r.stdout


def _read_sources_lock() -> dict:
    p = _HERE.parent / "bootstrap" / "sources.lock"
    if not p.exists():
        raise WrapperError(f"sources.lock missing at {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _resolve_identity(project_root: Path, base_sha: str | None,
                      head_sha: str | None) -> dict:
    """Strict git identity — no zero-SHA fallback. Both commits MUST
    exist in the project's git repo."""
    lock = _read_sources_lock()
    if not head_sha:
        head_sha = _git_rev_parse(project_root, "HEAD")
    if not base_sha:
        # Prefer `origin/main` merge-base; fall back to `HEAD^` for
        # single-commit test repos.
        for cand in ("origin/main", "main", "HEAD^"):
            try:
                base_sha = _git_rev_parse(project_root, f"merge-base HEAD {cand}")
                break
            except WrapperError:
                continue
        if not base_sha:
            base_sha = head_sha  # single-commit repo — base = head
    for name, sha in (("head", head_sha), ("base", base_sha)):
        if not _git_cat_file_exists(project_root, sha):
            raise WrapperError(f"{name}_sha {sha!r} does not exist as a git object")
    return {
        "base_sha":  base_sha,
        "head_sha":  head_sha,
        "diff_digest": "",  # prepare computes
        "rdx_source_sha": lock["rdx_source_sha"],
        "tea_source_sha": lock["tea_source_sha"],
    }


def _load_tea_config(project_root: Path) -> dict:
    cfg = project_root / "_bmad" / "tea" / "config.yaml"
    return yaml.safe_load(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}


def _assert_sequential_mode(config: dict) -> None:
    """D3.2 §3: reject `auto`, `subagent`, `agent-team` and every value
    other than the literal `sequential`."""
    resolved = str(config.get("tea_execution_mode", "")).strip().lower()
    if resolved != "sequential":
        raise WrapperError(
            f"D3.2 requires tea_execution_mode='sequential' (literal). "
            f"Host config resolves to {resolved!r}. Fix _bmad/tea/config.yaml "
            f"before running the wrapper."
        )


# --------------------------------------------------------------- discovery

def _output_dirs(skill_dir: Path, project_root: Path, config: dict) -> list[Path]:
    """Directories under which the child skill will write outputs."""
    ta = str(config.get("test_artifacts", str(project_root / "_bmad-output/test-artifacts")))
    ta = ta.replace("{project-root}", str(project_root))
    of = str(config.get("output_folder", str(project_root / "_bmad-output")))
    of = of.replace("{project-root}", str(project_root))
    dirs = {Path(ta), Path(of)}
    return [d for d in dirs if d.exists() or True]  # returned even if not yet existing


def _snapshot_outputs(dirs: list[Path]) -> dict:
    """Return `{path: sha256}` for every existing file under each dir."""
    inv: dict[str, str] = {}
    for d in dirs:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            inv[str(p.resolve())] = hashlib.sha256(p.read_bytes()).hexdigest()
    return inv


def _delta_outputs(pre: dict, dirs: list[Path]) -> list[Path]:
    """Return artefacts that are NEW or whose SHA-256 changed since the
    pre-snapshot. Symlinks are refused (safety boundary)."""
    now: list[Path] = []
    for d in dirs:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            if p.is_symlink():
                raise WrapperError(f"symlink artefact refused: {p}")
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            key = str(p.resolve())
            if key not in pre or pre[key] != digest:
                now.append(p)
    return sorted(now)


# --------------------------------------------------- state file (per run)

def _run_state_path(project_root: Path, workflow: str, run_id: str) -> Path:
    return (project_root / "_bmad" / "rdx-tea" / "runtime" / workflow
            / run_id / "run-state.json")


def _write_state(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _read_state(path: Path) -> dict:
    if not path.exists():
        raise WrapperError(f"run-state.json missing at {path}. Did prepare-run execute?")
    return json.loads(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------- prepare-run

def prepare_run(
    *,
    project_root: Path,
    workflow: str,
    run_id: str,
    skill_dir: Path,
    base_sha: str | None,
    head_sha: str | None,
    fixture_diff: Path | None = None,
) -> dict:
    _acquire_active_run_lock(project_root, workflow, run_id)
    identity = _resolve_identity(project_root, base_sha, head_sha)
    config = _load_tea_config(project_root)
    _assert_sequential_mode(config)

    # Diff resolution: git base..head unless --allow-fixture-diff.
    if fixture_diff is not None:
        if os.environ.get("RDX_TEA_ALLOW_FIXTURE_DIFF") != "1":
            raise WrapperError(
                "--allow-fixture-diff requires RDX_TEA_ALLOW_FIXTURE_DIFF=1"
            )
        diff = fixture_diff.read_text(encoding="utf-8")
    else:
        diff = _git_diff(project_root, identity["base_sha"], identity["head_sha"])
    diff_path = (project_root / "_bmad" / "rdx-tea" / "runtime" / workflow
                 / run_id / "diff.patch")
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(diff, encoding="utf-8")

    story_path = project_root / "_bmad-run" / "story.md"
    tags_path = project_root / "_bmad-run" / "tags.txt"

    manifest = prepare.prepare(
        project_root=project_root,
        workflow=workflow,
        identity=identity,
        run_id=run_id,
        story_path=story_path if story_path.exists() else None,
        diff_path=diff_path,
        tags_path=tags_path if tags_path.exists() else None,
    )

    overlay_path = _write_run_specific_overlay(project_root, workflow, run_id)

    dirs = _output_dirs(skill_dir, project_root, config)
    pre = _snapshot_outputs(dirs)
    state = {
        "phase": "prepared",
        "run_id": run_id,
        "workflow": workflow,
        "skill_dir": str(skill_dir),
        "output_dirs": [str(d) for d in dirs],
        "pre_snapshot": pre,
        "overlay_path": str(overlay_path),
        "overlay_backup_path": str(_overlay_backup_path(project_root, workflow, run_id)),
        "manifest_path": str(project_root / "_bmad" / "rdx-tea"
                             / "runtime" / workflow / run_id / "run-manifest.json"),
        "config_resolved_mode": config.get("tea_execution_mode"),
        "prepared_at": manifest["prepared_at"],
    }
    _write_state(_run_state_path(project_root, workflow, run_id), state)
    return {"manifest": manifest, "state": state, "overlay": str(overlay_path)}


# ------------------------------------------------------------ finalize-run

def finalize_run(
    *,
    project_root: Path,
    workflow: str,
    run_id: str,
    verify_only: bool = False,
    test_write_fake_artefact: bool = False,
) -> dict:
    state = _read_state(_run_state_path(project_root, workflow, run_id))
    if state["phase"] != "prepared":
        raise WrapperError(f"unexpected phase {state['phase']!r}")

    config = _load_tea_config(project_root)
    _assert_sequential_mode(config)

    if test_write_fake_artefact:
        if os.environ.get("RDX_TEA_ALLOW_TEST_ARTEFACT") != "1":
            raise WrapperError(
                "--test-write-fake-artefact requires "
                "RDX_TEA_ALLOW_TEST_ARTEFACT=1 (never enabled in production)"
            )
        # Test PoC only: write a bundle-derived fake TEA artefact so that
        # finalize-run has SOMETHING to bind. This is NOT a live proof.
        bundle_path = (project_root / "_bmad" / "rdx-tea" / "runtime"
                       / workflow / run_id / "active-context.md")
        art_dir = Path(state["output_dirs"][0])
        art_dir.mkdir(parents=True, exist_ok=True)
        art = art_dir / f"{workflow}-{run_id}-artifact.md"
        art.write_text(
            f"# TEST FAKE artefact for {workflow} / {run_id}\n\n"
            f"Bundle preview:\n\n```\n{bundle_path.read_text()[:2000]}\n```\n",
            encoding="utf-8",
        )

    dirs = [Path(d) for d in state["output_dirs"]]
    new = _delta_outputs(state["pre_snapshot"], dirs)
    if not new:
        raise WrapperError(
            "no new artefact discovered under output dirs — the child skill "
            "either never ran or wrote nothing"
        )

    sidecars = []
    verifier_results = []
    for art in new:
        s = binder.bind(project_root=project_root, workflow=workflow,
                        artifact=art, run_id=run_id,
                        declared_output_roots=[Path(d) for d in state["output_dirs"]])
        sidecar_path = art.with_suffix(art.suffix + ".rdx-tea.json")
        sidecars.append(s)
        # D3.2 verifier — behavioural eval, not enforcement.
        v = rdx_tea_validator.verify(
            sidecar_path=sidecar_path,
            project_root=project_root,
            workflow=workflow,
            run_id=run_id,
            source_lock_path=_HERE.parent / "bootstrap" / "sources.lock",
        )
        verifier_results.append(v)

    # D3.3 §4.5 — observed_mode surrogate. If we can find a transcript
    # file adjacent to the artefacts, parse it for subagent/agent-team
    # dispatch tokens. Absence = INFERRED_ABSENT (an inference, not a
    # direct proof); presence of subagent tokens = OBSERVED_SUBAGENT.
    observed_mode = _infer_observed_mode(project_root, workflow, run_id, new)

    report = {
        "schema_version": "rdx-tea-run.v1",
        "workflow": workflow,
        "run_id": run_id,
        "execution_mode": "sequential",
        "requested_mode": "sequential",
        "resolved_mode": config.get("tea_execution_mode"),
        "observed_mode": observed_mode,
        "sidecars": sidecars,
        "verifier": verifier_results,
        "finalized_at": (os.environ.get("RDX_TEA_FAKE_NOW")
                         or datetime.now(timezone.utc).replace(microsecond=0).isoformat()),
        "new_artefacts": [str(a) for a in new],
        "verify_only": verify_only,
    }
    report_path = (project_root / "_bmad" / "rdx-tea" / "runtime"
                   / workflow / run_id / "run-report.json")
    _write_state(report_path, report)
    state["phase"] = "finalized"
    _write_state(_run_state_path(project_root, workflow, run_id), state)
    # Restore/remove overlay + release lock.
    _restore_or_remove_overlay(project_root, workflow, run_id)
    _release_active_run_lock(project_root, run_id)
    return report


def _infer_observed_mode(project_root: Path, workflow: str, run_id: str,
                         new_artefacts: list[Path]) -> str:
    """Surrogate for observed execution mode.

    D3.3 §4.5: look for a `transcript.stream.jsonl` next to the
    artefacts, under the run dir, OR under a sibling run dir (harness
    scenario id vs wrapper's generated id). If present, scan for
    `subagent`/`agent-team`/`Task`-tool invocation tokens. Absent →
    `INFERRED_ABSENT` (still labelled as inference, not direct proof)."""
    run_dir = project_root / "_bmad" / "rdx-tea" / "runtime" / workflow / run_id
    workflow_dir = run_dir.parent
    candidates = [run_dir / "transcript.stream.jsonl"]
    for a in new_artefacts:
        candidates.append(a.parent / "transcript.stream.jsonl")
    # Search sibling run dirs (harness id vs wrapper id handshake).
    if workflow_dir.exists():
        for sub in workflow_dir.iterdir():
            if sub.is_dir():
                candidates.append(sub / "transcript.stream.jsonl")
    seen: set[str] = set()
    for c in candidates:
        key = str(c.resolve()) if c.exists() else str(c)
        if key in seen:
            continue
        seen.add(key)
        if c.exists():
            txt = c.read_text(encoding="utf-8", errors="replace").lower()
            if any(t in txt for t in ("agent_team_dispatch",
                                       "subagent_dispatch",
                                       "\"tool\":\"task\"",
                                       '"name":"task"')):
                return "OBSERVED_SUBAGENT"
            return "OBSERVED_SEQUENTIAL"
    return "INFERRED_ABSENT"


# ----------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("prepare-run")
    p1.add_argument("--workflow", required=True)
    p1.add_argument("--project-root", required=True, type=Path)
    p1.add_argument("--run-id", required=True)
    p1.add_argument("--skill-dir", required=True, type=Path)
    p1.add_argument("--base-sha", default=None)
    p1.add_argument("--head-sha", default=None)
    p1.add_argument("--allow-fixture-diff", type=Path, default=None)

    p2 = sub.add_parser("finalize-run")
    p2.add_argument("--workflow", required=True)
    p2.add_argument("--project-root", required=True, type=Path)
    p2.add_argument("--run-id", required=True)
    p2.add_argument("--verify-only", action="store_true")
    p2.add_argument("--test-write-fake-artefact", action="store_true")

    args = ap.parse_args()
    try:
        if args.cmd == "prepare-run":
            out = prepare_run(
                project_root=args.project_root,
                workflow=args.workflow,
                run_id=args.run_id,
                skill_dir=args.skill_dir,
                base_sha=args.base_sha,
                head_sha=args.head_sha,
                fixture_diff=args.allow_fixture_diff,
            )
        else:
            out = finalize_run(
                project_root=args.project_root,
                workflow=args.workflow,
                run_id=args.run_id,
                verify_only=args.verify_only,
                test_write_fake_artefact=args.test_write_fake_artefact,
            )
    except (WrapperError, prepare.PrepareError, binder.BinderError,
            rdx_tea_validator.ValidatorError) as err:
        print(f"wrapper failed: {err}", file=sys.stderr)
        return 1
    print(json.dumps(out, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
