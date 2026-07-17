---
name: route-failure-back
description: Route a clean-validation failure to the smallest appropriate Phase 2 loop. Use only when the LightCoder controller dispatches ROUTE_FAILURE_BACK.
---

# ROUTE_FAILURE_BACK

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Finalize Flow Contract`](../references/finalize-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- final_validation.failure_class
- final_validation.results
- task_profile
- control.route_history

## Entry Criteria

- The controller must dispatch `ROUTE_FAILURE_BACK` in the `finalize` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `final_validation.failure_class`, `final_validation.results`, `task_profile`, `control.route_history`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Classify the failure as repair, feature, project integration, performance, transform, or unknown.
2. Preserve the clean reproduction command and evidence in the selected subgraph state.
3. Route to the loop start rather than reinitializing the task.
4. Record why this route differs from the previous execution path.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `control.active_flow`, `control.route_history`, `control.phase2_return_reason`, `control.subgraph_state`.
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
- Route guard applied: repair -> `REPAIR_LOOP_START`; feature -> `FEATURE_LOOP_START`; project -> `PROJECT_LOOP_START`; performance -> `OPTIMIZATION_LOOP_START`; migration/refactor -> `TRANSFORM_LOOP_START`; unknown/mixed -> `GENERALIST_LOOP_START`
- The proposed route is one of: `REPAIR_LOOP_START`, `FEATURE_LOOP_START`, `PROJECT_LOOP_START`, `OPTIMIZATION_LOOP_START`, `TRANSFORM_LOOP_START`, `GENERALIST_LOOP_START`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- control.active_flow
- control.route_history
- control.phase2_return_reason
- control.subgraph_state

## Routes

- `REPAIR_LOOP_START`
- `FEATURE_LOOP_START`
- `PROJECT_LOOP_START`
- `OPTIMIZATION_LOOP_START`
- `TRANSFORM_LOOP_START`
- `GENERALIST_LOOP_START`

## Constraints

- Do not discard accepted Phase 2 evidence.
