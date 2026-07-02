---
name: zz-spike-child
description: Phase 0.1 spike — child skill that writes a marker and returns. Use only when invoked by zz-spike-wrapper.
---

# Phase 0.1 Child Test

Execute exactly one step:

## Step 1 — CHILD marker

Run this bash command:
```bash
echo "CHILD child-step-1 ts=$(date +%s)" >> /tmp/rdx-phase0/spike-0.1/trace.log
```

Then output the literal text:
```
CHILD_DONE
```

Do not perform any other actions. Return control to the invoker.
