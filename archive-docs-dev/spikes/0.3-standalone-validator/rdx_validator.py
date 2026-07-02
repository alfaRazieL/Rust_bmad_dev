#!/usr/bin/env python3
"""
rdx-validator — Phase 0.3 prototype.

Standalone CLI for RDX deterministic checks. No BMAD imports.

This prototype demonstrates:
  - git diff parsing (paths, hunks, added lines)
  - diff_digest computation
  - Risk Router replay over a small inline rule set
  - Structured JSON verdict output
  - Stable exit codes

Stable exit codes:
   0 = PASS or all checks NOT_APPLICABLE
   1 = FAIL (blocking finding)
   2 = ENVIRONMENT_UNAVAILABLE (git missing, not a repo, etc.)
   3 = NOT_RUN with insufficient reason (e.g., required tool missing)

CLI:
    python3 rdx_validator.py --base <ref> --head <ref> [--evidence-out FILE]
    python3 rdx_validator.py --diff-file FILE     (read pre-prepared diff for testing)

This prototype is intentionally minimal. Production version will add:
    - full Top-5 Cat-1 checks (CORE-007/011/014/008)
    - schema-validated evidence
    - base/head dual-run for baseline/regression
    - exception parsing
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


PROTOTYPE_VERSION = "0.3.0-spike"

# Minimal inline router rules. Production will load from router-rules.json.
ROUTER_RULES = {
    "async": {
        "positive_signals": [
            r"\basync\s+fn\b",
            r"\.await\b",
            r"tokio::spawn",
            r"\bJoinHandle\b",
            r"\bselect!\s*\{",
        ],
        "path_signals": [],
        "negative_signals": [
            # comments and doc lines that mention async without actually using it
        ],
        "activation_policy": "AUTO_ACTIVATE",
    },
    "unsafe": {
        "positive_signals": [
            r"\bunsafe\s*\{",
            r"\bunsafe\s+fn\b",
            r"\bunsafe\s+impl\b",
            r"\bMaybeUninit\b",
            r"\btransmute\b",
            r"\bNonNull\b",
        ],
        "path_signals": [],
        "negative_signals": [],
        "activation_policy": "AUTO_ACTIVATE",
    },
    "ffi": {
        "positive_signals": [
            r'extern\s+"C"',
            r"#\[no_mangle\]",
            r"#\[export_name",
        ],
        "path_signals": [r"\.h$"],
        "negative_signals": [],
        "activation_policy": "AUTO_ACTIVATE",
    },
    "cargo": {
        "positive_signals": [],
        "path_signals": [
            r"(^|/)Cargo\.toml$",
            r"(^|/)Cargo\.lock$",
            r"(^|/)rust-toolchain(\.toml)?$",
        ],
        "negative_signals": [],
        "activation_policy": "AUTO_ACTIVATE",
    },
}


def run_git(args, cwd=None):
    """Run a git command, return (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        return "", "git not found in PATH", 127


def get_diff(base_ref, head_ref, cwd=None):
    """Return the diff text between base and head."""
    out, err, rc = run_git(["diff", f"{base_ref}...{head_ref}"], cwd=cwd)
    if rc != 0:
        return None, err
    return out, None


def compute_diff_digest(diff_text):
    """SHA-256 of the diff content. Stable input → stable digest."""
    return "sha256:" + hashlib.sha256(diff_text.encode("utf-8")).hexdigest()


def parse_diff_paths(diff_text):
    """Return the list of file paths changed in the diff (post-image, b/<path>)."""
    paths = []
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            spec = line[4:].strip()
            if spec == "/dev/null":
                continue
            # `+++ b/path/to/file` or `+++ path/to/file`
            if spec.startswith("b/"):
                spec = spec[2:]
            paths.append(spec)
    return paths


def parse_added_lines(diff_text):
    """Return only the added lines (lines starting with `+` but not `+++`)."""
    added = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or not line.startswith("+"):
            continue
        added.append(line[1:])
    return added


def is_likely_comment_or_doc(line):
    """Quick heuristic to suppress comment-only matches.

    Catches the common patterns: `//`, `///`, `/*`, `*` (continuation),
    `#` (only Cargo.toml / shell). Production should be smarter and respect
    string literals vs real code.
    """
    stripped = line.lstrip()
    return (
        stripped.startswith("//")
        or stripped.startswith("/*")
        or stripped.startswith("*")
        or stripped.startswith("#")
    )


def router_replay(diff_text):
    """Apply the inline router rules to the diff.

    Returns dict { pack_name: {activated: bool, signals: [...]} }.
    """
    paths = parse_diff_paths(diff_text)
    added_lines = parse_added_lines(diff_text)
    code_added_lines = [ln for ln in added_lines if not is_likely_comment_or_doc(ln)]

    result = {}
    for pack_name, pack in ROUTER_RULES.items():
        matched_signals = []

        # Path signals match against the file paths in the diff
        for pattern in pack["path_signals"]:
            for path in paths:
                if re.search(pattern, path):
                    matched_signals.append({
                        "kind": "path",
                        "pattern": pattern,
                        "match": path,
                    })

        # Positive code signals match against added (non-comment) lines
        for pattern in pack["positive_signals"]:
            for line in code_added_lines:
                if re.search(pattern, line):
                    matched_signals.append({
                        "kind": "code",
                        "pattern": pattern,
                        "match": line.strip()[:80],
                    })
                    break  # one match per pattern is enough

        activated = len(matched_signals) > 0
        result[pack_name] = {
            "activated": activated,
            "activation_policy": pack["activation_policy"],
            "signals": matched_signals,
        }
    return result


def build_verdict(diff_text, paths, router_result):
    """Aggregate verdict for this prototype.

    The prototype does not yet implement CORE-007/011/014/008. It only
    proves router replay works deterministically.
    """
    activated_packs = [p for p, info in router_result.items() if info["activated"]]
    return {
        "schema_version": "0.3.0-spike",
        "rdx_version": PROTOTYPE_VERSION,
        "diff_digest": compute_diff_digest(diff_text),
        "diff": {
            "paths_changed": paths,
            "added_line_count": len(parse_added_lines(diff_text)),
        },
        "router_replay": {
            "activated_packs": activated_packs,
            "per_pack": router_result,
        },
        "final_verdict": "PASS_NO_BLOCKING_FINDINGS",  # No real checks yet
        "_note": "Phase 0.3 spike — router replay only. Real Cat-1 checks ship in Phase 2.",
    }


def main():
    parser = argparse.ArgumentParser(description="RDX validator prototype (Phase 0.3 spike)")
    parser.add_argument("--base", help="Base git ref")
    parser.add_argument("--head", default="HEAD", help="Head git ref (default: HEAD)")
    parser.add_argument("--diff-file", help="Read diff from a file instead of git")
    parser.add_argument("--cwd", help="Working directory (default: cwd)")
    parser.add_argument("--evidence-out", help="Write evidence JSON to this path")
    args = parser.parse_args()

    if args.diff_file:
        try:
            diff_text = Path(args.diff_file).read_text()
        except OSError as e:
            print(json.dumps({"error": f"cannot read diff file: {e}"}), file=sys.stderr)
            sys.exit(2)
    elif args.base:
        diff_text, err = get_diff(args.base, args.head, cwd=args.cwd)
        if err:
            print(json.dumps({"error": err}), file=sys.stderr)
            sys.exit(2)
    else:
        print(json.dumps({"error": "either --base or --diff-file required"}), file=sys.stderr)
        sys.exit(2)

    paths = parse_diff_paths(diff_text)
    router_result = router_replay(diff_text)
    verdict = build_verdict(diff_text, paths, router_result)

    output = json.dumps(verdict, indent=2)
    print(output)

    if args.evidence_out:
        Path(args.evidence_out).write_text(output + "\n")

    # Prototype always PASSes — real checks come in Phase 2
    sys.exit(0)


if __name__ == "__main__":
    main()
