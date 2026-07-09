#!/usr/bin/env python3
"""RDX-TEA project installer (Wave 7 / ADR-001 §14, ADR-006 §2).

Idempotent install / update / uninstall of the SHIPPED SURFACE
(``PRODUCTION_EVAL_SPLIT.md`` §2) from the canonical install-tree at
``rdx-tea/poc/install-tree/`` into a user project.

What installs (adapter-owned):

    <project>/_bmad/rdx-tea/canonical/**
    <project>/_bmad/rdx-tea/scripts/**            (all 10 production scripts)
    <project>/_bmad/rdx-tea/bootstrap/sources.lock (identity stamp)
    <project>/_bmad/rdx-tea/VERSION
    <project>/.claude/skills/rdx-tea-test-design/SKILL.md
    <project>/.claude/skills/rdx-tea-atdd/SKILL.md
    <project>/.claude/settings.json               (project-surface isolation)
    <project>/_bmad/custom/                        (empty dir for overlays)

Design invariants (Wave 7):

  * The installer NEVER writes or reads auth material of any kind, and
    NEVER sets or overrides the CLI config-dir environment variable. The
    project ``.claude/settings.json`` carries ONLY project-surface
    isolation keys — no auth fields. Auth is preserved by doing nothing
    with it (ADR-006 §1-2). The absence of auth handling is verified by a
    grep gate over this module and over the installed surface (G-AUTH).
  * Determinism only — no wall-clock, no random, sorted iteration. The
    same source tree always yields a byte-identical install and manifest.
  * The shipped surface installed here imports no eval/harness module and
    references no eval/evidence path (G-SPLIT-IMPORT). The installer copies
    ONLY from the canonical install-tree.
  * Idempotent: a second install with the same source is a no-op.
  * Update refuses to overwrite user-owned ``*.user.toml`` overlays.
  * Uninstall removes adapter-owned files (tracked in the install
    manifest) but keeps user content and ``*.user.toml``.
  * Version-range refusal: if ``_bmad/tea/config.yaml`` declares a TEA
    version outside the supported range (derived from ``sources.lock``),
    the installer fails closed and installs nothing.

This module is repo/distribution-side tooling (it performs the install);
it is not itself copied into the user project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Canonical source location (relative to this file — never an absolute pin).
# --------------------------------------------------------------------------- #
_INSTALLER_DIR = Path(__file__).resolve().parent
RDX_TEA_DIR = _INSTALLER_DIR.parent
INSTALL_TREE = RDX_TEA_DIR / "poc" / "install-tree"
SRC_ADAPTER = INSTALL_TREE / "_bmad" / "rdx-tea"
SRC_SOURCES_LOCK = SRC_ADAPTER / "bootstrap" / "sources.lock"

# --------------------------------------------------------------------------- #
# Shipped-surface contract.
# --------------------------------------------------------------------------- #
ADAPTER_REL = "_bmad/rdx-tea"
CUSTOM_REL = "_bmad/custom"
SETTINGS_REL = ".claude/settings.json"
MANIFEST_REL = "_bmad/rdx-tea/.rdx-tea-install-manifest.json"
MANIFEST_SCHEMA = "rdx-tea-install-manifest.v1"

WRAPPER_SKILLS = ("rdx-tea-test-design", "rdx-tea-atdd")

# All ten production scripts MUST be present in the source before we install.
REQUIRED_SCRIPTS = (
    "admission.py",
    "workspace_delta.py",
    "binder.py",
    "prepare.py",
    "rdx_tea_wrapper.py",
    "rdx_tea_validator.py",
    "router.py",
    "diff.py",
    "obligation_matrix.py",
    "rdx_parser.py",
)

# Project-surface isolation ONLY — no auth fields (ADR-006 §2).
ISOLATION_SETTINGS = {
    "autoMemoryEnabled": False,
    "disableBundledSkills": True,
    "disableClaudeAiConnectors": True,
}


# --------------------------------------------------------------------------- #
# Errors — all fail closed.
# --------------------------------------------------------------------------- #
class InstallerError(RuntimeError):
    """Base class for installer refusals."""


class MissingProductionFileError(InstallerError):
    """A required production file is absent from the canonical source."""


class VersionRangeError(InstallerError):
    """`_bmad/tea/config.yaml` declares a TEA version outside the range."""


class UserFileProtectedError(InstallerError):
    """Refused to write over a user-owned file (`*.user.toml`)."""


# --------------------------------------------------------------------------- #
# Small deterministic helpers.
# --------------------------------------------------------------------------- #
def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_if_changed(path: Path, data: bytes) -> bool:
    """Atomically write ``data`` to ``path`` only if the bytes differ.

    Returns True when the file was (re)written, False when it was already
    byte-identical (idempotent no-op).
    """
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return True


def _json_bytes(obj) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


# --------------------------------------------------------------------------- #
# TEA version-range gate (fail closed).
# --------------------------------------------------------------------------- #
_TAG_RE = re.compile(r'v?(\d+)\.(\d+)(?:\.(\d+))?')
# Recognised version keys inside `_bmad/tea/config.yaml`, in priority order.
_VERSION_KEYS = ("tea_version", "module_version", "version")


def _parse_semver(text: str):
    m = _TAG_RE.fullmatch(text.strip().strip('"').strip("'"))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def supported_tea_bounds(sources_lock: Path = SRC_SOURCES_LOCK):
    """Derive the supported TEA version window from ``sources.lock``.

    ``tea_source_tag: "v1.19.0"`` yields the half-open window
    ``[1.19.0, 2.0.0)`` — same major, at least the pinned minor/patch.
    """
    text = sources_lock.read_text(encoding="utf-8")
    m = re.search(r'tea_source_tag:\s*"([^"]+)"', text)
    if not m:
        raise InstallerError(f"sources.lock missing tea_source_tag: {sources_lock}")
    low = _parse_semver(m.group(1))
    if low is None:
        raise InstallerError(f"unparseable tea_source_tag: {m.group(1)!r}")
    high = (low[0] + 1, 0, 0)
    return low, high


def declared_tea_version(project_root: Path):
    """Return the (raw, parsed) TEA version declared in the project's
    ``_bmad/tea/config.yaml``, or ``(None, None)`` if none is declared.

    Uses a dependency-free line scan (no YAML parser) so the gate works on
    a project that has not installed PyYAML yet.
    """
    cfg = project_root / "_bmad" / "tea" / "config.yaml"
    if not cfg.exists():
        return None, None
    found: dict[str, str] = {}
    for line in cfg.read_text(encoding="utf-8").splitlines():
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$', line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip().strip('"').strip("'")
        if key in _VERSION_KEYS and key not in found:
            found[key] = raw
    for key in _VERSION_KEYS:
        if key in found:
            return found[key], _parse_semver(found[key])
    return None, None


def check_tea_version(project_root: Path, sources_lock: Path = SRC_SOURCES_LOCK):
    """Fail closed if the project declares an unsupported/unparseable TEA
    version. Returns the accepted raw version string, or ``None`` when the
    project declares no TEA version (nothing to be incompatible with)."""
    raw, parsed = declared_tea_version(project_root)
    if raw is None:
        return None
    low, high = supported_tea_bounds(sources_lock)
    if parsed is None:
        raise VersionRangeError(
            f"_bmad/tea/config.yaml declares an unparseable TEA version "
            f"{raw!r}; supported range is >={_fmt(low)},<{_fmt(high)}"
        )
    if not (low <= parsed < high):
        raise VersionRangeError(
            f"_bmad/tea/config.yaml declares TEA version {raw!r} outside the "
            f"supported range >={_fmt(low)},<{_fmt(high)}"
        )
    return raw


def _fmt(v) -> str:
    return ".".join(str(x) for x in v)


# --------------------------------------------------------------------------- #
# Source inventory — deterministic, sorted, validated.
# --------------------------------------------------------------------------- #
def _iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            yield p


def source_inventory() -> list[tuple[str, Path]]:
    """Return the sorted ``(relative_dest, absolute_source)`` inventory of
    the shipped surface. Fails closed if a required production file is
    missing from the canonical source (catches a broken distribution)."""
    if not INSTALL_TREE.exists():
        raise MissingProductionFileError(f"install-tree missing: {INSTALL_TREE}")

    items: list[tuple[str, Path]] = []

    # canonical/**
    canonical = SRC_ADAPTER / "canonical"
    if not canonical.exists():
        raise MissingProductionFileError(f"missing canonical/: {canonical}")
    for p in _iter_files(canonical):
        items.append((f"{ADAPTER_REL}/canonical/{p.relative_to(canonical).as_posix()}", p))

    # scripts/** (all .py) + required-script assertion
    scripts = SRC_ADAPTER / "scripts"
    present = {p.name for p in _iter_files(scripts) if p.suffix == ".py"}
    missing = [s for s in REQUIRED_SCRIPTS if s not in present]
    if missing:
        raise MissingProductionFileError(
            f"required production scripts missing from source: {sorted(missing)}"
        )
    for p in _iter_files(scripts):
        if p.suffix == ".py":
            items.append((f"{ADAPTER_REL}/scripts/{p.name}", p))

    # bootstrap/sources.lock (identity stamp)
    if not SRC_SOURCES_LOCK.exists():
        raise MissingProductionFileError(f"missing sources.lock: {SRC_SOURCES_LOCK}")
    items.append((f"{ADAPTER_REL}/bootstrap/sources.lock", SRC_SOURCES_LOCK))

    # VERSION
    version_file = SRC_ADAPTER / "VERSION"
    if not version_file.exists():
        raise MissingProductionFileError(f"missing VERSION: {version_file}")
    items.append((f"{ADAPTER_REL}/VERSION", version_file))

    # wrapper Skills
    for slug in WRAPPER_SKILLS:
        skill_dir = INSTALL_TREE / ".claude" / "skills" / slug
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise MissingProductionFileError(f"missing wrapper Skill: {skill_md}")
        for p in _iter_files(skill_dir):
            items.append((f".claude/skills/{slug}/{p.relative_to(skill_dir).as_posix()}", p))

    items.sort(key=lambda t: t[0])
    return items


def adapter_version(sources_lock: Path = SRC_SOURCES_LOCK) -> str:
    text = sources_lock.read_text(encoding="utf-8")
    m = re.search(r'adapter_version:\s*"([^"]+)"', text)
    return m.group(1) if m else "unknown"


# --------------------------------------------------------------------------- #
# Project-surface isolation settings (merge-preserving, reversible).
# --------------------------------------------------------------------------- #
def _load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def _write_settings(project_root: Path) -> bool:
    """Merge the isolation keys into any existing project settings,
    preserving user keys. Never adds auth fields. Returns True if written."""
    path = project_root / SETTINGS_REL
    current = _load_settings(path)
    merged = dict(current)
    merged.update(ISOLATION_SETTINGS)
    return _write_if_changed(path, _json_bytes(merged))


def _unset_settings(project_root: Path) -> None:
    """Reverse the isolation merge: drop only the isolation keys whose
    value still equals our template, preserving any user overrides; delete
    the file if nothing remains."""
    path = project_root / SETTINGS_REL
    if not path.exists():
        return
    current = _load_settings(path)
    for key, value in ISOLATION_SETTINGS.items():
        if current.get(key) == value:
            current.pop(key, None)
    if current:
        _write_if_changed(path, _json_bytes(current))
    else:
        path.unlink()


# --------------------------------------------------------------------------- #
# Overlay writer (`_bmad/custom/bmad-testarch-<workflow>.toml`).
# --------------------------------------------------------------------------- #
_OVERLAY_HEADER = "# rdx-tea adapter-owned overlay — regenerate with the installer.\n"


def write_overlay(project_root: Path, workflow: str) -> Path:
    """Write the adapter-owned base overlay for ``workflow``. Refuses to
    target a user-owned ``*.user.toml``. Idempotent."""
    name = f"bmad-testarch-{workflow}.toml"
    if name.endswith(".user.toml"):  # defensive; never true for base overlays
        raise UserFileProtectedError(name)
    dest = project_root / CUSTOM_REL / name
    bundle = (
        f"{{project-root}}/_bmad/rdx-tea/runtime/{workflow}/active-context.md"
    )
    body = (
        _OVERLAY_HEADER
        + "[workflow]\n"
        + "persistent_facts = [\n"
        + f'  "file:{bundle}",\n'
        + "]\n"
    )
    _write_if_changed(dest, body.encode("utf-8"))
    return dest


# --------------------------------------------------------------------------- #
# Manifest.
# --------------------------------------------------------------------------- #
def _manifest_bytes(entries: list[tuple[str, str]]) -> bytes:
    obj = {
        "schema": MANIFEST_SCHEMA,
        "adapter_version": adapter_version(),
        "settings_keys": sorted(ISOLATION_SETTINGS),
        "settings_file": SETTINGS_REL,
        "files": [{"path": rel, "sha256": digest} for rel, digest in entries],
    }
    return _json_bytes(obj)


def _read_manifest(project_root: Path) -> dict | None:
    path = project_root / MANIFEST_REL
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- #
# Public lifecycle: install / update / uninstall.
# --------------------------------------------------------------------------- #
def install(project_root: Path, *, update: bool = False) -> dict:
    """Install (or update) the shipped surface into ``project_root``.

    Fails closed on an unsupported TEA version BEFORE writing anything.
    Idempotent: unchanged files are left untouched. ``update`` is
    behaviourally identical (idempotent re-install) and is provided as a
    named entrypoint; both refuse to overwrite ``*.user.toml``.
    """
    project_root = Path(project_root)
    project_root.mkdir(parents=True, exist_ok=True)

    # Fail closed on version range before any write.
    accepted_version = check_tea_version(project_root)

    inventory = source_inventory()
    written: list[str] = []
    unchanged: list[str] = []
    entries: list[tuple[str, str]] = []

    for rel, src in inventory:
        if rel.endswith(".user.toml"):  # never overwrite user overlays
            raise UserFileProtectedError(rel)
        data = src.read_bytes()
        dest = project_root / rel
        if _write_if_changed(dest, data):
            written.append(rel)
        else:
            unchanged.append(rel)
        entries.append((rel, _sha256_bytes(data)))

    # Project-surface isolation settings (auth-free, merge-preserving).
    settings_changed = _write_settings(project_root)

    # Ensure the overlay dir exists (overlays are generated per run).
    (project_root / CUSTOM_REL).mkdir(parents=True, exist_ok=True)

    # Manifest (deterministic; enables idempotent uninstall).
    manifest_changed = _write_if_changed(
        project_root / MANIFEST_REL, _manifest_bytes(sorted(entries))
    )

    changed = sorted(
        written
        + ([SETTINGS_REL] if settings_changed else [])
        + ([MANIFEST_REL] if manifest_changed else [])
    )
    return {
        "mode": "update" if update else "install",
        "project_root": str(project_root),
        "adapter_version": adapter_version(),
        "tea_version": accepted_version,
        "written": sorted(written),
        "unchanged": sorted(unchanged),
        "settings_changed": settings_changed,
        "manifest_changed": manifest_changed,
        "changed": changed,
        "file_count": len(inventory),
    }


def update(project_root: Path) -> dict:
    """Idempotent update. Refuses to overwrite ``*.user.toml`` (inherent —
    user overlays are never part of the inventory)."""
    return install(project_root, update=True)


def _prune_empty_dirs(project_root: Path, rel_dirs: list[str]) -> None:
    # Longest paths first so children are pruned before parents.
    for rel in sorted(rel_dirs, key=len, reverse=True):
        d = project_root / rel
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


def uninstall(project_root: Path) -> dict:
    """Remove adapter-owned files (from the manifest) plus adapter-owned
    base overlays, keeping user content and every ``*.user.toml``."""
    project_root = Path(project_root)
    manifest = _read_manifest(project_root)
    removed: list[str] = []
    kept: list[str] = []
    candidate_dirs: set[str] = set()

    if manifest:
        for entry in manifest.get("files", []):
            rel = entry["path"]
            if rel.endswith(".user.toml"):
                kept.append(rel)
                continue
            target = project_root / rel
            if target.exists():
                target.unlink()
                removed.append(rel)
            parent = os.path.dirname(rel)
            while parent:
                candidate_dirs.add(parent)
                parent = os.path.dirname(parent)

    # Adapter-owned base overlays (bmad-testarch-*.toml, NOT *.user.toml).
    custom = project_root / CUSTOM_REL
    if custom.is_dir():
        for p in sorted(custom.glob("bmad-testarch-*.toml")):
            if p.name.endswith(".user.toml"):
                kept.append(f"{CUSTOM_REL}/{p.name}")
                continue
            p.unlink()
            removed.append(f"{CUSTOM_REL}/{p.name}")

    # Reverse the settings isolation merge (preserve user keys).
    _unset_settings(project_root)

    # Remove the manifest itself.
    manifest_path = project_root / MANIFEST_REL
    if manifest_path.exists():
        manifest_path.unlink()
        removed.append(MANIFEST_REL)

    # Preserve any surviving *.user.toml explicitly in the report.
    if custom.is_dir():
        for p in sorted(custom.glob("*.user.toml")):
            kept.append(f"{CUSTOM_REL}/{p.name}")

    _prune_empty_dirs(
        project_root,
        sorted(candidate_dirs)
        + [f".claude/skills/{s}" for s in WRAPPER_SKILLS]
        + [".claude/skills", ADAPTER_REL],
    )

    return {
        "project_root": str(project_root),
        "removed": sorted(removed),
        "kept": sorted(set(kept)),
    }


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="rdx-tea-setup",
        description="Install / update / uninstall the RDX-TEA shipped surface "
        "into a user project (auth-preserving, idempotent).",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("install", "update", "uninstall"):
        p = sub.add_parser(cmd, help=f"{cmd} the RDX-TEA adapter")
        p.add_argument("--project", required=True, type=Path,
                       help="target project root")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "install":
            result = install(args.project)
        elif args.cmd == "update":
            result = update(args.project)
        else:
            result = uninstall(args.project)
    except InstallerError as err:
        print(json.dumps({"status": "REFUSED", "reason": str(err)},
                         indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
