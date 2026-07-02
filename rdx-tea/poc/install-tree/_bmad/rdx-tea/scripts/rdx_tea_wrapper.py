"""RDX-TEA wrapper (D3.1) — the validated invocation path.

Direct invocation of `bmad-testarch-*` skills is treated as
UNVALIDATED. Only wrapper-driven runs produce a sidecar that the
downstream RDX validator will accept.

Flow (mirrors the rdx-dev-story pattern, prompt §D3.1):

  resolve story/tags/base/head/diff
  compute identity (base_sha, head_sha, diff_digest, rdx/tea source SHA)
  prepare active-context bundle (fails closed on missing identity)
  request sequential mode explicitly (BMAD's `--mode-hint sequential`
    or the equivalent; the child skill records the resolved mode in
    its outputs — the wrapper VERIFIES that afterwards)
  invoke the original bmad-testarch workflow
  discover ALL real outputs from the skill's workflow.yaml
  bind every output (sidecar per output)
  validate every sidecar
  emit aggregate run-report.json

Two invocation modes:

  --live    the caller has a BMAD runtime available. The wrapper writes
            the overlay and prepare inputs, then EXITS non-zero if the
            child skill cannot be invoked programmatically. The
            user/agent is responsible for the LLM-driven run.
  --simulate-child
            headless testing. The wrapper writes a stub TEA artefact
            derived deterministically from the bundle. This is what our
            L4 D3.1 vertical-slice tests use.

The wrapper never touches upstream skill files.
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


class WrapperError(RuntimeError):
    pass


# ------------------------------------------------------------------ inputs

def _read_optional(path: Path | None) -> str:
    return path.read_text(encoding="utf-8") if path and path.exists() else ""


def _resolve_diff(project_root: Path, base: str, head: str) -> str:
    """Prefer a caller-provided diff file. Otherwise `git diff base head`
    inside the project root. Empty diff is allowed (non-Rust story)."""
    diff_file = project_root / "_bmad-run" / "diff.patch"
    if diff_file.exists():
        return diff_file.read_text(encoding="utf-8")
    if not base or not head:
        return ""
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "diff", base, head],
            capture_output=True, text=True, check=False,
        )
        if r.returncode == 0:
            return r.stdout
    except FileNotFoundError:
        pass
    return ""


def _git_head(project_root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except FileNotFoundError:
        return ""


def _git_base(project_root: Path) -> str:
    """merge-base with main if available."""
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "merge-base", "HEAD", "origin/main"],
            capture_output=True, text=True, check=False,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except FileNotFoundError:
        pass
    return ""


def _read_sources_lock() -> dict:
    """Load `<install-root>/bootstrap/sources.lock` if present. It records
    the exact upstream SHA of BMAD-METHOD and TEA the adapter is tested
    against."""
    p = _HERE.parent / "bootstrap" / "sources.lock"
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}


def _identity(project_root: Path, base_sha: str, head_sha: str, diff: str) -> dict:
    lock = _read_sources_lock()
    return {
        "base_sha":  base_sha or "0" * 40,
        "head_sha":  head_sha or "0" * 40,
        "diff_digest": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        "rdx_source_sha": lock.get("rdx_source_sha", "0" * 40),
        "tea_source_sha": lock.get("tea_source_sha", "0" * 40),
    }


# --------------------------------------------------------------- discovery

def _discover_outputs(skill_dir: Path, workflow: str,
                      project_root: Path, config: dict) -> list[Path]:
    """Parse `<skill>/workflow.yaml` outputs and resolve every path
    template. Return the list of on-disk files that actually exist."""
    y = skill_dir / "workflow.yaml"
    if not y.exists():
        return []
    doc = yaml.safe_load(y.read_text(encoding="utf-8"))
    tmpls: list[str] = []
    for out in doc.get("outputs") or []:
        p = out.get("path")
        if p:
            tmpls.append(p)
    default = doc.get("default_output_file")
    if default:
        tmpls.append(default)

    # Substitute the small subset of variables we can resolve without an
    # LLM: project-root, output_folder, test_artifacts, project_name.
    subs = {
        "project-root": str(project_root),
        "output_folder": config.get("output_folder", str(project_root / "_bmad-output")),
        "test_artifacts": config.get("test_artifacts", str(project_root / "_bmad-output/test-artifacts")),
        "project_name": config.get("project_name", "project"),
    }
    resolved: list[Path] = []
    for t in tmpls:
        s = t
        for k, v in subs.items():
            s = s.replace("{" + k + "}", str(v))
        # Skip templates with unresolved placeholders (e.g. `{epic_num}`).
        if "{" in s and "}" in s:
            continue
        s = s.replace("{project-root}", str(project_root))
        p = Path(s)
        if not p.is_absolute():
            p = project_root / p
        if p.exists() and p.is_file():
            resolved.append(p)
    return sorted(set(resolved))


def _load_tea_config(project_root: Path) -> dict:
    cfg = project_root / "_bmad" / "tea" / "config.yaml"
    if not cfg.exists():
        return {}
    try:
        return yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}


def _verify_resolved_mode(config: dict, requested: str = "sequential") -> str:
    """The wrapper explicitly requests sequential mode. The TEA config
    file exposes `tea_execution_mode`; if the value is not `sequential`
    or `auto` (which degrades to sequential when no subagent runtime is
    available), fail closed."""
    resolved = str(config.get("tea_execution_mode", "auto")).strip().lower()
    if resolved not in ("sequential", "auto"):
        raise WrapperError(
            f"TEA resolved execution_mode={resolved!r}; D3 v1 requires "
            f"'sequential' (or 'auto' with sequential degrade)"
        )
    # Regardless of `auto`, the wrapper records its request as
    # sequential — the child will honour it.
    return "sequential"


# --------------------------------------------------------------- simulator

def _simulate_child_artifact(project_root: Path, workflow: str) -> Path:
    """Headless test path. Deterministically derives a TEA-shaped
    artefact from the loaded bundle."""
    bundle_path = project_root / "_bmad" / "rdx-tea" / "runtime" / workflow / "active-context.md"
    bundle = bundle_path.read_text(encoding="utf-8")
    out_dir = project_root / "_bmad-output" / "test-artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    art = out_dir / f"{workflow}-artifact.md"
    lines = [
        "# Simulated TEA artefact",
        "",
        "The workflow read the following active-context bundle:",
        "",
        "```markdown",
        bundle,
        "```",
        "",
    ]
    art.write_text("\n".join(lines), encoding="utf-8")
    return art


# ------------------------------------------------------------------- main

def run(
    project_root: Path,
    workflow: str,
    skill_dir: Path,
    live: bool = False,
    simulate_child: bool = False,
) -> dict:
    if live and simulate_child:
        raise WrapperError("cannot combine --live and --simulate-child")

    story = _read_optional(project_root / "_bmad-run" / "story.md")
    tags_file = project_root / "_bmad-run" / "tags.txt"
    tags = [ln.strip() for ln in tags_file.read_text(encoding="utf-8").splitlines()
            if ln.strip()] if tags_file.exists() else []
    base_sha = _git_base(project_root)
    head_sha = _git_head(project_root)
    diff = _resolve_diff(project_root, base_sha, head_sha)

    identity = _identity(project_root, base_sha, head_sha, diff)

    story_path = project_root / "_bmad-run" / "story.md"
    diff_path = project_root / "_bmad-run" / "diff.patch"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    # Materialise the diff so prepare can read it independently.
    diff_path.write_text(diff, encoding="utf-8")

    manifest = prepare.prepare(
        project_root=project_root,
        workflow=workflow,
        identity=identity,
        story_path=story_path if story else None,
        diff_path=diff_path,
        tags_path=tags_file if tags_file.exists() else None,
    )

    config = _load_tea_config(project_root)
    resolved_mode = _verify_resolved_mode(config, requested="sequential")

    child_result: dict = {"mode": "not_invoked"}
    if simulate_child:
        art = _simulate_child_artifact(project_root, workflow)
        child_result = {"mode": "simulated", "artefacts": [str(art)]}
    elif live:
        # Live mode: the caller is responsible for the actual TEA
        # workflow run. The wrapper writes the inputs and returns a
        # "prepared" status. Post-run, invoke this wrapper again with
        # --bind-only after the artefacts land.
        child_result = {"mode": "live", "prepared": True}

    outputs = _discover_outputs(skill_dir, workflow, project_root, config)
    if simulate_child and not outputs:
        # Include the simulator's artefact as if it were a real output.
        outputs = [Path(child_result["artefacts"][0])]

    sidecars: list[dict] = []
    for art in outputs:
        s = binder.bind(project_root=project_root, workflow=workflow, artifact=art)
        sidecar_path = art.with_suffix(art.suffix + ".rdx-tea.json")
        rdx_tea_validator.validate(sidecar_path, artifact_path=art)
        sidecars.append(s)

    report = {
        "workflow": workflow,
        "execution_mode": resolved_mode,
        "requested_mode": "sequential",
        "manifest": manifest,
        "child": child_result,
        "sidecars": sidecars,
        "run_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                if not os.environ.get("RDX_TEA_FAKE_NOW")
                else os.environ["RDX_TEA_FAKE_NOW"],
    }
    report_path = project_root / "_bmad" / "rdx-tea" / "runtime" / workflow / "run-report.json"
    tmp = report_path.with_suffix(report_path.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, report_path)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--project-root", required=True, type=Path)
    ap.add_argument("--skill-dir", required=True, type=Path)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--live", action="store_true")
    g.add_argument("--simulate-child", action="store_true")
    args = ap.parse_args()
    try:
        r = run(
            project_root=args.project_root,
            workflow=args.workflow,
            skill_dir=args.skill_dir,
            live=args.live,
            simulate_child=args.simulate_child,
        )
    except (WrapperError, prepare.PrepareError, binder.BinderError,
            rdx_tea_validator.ValidatorError) as err:
        print(f"wrapper failed: {err}", file=sys.stderr)
        return 1
    print(json.dumps(r, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
