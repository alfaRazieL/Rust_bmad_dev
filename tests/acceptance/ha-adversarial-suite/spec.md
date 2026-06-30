# T-V6-ACC-05 — High Assurance adversarial-suite acceptance

Phase 9 exit gate. RDX_IMPLEMENTATION_PLAN_TESTED.md §"Phase 9" requires:

> Exit gate
> - T-V6-ACC-05 — all adversarial paths caught in HA mode

This fixture catalogues which L7 mutation modules cover which V5 / V6
bypass classes and acts as the single source of truth for the HA suite
that `test_v6_acc_05.py` runs as a subprocess.

| Test ID                       | Bypass class                                    | Test module                                      | Defence layer       |
|-------------------------------|-------------------------------------------------|--------------------------------------------------|---------------------|
| T-L7-FAKE-PASS-001            | Hand-edited evidence.json with verdict=PASS     | tests/mutation/test_l7_fake_pass.py              | L2 schema + L6 CI   |
| T-L7-STALE-DIFF-001           | Evidence pinned to a previous diff_digest       | tests/mutation/test_l7_stale_diff.py             | L6 CI               |
| T-L7-WRONG-BASE-001           | Envelope claims wrong base_sha                  | tests/mutation/test_l7_wrong_base.py             | L6 CI               |
| T-L7-DISABLED-PACK-001        | Agent omits a router pack                       | tests/mutation/test_l7_disabled_pack.py          | L2 (replay)         |
| T-L7-MOD-SCHEMA-001           | PR weakens evidence schema                      | tests/mutation/test_l7_mod_schema.py             | L6 (base ref)       |
| T-L7-MOD-VALIDATOR-001        | PR rewrites validator                           | tests/mutation/test_l7_mod_validator.py          | L6 (`--validator-ref`) |
| T-L7-DEL-TEST-001             | PR removes failing test                         | tests/mutation/test_l7_del_test.py               | L1 baseline         |
| T-L7-OVERSIZED-DIFF-001       | DoS via huge diff                               | tests/mutation/test_l7_oversized_diff.py         | L1 validator cap    |
| T-L7-WORKFLOW-MOD-001         | PR weakens .github/workflows/rdx-gate.yml       | tests/mutation/test_l7_workflow_mod.py           | L8 governance       |
| T-L7-APPROVAL-REUSE-001       | Old approval replayed on new diff               | tests/integration/cat4/test_l8_cat4.py (reused)  | L8 governance       |
| **T-L7-HA-MODE-DOWNGRADE-001** | PR lowers mode in `_bmad/rdx/config.toml`       | tests/mutation/test_l7_ha_mode_downgrade.py      | L8 governance (HA)  |
| **T-L7-HA-APPROVERS-FORGERY-001** | PR adds attacker to `_bmad/rdx/approvers.yaml`  | tests/mutation/test_l7_ha_approvers_forgery.py   | L8 governance (HA)  |

T-V6-ACC-05 invokes `pytest tests/mutation/` as a subprocess; an exit
code of 0 means every module above passed (100% adversarial detection).
The acceptance driver also asserts the catalog above is in sync with
`RDX_TEST_CASES.yaml` so that adding a new L7 bypass class always
forces a corresponding test module.

Threat model cross-reference: `docs/threat-model.md` §6 enumerates each
bypass class above and explains why the defence layer holds. T-V6-ACC-05
is the operational proof that the threat model's claims correspond to
runnable tests.
