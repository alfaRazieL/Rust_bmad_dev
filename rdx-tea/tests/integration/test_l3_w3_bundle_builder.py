"""L3 W3 active-context bundle-builder productionization tests.

Covers Wave 3 (``MASTER_IMPLEMENTATION_PLAN`` §6.6 W3; ``ACCEPTANCE_GATES``
G-W3-DETERMINISM / G-W3-IDENTITY / G-W3-SCHEMA; cross-cutting G-DET):

  * byte-determinism of the bundle AND the run-manifest across two *OS
    processes* with NO env injection (``prepare`` is wall-clock/random
    free);
  * identity fail-closed (missing / all-zero / non-hex mandatory SHAs;
    diff_digest agreement);
  * docs-only diff → empty bundle even for an "all"-CORE workflow;
  * obligation-matrix field filtering per ``fields_allowed(workflow)``;
  * schema conformance — the run-manifest carries schema-consistent
    fields and the binder sidecar validates against
    ``canonical/rdx-tea-run.v1``;
  * schema-authority — ``canonical/`` (shipped) is byte-identical to the
    ``architecture/`` mirror (drift guard).

The tests import ONLY the production install-tree scripts; nothing under
``live-harness``/``evals`` is imported (G-SPLIT-IMPORT).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
INSTALL_TREE = RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea"
INSTALL_SCRIPTS = INSTALL_TREE / "scripts"
CANONICAL = INSTALL_TREE / "canonical"
SCHEMA_CANONICAL = CANONICAL / "rdx-tea-run.v1.schema.json"
SCHEMA_MIRROR = RDX_TEA_DIR / "architecture" / "rdx-tea-run.v1.schema.json"
PREPARE_CLI = INSTALL_SCRIPTS / "prepare.py"
VENV_PY = Path(sys.executable)


def _load(name: str):
    """Import an install-tree script with canonical resolving to the
    shipped install-tree copy (never the dev-tree fallback)."""
    if str(INSTALL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(INSTALL_SCRIPTS))
    for m in ("rdx_parser", "prepare", "obligation_matrix", "binder"):
        sys.modules.pop(m, None)
    return importlib.import_module(name)


prepare_mod = _load("prepare")
obligation = _load("obligation_matrix")
binder_mod = _load("binder")
# re-import prepare after the fresh binder import purged it
prepare_mod = _load("prepare")

SCHEMA = json.loads(SCHEMA_CANONICAL.read_text(encoding="utf-8"))

IDENTITY = {
    "base_sha": "1" * 40,
    "head_sha": "2" * 40,
    "diff_digest": "",  # computed by prepare
    "rdx_source_sha": "d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d",
    "tea_source_sha": "8734d51f24071ddbcb3617390b5fcddb4128ef77",
}

ASYNC_DIFF = (
    "diff --git a/src/lib.rs b/src/lib.rs\n"
    "--- a/src/lib.rs\n"
    "+++ b/src/lib.rs\n"
    "@@ -0,0 +1,4 @@\n"
    "+pub async fn f() -> Result<(), std::io::Error> {\n"
    "+    let h = tokio::spawn(async {});\n"
    "+    h.await.unwrap();\n"
    "+    Ok(())\n"
    "+}\n"
)

DOCS_ONLY_DIFF = (
    "diff --git a/README.md b/README.md\n"
    "--- a/README.md\n"
    "+++ b/README.md\n"
    "@@ -0,0 +1,1 @@\n"
    "+# Docs update inside a Rust project.\n"
)


# --------------------------------------------------------------- helpers
def _rust_project(root: Path) -> Path:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "Cargo.toml").write_text("[package]\nname='p'\nversion='0'\n",
                                     encoding="utf-8")
    (root / "src" / "lib.rs").write_text("// lib\n", encoding="utf-8")
    (root / "_bmad-run").mkdir(exist_ok=True)
    return root


def _write_inputs(project: Path, diff: str, tags: list[str] | None):
    diff_p = project / "_bmad-run" / "diff.patch"
    diff_p.write_text(diff, encoding="utf-8")
    tags_p = None
    if tags:
        tags_p = project / "_bmad-run" / "tags.txt"
        tags_p.write_text("\n".join(tags) + "\n", encoding="utf-8")
    story_p = project / "_bmad-run" / "story.md"
    story_p.write_text("# story\n", encoding="utf-8")
    return diff_p, tags_p, story_p


def _prepare(project: Path, workflow: str, diff: str, run_id: str,
             tags: list[str] | None = None, rust_scope=None,
             identity: dict | None = None) -> dict:
    diff_p, tags_p, story_p = _write_inputs(project, diff, tags)
    return prepare_mod.prepare(
        project_root=project,
        workflow=workflow,
        identity=dict(identity or IDENTITY),
        run_id=run_id,
        story_path=story_p,
        diff_path=diff_p,
        tags_path=tags_p,
        rust_scope=rust_scope,
    )


def _clean_env() -> dict:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("RDX_TEA_FAKE_NOW", None)  # prove determinism WITHOUT injection
    return env


def _run_prepare_cli(project: Path, workflow: str, diff_p: Path,
                     run_id: str, out_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(VENV_PY), str(PREPARE_CLI),
         "--workflow", workflow,
         "--project-root", str(project),
         "--run-id", run_id,
         "--diff", str(diff_p),
         "--output-root", str(out_root),
         "--base-sha", IDENTITY["base_sha"],
         "--head-sha", IDENTITY["head_sha"],
         "--rdx-source-sha", IDENTITY["rdx_source_sha"],
         "--tea-source-sha", IDENTITY["tea_source_sha"],
         "--rust-scope", "true"],
        capture_output=True, text=True, env=_clean_env(), check=False,
    )


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ==================================================== G-W3-DETERMINISM / G-DET
def test_w3_determinism_two_processes_bundle_and_manifest_identical(tmp_path):
    """Run the production prepare CLI in two independent OS processes with
    NO ``RDX_TEA_FAKE_NOW`` injection; the bundle AND the manifest bytes
    must be byte-identical (G-W3-DETERMINISM)."""
    project = _rust_project(tmp_path / "proj")
    diff_p = project / "_bmad-run" / "diff.patch"
    project.joinpath("_bmad-run").mkdir(exist_ok=True)
    diff_p.write_text(ASYNC_DIFF, encoding="utf-8")

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    r1 = _run_prepare_cli(project, "test-design", diff_p, "det-0001", out1)
    r2 = _run_prepare_cli(project, "test-design", diff_p, "det-0001", out2)
    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr

    b1 = (out1 / "active-context.md").read_bytes()
    b2 = (out2 / "active-context.md").read_bytes()
    m1 = (out1 / "run-manifest.json").read_bytes()
    m2 = (out2 / "run-manifest.json").read_bytes()
    assert _sha(b1) == _sha(b2), "bundle bytes differ across processes"
    assert _sha(m1) == _sha(m2), "manifest bytes differ across processes"

    # The manifest must NOT carry a wall-clock value.
    manifest = json.loads(m1)
    assert manifest["prepared_at"] == "", (
        f"prepare stamped a wall-clock prepared_at: {manifest['prepared_at']!r}"
    )


def test_w3_determinism_prepare_source_has_no_wallclock():
    """Belt-and-suspenders for G-DET: the generator source contains no
    wall-clock / randomness call."""
    src = PREPARE_CLI.read_text(encoding="utf-8")
    for banned in ("datetime.now", "time.time(", "time.monotonic",
                   "perf_counter", "random.", "os.urandom", "uuid."):
        assert banned not in src, f"prepare.py uses non-deterministic {banned!r}"


def test_w3_determinism_in_process_repeatable(tmp_path):
    project = _rust_project(tmp_path / "proj")
    m1 = _prepare(project, "test-design", ASYNC_DIFF, "rep-01", rust_scope=True)
    m2 = _prepare(project, "test-design", ASYNC_DIFF, "rep-01", rust_scope=True)
    assert m1 == m2
    assert m1["bundle_sha256"] == m2["bundle_sha256"]


# ==================================================== G-W3-IDENTITY
@pytest.mark.parametrize("drop", ["base_sha", "head_sha",
                                  "rdx_source_sha", "tea_source_sha"])
def test_w3_identity_missing_mandatory_sha_fails_closed(tmp_path, drop):
    project = _rust_project(tmp_path / "proj")
    ident = dict(IDENTITY)
    ident[drop] = ""
    with pytest.raises(prepare_mod.PrepareError):
        _prepare(project, "test-design", ASYNC_DIFF, "id-miss",
                 rust_scope=True, identity=ident)


@pytest.mark.parametrize("field", ["base_sha", "head_sha",
                                   "rdx_source_sha", "tea_source_sha"])
def test_w3_identity_all_zero_sha_rejected(tmp_path, field):
    project = _rust_project(tmp_path / "proj")
    ident = dict(IDENTITY)
    ident[field] = "0" * 40
    with pytest.raises(prepare_mod.PrepareError, match="all-zero"):
        _prepare(project, "test-design", ASYNC_DIFF, "id-zero",
                 rust_scope=True, identity=ident)


def test_w3_identity_nonhex_sha_rejected(tmp_path):
    project = _rust_project(tmp_path / "proj")
    ident = dict(IDENTITY)
    ident["base_sha"] = "Z" * 40  # non-hex
    with pytest.raises(prepare_mod.PrepareError, match="40-hex"):
        _prepare(project, "test-design", ASYNC_DIFF, "id-nonhex",
                 rust_scope=True, identity=ident)


def test_w3_identity_diff_digest_mismatch_refused(tmp_path):
    project = _rust_project(tmp_path / "proj")
    ident = dict(IDENTITY)
    ident["diff_digest"] = "d" * 64  # wrong but well-formed digest
    with pytest.raises(prepare_mod.PrepareError, match="diff_digest"):
        _prepare(project, "test-design", ASYNC_DIFF, "id-dd",
                 rust_scope=True, identity=ident)


def test_w3_identity_diff_digest_empty_is_computed_and_stamped(tmp_path):
    project = _rust_project(tmp_path / "proj")
    m = _prepare(project, "test-design", ASYNC_DIFF, "id-dd-ok", rust_scope=True)
    expected = hashlib.sha256(ASYNC_DIFF.encode("utf-8")).hexdigest()
    assert m["identity"]["diff_digest"] == expected


def test_w3_identity_matching_diff_digest_accepted(tmp_path):
    project = _rust_project(tmp_path / "proj")
    ident = dict(IDENTITY)
    ident["diff_digest"] = hashlib.sha256(ASYNC_DIFF.encode("utf-8")).hexdigest()
    m = _prepare(project, "test-design", ASYNC_DIFF, "id-dd-match",
                 rust_scope=True, identity=ident)
    assert m["identity"]["diff_digest"] == ident["diff_digest"]


# ==================================================== G-W3-SCHEMA
def _sidecar_from_binder(project: Path, workflow: str, run_id: str) -> dict:
    """Drive the production binder against a fake artefact to obtain the
    real sidecar the way the finalize path does."""
    artifacts = project / "_bmad-output" / "test-artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    art = artifacts / "test-design.md"
    art.write_text("# generated test design\n", encoding="utf-8")
    return binder_mod.bind(project_root=project, workflow=workflow,
                           artifact=art, run_id=run_id,
                           declared_output_roots=[artifacts])


def test_w3_schema_binder_sidecar_validates_against_rdx_tea_run_v1(tmp_path):
    project = _rust_project(tmp_path / "proj")
    _prepare(project, "test-design", ASYNC_DIFF, "sc-01", rust_scope=True)
    sidecar = _sidecar_from_binder(project, "test-design", "sc-01")
    jsonschema.validate(instance=sidecar, schema=SCHEMA)


def test_w3_schema_manifest_fields_conform(tmp_path):
    """The run-manifest carries the identity + pack fields the sidecar is
    built from; each must satisfy the rdx-tea-run.v1 field constraints."""
    project = _rust_project(tmp_path / "proj")
    m = _prepare(project, "test-design", ASYNC_DIFF, "sc-fields", rust_scope=True)
    assert m["schema_version"] == "rdx-tea-run.v1"
    assert m["execution_mode"] == "sequential"
    wf_enum = SCHEMA["properties"]["workflow"]["enum"]
    assert m["workflow"] in wf_enum
    pack_enum = (SCHEMA["properties"]["active_packs"]["items"]
                 ["properties"]["pack_id"]["enum"])
    rule_pat = re.compile(r"^(CORE|RP-[A-Z]+|GOV)-\d{3}$")
    for p in m["active_packs"]:
        assert p["pack_id"] in pack_enum, p["pack_id"]
        for rid in p["rule_ids"]:
            assert rule_pat.match(rid), rid
    idn = m["identity"]
    for k in ("base_sha", "head_sha", "rdx_source_sha", "tea_source_sha"):
        assert re.match(r"^[0-9a-f]{40}$", idn[k]), (k, idn[k])
    assert re.match(r"^[0-9a-f]{64}$", idn["diff_digest"])
    core_pat = re.compile(r"^CORE-\d{3}$")
    for rid in m["core_rules"]:
        assert core_pat.match(rid), rid


def test_w3_schema_docs_only_diff_yields_empty_bundle_all_core_workflow(tmp_path):
    """`test-design` has core_rules=True ("all"). A docs-only diff inside a
    Rust repo must STILL yield an empty bundle (rust_scope=False), no packs,
    no CORE dump — and remain schema-valid at bind time."""
    project = _rust_project(tmp_path / "proj")
    m = _prepare(project, "test-design", DOCS_ONLY_DIFF, "docs-01",
                 rust_scope=None)
    assert m["rust_scope"] is False
    assert m["active_packs"] == []
    assert m["core_rules"] == []
    body = (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
            / "docs-01" / "active-context.md").read_text(encoding="utf-8")
    assert "_No RDX pack activated" in body
    # Even an empty-bundle run binds a schema-valid sidecar.
    sidecar = _sidecar_from_binder(project, "test-design", "docs-01")
    jsonschema.validate(instance=sidecar, schema=SCHEMA)
    assert sidecar["active_packs"] == []


def test_w3_schema_explicit_rust_scope_false_empty_even_for_all_core(tmp_path):
    project = _rust_project(tmp_path / "proj")
    m = _prepare(project, "test-design", ASYNC_DIFF, "scope-off",
                 rust_scope=False)
    assert m["rust_scope"] is False
    assert m["active_packs"] == []
    assert m["core_rules"] == []


# ==================================================== field filtering
def _field_header(field: str) -> str:
    return f"**{prepare_mod._rule_pretty_field(field)}:**"


def test_w3_field_filtering_restricted_workflow(tmp_path):
    """`automate` allows only {rule, validation, exceptions}. The bundle
    must emit those field headers and NONE of the excluded ones, even
    though the underlying rule IR carries every field."""
    project = _rust_project(tmp_path / "proj")
    _prepare(project, "automate", ASYNC_DIFF, "ff-01", rust_scope=True)
    body = (project / "_bmad" / "rdx-tea" / "runtime" / "automate"
            / "ff-01" / "active-context.md").read_text(encoding="utf-8")
    allowed = obligation.fields_allowed("automate")
    excluded = obligation.ALL_FIELDS - allowed
    # A pack rule is present, so at least one allowed header appears.
    assert _field_header("rule") in body
    for f in excluded:
        assert _field_header(f) not in body, (
            f"excluded field {f!r} leaked into automate bundle"
        )


def test_w3_field_filtering_full_workflow_carries_context(tmp_path):
    """`test-design` uses FULL_FIELDS — trigger/risk/sources context is
    present (contrast with the restricted workflow above)."""
    project = _rust_project(tmp_path / "proj")
    _prepare(project, "test-design", ASYNC_DIFF, "ff-full", rust_scope=True)
    body = (project / "_bmad" / "rdx-tea" / "runtime" / "test-design"
            / "ff-full" / "active-context.md").read_text(encoding="utf-8")
    for f in ("trigger", "risk"):
        assert _field_header(f) in body, f"full workflow missing {f!r} header"


# ==================================================== golden bundle hashes
def test_w3_golden_bundle_signature_matches_pin():
    """The pinned clock-free golden signature (bundle + manifest sha per
    scenario) must recompute exactly — G-W3-DETERMINISM / G-DET."""
    gold = RDX_TEA_DIR / "evidence" / "hashes" / "w3_bundle_golden.py"
    r = subprocess.run([str(VENV_PY), str(gold)], capture_output=True,
                       text=True, env=_clean_env(), check=False)
    assert r.returncode == 0, f"golden drift:\n{r.stdout}\n{r.stderr}"


# ==================================================== schema authority
def test_w3_schema_authority_canonical_is_mirror_of_architecture():
    """W3 decision: ``canonical/`` is the authoritative shipped copy;
    ``architecture/`` is a byte-identical mirror. Guard against drift."""
    assert SCHEMA_CANONICAL.read_bytes() == SCHEMA_MIRROR.read_bytes(), (
        "canonical/rdx-tea-run.v1.schema.json and its architecture/ mirror "
        "have diverged — re-sync the mirror to the shipped canonical copy"
    )
