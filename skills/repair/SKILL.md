---
name: repair
description: Repair an observed defect by reproducing it, localizing the causal boundary, applying the smallest coherent fix, and guarding against regression. Load as the playbook when incorrect existing behavior dominates.
---

# Repair Playbook

Start from a reproducible symptom. Preserve the original failing command, input, expected behavior, and actual behavior as baseline evidence.

Trace from the observable failure toward the earliest violated invariant. Reduce the reproducer when that makes competing hypotheses distinguishable. Inspect callers, data flow, state transitions, version boundaries, and error handling before editing the visible crash site.

Prefer the smallest coherent change that fixes the cause across the supported input class. Avoid test-specific branches, swallowed errors, broad rewrites, or weakened assertions.

Verification order:

1. original reproducer;
2. focused regression test for the causal edge case;
3. neighboring tests for the changed boundary;
4. broader suite or build.

If the failure changes form, record a new signature rather than treating it as the same attempt. If the reproducer cannot be trusted, repair the oracle or environment before modifying product code.
