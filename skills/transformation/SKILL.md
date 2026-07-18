---
name: transformation
description: Transform a codebase across languages, representations, APIs, or architecture while preserving defined behavior through differential evidence. Load when equivalence under structural change dominates.
---

# Transformation Playbook

Define the equivalence boundary before translating. Capture representative inputs, outputs, errors, ordering, numeric behavior, side effects, and performance constraints from the source system.

Proceed in behavior-preserving slices:

1. capture a source baseline or golden fixture;
2. establish the target build and invocation path;
3. transform one dependency-closed capability;
4. compare source and target at the boundary;
5. integrate callers and remove the superseded path only after parity.

Do not transliterate syntax while ignoring runtime semantics. Pay special attention to integer widths, overflow, floating point, Unicode, ownership and lifetimes, concurrency, exception models, iteration order, filesystem behavior, and foreign-function boundaries.

When intentional divergence is required, record it explicitly and update the acceptance oracle. Compilation is necessary but never sufficient evidence of semantic compatibility.
