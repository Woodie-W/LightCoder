---
name: check-repair-completion
description: Decide whether repair work is complete, should continue, or was misclassified. Use only when the LightCoder controller dispatches CHECK_REPAIR_COMPLETION.
---

# CHECK_REPAIR_COMPLETION

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Repair Flow Contract`](../references/repair-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- repair.status_flags
- repair.test_results
- repair.attempts
- task_profile

## Entry Criteria

- The controller must dispatch `CHECK_REPAIR_COMPLETION` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `repair.status_flags`, `repair.test_results`, `repair.attempts`, `task_profile`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Require the original issue to be fixed under its oracle.
2. Require targeted tests and relevant regressions to pass.
3. Check that the patch remains within repair scope.
4. Detect evidence that the task is primarily feature, project, optimize, or transform.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `repair.completion_decision`, `repair.completion_evidence`.
- Keep the result compact; reference existing evidence ids instead of copying logs or transcript text into state.

## Failure Handling

- If evidence is insufficient, choose a legal evidence-gathering/replan route rather than fabricate certainty.
- If candidates remain tied, prefer the smaller reversible action and record the tie.
- Transport-level model/tool failures may use the runtime retry allowance; a repeatable product or command failure must leave the node with evidence.
- Preserve the current accepted revision and external limits on every failure path.

## Exit Checklist

- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.
- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.
- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve.
- Route guard applied: all pass -> `REPAIR_COMPLETE`; task type changed -> `ROUTE_TASK`; otherwise -> `REPAIR_LOOP_START`
- The proposed route is one of: `REPAIR_COMPLETE`, `REPAIR_LOOP_START`, `ROUTE_TASK`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.completion_decision
- repair.completion_evidence

## Routes

- `REPAIR_COMPLETE`
- `REPAIR_LOOP_START`
- `ROUTE_TASK`

## Constraints

- Do not use iteration count alone as completion evidence.
