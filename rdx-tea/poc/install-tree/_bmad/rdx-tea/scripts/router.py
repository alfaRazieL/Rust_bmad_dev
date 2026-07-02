"""Router replay (vendored from RDX v1.1 rdx_validator/router.py).

Loads canonical router rules from the adapter-owned canonical payload
under `<install-root>/canonical/router-rules.json`.

Signals stored in the JSON are concrete substrings (`async fn`, `tokio::spawn`,
etc.) or glob-like paths (`**/*.rs`, `**/Cargo.toml`). Phase 2 treats them as
substring tokens for code signals and as fnmatch globs for path signals.

Closes (Phase 2):
  T-L2-ASYNC-001..004, T-L2-UNSAFE-001..004, T-L2-FFI-001/002,
  T-L2-MACRO-001/002, T-L2-API-001/002, T-L2-CARGO-001/002,
  T-L2-TEST-001/002, T-L2-DATA-001, T-L2-DB-001, T-L2-TIME-001,
  T-L2-OPS-001/002, T-L2-PERF-001/002, T-L2-CORE015-001/002.
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from .diff import added_lines_per_file, is_likely_comment_or_doc, parse_file_changes
except ImportError:  # pragma: no cover — vendored flat layout
    from diff import added_lines_per_file, is_likely_comment_or_doc, parse_file_changes

# Strong-pack policies always activate when a code/path signal matches.
_AUTO_ACTIVATE = "AUTO_ACTIVATE"
# Medium / weak packs.
_AUTO_SUGGEST = "AUTO_SUGGEST"
_STORY_TAG_REQUIRED = "STORY_TAG_REQUIRED"
_REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class PackActivation:
    pack: str
    activation_policy: str
    active: bool
    signals: tuple[str, ...]
    story_tags_present: tuple[str, ...]
    matched_paths: tuple[str, ...]
    suppressed_reason: str | None = None


@dataclass
class RouterRules:
    packs: dict[str, dict]

    @classmethod
    def load(cls, path: Path) -> "RouterRules":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(packs=data["packs"])


def _match_path(globs: Iterable[str], path: str) -> bool:
    for g in globs:
        if fnmatch.fnmatch(path, g):
            return True
        # Handle leading-doublestar globs like '**/Cargo.toml'
        if g.startswith("**/") and fnmatch.fnmatch(path, g[3:]):
            return True
        # Path equality fallback
        if g == path:
            return True
    return False


def _code_signal_matches(signal: str, line: str) -> bool:
    # Some KB signals contain regex-ish characters but they were authored as
    # plain substrings. Always use substring matching at this layer.
    return signal in line


def replay(
    diff_text: str,
    rules: RouterRules,
    story_tags: Iterable[str] = (),
    publish_true: bool | None = None,
) -> list[PackActivation]:
    """Replay router rules against the diff and return one activation per pack.

    `publish_true` is a project metadata flag — when False, the `api` pack
    auto-deactivates on the same diff (T-L2-API-002).
    """
    changes = parse_file_changes(diff_text)
    paths_changed = [c.post_path for c in changes if c.post_path is not None]
    per_file_added = added_lines_per_file(changes)

    # Code signals only apply to source files (.rs / .toml / .lock / .h /
    # .c / build scripts). Markdown and other docs are NEVER scanned for
    # code signals — they cannot activate a pack via a positive token.
    code_extensions = (".rs", ".toml", ".lock", ".h", ".c", ".hpp", ".cpp")
    code_lines_per_file: dict[str, list[str]] = {}
    for p, lines in per_file_added.items():
        if not p.endswith(code_extensions) and not p.endswith("/build.rs"):
            continue
        code_lines_per_file[p] = [ln for ln in lines if not is_likely_comment_or_doc(ln)]

    story_tag_set = set(story_tags)
    out: list[PackActivation] = []

    for pack_name, pack in rules.packs.items():
        matched_signals: list[str] = []
        matched_paths: list[str] = []

        # Path signals — concrete file paths trigger activation
        # Only "specific" path globs trigger (NOT bare '**/*.rs', which is
        # essentially "any Rust file" and would mean every Rust diff activates
        # every pack). Concrete path globs include things like
        # '**/Cargo.toml', '**/build.rs', '**/lib.rs', 'fuzz/**', etc.
        for g in pack.get("path_signals", []) or []:
            if g == "**/*.rs":
                continue  # too generic — used as "code may be in any file"
            for p in paths_changed:
                if _match_path([g], p):
                    matched_paths.append(p)
                    matched_signals.append(f"path:{g}")
                    break

        # Code signals — substring search over added code (non-comment)
        for sig in pack.get("positive_signals", []) or []:
            hit = False
            for lines in code_lines_per_file.values():
                for line in lines:
                    if _code_signal_matches(sig, line):
                        matched_signals.append(f"code:{sig}")
                        hit = True
                        break
                if hit:
                    break

        policy = pack.get("activation_policy", _AUTO_ACTIVATE)
        signal_present = bool(matched_signals)

        active = False
        suppressed: str | None = None
        if signal_present:
            if policy == _AUTO_ACTIVATE:
                active = True
            elif policy == _AUTO_SUGGEST:
                # Auto-suggest is "advisory": activate but treat as
                # REVIEW_REQUIRED downstream rather than blocking.
                active = True
            elif policy == _STORY_TAG_REQUIRED:
                tags = set(pack.get("story_tags", []) or [])
                if story_tag_set & tags or pack_name in story_tag_set:
                    active = True
                else:
                    suppressed = "STORY_TAG_REQUIRED"
            elif policy == _REVIEW_REQUIRED:
                active = True
            else:
                active = True

        # Project-metadata-based suppression (api pack only)
        if pack_name == "api" and publish_true is False and active:
            active = False
            suppressed = "publish_false"

        # `api` pack uses story tags as gating too — without a story tag it
        # is *suggested*, not blocking. T-L2-API-001 expects REVIEW_REQUIRED
        # when a public symbol is added in a library crate.
        if pack_name == "api" and active and policy == _STORY_TAG_REQUIRED and not (story_tag_set & set(pack.get("story_tags", []) or [])):
            # Activation remains True (REVIEW_REQUIRED is informational/advisory)
            pass

        out.append(
            PackActivation(
                pack=pack_name,
                activation_policy=policy,
                active=active,
                signals=tuple(matched_signals),
                story_tags_present=tuple(sorted(story_tag_set)),
                matched_paths=tuple(matched_paths),
                suppressed_reason=suppressed,
            )
        )

    return out


def activated_pack_names(activations: Iterable[PackActivation]) -> list[str]:
    return [a.pack for a in activations if a.active]
