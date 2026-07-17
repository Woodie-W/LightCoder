---
name: initialize-optimization-state
description: Establish correctness and metric baselines, then initialize experiment history. Use only when the LightCoder controller dispatches INITIALIZE_OPTIMIZATION_STATE.
---

# INITIALIZE_OPTIMIZATION_STATE

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

- task_profile
- recon_brief
- workspace
- external_run_config

## Entry Criteria

- The controller must dispatch `INITIALIZE_OPTIMIZATION_STATE` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `task_profile`, `recon_brief`, `workspace`, `external_run_config`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Define primary metric, direction, correctness constraints, and measurement command from the task or runner configuration.
2. Run the minimum correctness baseline.
3. Run a repeatable baseline measurement with raw values and environment details.
4. Create best-result, hypothesis, candidate, and rejected-history state.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `optimization.metric_spec`, `optimization.correctness_baseline`, `optimization.performance_baseline`, `optimization.best_result`, `optimization.history`.
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
- Route guard applied: -> `OPTIMIZATION_LOOP_START`
- The proposed route is one of: `OPTIMIZATION_LOOP_START`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.metric_spec
- optimization.correctness_baseline
- optimization.performance_baseline
- optimization.best_result
- optimization.history

## Routes

- `OPTIMIZATION_LOOP_START`

## Constraints

- Do not invent optimization targets or internal budgets.
- If no valid baseline can be measured, mark blocked.
