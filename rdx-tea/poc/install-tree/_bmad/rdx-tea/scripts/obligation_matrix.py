"""Workflow obligation matrix (D3.1 addendum).

Documented in `rdx-tea/architecture/WORKFLOW_OBLIGATION_MATRIX.csv`.
Encoded here for programmatic enforcement.

For every supported TEA workflow:

    packs:       set of pack_id values that may activate for this workflow
    core_rules:  True  → include ALL CORE-* rules
                 set   → include only listed CORE-* rules
                 None  → exclude every CORE-* rule
    fields:      set of IR field names to emit into the bundle (per rule)

Cells with `included_fields=""` in the CSV translate here to
`fields = set()` for that workflow×pack — the rule is present but
carries no normative body (only header). Cells with a subset of fields
constrain what the bundle emits.

Direct code-level filtering guarantees the CSV is not just documentation.
"""

from __future__ import annotations

# Field vocabulary — must match rdx_parser IR keys.
ALL_FIELDS = {
    "trigger", "risk", "rule", "required_reasoning",
    "validation", "exceptions", "sources",
}

# Minimal safe set: rule + validation + exceptions. Used when a workflow
# only needs "what to do" without the full reasoning trace.
MIN_FIELDS = {"rule", "validation", "exceptions"}

# Full set including trigger/risk context. Used when the workflow needs
# to justify test scenarios and reason about triggers.
FULL_FIELDS = ALL_FIELDS

WORKFLOW_OBLIGATION_MATRIX = {
    "test-design": {
        "packs": {"async", "unsafe", "ffi", "macro", "api", "testing",
                  "data-security-io", "db", "time-config-client"},
        "core_rules": True,
        "fields": FULL_FIELDS,
    },
    "atdd": {
        "packs": {"async", "api", "testing"},
        "core_rules": {"CORE-001", "CORE-004", "CORE-009"},
        "fields": {"rule", "required_reasoning", "validation", "exceptions"},
    },
    "automate": {
        "packs": {"async", "api", "testing"},
        "core_rules": {"CORE-001", "CORE-004"},
        "fields": {"rule", "validation", "exceptions"},
    },
    "test-review": {
        "packs": {"api", "testing"},
        "core_rules": {"CORE-001", "CORE-002", "CORE-004"},
        "fields": {"rule", "required_reasoning", "validation"},
    },
    "nfr": {
        "packs": {"unsafe", "data-security-io", "perf", "db",
                  "time-config-client", "ops"},
        "core_rules": {"CORE-004", "CORE-014", "CORE-015"},
        "fields": FULL_FIELDS,
    },
    "trace": {
        "packs": {"testing"},
        "core_rules": {"CORE-001"},
        "fields": {"rule", "validation"},
    },
    "framework": {
        "packs": {"cargo", "testing"},
        "core_rules": {"CORE-004"},
        "fields": {"rule", "validation"},
    },
    "ci": {
        "packs": {"testing", "cargo"},
        "core_rules": {"CORE-004"},
        "fields": {"rule", "validation"},
    },
}


def all_workflows() -> list[str]:
    return sorted(WORKFLOW_OBLIGATION_MATRIX.keys())


def coverage_for(workflow: str, rule_id: str, pack_id: str) -> dict:
    """Return the machine decision for one workflow × rule."""
    m = matrix_for(workflow)
    if rule_id.startswith("CORE-"):
        decision = "INCLUDE" if core_rules_allowed(workflow, rule_id) else "EXCLUDE"
        reason = f"core_rules_policy={type(m['core_rules']).__name__}"
    else:
        decision = "INCLUDE" if pack_id in m["packs"] else "EXCLUDE"
        reason = "pack in matrix" if pack_id in m["packs"] else "pack excluded by scope"
    return {
        "workflow": workflow,
        "rule_id": rule_id,
        "pack_id": pack_id,
        "decision": decision,
        "reason": reason,
        "fields": sorted(m["fields"]) if decision == "INCLUDE" else [],
    }


def generate_csv() -> str:
    """Return the WORKFLOW_OBLIGATION_MATRIX.csv content derived from
    this single source of truth."""
    import io
    import csv
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["workflow", "rule_id_or_pack", "included_fields",
                     "excluded_fields", "reason", "source_anchor", "test_id"])
    all_f = ";".join(sorted(ALL_FIELDS))
    for workflow in all_workflows():
        m = matrix_for(workflow)
        for pack in sorted(m["packs"]):
            fields = ";".join(sorted(m["fields"]))
            excluded = ";".join(sorted(ALL_FIELDS - m["fields"]))
            writer.writerow([workflow, f"pack:{pack}", fields, excluded,
                             f"pack in matrix for {workflow}",
                             "obligation_matrix.py", "L2/L4"])
        # CORE row
        cr = m["core_rules"]
        if cr is True:
            writer.writerow([workflow, "CORE-*", ";".join(sorted(m["fields"])),
                             "",
                             f"core_rules=True (all CORE-*)",
                             "obligation_matrix.py", "L2/L4"])
        elif isinstance(cr, (set, frozenset)):
            writer.writerow([workflow, ";".join(sorted(cr)),
                             ";".join(sorted(m["fields"])), "",
                             "core_rules=explicit subset",
                             "obligation_matrix.py", "L2/L4"])
    return buf.getvalue()


def matrix_for(workflow: str) -> dict:
    """Return the obligation-matrix entry for a workflow. Unknown workflow
    yields an empty entry (fail-safe — see test_l7_f08)."""
    return WORKFLOW_OBLIGATION_MATRIX.get(workflow, {
        "packs": set(),
        "core_rules": None,
        "fields": set(),
    })


def core_rules_allowed(workflow: str, rule_id: str) -> bool:
    m = matrix_for(workflow)
    cr = m["core_rules"]
    if cr is None:
        return False
    if cr is True:
        return True
    return rule_id in cr


def pack_allowed(workflow: str, pack_id: str) -> bool:
    return pack_id in matrix_for(workflow)["packs"]


def fields_allowed(workflow: str) -> set[str]:
    return matrix_for(workflow)["fields"]
