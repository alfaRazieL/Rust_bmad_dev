"""D3.3.2 §16.5 grader tests.

Cover the blinding contract (no arm/RP-ID/wrapper leakage), the layer-1
deterministic detector, and the merge stage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
GRADING = HERE.parent / "grading"
sys.path.insert(0, str(GRADING))
import grade_pilot  # noqa: E402


# ------------------------------------------------------- sanitisation

def test_sanitise_strips_rp_ids():
    text = "This case tests RP-ASYNC-005 and RP-API-001 semantics."
    out = grade_pilot.sanitise(text)
    assert "RP-ASYNC-005" not in out
    assert "RP-API-001" not in out
    assert "[RP-ID-REDACTED]" in out


def test_sanitise_strips_wrapper_names():
    text = "Invoked rdx-tea-atdd which called rdx-tea-test-design first."
    out = grade_pilot.sanitise(text)
    assert "rdx-tea-atdd" not in out
    assert "rdx-tea-test-design" not in out
    assert "wrapper-REDACTED" in out


def test_sanitise_strips_arm_path_prefixes():
    text = "See baseline/report.md or candidate/report.md for details."
    out = grade_pilot.sanitise(text)
    assert "baseline/" not in out
    assert "candidate/" not in out


def test_sanitise_zero_leakage_of_arm_words_when_present():
    """Even after sanitisation, the words 'baseline' and 'candidate'
    could survive when not followed by a slash. That is fine — the
    comparative rubric explicitly guards against arm-specific paths;
    a generic use of 'baseline' inside prose (e.g. "the baseline load
    should be less than X requests") does not identify the arm."""
    text = ("Cancellation baseline established at 100ms; candidate "
            "designs should preserve it.")
    out = grade_pilot.sanitise(text)
    assert "baseline" in out
    assert "candidate" in out


# --------------------------------------------------- prepare-blind

def test_prepare_blind_emits_samples_and_mapping(tmp_path):
    # Build a fake pilot evidence tree with two bundles.
    pilot_root = tmp_path / "pilot"
    for i, (arm, scenario) in enumerate([
        ("baseline", "test-design-async"),
        ("candidate", "test-design-async"),
    ]):
        d = pilot_root / scenario / arm / "rep-01" / f"pilot-00{i+1}"
        d.mkdir(parents=True)
        artefact = d / "artefact.md"
        artefact.write_text(
            f"# artefact for {arm}\nRP-ASYNC-005 is important.\n",
            encoding="utf-8",
        )
        (d / "live-evidence.v2.json").write_text(
            json.dumps({
                "arm": arm,
                "scenario": scenario,
                "run_id": f"pilot-00{i+1}",
                "artifacts": {"new_artefacts": [str(artefact)]},
            }),
            encoding="utf-8",
        )
    out = tmp_path / "blind"
    r = grade_pilot.prepare_blind(pilot_root, out)
    assert r["sample_count"] == 2
    samples = list((out / "samples").glob("sample-*.md"))
    assert len(samples) == 2
    for s in samples:
        content = s.read_text(encoding="utf-8")
        # Every sanitised sample must be free of arm-revealing tokens.
        assert "RP-ASYNC-005" not in content
        # And of wrapper name (there is none in this fixture, so trivially).
    mapping = json.loads((out / "mapping" / "MAPPING.json").read_text(encoding="utf-8"))
    assert len(mapping) == 2
    arms = {m["arm"] for m in mapping}
    assert arms == {"baseline", "candidate"}


# --------------------------------------------------- deterministic

def test_deterministic_layer_boolean_detectors(tmp_path):
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "sample-001.md").write_text(
        "The design uses cancellation-safe semantics and #[tokio::test].\n",
        encoding="utf-8",
    )
    out = tmp_path / "det"
    r = grade_pilot.grade_deterministic(samples, out)
    assert r["count"] == 1
    row = json.loads((out / "sample-001.det.json").read_text(encoding="utf-8"))
    assert row["metrics"]["cancellation_specificity"] is True
    assert row["metrics"]["executable_test_detail"] is True
    assert row["metrics"]["shutdown_specificity"] is False


# --------------------------------------------------- llm layer

def test_llm_layer_dry_run_emits_not_run(tmp_path):
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "sample-001.md").write_text("hello", encoding="utf-8")
    out = tmp_path / "llm"
    r = grade_pilot.grade_llm(samples, out, dry_run=True)
    assert r["dry_run"] is True
    payload = json.loads((out / "sample-001.llm.json").read_text(encoding="utf-8"))
    assert payload["status"] == "NOT_RUN"
    assert len(payload["grader_prompt_sha256"]) == 64


# --------------------------------------------------- merge disagreement

def test_merge_records_disagreements_without_overwriting(tmp_path):
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "sample-001.md").write_text(
        "cancellation-safe semantics", encoding="utf-8",
    )
    det_dir = tmp_path / "det"
    grade_pilot.grade_deterministic(samples, det_dir)
    llm_dir = tmp_path / "llm"
    llm_dir.mkdir()
    # LLM disagrees on cancellation.
    (llm_dir / "sample-001.llm.json").write_text(json.dumps({
        "sample_id": "sample-001",
        "grader_model": "claude-haiku-4-5-20251001",
        "grader_prompt_sha256": "z" * 64,
        "status": "OK",
        "metrics": {"cancellation_specificity_semantic":
                     {"verdict": False, "confidence": 0.7}},
    }), encoding="utf-8")
    mapping = tmp_path / "MAPPING.json"
    mapping.write_text(json.dumps([
        {"sample_id": "sample-001", "arm": "candidate",
         "scenario": "test-design-async", "run_id": "pilot-001"},
    ]), encoding="utf-8")
    out_dir = tmp_path / "merged"
    r = grade_pilot.merge(samples_dir=samples, mapping_path=mapping,
                          deterministic_dir=det_dir, llm_dir=llm_dir,
                          out_dir=out_dir)
    assert r["count"] == 1
    row = json.loads((out_dir / "sample-001.merged.json").read_text(encoding="utf-8"))
    # Deterministic true; LLM false → disagreement recorded, both retained.
    assert row["deterministic_metrics"]["cancellation_specificity"] is True
    assert row["llm_metrics"]["metrics"]["cancellation_specificity_semantic"]["verdict"] is False
    assert "cancellation_specificity" in row["disagreements"]


# --------------------------------------------------- mapping isolation

def test_mapping_file_marked_do_not_read(tmp_path):
    pilot_root = tmp_path / "pilot"
    pilot_root.mkdir()
    out = tmp_path / "blind"
    # Zero bundles is a valid edge case; mapping dir should still exist
    # with the DO_NOT_READ marker.
    grade_pilot.prepare_blind(pilot_root, out)
    marker = out / "mapping" / "DO_NOT_READ.txt"
    assert marker.exists()
    assert "MUST" in marker.read_text(encoding="utf-8")


# --------------------------------------------------- report is honest

def test_report_never_exceeds_inconclusive(tmp_path):
    merged = tmp_path / "merged"
    merged.mkdir()
    out = tmp_path / "report.json"
    r = grade_pilot.report(merged, out)
    assert r["verdict"] == "PILOT_INCONCLUSIVE"
    # Even with fake merged data the grader stops at INCONCLUSIVE
    # because LLM layer is NOT_RUN in D3.3.2.
    (merged / "sample-001.merged.json").write_text(json.dumps({
        "sample_id": "sample-001",
        "arm": "candidate",
        "deterministic_metrics": {"cancellation_specificity": True},
        "llm_metrics": None,
        "disagreements": [],
    }), encoding="utf-8")
    r = grade_pilot.report(merged, out)
    assert r["verdict"] == "PILOT_INCONCLUSIVE"
