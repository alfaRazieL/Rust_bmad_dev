"""rdx-validator CLI entrypoint.

CLI inputs (Phase 2):
  --project-root DIR       (default: cwd) project root containing the git repo
  --story FILE             optional story / contract JSON (supplies protected_files,
                            risk_tags, agent-claimed activated_packs, etc.)
  --base REF               base git ref (required unless --diff-file)
  --head REF               head git ref (default HEAD)
  --diff-file FILE         read diff from file instead of git
  --mode MODE              MODE_0..MODE_4
  --policy-config FILE     JSON policy file
  --evidence-in FILE       pre-recorded evidence to be re-validated
  --evidence-out FILE      write validator-produced evidence JSON here
  --dual-run               run twice (base + head) — for Phase 2 the dual-run
                            input is supplied via --story (base/head signatures)
  --validator-source       PR_HEAD|TARGET_BRANCH|PINNED_RELEASE|REUSABLE_WORKFLOW
                            recorded in evidence (default TARGET_BRANCH)

Outputs:
  - human summary to stderr
  - JSON evidence to stdout (always) and to --evidence-out (if set)
  - exit code per RDX_TEST_STRATEGY.md §5.3
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .baseline import RunResult, compare
from .checks import (
    check_core_007,
    check_core_008,
    check_core_011,
    check_core_014,
    check_core_015,
)
from .diff import compute_diff_digest, parse_diff_paths, parse_file_changes
from .policy import load as load_policy
from .router import RouterRules, replay
from .status import Aggregate, Mode, Policy, RuleVerdict, Severity, Verdict, aggregate


REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR_DEFAULT = REPO_ROOT_DEFAULT / "tests" / "contracts"


def _read_git_diff(base: str, head: str, cwd: Path) -> tuple[str | None, str | None]:
    try:
        r = subprocess.run(
            ["git", "diff", f"{base}...{head}"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None, "git not found"
    if r.returncode != 0:
        return None, r.stderr.strip() or "git diff failed"
    return r.stdout, None


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _resolve_sha(ref: str, cwd: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", ref],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _envelope(
    diff_text: str,
    story: dict,
    rules: list[RuleVerdict],
    agg: Aggregate,
    activations: list,
    head_sha: str,
    base_sha: str,
    mode: Mode,
    validator_source: str,
) -> dict:
    return {
        "rdx_schema_version": "v1",
        "story_id": story.get("story_id", "STORY-UNKNOWN"),
        "head_sha": head_sha,
        "base_sha": base_sha,
        "diff_digest": _sha(diff_text),
        "mode": mode.value,
        "router_activations": [
            {
                "pack": a.pack,
                "activation_policy": a.activation_policy,
                "active": a.active,
                "signals": list(a.signals),
                "story_tags": list(a.story_tags_present),
            }
            for a in activations
        ],
        "rules": {
            r.rule_id: _rule_finding(r) for r in rules
        },
        "exceptions": story.get("exceptions", []),
        "approvals": story.get("approvals", []),
        "aggregate": {
            "verdict": agg.verdict.value,
            "exit_code": agg.exit_code,
            "blocking_count": agg.blocking_count,
            "warning_count": agg.warning_count,
            "info_count": agg.info_count,
        },
        "validator": {
            "name": "rdx-validator",
            "version": __version__,
            "source": validator_source,
        },
        "generated_at": _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _rule_finding(r: RuleVerdict) -> dict:
    out: dict = {
        "category": r.category,
        "verdict": r.verdict.value,
        "severity": r.severity.value,
        "author": "VALIDATOR",
    }
    if r.reason:
        out["message"] = r.reason
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rdx-validator")
    p.add_argument("--project-root", default=".")
    p.add_argument("--story", default=None)
    p.add_argument("--base", default=None)
    p.add_argument("--head", default="HEAD")
    p.add_argument("--diff-file", default=None)
    p.add_argument("--mode", default="MODE_2")
    p.add_argument("--policy-config", default=None)
    p.add_argument("--evidence-in", default=None)
    p.add_argument("--evidence-out", default=None)
    p.add_argument("--dual-run", action="store_true")
    p.add_argument(
        "--baseline-data",
        default=None,
        help="JSON file with pre-recorded base/head RunResult (Phase 2 dual-run input).",
    )
    p.add_argument("--validator-source", default="TARGET_BRANCH")
    p.add_argument("--contracts-dir", default=str(CONTRACTS_DIR_DEFAULT))
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    project_root = Path(args.project_root).resolve()
    contracts_dir = Path(args.contracts_dir).resolve()

    # 1. Load contracts
    try:
        rules_def = RouterRules.load(contracts_dir / "router-rules.json")
    except OSError as e:
        print(json.dumps({"error": f"router-rules.json not loadable: {e}"}), file=sys.stderr)
        return 2

    # 2. Resolve mode & policy
    if args.policy_config:
        policy = load_policy(Path(args.policy_config))
    else:
        try:
            policy = Policy(mode=Mode(args.mode))
        except ValueError:
            print(f"unknown mode: {args.mode}", file=sys.stderr)
            return 2

    # 3. Load story
    story: dict = {}
    if args.story:
        story_path = Path(args.story)
        try:
            story = json.loads(story_path.read_text(encoding="utf-8"))
        except OSError as e:
            print(json.dumps({"error": f"story not loadable: {e}"}), file=sys.stderr)
            return 2

    # 4. Read diff
    if args.diff_file:
        diff_text = Path(args.diff_file).read_text(encoding="utf-8")
    elif args.base:
        diff_text, err = _read_git_diff(args.base, args.head, project_root)
        if diff_text is None:
            print(json.dumps({"error": err or "git diff unavailable"}), file=sys.stderr)
            return 2
    else:
        print("error: --base or --diff-file required", file=sys.stderr)
        return 2

    # 5. Pre-recorded evidence (optional)
    evidence_in: dict = {}
    if args.evidence_in:
        evidence_in = json.loads(Path(args.evidence_in).read_text(encoding="utf-8"))

    paths = parse_diff_paths(diff_text)
    changes = parse_file_changes(diff_text)
    activations = replay(
        diff_text,
        rules_def,
        story_tags=story.get("risk_tags", []),
        publish_true=story.get("publish_true"),
    )

    # 6. Run Cat-1/2 checks
    rule_verdicts: list[RuleVerdict] = []
    rule_verdicts.append(
        check_core_007(
            paths_changed=paths,
            protected_files=story.get("protected_files", []),
            authorised_exception=_exception_for(evidence_in, "CORE-007"),
        )
    )
    rule_verdicts.append(check_core_008(changes=changes, story_tags=story.get("risk_tags", [])))
    # In --dual-run mode the baseline comparator supplies the authoritative
    # CORE-011 verdict; the upstream evidence-based check would otherwise raise
    # EVIDENCE_REQUIRED whenever pre-recorded evidence is absent.
    if not (args.dual_run and args.baseline_data):
        rule_verdicts.append(
            check_core_011(
                paths_changed=paths,
                evidence_block=(evidence_in.get("rules") or {}).get("CORE-011"),
            )
        )
    rule_verdicts.append(
        check_core_014(
            changes=changes,
            authorised_exception=_exception_for(evidence_in, "CORE-014"),
        )
    )
    # CORE-015 only applies when the story records an agent claim. Without
    # one there is nothing to compare against.
    if "agent_activated_packs" in story:
        rule_verdicts.append(
            check_core_015(
                validator_activations=activations,
                agent_claimed=story.get("agent_activated_packs", []),
                documented_suppressions=story.get("router_suppressions", []),
            )
        )

    # 7. Active pack → APPROVAL_REQUIRED / REVIEW_REQUIRED translation
    rule_verdicts.extend(_pack_verdicts(activations))

    # 7b. Optional --dual-run baseline comparator (consumes pre-recorded results)
    if args.dual_run and args.baseline_data:
        rule_verdicts.append(_dual_run_verdict(Path(args.baseline_data)))

    agg = aggregate(rule_verdicts, policy)

    envelope = _envelope(
        diff_text=diff_text,
        story=story,
        rules=list(agg.by_rule.values()),
        agg=agg,
        activations=activations,
        head_sha=_resolve_sha(args.head, project_root) or _placeholder_sha(),
        base_sha=_resolve_sha(args.base, project_root) if args.base else _placeholder_sha(),
        mode=policy.mode,
        validator_source=args.validator_source,
    )

    if not args.quiet:
        sys.stdout.write(json.dumps(envelope, indent=2) + "\n")
    if args.evidence_out:
        Path(args.evidence_out).write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")

    return agg.exit_code


def _placeholder_sha() -> str:
    return "0" * 40


def _exception_for(evidence_in: dict, rule_id: str) -> bool:
    for e in evidence_in.get("exceptions") or []:
        if e.get("rule_id") == rule_id:
            return True
    return False


def _dual_run_verdict(baseline_path: Path) -> RuleVerdict:
    """Translate base/head run results into the matching baseline verdict.

    Closes the validator-side of T-L3-CRATE-003/004.
    """
    from .baseline import RunResult, compare

    data = json.loads(baseline_path.read_text(encoding="utf-8"))

    def to_run(d: dict) -> RunResult:
        return RunResult(passed=d["passed"], error_signature=d.get("error_signature"))

    base = to_run(data["base"])
    head = to_run(data["head"])
    v = compare(base, head)
    severity = Severity.BLOCKING if v == Verdict.REGRESSION_FAILURE else Severity.INFO
    return RuleVerdict(
        rule_id="CORE-011",
        category=1,
        verdict=v,
        severity=severity,
        reason=f"dual-run base.passed={base.passed} head.passed={head.passed}",
    )


def _pack_verdicts(activations) -> list[RuleVerdict]:
    """Translate router activations into per-pack rule verdicts.

    - AUTO_ACTIVATE strong pack with no escalation rule → PASS (just signals)
    - unsafe pack → RP-UNSAFE-001 APPROVAL_REQUIRED
    - ffi pack → RP-FFI-001 APPROVAL_REQUIRED
    - AUTO_SUGGEST (data, db, time) → REVIEW_REQUIRED
    - STORY_TAG_REQUIRED, active → REVIEW_REQUIRED
    - STORY_TAG_REQUIRED, suppressed → NOT_APPLICABLE
    """
    out: list[RuleVerdict] = []
    for a in activations:
        if a.pack == "unsafe" and a.active:
            out.append(
                RuleVerdict(
                    rule_id="RP-UNSAFE-001",
                    category=4,
                    verdict=Verdict.APPROVAL_REQUIRED,
                    severity=Severity.BLOCKING,
                    reason="unsafe surface added; specialist approval required",
                )
            )
            continue
        if a.pack == "ffi" and a.active:
            out.append(
                RuleVerdict(
                    rule_id="RP-FFI-001",
                    category=4,
                    verdict=Verdict.APPROVAL_REQUIRED,
                    severity=Severity.BLOCKING,
                    reason="FFI surface added; specialist approval required",
                )
            )
            continue
        if a.active and a.activation_policy == "AUTO_SUGGEST":
            out.append(
                RuleVerdict(
                    rule_id=f"RP-{a.pack.upper().replace('-', '_')}-001",
                    category=3,
                    verdict=Verdict.REVIEW_REQUIRED,
                    severity=Severity.INFO,
                    reason=f"{a.pack} pack auto-suggested",
                )
            )
            continue
        if a.active and a.activation_policy == "STORY_TAG_REQUIRED":
            out.append(
                RuleVerdict(
                    rule_id=f"RP-{a.pack.upper().replace('-', '_')}-001",
                    category=3,
                    verdict=Verdict.REVIEW_REQUIRED,
                    severity=Severity.INFO,
                    reason=f"{a.pack} pack activated by story tag",
                )
            )
            continue
    return out
