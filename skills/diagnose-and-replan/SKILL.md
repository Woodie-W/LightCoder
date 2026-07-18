---
name: diagnose-and-replan
description: Diagnose a rejected or stagnant work item from failure evidence and choose a materially different strategy or revise the pending work DAG. Use after failed verification or repeated non-progress.
---

# Diagnose And Replan

Failures update the model of the system; they do not consume a finite retry allowance.

## Procedure

1. Normalize the newest failure into a reproducible signature: command, input, observed output, expected invariant, and workspace revision.
2. Separate implementation defects from environment, dependency, fixture, oracle, and performance-noise failures.
3. Compare with previous signatures and strategies for this work item.
4. Form a new falsifiable hypothesis that explains more evidence than the previous one.
5. Choose a discriminating action that can falsify it cheaply.
6. Revise the plan only when evidence changes capability boundaries, ordering, or acceptance criteria.

A strategy is materially different when it changes at least one of:

- causal hypothesis;
- localization method;
- decomposition or integration order;
- tool, instrumentation, or input;
- implementation mechanism;
- verification oracle.

Renaming the same approach, rerunning an unchanged failing command, or making speculative edits around the same location is not a strategy change.

## Plan Revision Rules

- Preserve accepted work items and their evidence.
- Do not weaken acceptance merely because it is hard to satisfy.
- Add prerequisite work when a hidden dependency becomes observable.
- Split a work item when independent failure modes need distinct oracles.
- Keep the objective and protected constraints unchanged.

## Exit

Continue with a diagnostic tool action or return `revise_plan`. Do not declare the task impossible because the current hypothesis queue is empty; inspect a different boundary and construct new evidence.
