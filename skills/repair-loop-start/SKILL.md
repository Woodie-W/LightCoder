---
name: repair-loop-start
description: Synchronize repair state and enter one repair iteration. Use only when the LightCoder controller dispatches REPAIR_LOOP_START.
---

# REPAIR_LOOP_START

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `control`
- Execution mode: `deterministic`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Repair Flow Contract`](../references/repair-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- repair
- workspace
- external_run_config

## Entry Criteria

- The controller must dispatch `REPAIR_LOOP_START` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `repair`, `workspace`, `external_run_config`.
- Require a committed state revision and no unresolved active attempt.
- Do not call the model or workspace mutation tools; derive the outcome from structured state.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Load the latest code revision and repair checkpoint.
2. Summarize only the current failure, strongest evidence, active hypothesis, and last result.
3. Increment the iteration counter and hand control to action selection.

## Evidence And Artifacts

- Persist the selected route, guard result, previous node, and new state revision as a transition event.
- No repository diff or narrative evidence is expected from a pure control node.
- Proposed state updates are limited to: `repair.iteration`, `repair.current_summary`, `repair.last_revision`.
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
- Route guard applied: -> `SELECT_NEXT_REPAIR_ACTION`
- The proposed route is one of: `SELECT_NEXT_REPAIR_ACTION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.iteration
- repair.current_summary
- repair.last_revision

## Routes

- `SELECT_NEXT_REPAIR_ACTION`

## Constraints

- Do not repeat a failed action unless new evidence justifies it.
