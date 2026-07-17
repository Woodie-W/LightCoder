---
name: optimization-loop-start
description: Synchronize optimization state and begin one measured experiment cycle. Use only when the LightCoder controller dispatches OPTIMIZATION_LOOP_START.
---

# OPTIMIZATION_LOOP_START

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `control`
- Execution mode: `deterministic`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Optimization Flow Contract`](../references/optimization-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- optimization
- workspace
- external_run_config

## Entry Criteria

- The controller must dispatch `OPTIMIZATION_LOOP_START` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `optimization`, `workspace`, `external_run_config`.
- Require a committed state revision and no unresolved active attempt.
- Do not call the model or workspace mutation tools; derive the outcome from structured state.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Restore the current best accepted revision.
2. Summarize best metric, rejected hypotheses, active bottleneck evidence, and remaining candidates.
3. Increment experiment number and select the next hypothesis.

## Evidence And Artifacts

- Persist the selected route, guard result, previous node, and new state revision as a transition event.
- No repository diff or narrative evidence is expected from a pure control node.
- Proposed state updates are limited to: `optimization.iteration`, `optimization.current_summary`, `optimization.current_revision`.
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
- Route guard applied: -> `SELECT_NEXT_HYPOTHESIS`
- The proposed route is one of: `SELECT_NEXT_HYPOTHESIS`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.iteration
- optimization.current_summary
- optimization.current_revision

## Routes

- `SELECT_NEXT_HYPOTHESIS`

## Constraints

- Never build a new candidate on an unaccepted regression.
