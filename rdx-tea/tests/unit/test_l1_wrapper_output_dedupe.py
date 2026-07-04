"""D3.4.0 §6 — wrapper output dedupe at source.

Proves the wrapper never discovers a single artefact twice via nested
output roots, so run-report.json new_artefacts / sidecars / verifier
carry one entry per unique resolved artefact path.
"""

from __future__ import annotations

import sys
from pathlib import Path

RDX_TEA_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTS = RDX_TEA_DIR / "poc" / "install-tree" / "_bmad" / "rdx-tea" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import rdx_tea_wrapper as w  # noqa: E402


def test_canonical_roots_collapse_nested(tmp_path):
    of = tmp_path / "_bmad-output"
    ta = of / "test-artifacts"
    ta.mkdir(parents=True)
    roots = w._canonical_output_roots([ta, of])
    assert roots == [of.resolve()]


def test_delta_dedupes_nested_roots(tmp_path):
    of = tmp_path / "_bmad-output"
    ta = of / "test-artifacts"
    ta.mkdir(parents=True)
    (ta / "art.md").write_text("hello", encoding="utf-8")
    delta = w._delta_outputs({}, [ta, of])
    assert len(delta) == 1
    assert delta[0].name == "art.md"


def test_snapshot_dedupes_nested_roots(tmp_path):
    of = tmp_path / "_bmad-output"
    ta = of / "test-artifacts"
    ta.mkdir(parents=True)
    (ta / "art.md").write_text("hello", encoding="utf-8")
    inv = w._snapshot_outputs([ta, of])
    # Exactly one entry for the single artefact, not two.
    assert len(inv) == 1


def test_output_dirs_are_canonical(tmp_path):
    cfg = {
        "test_artifacts": str(tmp_path / "_bmad-output" / "test-artifacts"),
        "output_folder": str(tmp_path / "_bmad-output"),
    }
    dirs = w._output_dirs(tmp_path / ".claude", tmp_path, cfg)
    assert dirs == [(tmp_path / "_bmad-output").resolve()]


def test_delta_one_new_file_after_snapshot(tmp_path):
    of = tmp_path / "_bmad-output"
    ta = of / "test-artifacts"
    ta.mkdir(parents=True)
    (ta / "pre.md").write_text("pre", encoding="utf-8")
    pre = w._snapshot_outputs([ta, of])
    (ta / "new.md").write_text("new", encoding="utf-8")
    delta = w._delta_outputs(pre, [ta, of])
    names = sorted(p.name for p in delta)
    assert names == ["new.md"]
    # And the same artefact is never counted twice.
    assert len(delta) == len(set(str(p.resolve()) for p in delta))
