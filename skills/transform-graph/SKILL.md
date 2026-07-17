---
name: transform-graph
description: Orchestrate behavior-preserving refactoring or compatibility migration. Use only when the LightCoder controller dispatches TRANSFORM_GRAPH.
---

# TRANSFORM_GRAPH

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `control`
- Execution mode: `deterministic`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Orchestration Flow Contract`](../references/orchestration-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- task_profile
- recon_brief
- control.active_flow
- external_run_config

## Entry Criteria

- The controller must dispatch `TRANSFORM_GRAPH` in the `orchestration` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `task_profile`, `recon_brief`, `control.active_flow`, `external_run_config`.
- Require a committed state revision and no unresolved active attempt.
- Do not call the model or workspace mutation tools; derive the outcome from structured state.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Load the subgraph state or enter `INITIALIZE_TRANSFORM_STATE` if absent.
2. Run `TRANSFORM_LOOP_START` until completion, reroute, interruption, or external stop.
3. Persist state at graph boundaries and return only structured updates to the parent graph.

## Evidence And Artifacts

- Persist the selected route, guard result, previous node, and new state revision as a transition event.
- No repository diff or narrative evidence is expected from a pure control node.
- Proposed state updates are limited to: `control.active_flow`, `control.subgraph_status`, `control.last_checkpoint`.
- Keep the result compact; reference existing evidence ids instead of copying logs or transcript text into state.

## Failure Handling

- On stale or invalid state, reload once and fail closed instead of guessing a route.
- If no legal guard matches, leave the active node unchanged and return an invalid-state blocker.
- A persistence, schema, or lease failure interrupts the attempt; it is not product evidence and must not consume a business retry.
- Preserve the current accepted revision and external limits on every failure path.

## Exit Checklist

- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.
- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.
- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve.
- Route guard applied: new flow -> `INITIALIZE_TRANSFORM_STATE`; resumed flow -> `TRANSFORM_LOOP_START`; new type evidence -> `ROUTE_TASK`; candidate complete -> `PHASE_3_FINALIZE`
- The proposed route is one of: `INITIALIZE_TRANSFORM_STATE`, `TRANSFORM_LOOP_START`, `ROUTE_TASK`, `PHASE_3_FINALIZE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- control.active_flow
- control.subgraph_status
- control.last_checkpoint

## Routes

- `INITIALIZE_TRANSFORM_STATE`
- `TRANSFORM_LOOP_START`
- `ROUTE_TASK`
- `PHASE_3_FINALIZE`

## Constraints

- Do not duplicate the internal loop logic in this wrapper.
