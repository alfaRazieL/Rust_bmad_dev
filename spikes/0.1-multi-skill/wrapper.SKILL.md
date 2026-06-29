---
name: zz-spike-wrapper
description: Phase 0.1 spike — wrapper that invokes child skill then runs validator stub. Use only when explicitly told "run zz-spike-wrapper".
---

# Phase 0.1 Wrapper Test

This skill is a temporary spike fixture. Execute the following steps in order:

## Step 1 — BEFORE marker

Run this bash command:
```bash
echo "BEFORE wrapper-step-1 ts=$(date +%s)" >> /tmp/rdx-phase0/spike-0.1/trace.log
```

## Step 2 — Invoke child skill

Use the Skill tool to invoke the skill named `zz-spike-child`. Pass no arguments.

## Step 3 — AFTER marker (post-child)

After `zz-spike-child` completes and returns, run:
```bash
echo "AFTER wrapper-step-3 ts=$(date +%s)" >> /tmp/rdx-phase0/spike-0.1/trace.log
```

## Step 4 — Run validator stub

Run this bash command and report the exit code:
```bash
bash /tmp/rdx-phase0/spike-0.1/validator-stub.sh
```

The validator stub will print a JSON verdict and exit non-zero on FAIL.
**You MUST report the exact exit code.** Do not proceed past this step if the exit code is non-zero — instead, output `WRAPPER_HALTED_DUE_TO_VALIDATOR_FAIL` and stop.

## Step 5 — Final result

Output a single line:
```
WRAPPER_FLOW_COMPLETE
```
If you reached here, all 5 steps executed in order.
