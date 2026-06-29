"""L2 router activation tests, one per fixture diff.

Closes:
  T-L2-ASYNC-001..004
  T-L2-UNSAFE-001..004 (unsafe pack activation portion)
  T-L2-FFI-001/002
  T-L2-MACRO-001/002
  T-L2-API-001/002
  T-L2-CARGO-001/002
  T-L2-TEST-001/002
  T-L2-DATA-001
  T-L2-DB-001
  T-L2-TIME-001
  T-L2-OPS-001/002
  T-L2-PERF-001/002

Per-fixture expectations:
  fixture path → (pack name, must_be_active, story_tags, publish_true|None)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdx_validator.router import RouterRules, activated_pack_names, replay


_CASES = [
    # ASYNC pack — strong, AUTO_ACTIVATE
    ("diffs/async/positive-tokio-spawn.diff", "async", True, (), None),
    ("diffs/async/positive-async-fn-signature.diff", "async", True, (), None),
    ("diffs/async/negative-doc-only.diff", "async", False, (), None),
    ("diffs/async/negative-rename-only.diff", "async", False, (), None),
    # UNSAFE pack — strong, AUTO_ACTIVATE
    ("diffs/unsafe/positive-new-unsafe-block.diff", "unsafe", True, (), None),
    ("diffs/unsafe/negative-doc-mention.diff", "unsafe", False, (), None),
    ("diffs/unsafe/positive-with-safety-comment.diff", "unsafe", True, (), None),
    ("diffs/unsafe/negative-no-safety-comment.diff", "unsafe", True, (), None),
    # FFI pack
    ("diffs/ffi/positive-extern-c.diff", "ffi", True, (), None),
    ("diffs/ffi/positive-cdylib-cargo.diff", "ffi", True, (), None),
    ("diffs/ffi/negative-doc-only.diff", "ffi", False, (), None),
    # MACRO pack
    ("diffs/macro/positive-macro-rules.diff", "macro", True, (), None),
    ("diffs/macro/positive-build-rs.diff", "macro", True, (), None),
    ("diffs/macro/negative-doc-only.diff", "macro", False, (), None),
    # API pack — STORY_TAG_REQUIRED (story tag must allow activation)
    ("diffs/api/positive-pub-fn-lib.diff", "api", True, ("publish=true",), True),
    ("diffs/api/negative-pub-fn-binary.diff", "api", False, (), False),
    # CARGO pack — AUTO_ACTIVATE on Cargo.toml / toolchain
    ("diffs/cargo/positive-add-dep.diff", "cargo", True, (), None),
    ("diffs/cargo/positive-toolchain-change.diff", "cargo", True, (), None),
    # TESTING pack — STORY_TAG_REQUIRED
    ("diffs/test-pack/positive-no-tag.diff", "testing", False, (), None),
    ("diffs/test-pack/positive-with-tag.diff", "testing", True, ("high-assurance",), None),
    # DATA pack — AUTO_SUGGEST
    ("diffs/data/positive-serde-dto.diff", "data-security-io", True, (), None),
    ("diffs/data/negative-doc-only.diff", "data-security-io", False, (), None),
    # DB pack — AUTO_SUGGEST
    ("diffs/db/positive-new-migration.diff", "db", True, (), None),
    ("diffs/db/negative-doc-only.diff", "db", False, (), None),
    # TIME pack — AUTO_SUGGEST
    ("diffs/time/positive-instant-now.diff", "time-config-client", True, (), None),
    ("diffs/time/negative-doc-only.diff", "time-config-client", False, (), None),
    # OPS pack — STORY_TAG_REQUIRED
    ("diffs/ops/positive-tracing-no-tag.diff", "ops", False, (), None),
    ("diffs/ops/positive-tracing-with-tag.diff", "ops", True, ("ops",), None),
    # PERF pack — STORY_TAG_REQUIRED
    ("diffs/perf/positive-no-std.diff", "perf", True, ("no_std",), None),
    ("diffs/perf/negative-micro-opt-no-tag.diff", "perf", False, (), None),
]


@pytest.fixture(scope="module")
def router_rules(contracts_dir: Path) -> RouterRules:
    return RouterRules.load(contracts_dir / "router-rules.json")


@pytest.mark.parametrize("fixture,pack,active,tags,publish", _CASES, ids=[c[0] for c in _CASES])
def test_l2_router_pack_activation(
    fixtures_dir: Path,
    router_rules: RouterRules,
    fixture: str,
    pack: str,
    active: bool,
    tags: tuple[str, ...],
    publish: bool | None,
):
    diff = (fixtures_dir / fixture).read_text(encoding="utf-8")
    activations = replay(diff, router_rules, story_tags=tags, publish_true=publish)
    activated = activated_pack_names(activations)
    if active:
        assert pack in activated, (
            f"{fixture}: expected pack '{pack}' active; got {activated}"
        )
    else:
        assert pack not in activated, (
            f"{fixture}: expected pack '{pack}' NOT active; got {activated}"
        )
