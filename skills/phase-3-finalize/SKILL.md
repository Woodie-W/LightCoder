---
name: phase-3-finalize
description: Orchestrate final validation, integrity review, concise reporting, and delivery. Use only when the LightCoder controller dispatches PHASE_3_FINALIZE.
---

# PHASE_3_FINALIZE

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

- control.active_flow
- task_profile
- workspace
- control.subgraph_state

## Entry Criteria

- The controller must dispatch `PHASE_3_FINALIZE` in the `orchestration` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `control.active_flow`, `task_profile`, `workspace`, `control.subgraph_state`.
- Require a committed state revision and no unresolved active attempt.
- Do not call the model or workspace mutation tools; derive the outcome from structured state.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Enter clean-environment validation.
2. If validation fails, route the failure back to the correct Phase 2 loop.
3. After validation, inspect artifacts, run integrity checks, generate the report, and submit.

## Evidence And Artifacts

- Persist the selected route, guard result, previous node, and new state revision as a transition event.
- No repository diff or narrative evidence is expected from a pure control node.
- Proposed state updates are limited to: `control.phase3_status`, `final_validation.spec`, `final_validation.candidate_revision`, `delivery.status`.
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
- Route guard applied: -> `RUN_CLEAN_ENVIRONMENT_VALIDATION`
- The proposed route is one of: `RUN_CLEAN_ENVIRONMENT_VALIDATION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- control.phase3_status
- final_validation.spec
- final_validation.candidate_revision
- delivery.status

## Routes

- `RUN_CLEAN_ENVIRONMENT_VALIDATION`

## Constraints

- Do not report success before clean validation and integrity checks pass.
