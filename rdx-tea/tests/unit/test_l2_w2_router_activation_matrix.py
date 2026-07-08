"""W2 — Rule KB & router hardening (knowledge plane).

Locks in the Wave-2 invariants against the PRODUCTION install-tree runtime
(`poc/install-tree/_bmad/rdx-tea/`). Nothing here imports `live-harness`
or `evals`; the criteria-v1 scenarios are reproduced as literal, inline
diff fixtures so the suite is self-contained and deterministic.

Gates:
  * G-W2-PARITY   — (router ∩ obligation-matrix) == prepare's emitted
                    packs, EXACT set equality on every fixture. No subset
                    slack. Cross-checked against RDX `rdx_validator.router`
                    (no logic fork).
  * G-W2-FORBIDDEN— forbidden packs judged by the ACTIVE packs' projected
                    rule_ids (the manifest), NEVER by scanning prose;
                    docs-only activates `[]`; the over-broad `**/*.rs`
                    path glob never activates every pack.
  * G-W2-CANON    — canonical snapshot hash matches the pin in
                    `evidence/hashes/w2_canonical_snapshot.txt`.

Expected active packs per criteria v1
(`evals/D3_4_RULE_OPERATION_CRITERIA.v1.yaml`): `[async]`, `[api, async]`,
`[]`.
"""

from __future__ import annotations

import ast
import importlib
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

RDX_TEA_DIR = Path(__file__).resolve().parents[2]          # rdx-tea/
REPO_ROOT = RDX_TEA_DIR.parent                             # Rust_bmad_dev/
INSTALL_SCRIPTS = RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"
INSTALL_ROUTER_PY = INSTALL_SCRIPTS / "router.py"
INSTALL_ROUTER_RULES = (
    RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea"
    / "canonical" / "router-rules.json"
)
RDX_VALIDATOR_DIR = REPO_ROOT / "rdx-validator"
RDX_VALIDATOR_ROUTER_PY = RDX_VALIDATOR_DIR / "rdx_validator" / "router.py"
PIN_FILE = RDX_TEA_DIR / "evidence" / "hashes" / "w2_canonical_snapshot.txt"


# --------------------------------------------------------------- module load
def _load_install_runtime():
    """Import the PRODUCTION install-tree prepare/router/obligation_matrix.

    Fresh import guarantees `rdx_parser.CANONICAL_ROOT` resolves to the
    install-tree `canonical/` (candidate #2 in `_locate_canonical_root`),
    i.e. the shipped source of truth — never the dev-tree view.
    """
    if str(INSTALL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(INSTALL_SCRIPTS))
    for mod in ("rdx_parser", "prepare", "router", "obligation_matrix", "diff"):
        sys.modules.pop(mod, None)
    prepare = importlib.import_module("prepare")
    router = importlib.import_module("router")
    obligation_matrix = importlib.import_module("obligation_matrix")
    return prepare, router, obligation_matrix


prepare_mod, router_mod, obligation_mod = _load_install_runtime()


DEFAULT_IDENTITY = {
    "base_sha": "1" * 40,
    "head_sha": "2" * 40,
    "diff_digest": "",  # computed by prepare
    "rdx_source_sha": "d8140a25f8166bf0ca5ce5fc19f7cb1bd06a3d6d",
    "tea_source_sha": "8734d51f24071ddbcb3617390b5fcddb4128ef77",
}


# -------------------------------------------------------- criteria-v1 fixtures
# Inline diffs reproduce the three D3.4 rule-operation criteria scenarios.
# (fixture names in the yaml: test-design-async-latent, atdd-api-async-latent,
#  docs-only-rust-repo-control.)

DIFF_ASYNC = (
    "diff --git a/src/lib.rs b/src/lib.rs\n"
    "--- a/src/lib.rs\n"
    "+++ b/src/lib.rs\n"
    "@@ -0,0 +1,3 @@\n"
    "+pub async fn run() {\n"
    "+    tokio::spawn(async {}).await;\n"
    "+}\n"
)

DIFF_API_ASYNC = (
    "diff --git a/src/lib.rs b/src/lib.rs\n"
    "--- a/src/lib.rs\n"
    "+++ b/src/lib.rs\n"
    "@@ -0,0 +1,4 @@\n"
    "+pub async fn run() {\n"
    "+    tokio::spawn(async {}).await;\n"
    "+}\n"
    "+pub fn public_api(x: i32) -> i32 { x + 1 }\n"
)

# Docs-only control INSIDE a Rust repo. The prose deliberately BAITS a
# prose-based classifier: it names `tokio::spawn` and `pub fn`, which would
# activate async/api if activation were judged from text. It must not.
DIFF_DOCS_ONLY = (
    "diff --git a/README.md b/README.md\n"
    "--- a/README.md\n"
    "+++ b/README.md\n"
    "@@ -0,0 +1,2 @@\n"
    "+# Notes\n"
    "+This crate uses `tokio::spawn` and exposes a `pub fn` API (prose only).\n"
)
PROSE_BAIT_TOKENS = ("tokio::spawn", "pub fn")


@dataclass(frozen=True)
class Scenario:
    name: str
    workflow: str
    diff: str
    tags: tuple[str, ...]
    expected_packs: frozenset[str]
    forbidden_prefixes: tuple[str, ...]
    required_all_of: tuple[str, ...] = field(default_factory=tuple)
    required_any_of: tuple[str, ...] = field(default_factory=tuple)


SCENARIOS = [
    Scenario(
        name="test-design-async",
        workflow="test-design",
        diff=DIFF_ASYNC,
        tags=(),
        expected_packs=frozenset({"async"}),
        forbidden_prefixes=("RP-UNSAFE-", "RP-FFI-", "RP-MACRO-", "RP-CARGO-"),
        required_all_of=("RP-ASYNC-005",),
    ),
    Scenario(
        name="atdd-api-async-corrected",
        workflow="atdd",
        diff=DIFF_API_ASYNC,
        tags=("publish=true",),
        expected_packs=frozenset({"api", "async"}),
        forbidden_prefixes=("RP-UNSAFE-", "RP-FFI-", "RP-MACRO-"),
        required_all_of=("RP-ASYNC-005",),
        required_any_of=("RP-API-001", "RP-API-004", "RP-API-005"),
    ),
    Scenario(
        name="docs-only-rust-repo",
        workflow="test-design",
        diff=DIFF_DOCS_ONLY,
        tags=(),
        expected_packs=frozenset(),
        forbidden_prefixes=("RP-",),  # a docs-only control must not activate ANY RDX rule
    ),
]
SCENARIO_IDS = [s.name for s in SCENARIOS]


# -------------------------------------------------------------------- helpers
def _run_prepare(tmp_path: Path, scenario: Scenario) -> dict:
    """Run the PRODUCTION prepare with autodetected rust_scope.

    A `Cargo.toml` makes the project a Rust repo so the docs-only control
    genuinely exercises the diff-relevance scope gate (docs-only → False).
    """
    proj = tmp_path / scenario.name
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "Cargo.toml").write_text("[package]\nname='p'\nversion='0'\n", encoding="utf-8")
    diff_p = proj / "diff.patch"
    diff_p.write_text(scenario.diff, encoding="utf-8")
    tags_p = None
    if scenario.tags:
        tags_p = proj / "tags.txt"
        tags_p.write_text("\n".join(scenario.tags) + "\n", encoding="utf-8")
    return prepare_mod.prepare(
        project_root=proj,
        workflow=scenario.workflow,
        identity=dict(DEFAULT_IDENTITY),
        run_id="w2-run-0001",
        diff_path=diff_p,
        tags_path=tags_p,
        rust_scope=None,  # autodetect — exercises the real scope gate
    )


def _emitted_packs(manifest: dict) -> set[str]:
    return {p["pack_id"] for p in manifest["active_packs"]}


def _active_rule_ids(manifest: dict) -> list[str]:
    """Every rule id projected by the ACTIVE packs (the machine truth the
    forbidden check judges — NOT the bundle prose)."""
    return [rid for p in manifest["active_packs"] for rid in p["rule_ids"]]


def _router_intersect_matrix(scenario: Scenario) -> set[str]:
    router = prepare_mod._load_router()
    active = set(router_mod.activated_pack_names(
        router_mod.replay(scenario.diff, router, list(scenario.tags))
    ))
    return active & obligation_mod.matrix_for(scenario.workflow)["packs"]


# =====================================================================
# G-W2-PARITY — exact set equality, all fixtures, no subset slack.
# =====================================================================
@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_w2_router_parity_exact_set_equality(tmp_path: Path, scenario: Scenario) -> None:
    manifest = _run_prepare(tmp_path, scenario)
    emitted = _emitted_packs(manifest)
    intersect = _router_intersect_matrix(scenario)
    # Three-way exact equality: what prepare emits == what the router-∩-matrix
    # says == what criteria v1 precommitted. `==` (not `<=`) — no slack.
    assert emitted == intersect, (
        f"[{scenario.name}] parity break: emitted={sorted(emitted)} "
        f"!= router∩matrix={sorted(intersect)}"
    )
    assert emitted == set(scenario.expected_packs), (
        f"[{scenario.name}] emitted {sorted(emitted)} != criteria-v1 "
        f"expected {sorted(scenario.expected_packs)}"
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_w2_required_rules_projected(tmp_path: Path, scenario: Scenario) -> None:
    """Criteria-v1 required_rule_conditions are actually projected into the
    ACTIVE packs (rule-operation is proven by projection, not prose)."""
    manifest = _run_prepare(tmp_path, scenario)
    rule_ids = set(_active_rule_ids(manifest))
    for rid in scenario.required_all_of:
        assert rid in rule_ids, f"[{scenario.name}] required all_of {rid} not projected"
    if scenario.required_any_of:
        assert rule_ids & set(scenario.required_any_of), (
            f"[{scenario.name}] none of any_of {scenario.required_any_of} projected"
        )


# =====================================================================
# G-W2-FORBIDDEN — judged by ACTIVE packs' rule_ids, never prose.
# =====================================================================
@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_w2_forbidden_judged_by_active_packs(tmp_path: Path, scenario: Scenario) -> None:
    manifest = _run_prepare(tmp_path, scenario)
    rule_ids = _active_rule_ids(manifest)
    for rid in rule_ids:
        for bad in scenario.forbidden_prefixes:
            assert not rid.startswith(bad), (
                f"[{scenario.name}] forbidden prefix {bad} leaked via ACTIVE "
                f"pack rule id {rid}"
            )


def test_w2_docs_only_activates_empty(tmp_path: Path) -> None:
    """Docs-only control: `[]` packs, `[]` rule ids — even though the prose
    NAMES code tokens (prose-bait). Proves forbidden `[RP-]` holds because
    judgment is by active packs, not text."""
    scenario = next(s for s in SCENARIOS if s.name == "docs-only-rust-repo")
    # Sanity: the bait tokens really are present in the diff text.
    for tok in PROSE_BAIT_TOKENS:
        assert tok in scenario.diff, f"prose-bait token {tok} missing from fixture"
    manifest = _run_prepare(tmp_path, scenario)
    assert manifest["rust_scope"] is False, "docs-only diff must be scoped out"
    assert _emitted_packs(manifest) == set(), "docs-only must activate no pack"
    assert _active_rule_ids(manifest) == [], "docs-only must project no RP- rule id"


# =====================================================================
# Over-broad `**/*.rs` guard — must not activate every pack.
# =====================================================================
def test_w2_over_broad_rs_glob_guard_holds() -> None:
    """A bare `.rs` edit with NO positive code signal activates NOTHING.

    Negative control: at least two packs DO carry the bare `**/*.rs` path
    glob, so the guard is load-bearing — without the skip in `router.py`
    every Rust file change would activate all of them.
    """
    router = prepare_mod._load_router()
    rs_glob_packs = {
        name for name, pack in router.packs.items()
        if "**/*.rs" in (pack.get("path_signals") or [])
    }
    assert len(rs_glob_packs) >= 2, (
        f"expected multiple packs to carry the over-broad **/*.rs glob, "
        f"got {sorted(rs_glob_packs)}"
    )
    bare_rs = (
        "diff --git a/src/thing.rs b/src/thing.rs\n"
        "--- a/src/thing.rs\n"
        "+++ b/src/thing.rs\n"
        "@@ -0,0 +1,3 @@\n"
        "+fn add(a: i32, b: i32) -> i32 {\n"
        "+    a + b\n"
        "+}\n"
    )
    active = set(router_mod.activated_pack_names(router_mod.replay(bare_rs, router, [])))
    assert active == set(), (
        f"over-broad **/*.rs guard failed: bare .rs edit activated {sorted(active)}"
    )


def test_w2_bare_rs_path_glob_is_skipped_in_source() -> None:
    """The guard is present in the router source (defence in depth)."""
    src = INSTALL_ROUTER_PY.read_text(encoding="utf-8")
    assert '== "**/*.rs"' in src and "continue" in src, (
        "router.py must explicitly skip the over-broad '**/*.rs' path glob"
    )


# =====================================================================
# Per-pack × signal activation matrix — KB signal wiring is deterministic.
# =====================================================================
def _rs_diff(path: str, lines: list[str]) -> str:
    body = "".join("+" + ln + "\n" for ln in lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        f"{body}"
    )


# (pack, path, representative positive signal line, required story tags)
PACK_MATRIX = [
    ("async", "src/a.rs", "async fn f() {}", []),
    ("unsafe", "src/u.rs", "unsafe fn f() {}", []),
    ("ffi", "src/f.rs", 'extern "C" fn c() {}', []),
    ("macro", "src/m.rs", "macro_rules! m { () => {} }", []),
    ("api", "src/lib.rs", "pub fn p() -> i32 { 0 }", ["publish=true"]),
    ("cargo", "Cargo.toml", "[features]", []),
    ("testing", "src/t.rs", "let _ = proptest;", ["fuzz-required"]),
    ("data-security-io", "src/d.rs", "use serde_json;", []),
    ("db", "src/db.rs", 'let r = sqlx::query("SELECT 1");', []),
    ("time-config-client", "src/tc.rs", "let _ = Instant::now();", []),
    ("ops", "src/o.rs", 'tracing::info!("x");', ["production-service"]),
    ("perf", "src/p.rs", "criterion::black_box(1);", ["perf-budget"]),
]
PACK_MATRIX_IDS = [row[0] for row in PACK_MATRIX]


@pytest.mark.parametrize("pack,path,signal,tags", PACK_MATRIX, ids=PACK_MATRIX_IDS)
def test_w2_pack_activation_matrix(pack: str, path: str, signal: str, tags: list[str]) -> None:
    """Every KB pack activates on its representative signal (with its
    required story tag, where the policy is STORY_TAG_REQUIRED)."""
    router = prepare_mod._load_router()
    diff = _rs_diff(path, [signal])
    active = set(router_mod.activated_pack_names(router_mod.replay(diff, router, tags)))
    assert pack in active, (
        f"pack {pack!r} did not activate on signal {signal!r} (active={sorted(active)})"
    )


def test_w2_story_tag_required_pack_gated() -> None:
    """STORY_TAG_REQUIRED packs (api) do NOT activate without the tag —
    no `or True` escape hatch."""
    router = prepare_mod._load_router()
    diff = _rs_diff("src/lib.rs", ["pub fn p() -> i32 { 0 }"])
    without = set(router_mod.activated_pack_names(router_mod.replay(diff, router, [])))
    with_tag = set(router_mod.activated_pack_names(router_mod.replay(diff, router, ["publish=true"])))
    assert "api" not in without, f"api must NOT activate without a story tag: {sorted(without)}"
    assert "api" in with_tag, f"api MUST activate with story tag: {sorted(with_tag)}"


# =====================================================================
# No router fork from RDX.
# =====================================================================
def _logic_only(src: str) -> str:
    """AST dump with the module docstring + import statements removed.

    The vendored install-tree router differs from RDX `rdx_validator/router.py`
    ONLY in its docstring and an import-compat shim (`try/except ImportError`
    for the flat vendored layout). Stripping docstring + Import/ImportFrom/Try
    top-level nodes leaves the pure logic, which must be byte-identical.
    """
    tree = ast.parse(src)
    body = [
        n for n in tree.body
        if not (
            isinstance(n, ast.Expr)
            and isinstance(getattr(n, "value", None), ast.Constant)
            and isinstance(n.value.value, str)
        )
        and not isinstance(n, (ast.Import, ast.ImportFrom, ast.Try))
    ]
    return ast.dump(ast.Module(body=body, type_ignores=[]))


def test_w2_router_no_logic_fork_from_rdx() -> None:
    assert RDX_VALIDATOR_ROUTER_PY.exists(), "RDX rdx_validator/router.py missing"
    install_logic = _logic_only(INSTALL_ROUTER_PY.read_text(encoding="utf-8"))
    rdx_logic = _logic_only(RDX_VALIDATOR_ROUTER_PY.read_text(encoding="utf-8"))
    assert install_logic == rdx_logic, (
        "vendored install-tree router.py has forked from RDX "
        "rdx_validator/router.py (logic differs beyond docstring/imports)"
    )


def test_w2_router_no_behavioural_fork_from_rdx() -> None:
    """Behavioural cross-check: RDX's own router produces identical active
    packs to the install-tree router on every scenario diff."""
    if str(RDX_VALIDATOR_DIR) not in sys.path:
        sys.path.insert(0, str(RDX_VALIDATOR_DIR))
    from rdx_validator.router import (  # noqa: E402
        RouterRules as VRRouterRules,
        activated_pack_names as vr_activated,
        replay as vr_replay,
    )
    install_router = prepare_mod._load_router()
    rdx_router = VRRouterRules.load(INSTALL_ROUTER_RULES)
    for scenario in SCENARIOS:
        install_active = set(router_mod.activated_pack_names(
            router_mod.replay(scenario.diff, install_router, list(scenario.tags))
        ))
        rdx_active = set(vr_activated(
            vr_replay(scenario.diff, rdx_router, list(scenario.tags))
        ))
        assert install_active == rdx_active, (
            f"[{scenario.name}] behavioural fork: install={sorted(install_active)} "
            f"vs rdx_validator={sorted(rdx_active)}"
        )


# =====================================================================
# G-W2-CANON — canonical snapshot hash pinned.
# =====================================================================
def _read_pinned_hash() -> str:
    assert PIN_FILE.exists(), f"canonical snapshot pin missing: {PIN_FILE}"
    text = PIN_FILE.read_text(encoding="utf-8")
    m = re.search(r"\b([0-9a-f]{64})\b", text)
    assert m, f"no 64-hex sha256 found in pin file {PIN_FILE}"
    return m.group(1)


def test_w2_canonical_snapshot_hash_pinned() -> None:
    recomputed = prepare_mod._canonical_snapshot_hash()
    pinned = _read_pinned_hash()
    assert recomputed == pinned, (
        f"canonical snapshot hash drift: recomputed={recomputed} != pinned={pinned}. "
        f"Any canonical/ change REQUIRES a source-lock re-pin + SOURCE_LOCK addendum."
    )


def test_w2_manifest_stamps_pinned_canonical_snapshot(tmp_path: Path) -> None:
    """The value prepare stamps into every manifest is the pinned hash."""
    manifest = _run_prepare(tmp_path, SCENARIOS[0])
    assert manifest["rdx_canonical_snapshot_sha256"] == _read_pinned_hash()
