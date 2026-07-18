---
name: plan-work
description: Convert a profiled coding objective into a dependency-ordered work-item DAG with concrete outcomes and executable acceptance criteria. Use after reconnaissance and when creating the initial durable plan.
---

# Plan Work

Build a plan that can survive process restarts and context rotation.

## Procedure

1. Translate the objective into externally observable capabilities, not file-edit tasks.
2. Separate baseline discovery, implementation, integration, verification, and hardening when each produces distinct evidence.
3. Prefer vertical slices that reach an executable oracle early.
4. Assign stable identifiers and explicit dependencies.
5. Mark only genuinely optional improvements as optional.
6. Give every mandatory item concrete acceptance criteria and at least one exact verification command.
7. Return one `set_plan` action.

## Work Item Quality

A work item should be small enough to verify in one coherent episode and large enough to produce user-visible or integration-visible progress. Its description states the resulting capability. Its acceptance field states how an independent controller can distinguish pass from plausible-looking work.

Good acceptance criteria:

- a named test command passes;
- a build produces a specified artifact and a smoke invocation succeeds;
- behavior matches a captured fixture across enumerated cases;
- a correctness gate passes before a metric is compared;
- an integration command exercises the complete boundary.

Weak acceptance criteria:

- "implementation looks correct";
- "review the code" without named invariants;
- a command that does not exercise the changed behavior;
- a metric improvement without a correctness gate.

Put executable gates in `verification_commands` exactly as they should be run. Use shell inspection such as `test -f ...` when acceptance is artifact-based. The controller matches passing evidence to these strings, so do not use placeholders or prose in that field.

## Long-Horizon Planning

For long-horizon work, include an early baseline or executable scaffold, milestone-level integration checks, and a final clean-environment verification item. Keep the DAG revisable: new evidence may add or split pending work, but accepted work must remain represented.

## Exit

Return a non-empty, acyclic plan. Do not begin implementation in the same action.
