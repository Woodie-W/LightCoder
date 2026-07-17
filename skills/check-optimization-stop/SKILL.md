---
name: check-optimization-stop
description: Decide whether useful optimization should continue under external limits. Use only when the LightCoder controller dispatches CHECK_OPTIMIZATION_STOP.
---

# CHECK_OPTIMIZATION_STOP

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Optimization Flow Contract`](../references/optimization-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- optimization.history
- optimization.hypothesis_queue
- optimization.best_result
- external_run_config

## Entry Criteria

- The controller must dispatch `CHECK_OPTIMIZATION_STOP` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `optimization.history`, `optimization.hypothesis_queue`, `optimization.best_result`, `external_run_config`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Stop only when the target is met, an external hard limit is reached, execution is explicitly cancelled, or infrastructure is unrecoverable.
2. When no evidence-backed hypothesis remains or progress stalls, regenerate the hypothesis queue or switch search strategy rather than terminating.
3. Distinguish target attainment from administrative stopping, exhaustion, measurement instability, and infrastructure blocking.
4. Record the stop reason independently from success or failure.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `optimization.stop_decision`, `optimization.stop_reason`.
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
- Route guard applied: useful hypothesis+limits remain -> `OPTIMIZATION_LOOP_START`; otherwise -> `FINAL_PERFORMANCE_VALIDATION`
- The proposed route is one of: `OPTIMIZATION_LOOP_START`, `FINAL_PERFORMANCE_VALIDATION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.stop_decision
- optimization.stop_reason

## Routes

- `OPTIMIZATION_LOOP_START`
- `FINAL_PERFORMANCE_VALIDATION`

## Constraints

- Do not create or modify the external budget.
